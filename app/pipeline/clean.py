"""Turns article markup into the plain text the model is given.

The order of the three steps matters and is not interchangeable.

Tags go first because article text is untrusted input (N12): decoding first
would let an encoded angle bracket produce a tag that the remover then acts on.

Decoding comes before anything reads figures, because two of the entities in
this corpus are part of figures rather than decoration. `&sup3;` appears in
"4.6m&sup3;" and `&times;` in "4&times;2", which is a drivetrain specification.
Stripping either one leaves digits that still match the source, so the
corruption would pass the figure check unnoticed.
"""

import html
import re

TAG = re.compile(r"<[^>]*>")
WHITESPACE = re.compile(r"\s+")


def clean(body_html: str) -> str:
    if not body_html:
        return ""

    # A space, not an empty string. 236 places in the corpus put sentence
    # punctuation directly against a paragraph break, and gluing those
    # together destroys the boundary the length rule counts.
    text = TAG.sub(" ", body_html)
    text = html.unescape(text)
    return WHITESPACE.sub(" ", text).strip()
