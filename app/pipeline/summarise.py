"""Turns one article, in one locale, into one summary in that same language."""

from app.config import settings
from app.pipeline.prompts import build_prompt
from app.pipeline.protect import ProtectedTerms
from app.providers.base import Completion

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 400


async def summarise(
    *,
    title: str | None,
    text: str,
    locale: str,
    protected: ProtectedTerms,
    glossary: dict[str, str],
    provider,
    model: str,
    temperature: float = DEFAULT_TEMPERATURE,
    corrective: str | None = None,
) -> Completion:
    """One model call.

    `corrective` carries feedback from a previous failed attempt. It is
    appended after the article block, so a retry asks for something different
    rather than repeating a request that already produced the wrong answer.
    """
    messages = build_prompt(
        title=title,
        text=text,
        locale=locale,
        protected=protected,
        glossary=glossary,
        style_locales=settings.style_examples,
    )

    if corrective:
        messages.append({"role": "user", "content": corrective})

    return await provider.complete(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
