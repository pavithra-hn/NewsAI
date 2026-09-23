"""How long a quick read should be, given the article it summarises.

Length scales with the article. Most real articles are short, so a fixed
target would make many quick reads most of the length of their source.

Tiers are defined in English-equivalent words: a source's word count divided by
its language's factor, since French and Arabic use more words than English for
the same content. The resulting target is converted back to that language's
actual words, because that is what the model counts.

The 120 word cap is an actual word count in every language. It is the one
number anyone can check by counting, so it is never scaled.
"""

from dataclasses import dataclass

from app.config import settings

HARD_MAX_WORDS = 120
TOLERANCE = 10

# (upper bound in English-equivalent words, sentences, target words)
_TIERS = (
    ("short", 250, (2, 3), (40, 60)),
    ("medium", 600, (3, 4), (60, 90)),
    ("long", None, (4, 5), (90, 120)),
)


@dataclass(frozen=True)
class LengthTarget:
    tier: str
    min_sentences: int
    max_sentences: int
    min_words: int
    max_words: int


def target_for(source_words: int, locale: str, factors: dict | None = None) -> LengthTarget:
    factor = (factors or settings.language_factors)[locale]
    equivalent = source_words / factor

    for name, upper, (min_s, max_s), (min_w, max_w) in _TIERS:
        if upper is None or equivalent <= upper:
            break

    return LengthTarget(
        tier=name,
        min_sentences=min_s,
        max_sentences=max_s,
        min_words=min(round(min_w * factor), HARD_MAX_WORDS),
        max_words=min(round(max_w * factor), HARD_MAX_WORDS),
    )


def within_target(words: int, target: LengthTarget) -> bool:
    """Inside the target range with some tolerance, and never over the cap."""
    upper = min(target.max_words + TOLERANCE, HARD_MAX_WORDS)
    return target.min_words - TOLERANCE <= words <= upper
