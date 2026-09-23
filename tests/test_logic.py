import asyncio
import json
import threading
from datetime import date
from pathlib import Path

import pytest

from app.providers.base import Completion, ProviderError
from demo import logic

CORPUS = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "corpus.json").read_text(encoding="utf-8")
)

ENGLISH = (
    "Volvo Construction Equipment has delivered twelve EC220 excavators to a quarry "
    "operator in Oman. The machines will work on the new limestone site near Sohar, "
    "and the company says the fleet will help the operator double its output this year. "
    "Service and spare parts will be handled by the local dealer from its Muscat branch."
)
FRENCH = (
    "Volvo Construction Equipment a livré douze pelles EC220 à un exploitant de carrière "
    "à Oman. Les machines travailleront sur le nouveau site de calcaire près de Sohar, et "
    "la société indique que cette flotte aidera l'exploitant à doubler sa production cette "
    "année. Le service et les pièces seront assurés par le concessionnaire local."
)
ARABIC = (
    "سلمت شركة Volvo Construction Equipment اثنتي عشرة حفارة من طراز EC220 إلى مشغل "
    "محجر في سلطنة عمان. وستعمل الآلات في موقع الحجر الجيري الجديد بالقرب من صحار، "
    "وتقول الشركة إن هذا الأسطول سيساعد المشغل على مضاعفة إنتاجه هذا العام. وسيتولى "
    "الوكيل المحلي خدمات الصيانة وقطع الغيار من فرعه في مسقط."
)


def words(n, word="word"):
    return " ".join([word] * n)


# Language detection. The box fixes the language, and this guard stops the
# demo from summarising one language's text as another, which is translation.


@pytest.mark.parametrize(
    "text,expected", [(ENGLISH, "en"), (FRENCH, "fr"), (ARABIC, "ar")]
)
def test_detects_each_language(text, expected):
    assert logic.detect_language(text) == expected


@pytest.mark.parametrize("locale", ["en", "ar", "fr"])
def test_detects_every_corpus_article_correctly(locale):
    wrong = [
        (i + 1, logic.detect_language(a["locales"][locale]["body_html"]))
        for i, a in enumerate(CORPUS)
        if logic.detect_language(a["locales"][locale]["body_html"]) != locale
    ]
    assert wrong == []


def test_arabic_with_latin_brand_names_is_still_arabic():
    """Brand names and model codes stay in Latin script inside Arabic articles."""
    assert "Volvo Construction Equipment" in ARABIC
    assert logic.detect_language(ARABIC) == "ar"


def test_english_quoting_a_french_phrase_is_still_english():
    text = ENGLISH + " The event was billed as a salon de la construction."
    assert logic.detect_language(text) == "en"


def test_html_is_read_as_its_text_not_its_tags():
    html = "".join(f"<p><span style='x'>{s}.</span></p>" for s in FRENCH.split(". "))
    assert logic.detect_language(html) == "fr"


def test_text_with_too_few_letters_is_undetermined():
    assert logic.detect_language("2024 2025 4.6 930 12") is None


# The per-box checks. One bad box never blocks the others, so each box is
# judged on its own.


def test_an_empty_box_is_skipped_silently():
    check = logic.check_box("   ", "en")
    assert check.ok is False
    assert check.reason == "empty"


def test_a_ten_word_box_is_too_short():
    check = logic.check_box(words(10), "en")
    assert (check.ok, check.reason) == (False, "too_short")
    assert "too short to summarise" in check.message.lower()


@pytest.mark.parametrize("n,ok", [(39, False), (40, True)])
def test_the_minimum_is_forty_words(n, ok):
    text = " ".join(ENGLISH.split() * 3)[: 10**6]
    text = " ".join(text.split()[:n])
    assert logic.check_box(text, "en").ok is ok


@pytest.mark.parametrize("n,ok", [(2000, True), (2001, False)])
def test_the_maximum_is_two_thousand_words(n, ok):
    text = " ".join((ENGLISH.split() * 100)[:n])
    check = logic.check_box(text, "en")
    assert check.ok is ok
    if not ok:
        assert check.reason == "too_long"


def test_words_are_counted_after_cleaning():
    """Markup is not words. 45 words wrapped in heavy HTML is still 45."""
    html = "".join(f"<p style='a b c d e f'>{w}</p>" for w in ENGLISH.split()[:45])
    assert logic.check_box(html, "en").words == 45


@pytest.mark.parametrize(
    "text,box",
    [(ARABIC, "en"), (ENGLISH, "fr"), (FRENCH, "en"), (ENGLISH, "ar")],
)
def test_text_in_the_wrong_box_is_not_run(text, box):
    check = logic.check_box(text, box)
    assert (check.ok, check.reason) == (False, "language_mismatch")
    assert "does not translate" in check.message


def test_matching_text_passes_every_check():
    for text, box in ((ENGLISH, "en"), (FRENCH, "fr"), (ARABIC, "ar")):
        assert logic.check_box(text, box).ok is True


