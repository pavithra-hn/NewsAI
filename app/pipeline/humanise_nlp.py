"""NLP post-processing to alter the statistical signature of generated text.

AI detectors flag text with low perplexity (too predictable) and low
burstiness (sentences all the same length). This module attacks both
by replacing over-used AI vocabulary with natural alternatives and
checking sentence length variation.
"""

import random
import re


_EN_REPLACEMENTS = {
    "utilize": ["use", "employ"],
    "utilizes": ["uses", "employs"],
    "utilizing": ["using"],
    "facilitate": ["help", "support", "enable"],
    "facilitates": ["helps", "supports", "enables"],
    "comprehensive": ["full", "complete", "thorough"],
    "implement": ["carry out", "put in place", "set up"],
    "implements": ["carries out", "sets up"],
    "implementation": ["rollout", "setup", "launch"],
    "subsequently": ["then", "later", "after that"],
    "furthermore": ["also", "on top of that"],
    "additionally": ["also", "plus"],
    "demonstrate": ["show", "prove"],
    "demonstrates": ["shows", "proves"],
    "significant": ["major", "big", "notable"],
    "significantly": ["sharply", "notably"],
    "approximately": ["about", "around", "roughly"],
    "enhance": ["improve", "boost", "lift"],
    "enhances": ["improves", "boosts"],
    "leverage": ["use", "tap", "draw on"],
    "leverages": ["uses", "taps"],
    "leveraging": ["using", "tapping"],
    "innovative": ["new", "fresh"],
    "optimize": ["improve", "fine-tune"],
    "robust": ["strong", "solid"],
    "streamline": ["simplify", "speed up"],
    "commence": ["start", "begin", "kick off"],
    "commenced": ["started", "began", "kicked off"],
    "prior to": ["before"],
    "in order to": ["to"],
    "pertaining to": ["about", "on"],
    "in conjunction with": ["with", "alongside"],
    "a wide range of": ["many", "various"],
}

_FR_REPLACEMENTS = {
    "mettre en avant": ["souligner", "montrer"],
    "dans le cadre de": ["lors de", "pendant"],
    "afin de": ["pour"],
    "en vue de": ["pour"],
    "par consequent": ["donc", "du coup"],
    "neanmoins": ["mais", "toutefois"],
    "considerable": ["important", "notable"],
}

_CONTRACTIONS = {
    "it is": "it's",
    "It is": "It's",
    "do not": "don't",
    "Do not": "Don't",
    "does not": "doesn't",
    "Does not": "Doesn't",
    "will not": "won't",
    "Will not": "Won't",
    "is not": "isn't",
    "Is not": "Isn't",
    "has not": "hasn't",
    "Has not": "Hasn't",
    "have not": "haven't",
    "Have not": "Haven't",
    "that is": "that's",
    "That is": "That's",
}


def _replace_ai_words(text: str, locale: str) -> str:
    replacements = {"en": _EN_REPLACEMENTS, "fr": _FR_REPLACEMENTS}.get(locale, {})
    if not replacements:
        return text

    result = text
    changes = 0
    max_changes = 3

    for ai_word, alternatives in replacements.items():
        if changes >= max_changes:
            break
        pattern = re.compile(re.escape(ai_word), re.IGNORECASE)
        match = pattern.search(result)
        if match:
            replacement = random.choice(alternatives)
            if match.group(0)[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            result = result[:match.start()] + replacement + result[match.end():]
            changes += 1

    return result


def _insert_contractions(text: str) -> str:
    result = text
    changes = 0
    for formal, contracted in _CONTRACTIONS.items():
        if changes >= 2:
            break
        if formal in result:
            result = result.replace(formal, contracted, 1)
            changes += 1
    return result


def humanise_nlp(text: str, locale: str) -> str:
    """Apply NLP post-processing to make text less detectable."""
    if not text or not text.strip():
        return text

    result = text.strip()
    result = _replace_ai_words(result, locale)

    if locale == "en":
        result = _insert_contractions(result)

    return result
