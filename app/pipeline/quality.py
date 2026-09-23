"""Checks run against every quick read before it is handed back.

Hard checks mean the output is wrong, not merely weak, and they block delivery.
Soft checks mean it is probably fine but deserves a look, so they flag and let
the job complete.

Soft checks never raise. A raising soft check would turn a job that should
finish into a crash, which inverts the whole point of the distinction.
"""

import re
from dataclasses import dataclass, field

from app.pipeline.figures import dropped_hedges, invented_figures
from app.pipeline.length import HARD_MAX_WORDS, TOLERANCE, target_for
from app.pipeline.phrasing import stock_phrases
from app.pipeline.protect import ProtectedTerms

ARABIC = re.compile(r"[؀-ۿ]")
LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9.&'-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.&'-]*)*")

INSTRUCTION_LEAKS = (
    "here is a summary",
    "here's a summary",
    "summarise the following",
    "summarize the following",
    "as requested",
    "article text:",
)

REFUSALS = (
    "as an ai",
    "i cannot",
    "i can't",
    "i am unable",
    "language model",
)


class _NotScored:
    """Placeholder for the naturalness judge, which is not built yet.

    It needs a second model call and is meaningless until calibrated against
    people who read Arabic and French, so it reports that it did not score
    rather than raising or inventing a number.
    """

    def __repr__(self) -> str:
        return "NOT_SCORED"

    def __bool__(self) -> bool:
        return False


NOT_SCORED = _NotScored()


@dataclass(frozen=True)
class HardFailure:
    code: str
    detail: str = ""


@dataclass(frozen=True)
class SoftWarning:
    code: str
    detail: str = ""


@dataclass(frozen=True)
class CheckReport:
    hard: tuple[HardFailure, ...] = ()
    soft: tuple[SoftWarning, ...] = ()
    naturalness: object = field(default=NOT_SCORED)


def check_source(text: str, locale: str) -> list[HardFailure]:
    """Runs before any model call, so an unwritten locale costs nothing."""
    if not text or not text.strip():
        return [HardFailure("source_missing", f"no {locale} text for this article")]
    return []


def _hard_checks(source, output, locale, finish_reason) -> list[HardFailure]:
    failures = []

    if not output or not output.strip():
        return [HardFailure("empty", "the model returned nothing")]

    if finish_reason == "length":
        failures.append(HardFailure("truncated", "hit the output token ceiling"))

    source_words = len(source.split())
    output_words = len(output.split())
    # Two hard limits. Not shorter than the source is never a summary, whatever
    # its length, and 120 actual words is the ceiling in every language. How
    # long a quick read should be otherwise is set by the length tiers and
    # only flagged, below.
    if source_words and output_words >= source_words:
        failures.append(
            HardFailure("length_exceeded", f"{output_words} words, source is {source_words}")
        )
    elif output_words > HARD_MAX_WORDS:
        failures.append(
            HardFailure("length_exceeded", f"{output_words} words, the limit is {HARD_MAX_WORDS}")
        )

    has_arabic = bool(ARABIC.search(output))
    if locale == "ar" and not has_arabic:
        failures.append(HardFailure("wrong_script", "Arabic output is not in Arabic script"))
    if locale != "ar" and has_arabic:
        failures.append(HardFailure("wrong_script", f"Arabic script in {locale} output"))

    lowered = output.lower()
    if any(leak in lowered for leak in INSTRUCTION_LEAKS):
        failures.append(HardFailure("instruction_leak", "prompt text reached the output"))
    if any(refusal in lowered for refusal in REFUSALS):
        failures.append(HardFailure("refusal", "the model declined"))

    return failures


def _soft_checks(source, output, locale, protected) -> list[SoftWarning]:
    warnings = []

    invented = invented_figures(source, output)
    if invented:
        warnings.append(SoftWarning("invented_figures", ", ".join(invented[:3])))

    hardened = dropped_hedges(source, output)
    if hardened:
        warnings.append(SoftWarning("hedge_dropped", ", ".join(hardened[:3])))

    # Longer than the article's length tier allows, with some tolerance, is
    # flagged for a look. The hard limits above decide what is refused.
    words = len(output.split())
    target = target_for(len(source.split()), locale)
    if words > target.max_words + TOLERANCE:
        warnings.append(
            SoftWarning("over_length", f"{words} words, {target.tier} target up to {target.max_words}")
        )

    # Promotional filler the article never used reads as machine copy.
    filler = stock_phrases(output, source, locale)
    if filler:
        warnings.append(SoftWarning("stock_phrase", ", ".join(filler[:3])))

    # Latin script inside Arabic is correct for brand and product names, so
    # the check is that it matches something the source actually protected.
    if locale == "ar":
        approved = protected.all_terms
        unapproved = [
            run
            for run in LATIN_RUN.findall(output)
            if not any(run in term or term in run for term in approved)
        ]
        if unapproved:
            warnings.append(SoftWarning("unapproved_latin", ", ".join(unapproved[:3])))

    return warnings


def check_output(
    source: str,
    output: str,
    locale: str,
    protected: ProtectedTerms,
    finish_reason: str | None = None,
) -> CheckReport:
    hard = _hard_checks(source, output, locale, finish_reason)

    try:
        soft = _soft_checks(source, output, locale, protected)
    except Exception as exc:  # noqa: BLE001
        # A soft check is advisory. If one breaks, say so and carry on rather
        # than failing a job that may be perfectly good.
        soft = [SoftWarning("soft_check_error", str(exc))]

    return CheckReport(hard=tuple(hard), soft=tuple(soft), naturalness=NOT_SCORED)
