"""Stock phrases that make a quick read read like machine copy.

These are the promotional connectors a press release or a language model reaches
for, and a trade reporter filing a brief does not: "showcase", "aims to", "as
the Kingdom continues to". They were measured on the quality study's final
summaries: six of ten English and five of ten French quick reads carried one.

A phrase counts only when the quick read brings it in. If the article itself
uses it, repeating it is quoting the source rather than adding filler, so it is
allowed.

The lists are deliberately short and specific. A general word such as "تعزيز"
or "strengthen" is ordinary news vocabulary on its own, so only its stock
constructions are listed.
"""

import re

STOCK_PATTERNS = {
    "en": [
        r"showcas\w*",
        r"featuring",
        r"highlight(?:s|ed|ing)?",
        r"underscor\w*",
        r"aim(?:s|ed|ing)? to",
        r"continues? to",
        r"poised to",
        r"testament to",
        r"leverag\w*",
        r"pivotal",
        r"cutting-edge",
        r"state-of-the-art",
        r"bolster\w*",
        r"in a move to",
        r"commitment to",
        r"strengthen(?:s|ed|ing)? (?:its|their) (?:position|presence)",
    ],
    "fr": [
        r"vise à",
        r"visant à",
        r"visent à",
        r"met(?:tre|tant|tent)? en avant",
        r"soulign\w*",
        r"témoign\w*",
        r"s'inscri\w* dans",
        r"s’inscri\w* dans",
        r"de pointe",
        r"incontournable\w*",
        r"renforcer (?:sa|leur) (?:position|présence)",
        r"de premier plan",
    ],
    "ar": [
        r"في خطوة",
        # Arabic often puts the subject between the verb and its object:
        # يسلط المعرض الضوء, so up to two words may sit in between.
        r"[يت]سلط(?:\s+\S+){0,2}?\s+الضوء",
        r"تسليط الضوء",
        r"مما يعكس",
        r"نقلة نوعية",
        r"في إطار سعي\w*",
        r"بهدف تعزيز",
        r"تهدف إلى تعزيز",
        r"يهدف إلى تعزيز",
        r"بما يعزز",
    ],
}

_COMPILED = {
    locale: re.compile(r"(?<!\w)(?:" + "|".join(patterns) + r")(?!\w)", re.IGNORECASE)
    for locale, patterns in STOCK_PATTERNS.items()
}


def stock_phrases(output: str, source: str, locale: str) -> list[str]:
    """Stock phrases in the quick read that the article did not use itself."""
    pattern = _COMPILED.get(locale)
    if pattern is None:
        return []

    in_source = {m.lower() for m in pattern.findall(source or "")}
    found = []
    for match in pattern.findall(output or ""):
        phrase = match.lower()
        if phrase not in in_source and phrase not in found:
            found.append(phrase)
    return found
