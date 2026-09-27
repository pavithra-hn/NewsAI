"""Second-pass humanisation using a different model.

AI detectors identify text by its statistical signature. A single model
has one signature. Running text through a second, different model disrupts
that signature because the rewriter's word choices do not follow the first
model's probability distribution.

This is a light rewrite, not a regeneration. The facts stay the same.
"""

HUMANISE_PROMPT = """You are a native {language} copy editor at a trade magazine.

Below is a short news brief that is factually correct but reads a little stiff.
Rewrite it so it sounds like a real person wrote it quickly at their desk.

Rules:
- Keep every fact, name, number and figure exactly the same. Change NOTHING factual.
- Mix up the sentence lengths. One short, one longer, maybe one medium.
- Do not start two sentences the same way.
- Use contractions where natural (English only: "it's", "didn't", "won't").
- Replace any stiff or formal phrasing with something a journalist would actually say.
- Keep it the same length (within 10 words).
- Write in {language} only.
- Output ONLY the rewritten text. No explanation, no preamble.

Text to rewrite:
{text}"""

LANGUAGE = {"en": "English", "ar": "Arabic", "fr": "French"}


def build_humanise_messages(text: str, locale: str) -> list[dict[str, str]]:
    language = LANGUAGE[locale]
    return [
        {
            "role": "user",
            "content": HUMANISE_PROMPT.format(language=language, text=text),
        }
    ]
