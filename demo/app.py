"""NewsAI quick read demo. The page only; everything it does lives in logic.py.

    streamlit run demo/app.py
"""

import html
import logging
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitAPIException

# Streamlit puts demo/ on the path, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(".env")

from demo import logic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="NewsAI quick read demo", layout="wide")


def secrets() -> dict:
    # st.secrets raises when there is no secrets file, which is the normal
    # local case, and when the file is malformed. Either way there are none.
    try:
        return dict(st.secrets)
    except StreamlitAPIException:
        return {}


def not_configured(detail: str) -> None:
    st.error(f"Demo not configured. {detail}")
    st.stop()


# 1. The gate. Nothing below it renders until the password is right, and a
# missing password refuses rather than falling open.

environ, secret_values = os.environ, secrets()

expected = logic.demo_password(environ, secret_values)
if expected is None:
    not_configured("Set DEMO_PASSWORD to open it.")

try:
    daily_limit = logic.daily_limit(environ, secret_values)
except ValueError:
    not_configured("DEMO_DAILY_LIMIT must be a positive whole number.")

if not st.session_state.get("signed_in"):
    st.title("NewsAI quick read demo")
    given = st.text_input("Password", type="password", key="password")
    if given:
        if logic.password_matches(given, expected):
            st.session_state.signed_in = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()

if not logic.provider_ready():
    not_configured("The AI provider key is missing.")


@st.cache_resource
def usage_counter(limit: int) -> logic.UsageCounter:
    return logic.UsageCounter(limit)


@st.cache_resource
def samples():
    client = logic.sample_client()
    return client, logic.sample_titles(client)


counter = usage_counter(daily_limit)

# 2. The page.

st.markdown(
    """
    <style>
    .st-key-paste_ar textarea { direction: rtl; text-align: right; }
    .rtl { direction: rtl; text-align: right; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("NewsAI quick read demo")
st.info("Demo. Not yet connected to MakinatyNews.")


def quick_read_html(text: str, locale: str) -> str:
    # Model output is escaped before it reaches the page.
    direction = ' dir="rtl" class="rtl"' if locale == "ar" else ""
    return f"<div{direction}>{html.escape(text)}</div>"


def render_outcome(outcome: logic.RunOutcome) -> None:
    st.subheader(logic.LANGUAGE_NAMES[outcome.locale])
    label, reasons = logic.status_for(outcome)
    result = outcome.result

    if result is not None and result.deliverable:
        st.markdown(quick_read_html(result.text, outcome.locale), unsafe_allow_html=True)
        st.caption(
            f"{len(result.text.split())} words  |  {outcome.seconds:.2f} s  |  "
            f"cost {logic.format_cost(result)}"
        )
    elif result is not None:
        st.caption(f"{outcome.seconds:.2f} s  |  cost {logic.format_cost(result)}")

    message = label if not reasons else f"{label}. " + " ".join(reasons)
    if label == "Delivered":
        st.success(message)
    elif label.startswith("Delivered"):
        st.warning(message)
    else:
        st.error(message)

    if result is None:
        return

    with st.expander("Quality checks"):
        if not result.checks.hard and not result.checks.soft:
            st.markdown("All checks passed.")
        for failure in result.checks.hard:
            if failure.code != "provider_error":
                st.markdown(f"Blocked by `{failure.code}`")
        for warning in result.checks.soft:
            st.markdown(f"Flagged by `{warning.code}`: {html.escape(warning.detail)}")
        if not result.deliverable and result.text:
            st.markdown("Rejected output:")
            st.markdown(quick_read_html(result.text, outcome.locale), unsafe_allow_html=True)

    with st.expander("Protected names and figures"):
        terms = outcome.protected
        rows = [
            ("Names in Latin script", terms.latin_runs),
            ("Model codes", terms.model_codes),
            ("Figures", terms.figures),
        ]
        for title, values in rows:
            st.markdown(f"**{title}:** " + (", ".join(html.escape(v) for v in values) or "none"))

    with st.expander("Cleaned source text"):
        st.markdown(
            quick_read_html(outcome.cleaned_source, outcome.locale), unsafe_allow_html=True
        )


def run(article_id: int, locales: list[str], client) -> dict:
    if not counter.try_consume(len(locales)):
        return {
            "notice": (
                f"The demo has reached its daily limit of {counter.limit} runs. "
                f"It resets tomorrow. Runs left today: {counter.remaining()}."
            )
        }
    try:
        outcomes = logic.run_sync(logic.run_quick_reads(article_id, locales, client))
    except Exception:
        logging.getLogger("newsai.demo").exception("run failed")
        return {"notice": logic.UNEXPECTED}
    return {"outcomes": {o.locale: o for o in outcomes}}


def render_results(results: dict | None, locales) -> None:
    if not results:
        return
    if results.get("notice"):
        st.warning(results["notice"])

    shown = [
        loc for loc in locales
        if loc in results.get("refused", {}) or loc in results.get("outcomes", {})
    ]
    if not shown:
        return
    for column, locale in zip(st.columns(len(shown)), shown):
        with column:
            if locale in results.get("refused", {}):
                st.subheader(logic.LANGUAGE_NAMES[locale])
                st.warning(results["refused"][locale])
            else:
                render_outcome(results["outcomes"][locale])


paste_tab, sample_tab = st.tabs(["Paste article", "Sample articles"])

# 3. Paste tab.

with paste_tab:
    st.markdown(
        "Paste an article into one, two or all three boxes. Each box is summarised "
        "in its own language. Plain text or HTML both work."
    )
    texts = {}
    for column, locale in zip(st.columns(3), logic.LOCALES):
        with column:
            texts[locale] = st.text_area(
                logic.LANGUAGE_NAMES[locale], key=f"paste_{locale}", height=320
            )

    if st.button("Generate quick reads", key="paste_go", type="primary"):
        checks = [logic.check_box(texts[locale], locale) for locale in logic.LOCALES]
        filled = [c for c in checks if c.reason != "empty"]
        if not filled:
            st.session_state.paste_results = {
                "notice": "Paste an article into at least one box."
            }
        else:
            refused = {c.locale: c.message for c in filled if not c.ok}
            runnable = [c.locale for c in filled if c.ok]
            results = {"refused": refused}
            if runnable:
                results.update(run(0, runnable, logic.PastedClient(texts)))
            st.session_state.paste_results = results

    render_results(st.session_state.get("paste_results"), logic.LOCALES)

# 4. Sample tab.

with sample_tab:
    client, titles = samples()
    index = st.selectbox(
        "Article",
        range(len(titles)),
        format_func=lambda i: f"{i + 1}. {titles[i]}",
        key="sample_article",
    )
    choice = st.radio(
        "Language",
        ["English", "Arabic", "French", "All three"],
        horizontal=True,
        key="sample_lang",
    )
    if st.button("Generate quick read", key="sample_go", type="primary"):
        if choice == "All three":
            locales = list(logic.LOCALES)
        else:
            locales = [k for k, v in logic.LANGUAGE_NAMES.items() if v == choice]
        st.session_state.sample_results = run(index + 1, locales, client)

    render_results(st.session_state.get("sample_results"), logic.LOCALES)
