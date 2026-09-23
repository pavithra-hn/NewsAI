"""Everything the demo page does, apart from drawing it.

No Streamlit here, so all of it can be tested directly. The pipeline itself is
not copied: it is imported from news-ai-helper exactly as its own CLI uses it.
"""

import asyncio
import logging
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.actions.quick_read import QuickRead
from app.actions.registry import get_action
from app.cli import CorpusClient
from app.clients.makinaty import Article
from app.config import settings
from app.pipeline.clean import clean
from app.pipeline.protect import ProtectedTerms, protect
from app.providers.llm import LLMProvider

log = logging.getLogger("newsai.demo")

LOCALES = ("en", "ar", "fr")
LANGUAGE_NAMES = {"en": "English", "ar": "Arabic", "fr": "French"}

MIN_WORDS = 40
MAX_WORDS = 2000
DEFAULT_DAILY_LIMIT = 200

CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "corpus.json"

PROVIDER_DOWN = "The AI service did not respond, please try again."
UNEXPECTED = "Something went wrong with this run. It has been logged, please try again."


# Language detection.
#
# Arabic is decided by script. English against French is decided by counting
# short function words, which every real sentence is full of, plus French
# accents. Brand names and model codes are neutral, which is why an Arabic
# article carrying "Volvo Construction Equipment" still reads as Arabic.

ARABIC_LETTER = re.compile(r"[؀-ۿ]")
LATIN_LETTER = re.compile(r"[A-Za-zÀ-ÿœŒ]")
LATIN_WORD = re.compile(r"[a-zà-ÿœ]+")

FRENCH_WORDS = frozenset({
    "le", "la", "les", "des", "du", "de", "et", "est", "une", "un", "pour", "dans",
    "avec", "sur", "qui", "que", "au", "aux", "par", "ce", "cette", "ces", "ses", "son",
    "sa", "leur", "leurs", "plus", "en", "ne", "pas", "été", "sont", "ont", "il", "elle",
    "l", "d",
})
ENGLISH_WORDS = frozenset({
    "the", "and", "of", "to", "in", "is", "for", "with", "on", "that", "by", "from",
    "as", "at", "this", "its", "are", "was", "were", "has", "have", "had", "will", "be",
    "an", "it", "which", "their",
})
FRENCH_ACCENTS = frozenset("éèêëàâçîïôûùœ")

MIN_LETTERS = 20


def detect_language(text: str) -> str | None:
    """Return "en", "ar", "fr", or None when there is too little to tell."""
    text = clean(text)
    arabic = len(ARABIC_LETTER.findall(text))
    latin = len(LATIN_LETTER.findall(text))
    if arabic + latin < MIN_LETTERS:
        return None
    if arabic > latin:
        return "ar"

    lowered = text.lower()
    tokens = LATIN_WORD.findall(lowered)
    french = sum(t in FRENCH_WORDS for t in tokens)
    french += sum(c in FRENCH_ACCENTS for c in lowered) / 2
    english = sum(t in ENGLISH_WORDS for t in tokens)
    return "fr" if french > english else "en"


def paragraphs(body_html: str) -> list[str]:
    """An article's paragraphs as plain text, for showing it to a reader."""
    parts = re.split(r"</p\s*>|<br\s*/?>", body_html or "", flags=re.IGNORECASE)
    return [text for text in (clean(part) for part in parts) if text]


# Checking a box before anything is spent on it.


@dataclass(frozen=True)
class BoxCheck:
    locale: str
    ok: bool
    reason: str | None
    message: str
    words: int


def check_box(text: str, locale: str) -> BoxCheck:
    if not text or not text.strip():
        return BoxCheck(locale, False, "empty", "", 0)

    cleaned = clean(text)
    words = len(cleaned.split())
    name = LANGUAGE_NAMES[locale]

    if words < MIN_WORDS:
        return BoxCheck(
            locale, False, "too_short",
            f"Too short to summarise: {words} words. The minimum is {MIN_WORDS}.",
            words,
        )
    if words > MAX_WORDS:
        return BoxCheck(
            locale, False, "too_long",
            f"Too long: {words:,} words. The maximum is {MAX_WORDS:,}.",
            words,
        )

    detected = detect_language(cleaned)
    if detected != locale:
        seen = LANGUAGE_NAMES[detected] if detected else "no clear language"
        return BoxCheck(
            locale, False, "language_mismatch",
            f"This text looks like {seen}, not {name}. Each language is summarised "
            f"from its own text and the demo does not translate, so this box was not run.",
            words,
        )

    return BoxCheck(locale, True, None, "", words)


