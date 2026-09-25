import asyncio

import pytest

from app.providers.base import Completion, ProviderError
from demo import humanize

SOURCE = (
    "The Cat 966H is powered by an 11.1 L C11 ACERT engine that delivers 286 hp (213 kW). "
    "It weighs 23,125 kg and was built from 2011–2012.\n"
    "• Tires: 26.5R25\n"
    "• Rivals: Komatsu WA380-8 and Volvo L120H."
)

GOOD = (
    "Cat fitted the 966H with an 11.1 L C11 ACERT engine. It makes 286 hp (213 kW). "
    "The loader weighs 23,125 kg and was built from 2011 to 2012.\n"
    "• It runs on 26.5R25 tires.\n"
    "• Its closest rivals are the Komatsu WA380-8 and the Volvo L120H."
)

NO_213 = GOOD.replace(" (213 kW)", "")


class Scripted:
    """Answers with the given replies in turn and keeps what it was asked."""

    def __init__(self, *replies, finish="stop", fail=None):
        self.replies = list(replies)
        self.finish = finish
        self.fail = fail
        self.calls = []
        self.closed = False

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=400):
        self.calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        if self.fail is not None:
            raise self.fail
        text = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return Completion(
            text=text, input_tokens=300, output_tokens=200, finish_reason=self.finish,
            model=model, cost_usd=0.0002, cost_known=True,
        )

    async def aclose(self):
        self.closed = True


def run(provider, text=SOURCE, locale="en"):
    return asyncio.run(humanize.humanize(text, locale, provider=provider, model="test-model"))


# The prompt.


def test_the_prompt_names_the_language_and_the_rules():
    messages = humanize.build_messages(SOURCE, "fr")
    rules = messages[0]["content"]

    assert "Write in French" in rules
    assert "every number" in rules.lower()
    assert "dash" in rules.lower()
    assert "same sections" in rules.lower()
    assert SOURCE in messages[1]["content"]
    assert SOURCE not in rules


def test_a_correction_names_what_went_missing():
    messages = humanize.build_messages(SOURCE, "en", correction=["213", "WA380"])

    assert "213" in messages[-1]["content"]
    assert "WA380" in messages[-1]["content"]


# The checks.


def test_a_rewrite_that_keeps_every_figure_and_name_has_no_problems():
    check = humanize.check(SOURCE, GOOD, "en")

    assert check.facts_ok
    assert check.problems == []


def test_a_dropped_figure_is_named():
    check = humanize.check(SOURCE, NO_213, "en")

    assert check.missing_figures == ("213",)
    assert not check.facts_ok
    assert any("213" in problem for problem in check.problems)


def test_an_invented_figure_is_named():
    check = humanize.check(SOURCE, GOOD + " It sold 4,000 units.", "en")

    assert check.invented_figures == ("4000",)


def test_a_dropped_model_name_is_named():
    check = humanize.check(SOURCE, GOOD.replace("WA380-8", "WA-series"), "en")

    assert "WA380" in check.missing_codes


def test_figures_are_listed_once_and_without_stray_punctuation():
    check = humanize.check("Built in 2011, 2012 and 2012.", "Built then.", "en")

    assert check.missing_figures == ("2011", "2012")


def test_dashes_are_counted():
    check = humanize.check(SOURCE, GOOD + " Strong — and fast – always.", "en")

    assert check.dashes == 2


def test_ai_style_words_are_listed():
    check = humanize.check(SOURCE, GOOD + " Furthermore, it ensures seamless loading.", "en")

    assert {"furthermore", "ensures", "seamless"} <= set(check.stock)


def test_a_rewrite_much_shorter_than_the_original_is_flagged():
    check = humanize.check(SOURCE * 3, GOOD, "en")

    assert not check.length_ok
    assert any("shorter" in problem for problem in check.problems)


def test_a_rewrite_in_another_language_is_flagged():
    french = (
        "Le 966H de Cat est équipé d'un moteur C11 ACERT de 11.1 L qui développe 286 hp (213 kW). "
        "Il pèse 23,125 kg et a été construit de 2011 à 2012. Pneus 26.5R25. "
        "Ses concurrents sont la Komatsu WA380-8 et la Volvo L120H."
    )
    check = humanize.check(SOURCE, french, "en")

    assert not check.language_ok
    assert any("English" in problem for problem in check.problems)


