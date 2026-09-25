import asyncio
import json

from app.pipeline.clean import clean
from app.pipeline.prompts import build_prompt
from app.pipeline.protect import protect
from app.providers.base import Completion, ProviderError
from demo import logic, voice

VOLVO = (
    "Volvo Construction Equipment has delivered twelve EC220 excavators to a contractor in "
    "Oman. The machines will work on a highway project near Muscat, the company said. "
    "Deliveries were completed in September, and the contractor has an option on six more."
)
SUMMARY = "Volvo CE has delivered twelve EC220 excavators to an Omani contractor for a highway job."
BORROWED = "Volvo CE has delivered twelve EC220 excavators to Damietta for a highway job."


def corpus_article(slug: str, locale: str) -> str:
    items = json.loads(logic.CORPUS_PATH.read_text(encoding="utf-8"))
    item = next(item for item in items if slug in item["href"])
    return clean(item["locales"][locale]["body_html"])


def quick_read_messages(text: str, locale: str = "en") -> list[dict]:
    return build_prompt(None, text, locale, protect(text, locale), {})


class Scripted:
    """Answers with the given replies in turn and keeps what it was asked."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.closed = False

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=400):
        self.calls.append({"messages": messages, "temperature": temperature})
        text = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return Completion(
            text=text, input_tokens=100, output_tokens=20, finish_reason="stop",
            model=model, cost_usd=0.0001, cost_known=True,
        )

    async def aclose(self):
        self.closed = True


def ask(provider, messages, temperature=0.3):
    return asyncio.run(provider.complete(messages, model="test-model", temperature=temperature))


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


# The wrapper around the pipeline's provider.


def test_every_request_carries_the_desk_articles():
    inner = Scripted(SUMMARY)
    ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    system = inner.calls[0]["messages"][0]["content"]
    assert system.startswith("You write quick read summaries")
    assert voice.DESK_START in system
    assert "Kalmar has delivered" in system


def test_the_article_itself_is_passed_on_untouched():
    messages = quick_read_messages(VOLVO)
    inner = Scripted(SUMMARY)
    ask(voice.VoiceProvider(inner), messages)
    assert inner.calls[0]["messages"][1:] == messages[1:]


def test_every_request_runs_at_the_voice_temperature():
    inner = Scripted(SUMMARY)
    ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO), temperature=0.3)
    assert inner.calls[0]["temperature"] == voice.TEMPERATURE


def test_a_clean_answer_is_asked_for_once():
    inner = Scripted(SUMMARY)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == SUMMARY
    assert len(inner.calls) == 1


def test_a_name_borrowed_from_a_desk_article_is_asked_again():
    inner = Scripted(BORROWED, SUMMARY)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == SUMMARY
    assert len(inner.calls) == 2


def test_both_answers_are_paid_for():
    inner = Scripted(BORROWED, SUMMARY)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.cost_usd == 0.0002
    assert completion.input_tokens == 200


def test_a_name_the_article_itself_uses_is_not_borrowed():
    kalmar = corpus_article("kalmar-delivers-five", "en")
    reply = "Kalmar has handed five machines to Damietta Container and Cargo Handling Company."
    inner = Scripted(reply)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(kalmar))
    assert completion.text == reply
    assert len(inner.calls) == 1


def test_when_both_answers_borrow_the_one_that_borrows_less_is_kept():
    worse = "Kalmar and Volvo CE delivered twelve EC220 excavators to Damietta."
    inner = Scripted(worse, BORROWED)
    completion = ask(voice.VoiceProvider(inner), quick_read_messages(VOLVO))
    assert completion.text == BORROWED


def test_an_outage_on_the_second_try_keeps_the_first_answer():
    class FailsSecond(Scripted):
        async def complete(self, messages, **kwargs):
            if self.calls:
                raise ProviderError("gave up after 3 attempts: 503 from the provider")
            return await super().complete(messages, **kwargs)

    completion = ask(voice.VoiceProvider(FailsSecond(BORROWED)), quick_read_messages(VOLVO))
    assert completion.text == BORROWED
    # The failed call may still have been billed.
    assert not completion.cost_known


def test_closing_closes_the_wrapped_provider():
    inner = Scripted(SUMMARY)
    asyncio.run(voice.VoiceProvider(inner).aclose())
    assert inner.closed


def test_a_whole_quick_read_still_passes_the_pipeline_checks():
    client = logic.PastedClient({"en": VOLVO}, {"en": ""})
    inner = Scripted(SUMMARY)
    outcomes = asyncio.run(logic.run_quick_reads(
        0, ["en"], client,
        provider_factory=lambda: voice.VoiceProvider(inner), model="test-model",
    ))
    assert outcomes[0].result.text == SUMMARY
    assert not outcomes[0].result.checks.hard
