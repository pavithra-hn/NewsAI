"""Headless runs of the real page script. A stub stands in for the model."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app.providers.base import Completion, ProviderError
from demo import logic
from tests.test_logic import ARABIC, ENGLISH, FRENCH

APP = str(Path(__file__).resolve().parents[1] / "demo" / "streamlit_app.py")
PASSWORD = "correct horse"

REPLIES = {
    "English": "Volvo delivered twelve EC220 excavators to an Omani quarry operator.",
    "French": "Volvo a livré douze pelles EC220 à un exploitant de carrière à Oman.",
    "Arabic": "سلمت فولفو اثنتي عشرة حفارة EC220 إلى مشغل محجر في عمان.",
}


class Stub:
    """Answers in whichever language the prompt asks for."""

    def __init__(self, fail=None):
        self.fail = fail
        self.calls = 0

    def __call__(self):
        return self

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=400):
        self.calls += 1
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
    for name in ("DEMO_PASSWORD", "DEMO_DAILY_LIMIT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEMO_PASSWORD", PASSWORD)
    st.cache_resource.clear()

    provider = Stub()
    monkeypatch.setattr(logic, "make_provider", provider)
    monkeypatch.setattr(logic, "provider_ready", lambda: True)
    return provider


def start():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    return at


def signed_in():
    at = start()
    at.text_input(key="password").input(PASSWORD).run()
    return at


def page_text(at):
    parts = []
    for kind in ("markdown", "caption", "success", "warning", "error", "info", "subheader"):
        parts.extend(str(element.value) for element in getattr(at, kind))
    return "\n".join(parts)


def no_crash(at):
    assert not at.exception, [e.value for e in at.exception]


# The gate.


def test_an_unset_password_shows_not_configured_and_nothing_else(stub, monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD")
    at = start()

    no_crash(at)
    assert any("not configured" in e.value.lower() for e in at.error)
    assert len(at.text_input) == 0
    assert len(at.tabs) == 0


def test_nothing_renders_before_the_password(stub):
    at = start()

    no_crash(at)
    assert len(at.text_input) == 1
    assert len(at.tabs) == 0
    assert "Not yet connected" not in page_text(at)


def test_a_wrong_password_is_refused(stub):
    at = start()
    at.text_input(key="password").input("wrong").run()

    no_crash(at)
    assert any("incorrect password" in e.value.lower() for e in at.error)
    assert len(at.tabs) == 0


def test_the_right_password_opens_the_page(stub):
    at = signed_in()

    no_crash(at)
    assert [tab.label for tab in at.tabs] == ["Paste article", "Sample articles"]
    assert "Demo. Not yet connected to MakinatyNews." in page_text(at)


def test_an_invalid_daily_limit_means_not_configured(stub, monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_LIMIT", "lots")
    at = start()

    no_crash(at)
    assert any("not configured" in e.value.lower() for e in at.error)
    assert len(at.tabs) == 0


def test_a_missing_provider_key_means_not_configured(stub, monkeypatch):
    monkeypatch.setattr(logic, "provider_ready", lambda: False)
    at = signed_in()

    no_crash(at)
    assert any("not configured" in e.value.lower() for e in at.error)
    assert len(at.tabs) == 0


# Paste tab.


def paste(at, **texts):
    for locale, text in texts.items():
        at.text_area(key=f"paste_{locale}").input(text)
    at.button(key="paste_go").click().run()
    return at


def test_three_boxes_run_together(stub):
    at = paste(signed_in(), en=ENGLISH, ar=ARABIC, fr=FRENCH)

    no_crash(at)
    text = page_text(at)
    for reply in REPLIES.values():
        assert reply in text
    assert text.count("Delivered") >= 3
    assert stub.calls == 3


def test_the_arabic_quick_read_is_right_to_left(stub):
    at = paste(signed_in(), ar=ARABIC)

    assert any('dir="rtl"' in m.value and REPLIES["Arabic"] in m.value for m in at.markdown)


def test_each_result_shows_words_time_and_cost(stub):
    at = paste(signed_in(), en=ENGLISH)

    captions = " ".join(c.value for c in at.caption)
    assert "words" in captions and "s" in captions and "$0.000100" in captions


def test_empty_boxes_ask_for_an_article(stub):
    at = paste(signed_in())

    no_crash(at)
    assert "Paste an article into at least one box." in page_text(at)
    assert stub.calls == 0


def test_a_short_box_is_refused_without_blocking_the_others(stub):
    at = paste(signed_in(), en="Too short to be an article at all, ten words.", fr=FRENCH)

    no_crash(at)
    text = page_text(at)
    assert "Too short to summarise" in text
    assert REPLIES["French"] in text
    assert stub.calls == 1


def test_arabic_in_the_english_box_is_not_run(stub):
    at = paste(signed_in(), en=ARABIC)

    no_crash(at)
    assert "does not translate" in page_text(at)
    assert stub.calls == 0


# Sample tab.


def test_a_sample_in_all_three_languages(stub):
    at = signed_in()
    at.selectbox(key="sample_article").select(0)
    at.radio(key="sample_lang").set_value("All three")
    at.button(key="sample_go").click().run()

    no_crash(at)
    text = page_text(at)
    for reply in REPLIES.values():
        assert reply in text
    assert stub.calls == 3


def test_a_sample_in_one_language(stub):
    at = signed_in()
    at.selectbox(key="sample_article").select(11)
    at.radio(key="sample_lang").set_value("English")
    at.button(key="sample_go").click().run()

    no_crash(at)
    assert REPLIES["English"] in page_text(at)
    assert stub.calls == 1


# Things going wrong, in front of an audience.


def test_a_provider_outage_is_a_polite_message(stub):
    stub.fail = ProviderError("gave up after 3 attempts: 503 from the provider")
    at = paste(signed_in(), en=ENGLISH)

    no_crash(at)
    text = page_text(at)
    assert "The AI service did not respond, please try again." in text
    assert "503" not in text


def test_an_unexpected_error_is_not_a_traceback(stub):
    stub.fail = RuntimeError("something internal")
    at = paste(signed_in(), en=ENGLISH)

    no_crash(at)
    text = page_text(at)
    assert "Something went wrong" in text
    assert "something internal" not in text


def test_the_daily_limit_is_polite_and_spends_nothing(stub, monkeypatch):
    monkeypatch.setenv("DEMO_DAILY_LIMIT", "2")
    at = paste(signed_in(), en=ENGLISH, ar=ARABIC, fr=FRENCH)

    no_crash(at)
    assert "daily limit" in page_text(at).lower()
    assert stub.calls == 0


def test_model_output_is_escaped_not_rendered_as_html(stub):
    REPLIES_BEFORE = dict(REPLIES)
    REPLIES["English"] = "Volvo <script>alert(1)</script> delivered twelve excavators."
    try:
        at = paste(signed_in(), en=ENGLISH)
        assert not any("<script>" in m.value for m in at.markdown)
        assert any("&lt;script&gt;" in m.value for m in at.markdown)
    finally:
        REPLIES.clear()
        REPLIES.update(REPLIES_BEFORE)


def test_both_buttons_say_quick_read_like_the_real_product(stub):
    at = signed_in()
    assert at.button(key="paste_go").label == "Quick read"
    assert at.button(key="sample_go").label == "Quick read"


def test_the_page_shows_which_pipeline_version_it_runs(stub):
    commit = (Path(APP).parents[1] / "PIPELINE_VERSION").read_text().split()[0]
    at = signed_in()
    assert commit[:7] in page_text(at)
