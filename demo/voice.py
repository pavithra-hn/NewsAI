"""Quick reads in the desk's own voice.

The pipeline snapshot in app/ is never edited here, so this wraps the provider
it is given. Every request gains articles the desk wrote in the same language,
as the voice to copy, and runs at a higher temperature. The pipeline's own
checks still judge every answer. A summary that borrows a name from one of
those articles is asked for once more.
"""

import dataclasses
import functools
import json
import re

from app.pipeline.prompts import ARTICLE_END, ARTICLE_START, LANGUAGE
from app.providers.base import ProviderError
from demo.humanize import NAME, NOT_NAMES
from demo.logic import CORPUS_PATH, paragraphs

# Detectors flag text whose every word is the most likely one. The pipeline's
# checks catch what a higher temperature costs in accuracy.
TEMPERATURE = 0.9

# Articles the desk wrote, which the corpus holds in all three languages.
DESK_SLUGS = (
    "kalmar-delivers-five-container-handling-machines-to-damietta-terminal",
    "man-truck-bus-appoints-libya-motors-company-as-official-dealer-in-libya",
    "dubai-rta-awards-316m-contracts-for-al-meydan-street-development",
)

DATELINE = re.compile(r"^[^()\n]{1,40}\(\s*PlantAndEquipment\.com\s*\)\s*-\s*")

DESK_START = "<<<DESK ARTICLES>>>"
DESK_END = "<<<END DESK ARTICLES>>>"

VOICE = """Voice: below are articles your desk published in {language}. Write the quick \
read the way they are written: how their sentences open and run, their plain verbs, no \
contractions. They are about other stories, so take nothing else from them: no facts, \
names, figures or places.

{start}
{articles}
{end}"""

# An example whose opening words appear in the article is the article itself.
OPENING_WORDS = 12


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


@functools.cache
def _desk_texts(locale: str) -> tuple[str, ...]:
    items = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    texts = []
    for slug in DESK_SLUGS:
        item = next(item for item in items if item["href"].endswith(slug))
        body = "\n\n".join(paragraphs(item["locales"][locale]["body_html"]))
        texts.append(DATELINE.sub("", body, count=1))
    return tuple(texts)


def desk_articles(locale: str, article: str) -> tuple[str, ...]:
    """The desk's articles in this language, leaving out the one being summarised."""
    words = " ".join(_words(article))
    return tuple(
        text for text in _desk_texts(locale)
        if " ".join(_words(text)[:OPENING_WORDS]) not in words
    )


def _names(texts) -> frozenset[str]:
    """Capitalised words the desk's articles never write in lower case."""
    text = "\n".join(texts)
    lower = set(re.findall(r"\b[a-z][a-z'.-]*\b", text))
    return frozenset(
        name for name in NAME.findall(text) if name.lower() not in lower and name not in NOT_NAMES
    )


def _borrowed(names, article: str, output: str) -> tuple[str, ...]:
    in_article = article.lower()
    return tuple(sorted(
        name for name in names
        if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", output)
        and not re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", in_article)
    ))


def _article(messages) -> str:
    text = "\n".join(message["content"] for message in messages)
    start, end = text.find(ARTICLE_START), text.find(ARTICLE_END)
    return text[start + len(ARTICLE_START):end] if 0 <= start < end else ""


def _locale(system: str) -> str | None:
    return next((code for code, name in LANGUAGE.items() if f"Write in {name}." in system), None)


def _paid_for_both(kept, other):
    """The answer kept, carrying the tokens and cost of both calls."""
    return dataclasses.replace(
        kept,
        input_tokens=kept.input_tokens + other.input_tokens,
        output_tokens=kept.output_tokens + other.output_tokens,
        cost_usd=kept.cost_usd + other.cost_usd,
        cost_known=kept.cost_known and other.cost_known,
    )


class VoiceProvider:
    """Passes every call through with the desk's voice and a higher temperature."""

    def __init__(self, provider) -> None:
        self._provider = provider

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=400):
        locale = _locale(messages[0]["content"])
        article = _article(messages)
        if locale is None or not article:
            return await self._provider.complete(
                messages, model=model, temperature=temperature, max_tokens=max_tokens
            )

        shown = desk_articles(locale, article)
        voice = VOICE.format(
            language=LANGUAGE[locale], start=DESK_START,
            articles="\n\n---\n\n".join(shown), end=DESK_END,
        )
        voiced = [{**messages[0], "content": messages[0]["content"] + "\n\n" + voice}, *messages[1:]]

        async def ask():
            return await self._provider.complete(
                voiced, model=model, temperature=TEMPERATURE, max_tokens=max_tokens
            )

        names = _names(shown)
        first = await ask()
        if not _borrowed(names, article, first.text):
            return first
        try:
            second = await ask()
        except ProviderError:
            return dataclasses.replace(first, cost_known=False)

        if len(_borrowed(names, article, second.text)) <= len(_borrowed(names, article, first.text)):
            return _paid_for_both(second, first)
        return _paid_for_both(first, second)

    async def aclose(self) -> None:
        close = getattr(self._provider, "aclose", None)
        if close is not None:
            await close()
