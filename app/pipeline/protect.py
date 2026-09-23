"""Finds the terms a summary must reproduce exactly.

Terms are derived from the article itself rather than from a curated list,
because no glossary exists yet. The same set serves two purposes: it tells the
model what to preserve, and it is the approved list the Latin-script soft check
compares Arabic output against. Without it that check has nothing to compare to.

The glossary card later adds a curated layer on top of this.
"""

import re
from dataclasses import dataclass

# A drivetrain configuration such as 4x2 or 6x4. Extracted before figures so
# that it stays one specification instead of becoming two unrelated numbers.
DRIVETRAIN = re.compile(r"\d+\s*[×x]\s*\d+")

# A model code, in two shapes: letters joined to digits such as EC650, or a
# short capitalised prefix separated by a space such as Cat 345 GC.
#
# The prefix is capped at four characters on purpose. An earlier, looser
# pattern matched any word before a number, so "delivered 20" was read as a
# model code and the quantity stopped being treated as a figure.
MODEL_CODE = re.compile(
    r"\b(?:[A-Z][A-Za-z]*\d+[A-Za-z]*|[A-Z][a-zA-Z]{0,3}\s\d{2,}(?:\s[A-Z]{1,3})?)\b"
)

# A run of Latin script. In Arabic this is where brand and product names live,
# and it is correct for them to stay in Latin script.
LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9.&'-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.&'-]*)*")

FIGURE = re.compile(r"\d[\d,.]*\s*(?:m³|m3|km|kg|tonnes?|tons?|%)?")


def _unique(values) -> tuple[str, ...]:
    seen = {}
    for value in values:
        cleaned = value.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return tuple(seen)


@dataclass(frozen=True)
class ProtectedTerms:
    latin_runs: tuple[str, ...] = ()
    model_codes: tuple[str, ...] = ()
    figures: tuple[str, ...] = ()

    @property
    def all_terms(self) -> tuple[str, ...]:
        return _unique(self.latin_runs + self.model_codes + self.figures)


def protect(text: str, locale: str) -> ProtectedTerms:
    if not text:
        return ProtectedTerms()

    model_codes = _unique(DRIVETRAIN.findall(text) + MODEL_CODE.findall(text))

    # Figures are read from the text with the model codes removed, so a code
    # like 4x2 or EC650 does not also register as a loose number.
    remainder = text
    for code in model_codes:
        remainder = remainder.replace(code, " ")

    # Latin script marks a brand name only inside Arabic, where it is at risk
    # of being transliterated. In English and French it is the whole article,
    # and listing it would paste the article back into the prompt.
    latin_runs = _unique(LATIN_RUN.findall(text)) if locale == "ar" else ()
    figures = _unique(FIGURE.findall(remainder))

    return ProtectedTerms(
        latin_runs=latin_runs,
        model_codes=model_codes,
        figures=figures,
    )
