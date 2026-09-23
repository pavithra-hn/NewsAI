"""Headless runs of the real page script. A stub stands in for the model."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app.providers.base import Completion, ProviderError
from demo import logic
from tests.test_logic import ARABIC, CORPUS, ENGLISH, FRENCH

APP = str(Path(__file__).resolve().parents[1] / "demo" / "streamlit_app.py")

REPLIES = {
    "English": "Volvo delivered twelve EC220 excavators to an Omani quarry operator.",
    "French": "Volvo a livré douze pelles EC220 à un exploitant de carrière à Oman.",
    "Arabic": "سلمت فولفو اثنتي عشرة حفارة EC220 إلى مشغل محجر في عمان.",
}


class Stub:
    """Answers in whichever language the prompt asks for, and keeps the prompts."""

    def __init__(self, fail=None):
        self.fail = fail
        self.calls = 0
        self.prompts = []

    def __call__(self):
        return self

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=400):
        self.calls += 1
        self.prompts.append("\n".join(m["content"] for m in messages))
        if self.fail is not None:
            raise self.fail
        language = next(name for name in REPLIES if f"Write in {name}" in messages[0]["content"])
        return Completion(
            text=REPLIES[language], input_tokens=100, output_tokens=20,
            finish_reason="stop", model=model, cost_usd=0.0001, cost_known=True,
        )

    async def aclose(self):
        pass


@pytest.fixture
def stub(monkeypatch, tmp_path):
    # A developer's .env must not leak into these runs.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEMO_DAILY_LIMIT", raising=False)
    st.cache_resource.clear()

    provider = Stub()
    monkeypatch.setattr(logic, "make_provider", provider)
    monkeypatch.setattr(logic, "provider_ready", lambda: True)
    return provider


def start():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    return at


def page_text(at):
    parts = []
    for kind in ("markdown", "caption", "success", "warning", "error", "info", "subheader"):
        parts.extend(str(element.value) for element in getattr(at, kind))
    return "\n".join(parts)


def no_crash(at):
    assert not at.exception, [e.value for e in at.exception]


def paste(at, body="", title=""):
    at.text_input(key="paste_title").input(title)
    at.text_area(key="paste_body").input(body)
    at.button(key="paste_go").click().run()
    return at


# Opening the page.


def test_the_page_opens_straight_away_with_no_password(stub):
    at = start()

    no_crash(at)
    assert [tab.label for tab in at.tabs] == ["Paste article", "Sample articles"]
    assert [t.key for t in at.text_input] == ["paste_title"]


def test_the_headline_is_quick_read_in_all_three_languages(stub):
    text = page_text(start())
    for name in ("Quick read", "Lecture rapide", "قراءة سريعة"):
        assert name in text


def test_the_page_carries_no_internal_notices(stub):
    commit = (Path(APP).parents[1] / "PIPELINE_VERSION").read_text().split()[0]
    text = page_text(start())
    assert "Not yet connected" not in text
    assert "Pipeline version" not in text
    assert commit[:7] not in text


def test_an_invalid_daily_limit_means_not_configured(stub, monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_LIMIT", "lots")
    at = start()

    no_crash(at)
    assert any("not configured" in e.value.lower() for e in at.error)
    assert len(at.tabs) == 0


def test_a_missing_provider_key_means_not_configured(stub, monkeypatch):
    monkeypatch.setattr(logic, "provider_ready", lambda: False)
    at = start()

    no_crash(at)
    assert any("not configured" in e.value.lower() for e in at.error)
    assert len(at.tabs) == 0


def test_both_buttons_say_quick_read_like_the_real_product(stub):
    at = start()
    assert at.button(key="paste_go").label == "Quick read"
    assert at.button(key="sample_go").label == "Quick read"


# Paste tab: one article, a title if you have one, one quick read back.


def test_the_paste_tab_has_one_title_and_one_content_box(stub):
    at = start()
    assert at.text_input(key="paste_title").label == "Title"
    assert at.text_area(key="paste_body").label == "Content"


def test_an_english_article_gets_only_an_english_quick_read(stub):
    at = paste(start(), body=ENGLISH)

    no_crash(at)
    text = page_text(at)
    assert REPLIES["English"] in text
    assert REPLIES["French"] not in text and REPLIES["Arabic"] not in text
    assert stub.calls == 1


def test_the_language_is_detected_from_the_content(stub):
    at = paste(start(), body=FRENCH)

    no_crash(at)
    assert REPLIES["French"] in page_text(at)
    assert "Write in French" in stub.prompts[0]


def test_an_arabic_quick_read_is_right_to_left(stub):
    at = paste(start(), body=ARABIC)

    no_crash(at)
    assert any('dir="rtl"' in m.value and REPLIES["Arabic"] in m.value for m in at.markdown)


def test_the_title_is_given_to_the_model(stub):
    paste(start(), body=ENGLISH, title="Volvo delivers twelve excavators to Oman")
    assert "Volvo delivers twelve excavators to Oman" in stub.prompts[0]


def test_the_title_is_optional(stub):
    at = paste(start(), body=ENGLISH, title="")

    no_crash(at)
    assert REPLIES["English"] in page_text(at)


def test_the_article_and_the_quick_read_are_labelled_apart(stub):
    text = page_text(paste(start(), body=ENGLISH, title="Volvo in Oman"))
    assert "Your article" in text
    assert "Volvo in Oman" in text
    assert 'class="qr' in text


def test_each_quick_read_shows_its_length_and_time(stub):
    text = page_text(paste(start(), body=ENGLISH))
    assert "words" in text and "seconds" in text


def test_there_is_no_cost_or_figures_plate(stub):
    text = page_text(paste(start(), body=ENGLISH))
    assert "$0.000100" not in text
    assert "Kept exactly" not in text
    assert 'class="plate' not in text


def test_there_is_no_checking_panel_to_confuse_a_reader(stub):
    at = paste(start(), body=ENGLISH)
    assert len(at.expander) == 0


def test_an_empty_box_asks_for_an_article(stub):
    at = paste(start(), body="")

    no_crash(at)
    assert "Paste an article" in page_text(at)
    assert stub.calls == 0


def test_a_short_article_is_refused(stub):
    at = paste(start(), body="Too short to be an article at all, ten words.")

    no_crash(at)
    assert "Too short to summarise" in page_text(at)
    assert stub.calls == 0


def test_text_with_no_clear_language_is_refused(stub):
    at = paste(start(), body=" ".join(["2026"] * 60))

    no_crash(at)
    assert "language" in page_text(at).lower()
    assert stub.calls == 0


# Sample tab: pick an article and a language, read it, then summarise it.


def test_choosing_a_sample_shows_its_title_and_content_straight_away(stub):
    at = start()
    at.selectbox(key="sample_article").select(0)
    at.radio(key="sample_lang").set_value("English").run()

    no_crash(at)
    text = page_text(at)
    article = CORPUS[0]["locales"]["en"]
    assert article["title"] in text
    assert "Manitou" in text
    assert stub.calls == 0


def test_switching_the_sample_language_shows_that_version(stub):
    at = start()
    at.selectbox(key="sample_article").select(0)
    at.radio(key="sample_lang").set_value("العربية").run()

    no_crash(at)
    assert CORPUS[0]["locales"]["ar"]["title"] in page_text(at)


def test_a_sample_quick_read_is_one_language(stub):
    at = start()
    at.selectbox(key="sample_article").select(11)
    at.radio(key="sample_lang").set_value("English").run()
    at.button(key="sample_go").click().run()

    no_crash(at)
    text = page_text(at)
    assert REPLIES["English"] in text
    assert REPLIES["French"] not in text
    assert stub.calls == 1


# Things going wrong, in front of an audience.


def test_a_provider_outage_is_a_polite_message(stub):
    stub.fail = ProviderError("gave up after 3 attempts: 503 from the provider")
    at = paste(start(), body=ENGLISH)

    no_crash(at)
    text = page_text(at)
    assert "The AI service did not respond, please try again." in text
    assert "503" not in text


def test_an_unexpected_error_is_not_a_traceback(stub):
    stub.fail = RuntimeError("something internal")
    at = paste(start(), body=ENGLISH)

    no_crash(at)
    text = page_text(at)
    assert "Something went wrong" in text
    assert "something internal" not in text


def test_the_daily_limit_is_polite_and_spends_nothing(stub, monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_LIMIT", "1")
    at = paste(start(), body=ENGLISH)
    at.button(key="paste_go").click().run()

    no_crash(at)
    assert "daily limit" in page_text(at).lower()
    assert stub.calls == 1


def test_model_output_is_escaped_not_rendered_as_html(stub):
    before = dict(REPLIES)
    REPLIES["English"] = "Volvo <script>alert(1)</script> delivered twelve excavators."
    try:
        at = paste(start(), body=ENGLISH)
        assert not any("<script>" in m.value for m in at.markdown)
        assert any("&lt;script&gt;" in m.value for m in at.markdown)
    finally:
        REPLIES.clear()
        REPLIES.update(before)


def test_a_pasted_title_is_escaped_too(stub):
    at = paste(start(), body=ENGLISH, title="<b>Bold</b> headline")
    assert not any("<b>Bold</b>" in m.value for m in at.markdown)
