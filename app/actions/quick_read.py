"""The quick read capability.

This handler owns no logic of its own. It composes the shared services in a
fixed order, which is what keeps them reusable by whatever capability comes
next.
"""

from dataclasses import dataclass

from app.config import settings
from app.glossary.terms import lookup
from app.pipeline.clean import clean
from app.pipeline.phrasing import stock_phrases
from app.pipeline.protect import protect
from app.pipeline.quality import CheckReport, HardFailure, check_output, check_source
from app.pipeline.summarise import DEFAULT_TEMPERATURE, summarise
from app.providers.base import ProviderError

# Each retry nudges the model further from the answer that just failed.
TEMPERATURE_STEP = 0.2


@dataclass(frozen=True)
class QuickRead:
    article_id: int
    locale: str
    text: str
    checks: CheckReport
    cost_usd: float = 0.0
    # False when any call went to a model we hold no rate for. A total built
    # partly from unknown prices is itself unknown, not a smaller number.
    cost_known: bool = True
    model: str = ""
    deliverable: bool = False
    needs_review: bool = False


def _corrective(report: CheckReport) -> str:
    """Tell the model what was wrong with its last answer.

    Retrying an identical prompt at the same temperature, against a model that
    has just produced the wrong thing, mostly produces the wrong thing again
    and pays twice for it.
    """
    reasons = "; ".join(f"{f.code}: {f.detail}" if f.detail else f.code for f in report.hard)
    return (
        f"Your previous answer was rejected for: {reasons}. "
        "Write a different summary that does not repeat that problem. "
        "Follow the original instructions exactly."
    )


def _rewrite_request(summary: str, phrases: list[str]) -> str:
    named = ", ".join(f'"{phrase}"' for phrase in phrases)
    return (
        f"Here is your summary:\n{summary}\n\n"
        f"Rewrite it without {named}. Say what happened in plain verbs instead. "
        "Keep every fact, name and figure exactly as it is, in the same language and "
        "at about the same length. Write only the summary."
    )


async def handle(
    article_id: int,
    locale: str,
    *,
    client,
    provider,
    model: str | None = None,
    max_attempts: int | None = None,
) -> QuickRead:
    model = model or settings.model_for(locale)
    if max_attempts is None:
        max_attempts = settings.max_generation_attempts
    if max_attempts < 1:
        # No attempt means no model call and no check, and so nothing that may
        # be delivered. Refuse rather than return an empty quick read.
        raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

    article = await client.fetch_article(article_id, locale)
    text = clean(article.body_html)

    source_failures = check_source(text, locale)
    if source_failures:
        # Nothing to summarise, so nothing is spent finding that out.
        return QuickRead(
            article_id=article_id,
            locale=locale,
            text="",
            checks=CheckReport(hard=tuple(source_failures)),
            model=model,
        )

    protected = protect(text, locale)
    glossary = lookup(protected.all_terms, locale)

    cost = 0.0
    cost_known = True
    report = CheckReport()
    completion = None
    corrective = None

    for attempt in range(max_attempts):
        try:
            completion = await summarise(
                title=article.title,
                text=text,
                locale=locale,
                protected=protected,
                glossary=glossary,
                provider=provider,
                model=model,
                temperature=DEFAULT_TEMPERATURE + TEMPERATURE_STEP * attempt,
                corrective=corrective,
            )
        except ProviderError as exc:
            # An outage is an outcome to report, not a crash for the caller to
            # special-case. A timeout can land after the provider has billed,
            # so the spend for this run is no longer known.
            report = CheckReport(hard=(HardFailure("provider_error", str(exc)),))
            cost_known = False
            break

        cost += completion.cost_usd
        cost_known = cost_known and completion.cost_known

        report = check_output(
            text,
            completion.text,
            locale,
            protected,
            finish_reason=completion.finish_reason,
        )
        if not report.hard:
            break

        corrective = _corrective(report)

    # One rewrite pass for stock filler. A model follows "remove 'showcasing'"
    # far better than a general rule it has already ignored once. The rewrite
    # is kept only if it is still correct and carries less filler.
    filler = stock_phrases(completion.text, text, locale) if completion and not report.hard else []
    if filler:
        try:
            revised = await summarise(
                title=article.title,
                text=text,
                locale=locale,
                protected=protected,
                glossary=glossary,
                provider=provider,
                model=model,
                temperature=DEFAULT_TEMPERATURE,
                corrective=_rewrite_request(completion.text, filler),
            )
        except ProviderError:
            # The original stands. The failed call may still have been billed.
            cost_known = False
        else:
            cost += revised.cost_usd
            cost_known = cost_known and revised.cost_known
            revised_report = check_output(
                text, revised.text, locale, protected, finish_reason=revised.finish_reason
            )
            cleaner = len(stock_phrases(revised.text, text, locale)) < len(filler)
            if not revised_report.hard and cleaner:
                completion, report = revised, revised_report

    return QuickRead(
        article_id=article_id,
        locale=locale,
        # The rejected text is kept on failure so there is a record of what
        # was refused.
        text=completion.text if completion else "",
        checks=report,
        cost_usd=cost,
        cost_known=cost_known,
        model=model,
        deliverable=not report.hard,
        needs_review=bool(report.soft),
    )
