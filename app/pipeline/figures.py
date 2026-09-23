"""Comparing figures in a summary against figures in its source.

A summary is supposed to leave things out, so there is no rule that every
figure must appear. The rule is that a figure which does appear must match the
source. Tonnages, model numbers, quantities and prices may be omitted. They may
never be changed.

This lives in the package rather than in benchmark/ because both the pipeline's
soft check and the benchmark scorer need it, and two implementations of the
same comparison would drift and then disagree.
"""

import re

NUMBER = re.compile(r"\d[\d,.]*")

# Arabic text may use either Latin or Arabic-Indic digits, and a model can
# answer in the other set. Fold them together before comparing.
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


# A comma before one or two digits at the end is a French decimal comma: "3,5".
# A comma before exactly three digits is a thousands separator: "70,000".
_DECIMAL_COMMA = re.compile(r",(\d{1,2})$")


def normalise_number(value: str) -> str:
    value = value.translate(ARABIC_INDIC_DIGITS).rstrip(".,")
    value = _DECIMAL_COMMA.sub(r".\1", value)
    return value.replace(",", "")


def invented_figures(source: str, output: str) -> list[str]:
    """Figures in the output that do not appear in the source."""
    source_numbers = {normalise_number(n) for n in NUMBER.findall(source)}
    return [n for n in NUMBER.findall(output) if normalise_number(n) not in source_numbers]


# Hedges. "About 70,000" and "70,000" are different claims: the first is what the
# article reported, the second is a precision the article never gave. A summary
# may leave a figure out, but it must not harden an approximation into a fact.

_PRE_HEDGES = [
    # English
    "about", "around", "approximately", "roughly", "nearly", "almost", "some",
    "more than", "less than", "up to", "close to", "at least",
    "upwards of", "just over", "just under",
    # Bare "over" and "under" are left out on purpose: "space over 26 stores"
    # means spread across 26 stores. The judge still checks hedges by meaning.
    # French
    "environ", "près de", "plus de", "moins de", "quelque", "jusqu'à", "jusqu’à",
    "autour de", "presque", "quasiment", "au moins", "pas moins de",
    # Arabic
    "حوالي", "حوالى", "نحو", "قرابة", "زهاء", "ما يقارب", "ما يقرب من",
    "أكثر من", "أقل من", "ما يزيد على", "ما يزيد عن", "ما يصل إلى",
]

# Currency written between a hedge and its figure: "about $930 million".
_CURRENCY = r"(?:US\$|\$|€|£|USD|AED|SAR|EUR|QAR|KWD|OMR|BHD|Dhs?|Rs\.?|INR)"

_PRE = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(h).replace(r"\ ", r"\s+") for h in sorted(_PRE_HEDGES, key=len, reverse=True))
    + r")\s*(?:d['’]\s*)?(?:" + _CURRENCY + r"\s*)?(\d[\d,.  ]*\d|\d)",
    re.IGNORECASE,
)
# Arabic can hedge after the figure: "930 مليون دولار تقريبًا".
_POST = re.compile(r"(\d[\d,.]*)\s+(?:\S+\s+){0,3}?تقريب[اًﹰ]*")


def _fold(text: str) -> str:
    return text.translate(ARABIC_INDIC_DIGITS)


def figure_key(value: str) -> str:
    # French writes 70 000 with a space, and sometimes a narrow no-break space.
    return normalise_number(re.sub(r"[\s  ]", "", value))


def hedged_figures(text: str) -> set[str]:
    """Figures stated with a hedge, normalised so they can be compared."""
    text = _fold(text)
    found = {figure_key(m.group(1)) for m in _PRE.finditer(text)}
    found |= {figure_key(m.group(1)) for m in _POST.finditer(text)}
    return {f for f in found if f}


def hedged_phrases(text: str) -> dict[str, str]:
    """For each hedged figure, the words the article used: "about 70,000".

    Handed to the model in place of the bare figure, so the list of things to
    preserve exactly never strips the qualifier off.
    """
    folded = _fold(text)
    phrases = {}
    for match in list(_PRE.finditer(folded)) + list(_POST.finditer(folded)):
        phrases.setdefault(figure_key(match.group(1)), " ".join(match.group(0).split()))
    return phrases


def _all_figures(text: str) -> list[str]:
    return [figure_key(n) for n in NUMBER.findall(_fold(text))]


def dropped_hedges(source: str, output: str) -> list[str]:
    """Figures the source only approximated, stated in the output without a hedge.

    A figure counts as approximated only if every mention of it in the source
    is hedged. If the article also states it exactly, an exact figure in the
    summary is not clearly wrong.
    """
    source_hedged = hedged_figures(source)
    source_counts = {}
    for figure in _all_figures(source):
        source_counts[figure] = source_counts.get(figure, 0) + 1
    hedged_mentions = {}
    folded = _fold(source)
    for m in list(_PRE.finditer(folded)) + list(_POST.finditer(folded)):
        key = figure_key(m.group(1))
        hedged_mentions[key] = hedged_mentions.get(key, 0) + 1

    only_approximate = {
        f for f in source_hedged if hedged_mentions.get(f, 0) >= source_counts.get(f, 0)
    }
    output_hedged = hedged_figures(output)

    dropped = []
    for raw in NUMBER.findall(_fold(output)):
        key = figure_key(raw)
        if key in only_approximate and key not in output_hedged:
            dropped.append(raw.rstrip(".,"))
    return list(dict.fromkeys(dropped))