def check_paste(text: str) -> BoxCheck:
    """Check one pasted article, in the language it is written in.

    The language is detected rather than chosen, so a reader pastes and presses
    one button. Text too thin to tell the language from is refused, because
    guessing would mean summarising it in a language it was not written in.
    """
    if not text or not text.strip():
        return BoxCheck("", False, "empty", "Paste an article to summarise.", 0)

    cleaned = clean(text)
    words = len(cleaned.split())
    if words < MIN_WORDS:
        return BoxCheck(
            "", False, "too_short",
            f"Too short to summarise: {words} words. The minimum is {MIN_WORDS}.",
            words,
        )
    if words > MAX_WORDS:
        return BoxCheck(
            "", False, "too_long",
            f"Too long: {words:,} words. The maximum is {MAX_WORDS:,}.",
            words,
        )

    locale = detect_language(cleaned)
    if locale is None:
        return BoxCheck(
            "", False, "no_language",
            "The language of this text is not clear. Paste an article written in "
            "English, French or Arabic.",
            words,
        )
    return BoxCheck(locale, True, None, "", words)


class PastedClient:
    """Serves pasted text in place of MakinatyNews, so handle() runs unchanged."""

    def __init__(
        self, texts: Mapping[str, str], titles: Mapping[str, str] | None = None
    ) -> None:
        self.texts = dict(texts)
        self.titles = dict(titles or {})

    async def fetch_article(self, article_id: int, locale: str) -> Article:
        return Article(
            article_id=article_id,
            locale=locale,
            body_html=self.texts[locale],
            title=self.titles.get(locale) or None,
        )


# Running.


@dataclass(frozen=True)
class RunOutcome:
    locale: str
    result: QuickRead | None
    seconds: float
    error: str | None = None
    cleaned_source: str = ""
    protected: ProtectedTerms = field(default_factory=ProtectedTerms)


def make_provider():
    return LLMProvider()


def provider_ready() -> bool:
    return bool(settings.provider_api_key)


async def _run_one(article_id, locale, client, provider) -> RunOutcome:
    started = time.monotonic()
    try:
        article = await client.fetch_article(article_id, locale)
        cleaned = clean(article.body_html)
        result = await get_action("quick_read")(
            article_id, locale, client=client, provider=provider
        )
    except Exception:
        log.exception("quick read failed for %s, article %s", locale, article_id)
        return RunOutcome(locale, None, time.monotonic() - started, error=UNEXPECTED)

    for failure in result.checks.hard:
        if failure.code == "provider_error":
            log.error("provider error for %s, article %s: %s", locale, article_id, failure.detail)

    return RunOutcome(
        locale=locale,
        result=result,
        seconds=time.monotonic() - started,
        cleaned_source=cleaned,
        protected=protect(cleaned, locale),
    )


async def run_quick_reads(
    article_id: int,
    locales,
    client,
    provider_factory: Callable | None = None,
) -> list[RunOutcome]:
    """Run the given locales concurrently on one provider, then close it.

    The provider is created inside the running event loop and closed before
    it ends, so its HTTP client never outlives the loop that owns it.
    """
    provider = (provider_factory or make_provider)()
    try:
        return list(
            await asyncio.gather(
                *(_run_one(article_id, locale, client, provider) for locale in locales)
            )
        )
    finally:
        close = getattr(provider, "aclose", None)
        if close is not None:
            await close()


def run_sync(coroutine):
    return asyncio.run(coroutine)


# Presenting a result in plain English.

HARD_REASONS = {
    "source_missing": "There was no article text to summarise.",
    "empty": "The AI returned nothing.",
    "length_exceeded": "The summary was not short enough.",
    "wrong_script": "The summary came back in the wrong language or script.",
    "instruction_leak": "The reply contained instructions rather than a summary.",
    "refusal": "The AI declined to summarise this text.",
    "truncated": "The summary was cut off before it finished.",
    "provider_error": PROVIDER_DOWN,
}