# The pasted-text client lets handle() run unchanged.


def test_the_pasted_client_serves_the_text_for_that_box():
    client = logic.PastedClient({"en": ENGLISH, "fr": FRENCH})
    article = asyncio.run(client.fetch_article(0, "fr"))
    assert article.body_html == FRENCH
    assert article.locale == "fr"


# Running. A stub provider stands in for the model so nothing is spent.


class StubProvider:
    def __init__(self, text="A short summary of the article.", *, fail=False, barrier=None):
        self.text = text
        self.fail = fail
        self.barrier = barrier
        self.calls = 0
        self.closed = False

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=400):
        self.calls += 1
        if self.barrier is not None:
            await asyncio.wait_for(self.barrier.wait(), timeout=2)
        if self.fail:
            raise ProviderError("gave up after 3 attempts: 503 from the provider")
        text = self.text[model] if isinstance(self.text, dict) else self.text
        return Completion(
            text=text, input_tokens=100, output_tokens=20, finish_reason="stop",
            model=model, cost_usd=0.0001, cost_known=True,
        )

    async def aclose(self):
        self.closed = True


SUMMARIES = {
    "en": "Volvo delivered twelve EC220 excavators to an Omani quarry operator.",
    "fr": "Volvo a livré douze pelles EC220 à un exploitant de carrière à Oman.",
    "ar": "سلمت فولفو اثنتي عشرة حفارة EC220 إلى مشغل محجر في عمان.",
}


def run(locales, provider, texts=None):
    client = logic.PastedClient(texts or {"en": ENGLISH, "fr": FRENCH, "ar": ARABIC})
    return asyncio.run(logic.run_quick_reads(0, locales, client, lambda: provider))


def test_runs_return_one_outcome_per_locale_in_order():
    outcomes = run(["en", "fr"], StubProvider(SUMMARIES["en"]))
    assert [o.locale for o in outcomes] == ["en", "fr"]


def test_the_languages_run_concurrently():
    """Three calls must be in flight together. Run one at a time, the barrier
    would never fill and the stub would time out."""

    class Barrier:
        def __init__(self, n):
            self.n, self.count, self.event = n, 0, None

        async def wait(self):
            self.event = self.event or asyncio.Event()
            self.count += 1
            if self.count >= self.n:
                self.event.set()
            await self.event.wait()

    provider = StubProvider(SUMMARIES["en"], barrier=Barrier(3))
    outcomes = run(["en", "fr", "ar"], provider)
    assert len(outcomes) == 3
    assert all(o.error is None for o in outcomes)


def test_the_provider_is_closed_after_the_run():
    provider = StubProvider(SUMMARIES["en"])
    run(["en"], provider)
    assert provider.closed is True


def test_a_provider_outage_is_a_plain_message_not_an_exception(caplog):
    outcomes = run(["en"], StubProvider(fail=True))
    label, reasons = logic.status_for(outcomes[0])
    assert label == "Blocked"
    assert reasons == ["The AI service did not respond, please try again."]
    # The real error goes to the console log, not to the page.
    assert "503" in caplog.text


def test_an_unexpected_error_in_one_run_does_not_stop_the_others(monkeypatch):
    class Broken(logic.PastedClient):
        async def fetch_article(self, article_id, locale):
            if locale == "fr":
                raise RuntimeError("boom")
            return await super().fetch_article(article_id, locale)

    client = Broken({"en": ENGLISH, "fr": FRENCH})
    outcomes = asyncio.run(
        logic.run_quick_reads(0, ["en", "fr"], client, lambda: StubProvider(SUMMARIES["en"]))
    )
    en, fr = outcomes
    assert en.error is None and en.result is not None
    assert fr.result is None and fr.error
    assert "boom" not in fr.error


def test_an_outcome_carries_the_cleaned_source_and_protected_terms():
    outcome = run(["en"], StubProvider(SUMMARIES["en"]))[0]
    assert outcome.cleaned_source.startswith("Volvo Construction Equipment")
    assert "EC220" in outcome.protected.model_codes
    assert outcome.seconds >= 0


# Status in plain English.


def test_a_clean_result_is_delivered():
    outcome = run(["en"], StubProvider(SUMMARIES["en"]))[0]
    assert logic.status_for(outcome) == ("Delivered", [])


def test_a_soft_warning_suggests_review():
    outcome = run(["en"], StubProvider("Volvo delivered 99 excavators to Oman."))[0]
    label, reasons = logic.status_for(outcome)
    assert label == "Delivered, review suggested"
    assert any("99" in r and "does not appear in the article" in r for r in reasons)


def test_a_hard_failure_is_blocked_with_a_reason():
    outcome = run(["en"], StubProvider(SUMMARIES["ar"]))[0]
    label, reasons = logic.status_for(outcome)
    assert label == "Blocked"
    assert "wrong language" in reasons[0]


