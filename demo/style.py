"""How the desk writes and a language model does not, as rules and as a check.

Detectors flag text that reads as machine copy, and a few habits give it away:
every sentence the same length, sentences that open on a product description,
an "-ing" add-on at the end of a sentence, sales words, a closing line that
sums up. RULES asks the model to avoid them; problems() finds the ones it wrote
anyway, so they can be named in a second request.

A word counts only when the writer brings it in. If the source uses it,
repeating it is quoting the source.
"""

import re
from itertools import pairwise

from app.pipeline.phrasing import stock_phrases

# Words that mark trade copy as machine-written, on top of the pipeline's own list.
TELLS = {
    "en": (
        "ensure", "ensures", "ensuring", "boast", "boasts", "boasting", "robust",
        "seamless", "seamlessly", "cutting-edge", "state-of-the-art", "well-suited",
        "furthermore", "moreover", "additionally", "notably", "leverage", "leverages",
        "comprehensive", "unparalleled", "renowned", "delve", "plays a crucial role",
        "plays a key role", "in today's",
    ),
    "fr": (
        "par ailleurs", "en outre", "de surcroît", "garantit", "garantissant", "robuste",
        "de pointe", "incontournable", "joue un rôle clé", "joue un rôle essentiel",
    ),
    "ar": (
        "علاوة على ذلك", "بالإضافة إلى ذلك", "فضلاً عن ذلك", "يضمن", "تضمن", "يتميز", "تتميز",
    ),
}
TELL_PATTERNS = {
    locale: re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(word) for word in words) + r")(?!\w)", re.IGNORECASE
    )
    for locale, words in TELLS.items()
}

# Sales words a reporter leaves to the brochure.
SALES = re.compile(
    r"(?<![\w-])(?:features?|boasts?|delivers?|designed (?:to|for)|ideal for|versatile|"
    r"reliable|efficient|powerful|impressive|enhanced|offers)(?![\w-])",
    re.IGNORECASE,
)

PRODUCT_OPENING = re.compile(r"^(?:The|This)\s+(?:[\w³.&'-]+\s+){0,4}?is\b|^It is\b")
ING_TAIL = re.compile(
    r",\s+(making|ensuring|providing|allowing|enabling|offering|giving|helping|highlighting|"
    r"underscoring|reflecting|delivering|positioning|solidifying|cementing)\b"
)
SUMMING_UP = re.compile(r"^(Overall|In summary|In short|All in all|Ultimately|With this|This move)\b")

MIN_SPREAD = 10

RULES = """How a person on your desk writes, and a machine does not. In English, follow \
every point:
- Open with what happened and who did it. Never open a sentence with "The [name] is", \
"This [name] is" or "It is".
- Do not open two sentences in a row with the same word.
- Mix long and short sentences: your longest sentence is at least 10 words longer than \
your shortest. A long one carries two facts joined by "and" or a clause; a short one \
carries one.
- Never end a sentence with an "-ing" add-on such as ", making it", ", ensuring" or \
", providing".
- Use plain verbs: has, uses, runs, weighs, carries, built, sold. Never "features", \
"boasts", "offers", "delivers", "designed to" or "ideal for".
- Add no praise the source does not give: no "versatile", "reliable", "efficient", \
"powerful", "impressive" or "enhanced".
- End on a fact. No closing line that sums up or looks ahead, such as "Overall" or \
"With this"."""


def sentences(text: str) -> list[str]:
    """Sentences split at a full stop, question or exclamation mark followed by a space."""
    return [part for part in re.split(r"(?<=[.!?؟])\s+", text.strip()) if part]


def _new_words(pattern: re.Pattern, text: str, source: str) -> list[str]:
    found = dict.fromkeys(match.group(0).lower() for match in pattern.finditer(text))
    return [word for word in found if not re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])",
                                                    source, re.IGNORECASE)]


def problems(text: str, source: str, locale: str) -> list[str]:
    """What in this text reads as machine copy, each named so it can be fixed."""
    words = _new_words(TELL_PATTERNS[locale], text, source)
    words += [phrase.lower() for phrase in stock_phrases(text, source, locale)]
    if locale != "en":
        return [f'"{word}"' for word in dict.fromkeys(words)]

    words += _new_words(SALES, text, source)
    found = [f'"{word}"' for word in dict.fromkeys(words)]
    parts = sentences(text)

    for part in parts:
        opening = PRODUCT_OPENING.match(part)
        if opening:
            found.append(f'a sentence opens with "{opening.group(0)}"')
        tail = ING_TAIL.search(part)
        if tail:
            found.append(f'a sentence ends with an add-on: ", {tail.group(1)}"')

    openers = [part.split()[0].lower() for part in parts]
    for first, second in pairwise(openers):
        if first == second:
            found.append(f'two sentences in a row open with "{first.capitalize()}"')
            break

    lengths = [len(part.split()) for part in parts]
    if len(lengths) >= 2 and max(lengths) - min(lengths) < MIN_SPREAD:
        found.append(
            f"the sentences are all about the same length ({min(lengths)} to {max(lengths)} "
            f"words); make the longest at least {MIN_SPREAD} words longer than the shortest"
        )

    closing = SUMMING_UP.match(parts[-1]) if parts else None
    if closing:
        found.append(f'the last sentence sums up with "{closing.group(0)}"')
    return found
