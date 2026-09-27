import asyncio
import json

from app.pipeline.clean import clean
from app.pipeline.prompts import build_prompt
from app.pipeline.protect import protect
from app.providers.base import Completion, ProviderError
from demo import logic, style, voice

VOLVO = (
    "Volvo Construction Equipment has delivered twelve EC220 excavators to a contractor in "
    "Oman. The machines will work on a highway project near Muscat, the company said. "
    "Deliveries were completed in September, and the contractor has an option on six more."
)
NOTES = "- Volvo CE delivered twelve EC220 excavators\n- buyer: contractor in Oman\n- highway near Muscat"
SUMMARY = "Volvo CE has delivered twelve EC220 excavators to an Omani contractor for a highway job."
BORROWED = "Volvo CE has delivered twelve EC220 excavators to Damietta for a highway job."
STIFF = "The Volvo EC220 is an excavator. It went to Oman."


def corpus_article(slug: str, locale: str) -> str:
    items = json.loads(logic.CORPUS_PATH.read_text(encoding="utf-8"))
    item = next(item for item in items if slug in item["href"])
    return clean(item["locales"][locale]["body_html"])


def quick_read_messages(text: str, locale: str = "en") -> list[dict]:
    return build_prompt(None, text, locale, protect(text, locale), {})


class Scripted:
    """Answers with the given replies in turn and keeps what it was asked."""

    def __init__(self, *replies, fail_on=None):
        self.replies = list(replies)
        self.fail_on = fail_on
        self.calls = []
        self.closed = False

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=400):
        self.calls.append({"messages": messages, "temperature": temperature})
        if len(self.calls) == self.fail_on:
            raise ProviderError("gave up after 3 attempts: 503 from the provider")
        text = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return Completion(
            text=text, input_tokens=100, output_tokens=20, finish_reason="stop",
            model=model, cost_usd=0.0001, cost_known=True,
        )

    async def aclose(self):
        self.closed = True


def ask(provider, messages, temperature=0.3):
    return asyncio.run(provider.complete(messages, model="test-model", temperature=temperature))


def text_of(call) -> str:
    return "\n".join(message["content"] for message in call["messages"])


# The desk's own articles, as the voice to copy.


def test_each_language_gets_the_desk_articles_written_in_it():
    assert len(voice.desk_articles("en", VOLVO)) == 3
    assert any("Kalmar has delivered" in text for text in voice.desk_articles("en", VOLVO))
    assert any("Kalmar a livré" in text for text in voice.desk_articles("fr", VOLVO))
    assert any("كالمار" in text for text in voice.desk_articles("ar", VOLVO))


def test_the_dateline_is_taken_off_every_desk_article():
    for locale in logic.LOCALES:
        for text in voice.desk_articles(locale, VOLVO):
            assert "PlantAndEquipment.com" not in text


def test_the_article_being_summarised_is_never_its_own_example():
    kalmar = corpus_article("kalmar-delivers-five", "en")
    shown = voice.desk_articles("en", kalmar)
    assert len(shown) == 2
    assert not any("Damietta" in text for text in shown)


# Notes first, so the quick read is written from facts and not from the article's sentences.


def test_the_article_is_turned_into_notes_first():
    inner = Scripted(NOTES, SUMMARY)
    ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    notes_call = inner.calls[0]
    assert notes_call["messages"][0]["content"].startswith(voice.NOTES.split(".")[0])
    assert "the company said" in text_of(notes_call)
    assert notes_call["temperature"] == voice.NOTES_TEMPERATURE


def test_the_writer_sees_the_notes_and_not_the_article():
    inner = Scripted(NOTES, SUMMARY)
    ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    written = text_of(inner.calls[1])
    assert NOTES in written
    assert "the company said" not in written


def test_notes_are_taken_once_per_article():
    provider = voice.VoiceProvider(Scripted(NOTES, SUMMARY))
    ask(provider, quick_read_messages(VOLVO))
    ask(provider, quick_read_messages(VOLVO))
    assert len(provider._provider.calls) == 3


def test_the_writer_gets_the_pipeline_rules_the_style_rules_and_the_desk_articles():
    inner = Scripted(NOTES, SUMMARY)
    ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    system = inner.calls[1]["messages"][0]["content"]
    assert system.startswith("You write quick read summaries")
    assert style.RULES in system
    assert voice.DESK_START in system
    assert "Kalmar has delivered" in system


def test_the_writer_runs_at_the_voice_temperature():
    inner = Scripted(NOTES, SUMMARY)
    ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO), temperature=0.3)
    assert inner.calls[1]["temperature"] == voice.TEMPERATURE


def test_a_request_that_is_not_a_quick_read_passes_through_untouched():
    inner = Scripted(SUMMARY)
    messages = [{"role": "user", "content": "Say hello."}]
    ask(voice.VoiceProvider(inner), messages, temperature=0.4)
    assert inner.calls == [{"messages": messages, "temperature": 0.4}]


# A second request when the first answer reads as machine copy or borrows a name.


def test_a_clean_answer_is_written_once():
    inner = Scripted(NOTES, SUMMARY)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == SUMMARY
    assert len(inner.calls) == 2


def test_a_style_problem_is_named_and_asked_for_again():
    inner = Scripted(NOTES, STIFF, SUMMARY)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == SUMMARY
    retry = inner.calls[2]["messages"]
    assert retry[-2] == {"role": "assistant", "content": STIFF}
    assert 'a sentence opens with "The Volvo EC220 is"' in retry[-1]["content"]


def test_a_name_borrowed_from_a_desk_article_is_asked_for_again():
    inner = Scripted(NOTES, BORROWED, SUMMARY)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == SUMMARY
    assert "Damietta" in inner.calls[2]["messages"][-1]["content"]


def test_every_call_is_paid_for():
    inner = Scripted(NOTES, BORROWED, SUMMARY)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert round(completion.cost_usd, 6) == 0.0003
    assert completion.input_tokens == 300


def test_a_name_the_article_itself_uses_is_not_borrowed():
    kalmar = corpus_article("kalmar-delivers-five", "en")
    reply = "Kalmar has handed five machines to Damietta Container and Cargo Handling Company."
    inner = Scripted(NOTES, reply)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(kalmar))
    assert completion.text == reply
    assert len(inner.calls) == 2


def test_when_both_answers_have_problems_the_one_with_fewer_is_kept():
    worse = "The Volvo EC220 is an excavator for Kalmar and Damietta."
    inner = Scripted(NOTES, BORROWED, worse)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == BORROWED


def test_an_outage_on_the_second_try_keeps_the_first_answer():
    inner = Scripted(NOTES, BORROWED, fail_on=3)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == BORROWED
    # The failed call may still have been billed.
    assert not completion.cost_known


def test_closing_closes_the_wrapped_provider():
    inner = Scripted(SUMMARY)
    asyncio.run(voice.VoiceProvider(inner).aclose())
    assert inner.closed


def test_a_whole_quick_read_still_passes_the_pipeline_checks():
    client = logic.PastedClient({"en": VOLVO}, {"en": ""})
    inner = Scripted(NOTES, SUMMARY)
    outcomes = asyncio.run(logic.run_quick_reads(
        0, ["en"], client,
        provider_factory=lambda: voice.VoiceProvider(inner), model="test-model",
    ))
    assert outcomes[0].result.text == SUMMARY
    assert not outcomes[0].result.checks.hard