SOFT_REASONS = {
    "invented_figures": "A figure in the summary does not appear in the article: {detail}.",
    "unapproved_latin": "Latin-script text in the Arabic summary is not in the article: {detail}.",
    "hedge_dropped": (
        "An approximate figure is stated as exact: {detail}. "
        "The article says about or around."
    ),
    "over_length": "Longer than intended for an article this size: {detail}.",
    "soft_check_error": "One of the review checks could not run.",
}


def status_for(outcome: RunOutcome) -> tuple[str, list[str]]:
    if outcome.result is None:
        return "Blocked", [outcome.error or UNEXPECTED]

    result = outcome.result
    if not result.deliverable:
        reasons = [HARD_REASONS.get(f.code, f"Failed check: {f.code}.") for f in result.checks.hard]
        return "Blocked", list(dict.fromkeys(reasons))

    if result.needs_review:
        reasons = [
            SOFT_REASONS.get(w.code, "Flagged by check: {code}.").format(
                detail=w.detail, code=w.code
            )
            for w in result.checks.soft
        ]
        return "Delivered, review suggested", reasons

    return "Delivered", []


# The data plate's "kept exactly" list.
#
# Read whole tokens, never fragments: French groups thousands with a space, so
# 70 000 is one figure, and model codes carry hyphens and letters, so CQD20-G2,
# 2C140 and 4×2 are each one term. A token is listed only if it carries a digit
# and the article states it too. Tokens are compared folded (digit set, spaces,
# thousands commas) but shown exactly as the quick read writes them.

_TOKEN = re.compile(
    r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?"
    r"|[A-Za-z0-9٠-٩۰-۹]+(?:[-/×.,][A-Za-z0-9٠-٩۰-۹]+)*"
)
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
MAX_KEPT = 6


def _key(token: str) -> str:
    folded = re.sub(r"[\s  ]", "", token.translate(_ARABIC_INDIC)).rstrip(".,")
    if re.fullmatch(r"[\d.,]+", folded):
        folded = folded.replace(",", "")
    return folded


def _terms(text: str) -> list[str]:
    return [t.rstrip(".,") for t in _TOKEN.findall(text) if re.search(r"\d", _key(t))]


def kept_exactly(summary: str, source: str) -> list[str]:
    """Figures and model codes from the article that the quick read repeats."""
    in_source = {_key(term) for term in _terms(source)}
    kept = [term for term in _terms(summary) if len(_key(term)) > 1 and _key(term) in in_source]
    return list(dict.fromkeys(kept))[:MAX_KEPT]


def format_cost(result: QuickRead | None) -> str:
    if result is None or not result.cost_known:
        return "unknown"
    return f"${result.cost_usd:.6f}"


# The daily limit.


class UsageCounter:
    """Runs used today, shared by every session in this process.

    It lives in memory, so a restart resets it. That is acceptable for a demo.
    """

    def __init__(self, limit: int, today: Callable[[], date] = date.today) -> None:
        self.limit = limit
        self._today = today
        self._day = today()
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        if self._today() != self._day:
            self._day = self._today()
            self._used = 0

    def remaining(self) -> int:
        with self._lock:
            self._roll()
            return self.limit - self._used

    def try_consume(self, runs: int) -> bool:
        """Take all the runs a request needs, or none of them."""
        with self._lock:
            self._roll()
            if self._used + runs > self.limit:
                return False
            self._used += runs
            return True


# Configuration. Read from the environment first, then Streamlit secrets.


def _setting(name: str, environ: Mapping, secrets: Mapping) -> str | None:
    value = environ.get(name)
    if value is None:
        value = secrets.get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def daily_limit(environ: Mapping, secrets: Mapping) -> int:
    value = _setting("DEMO_DAILY_LIMIT", environ, secrets)
    if value is None:
        return DEFAULT_DAILY_LIMIT
    if not value.isdigit() or int(value) < 1:
        raise ValueError(f"DEMO_DAILY_LIMIT must be a positive whole number, got {value!r}")
    return int(value)


# Samples.


def sample_client() -> CorpusClient:
    return CorpusClient(CORPUS_PATH)


def sample_titles(client: CorpusClient | None = None) -> list[str]:
    client = client or sample_client()
    return [article["locales"]["en"]["title"] for article in client.articles]