def test_cost_is_unknown_for_an_unpriced_model():
    class Unpriced(StubProvider):
        async def complete(self, *a, **k):
            from dataclasses import replace

            return replace(await super().complete(*a, **k), cost_known=False, cost_usd=0.0)

    outcome = run(["en"], Unpriced(SUMMARIES["en"]))[0]
    assert logic.format_cost(outcome.result) == "unknown"


def test_known_cost_is_a_dollar_figure():
    outcome = run(["en"], StubProvider(SUMMARIES["en"]))[0]
    assert logic.format_cost(outcome.result).startswith("$")


# The daily limit, shared by every session.


def test_the_counter_allows_runs_up_to_the_limit():
    counter = logic.UsageCounter(limit=3)
    assert counter.try_consume(2) is True
    assert counter.remaining() == 1
    assert counter.try_consume(1) is True
    assert counter.try_consume(1) is False


def test_a_request_bigger_than_what_is_left_is_refused_whole():
    counter = logic.UsageCounter(limit=2)
    assert counter.try_consume(3) is False
    assert counter.remaining() == 2


def test_the_counter_resets_on_a_new_day():
    today = [date(2026, 9, 23)]
    counter = logic.UsageCounter(limit=1, today=lambda: today[0])
    assert counter.try_consume(1) is True
    assert counter.try_consume(1) is False
    today[0] = date(2026, 9, 24)
    assert counter.try_consume(1) is True


def test_the_counter_is_safe_across_threads():
    """Streamlit serves each session on its own thread."""
    counter = logic.UsageCounter(limit=100)
    granted = []

    def worker():
        for _ in range(50):
            granted.append(counter.try_consume(1))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert granted.count(True) == 100
    assert counter.remaining() == 0


# Configuration.


def test_the_daily_limit_defaults_to_200():
    assert logic.daily_limit({}, {}) == 200


def test_the_daily_limit_is_read_from_the_environment():
    assert logic.daily_limit({"DEMO_DAILY_LIMIT": "15"}, {}) == 15


@pytest.mark.parametrize("value", ["abc", "0", "-5", "2.5"])
def test_an_invalid_daily_limit_is_refused(value):
    with pytest.raises(ValueError):
        logic.daily_limit({"DEMO_DAILY_LIMIT": value}, {})


# Samples.


def test_the_samples_are_the_25_vendored_articles():
    titles = logic.sample_titles()
    assert len(titles) == 25
    assert titles[0].startswith("HD Construction Equipment")


# The two checks added with the length tiers and hedges. The manager must see
# a sentence, never a raw code.


def _flagged(code, detail):
    from app.actions.quick_read import QuickRead
    from app.pipeline.quality import CheckReport, SoftWarning

    result = QuickRead(
        article_id=0, locale="en", text="A summary.",
        checks=CheckReport(soft=(SoftWarning(code, detail),)),
        deliverable=True, needs_review=True,
    )
    return logic.status_for(logic.RunOutcome("en", result, 1.0))


def test_a_dropped_hedge_is_explained_in_plain_english():
    label, reasons = _flagged("hedge_dropped", "70,000")
    assert label == "Delivered, review suggested"
    assert "70,000" in reasons[0]
    assert "approximate" in reasons[0]
    assert "hedge_dropped" not in reasons[0]


def test_an_over_long_summary_is_explained_in_plain_english():
    _label, reasons = _flagged("over_length", "73 words, short target up to 60")
    assert "73 words" in reasons[0]
    assert "Longer than intended" in reasons[0]
    assert "over_length" not in reasons[0]


# One pasted article: its language is detected, not chosen.


@pytest.mark.parametrize("text,expected", [(ENGLISH, "en"), (FRENCH, "fr"), (ARABIC, "ar")])
def test_a_pasted_article_is_checked_in_its_detected_language(text, expected):
    check = logic.check_paste(text)
    assert check.ok and check.locale == expected


def test_an_empty_paste_is_reported_as_empty():
    check = logic.check_paste("   ")
    assert not check.ok and check.reason == "empty"


def test_a_short_paste_is_too_short():
    check = logic.check_paste("Volvo delivered ten excavators in Dubai today.")
    assert not check.ok and check.reason == "too_short"
    assert "Too short to summarise" in check.message


def test_a_paste_with_no_clear_language_is_refused():
    check = logic.check_paste(" ".join(["2026"] * 60))
    assert not check.ok and check.reason == "no_language"
    assert "language" in check.message.lower()


def test_the_pasted_client_carries_an_optional_title():
    client = logic.PastedClient({"en": ENGLISH}, titles={"en": "Volvo in Oman"})
    assert asyncio.run(client.fetch_article(0, "en")).title == "Volvo in Oman"
    untitled = logic.PastedClient({"en": ENGLISH})
    assert asyncio.run(untitled.fetch_article(0, "en")).title is None


def test_an_article_is_split_into_its_paragraphs_for_reading():
    body = "<p>First <b>paragraph</b>.</p><p>&nbsp;</p><p>Second&nbsp;one.</p>"
    assert logic.paragraphs(body) == ["First paragraph .", "Second one."]