def test_an_answer_cut_off_by_the_token_limit_is_flagged():
    check = humanize.check(SOURCE, GOOD, "en", finish_reason="length")

    assert check.cut_off
    assert any("stopped before" in problem for problem in check.problems)


# Running.


def test_a_good_first_answer_is_not_retried():
    provider = Scripted(GOOD)

    result = run(provider)

    assert len(provider.calls) == 1
    assert result.attempts == 1
    assert result.text == GOOD
    assert result.check.facts_ok


def test_a_missing_figure_gets_one_retry_that_names_it():
    provider = Scripted(NO_213, GOOD)

    result = run(provider)

    assert len(provider.calls) == 2
    assert "213" in provider.calls[1]["messages"][-1]["content"]
    assert result.attempts == 2
    assert result.text == GOOD


def test_the_better_attempt_is_kept_when_the_retry_is_worse():
    worse = NO_213.replace("286", "about three hundred").replace("23,125", "many")
    provider = Scripted(NO_213, worse)

    result = run(provider)

    assert result.attempts == 2
    assert result.text == NO_213


def test_the_cost_of_every_attempt_is_counted():
    result = run(Scripted(NO_213, GOOD))

    assert result.cost_usd == pytest.approx(0.0004)
    assert result.cost_known


def test_a_provider_outage_gives_a_plain_message_and_no_text():
    result = run(Scripted(fail=ProviderError("503 from the provider")))

    assert result.text == ""
    assert result.error == humanize.PROVIDER_DOWN


def test_the_token_allowance_grows_with_the_text_within_limits():
    short = humanize.max_tokens_for("word " * 50)
    long = humanize.max_tokens_for("word " * 2000)

    assert short >= humanize.MIN_TOKENS
    assert long > short
    assert long <= humanize.MAX_TOKENS


def test_the_run_uses_the_computed_token_allowance():
    provider = Scripted(GOOD)

    run(provider)

    assert provider.calls[0]["max_tokens"] == humanize.max_tokens_for(SOURCE)


def test_run_humanize_opens_and_closes_its_own_provider():
    provider = Scripted(GOOD)

    result = asyncio.run(humanize.run_humanize(SOURCE, "en", lambda: provider, "test-model"))

    assert result.text == GOOD
    assert provider.closed


# Checking the box before anything is spent.


def test_empty_text_asks_for_text():
    assert humanize.check_input("   ").reason == "empty"


def test_text_under_the_minimum_is_refused():
    assert humanize.check_input("Too short to rewrite.").reason == "too_short"


def test_text_over_the_maximum_is_refused():
    assert humanize.check_input("Loader engine hp " * 1000).reason == "too_long"


def test_the_language_is_detected():
    check = humanize.check_input(SOURCE * 3)

    assert check.ok
    assert check.locale == "en"


# Found on the 966H spec sheet: one model dropped every hyphen, and one made a
# comparison stronger than the original.


def test_the_prompt_keeps_hyphens_and_bans_only_long_dashes():
    rules = humanize.build_messages(SOURCE, "en")[0]["content"]

    assert "heavy-duty" in rules
    assert "hyphen" in rules.lower()


def test_the_prompt_keeps_each_claim_as_strong_as_it_is():
    rules = humanize.build_messages(SOURCE, "en")[0]["content"].lower()

    assert "as strong as" in rules


def test_a_rewrite_that_strips_hyphens_from_compound_words_is_flagged():
    source = SOURCE + " It is a heavy-duty, load-sensing, air-conditioned, pre-owned machine."
    output = GOOD + " It is a heavy duty, load sensing, air conditioned, pre owned machine."

    check = humanize.check(source, output, "en")

    assert check.hyphens_lost == 4
    assert any("hyphen" in problem.lower() for problem in check.problems)


def test_model_code_hyphens_do_not_count_as_compound_words():
    check = humanize.check(SOURCE, GOOD, "en")

    assert check.hyphens_lost == 0
