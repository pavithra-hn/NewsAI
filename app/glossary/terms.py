"""The industry glossary.

This is a seam, not an implementation. Building the termbase is its own piece
of work, and the storage format is deliberately not decided here so that the
glossary card can choose it rather than inherit a choice made in passing.

Until then the pipeline runs on terms derived from the article itself, which
`app.pipeline.protect` handles, and this returns nothing.
"""

from collections.abc import Iterable


def lookup(terms: Iterable[str], locale: str) -> dict[str, str]:
    """Return the approved rendering of each term in the given locale.

    Empty until the glossary exists. Callers must treat an absent term as
    "no house style recorded" rather than as an error.
    """
    return {}
