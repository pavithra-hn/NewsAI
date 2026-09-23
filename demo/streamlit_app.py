"""NewsAI quick read demo. The page only; everything it does lives in logic.py.

    streamlit run demo/streamlit_app.py
"""

import html
import logging
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Streamlit puts demo/ on the path, not the repository root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(".env")

# Secrets from the Streamlit Secrets box must reach the environment before the
# pipeline reads its settings, which it does on import.
from demo import bootstrap

bootstrap.export_secrets(bootstrap.read_streamlit_secrets(), os.environ)

from demo import logic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="Quick read", layout="wide")

NATIVE_NAMES = {"en": "English", "fr": "Français", "ar": "العربية"}
SAMPLE_LANGUAGES = {"English": "en", "Français": "fr", "العربية": "ar"}

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Noto+Naskh+Arabic:wght@400;600;700&display=swap');

:root {
  --concrete: #E6E8E3;
  --slab: #F7F8F5;
  --ink: #18222E;
  --graphite: #56606B;
  --rule: #C5CAC2;
  --cobalt: #1F45A8;
  --focus: #F0B429;
  --blocked: #A8231B;
  --display: 'IBM Plex Sans Condensed', 'Arial Narrow', sans-serif;
  --ui: 'IBM Plex Sans', system-ui, sans-serif;
  --read: 'Source Serif 4', Georgia, serif;
  --arabic: 'Noto Naskh Arabic', 'Traditional Arabic', serif;
}

.stApp { background: var(--concrete); color: var(--ink); font-family: var(--ui); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none; }
[data-testid="stHeaderActionElements"] { display: none; }
.block-container { max-width: 1240px; padding-top: 2.75rem; padding-bottom: 4rem; }

/* Masthead: the same two words in the three languages the tool works in. */
.stApp .mast-title {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem;
  margin: 0; padding: 0 0 1.1rem; border-bottom: 3px solid var(--ink);
  font-family: var(--display); font-weight: 700; color: var(--ink);
  font-size: clamp(1.9rem, 3.3vw, 3rem); line-height: 1.05; letter-spacing: -0.01em;
  white-space: nowrap;
}
.stApp .mast-title [lang="ar"] {
  font-family: var(--arabic); text-align: right; line-height: 1.25; font-size: 0.92em;
}
.stApp .mast-lede {
  max-width: 62ch; margin: 1rem 0 0.5rem; color: var(--graphite);
  font-size: 1.05rem; line-height: 1.6;
}

/* Tabs */
.stApp [role="tablist"] { gap: 2.25rem; }
.stApp [data-testid="stTab"] { min-height: 44px; }
.stApp [data-testid="stTab"] p { font-family: var(--display); font-weight: 600; font-size: 1.15rem; }

/* Column headings: which side is the article and which is the quick read. */
.stApp .panel-head {
  margin: 0.4rem 0 1rem; padding-bottom: 0.45rem; border-bottom: 2px solid var(--ink);
  font-family: var(--display); font-weight: 700; font-size: 1.35rem; color: var(--ink);
}

/* Inputs. plaintext bidi lets pasted Arabic run right to left by itself. */
.stApp .stTextInput label p, .stApp .stTextArea label p,
.stApp .stSelectbox label p, .stApp .stRadio > label p {
  font-family: var(--display); font-weight: 600; font-size: 1.05rem; color: var(--ink);
}
.stTextArea textarea, .stTextInput input {
  font-family: var(--read); font-size: 1.02rem; color: var(--ink);
  unicode-bidi: plaintext; text-align: start;
}
.stTextArea textarea { line-height: 1.65; }
.stTextInput input { font-weight: 600; }

/* The one action */
.stButton button[kind="primary"] { min-height: 48px; padding: 0 2.5rem; border-radius: 4px; }
.stApp .stButton button[kind="primary"] p {
  font-family: var(--display); font-weight: 600; font-size: 1.15rem; letter-spacing: 0.01em;
}
.stButton button:focus-visible, .stTextArea textarea:focus-visible,
.stTextInput input:focus-visible, .stApp [data-testid="stTab"]:focus-visible {
  outline: 3px solid var(--focus); outline-offset: 2px;
}

/* The article, as a reader sees it */
.stApp .article {
  background: var(--slab); border-top: 3px solid var(--ink);
  padding: 1.1rem 1.35rem 0.4rem; max-height: 440px; overflow-y: auto; margin-bottom: 1rem;
}
.stApp .article-title {
  margin: 0 0 0.75rem; font-family: var(--read); font-weight: 600;
  font-size: 1.3rem; line-height: 1.35; color: var(--ink);
}
.stApp .article p { margin: 0 0 0.85rem; font-family: var(--read); font-size: 1rem; line-height: 1.7; color: var(--ink); }
.stApp .article[dir="rtl"] .article-title, .stApp .article[dir="rtl"] p { font-family: var(--arabic); }
.stApp .article[dir="rtl"] p { font-size: 1.1rem; line-height: 1.9; }

/* The quick read */
.stApp .qr { background: var(--slab); border-top: 3px solid var(--cobalt); padding: 1.1rem 1.35rem 1.35rem; }
.stApp .qr-lang { margin: 0 0 0.6rem; font-family: var(--display); font-weight: 600; font-size: 1rem; color: var(--cobalt); }
.stApp .qr[dir="rtl"] .qr-lang { font-family: var(--arabic); }
.stApp .qr-title { margin: 0 0 0.5rem; font-family: var(--read); font-weight: 600; font-size: 1.2rem; line-height: 1.35; color: var(--ink); }
.stApp .qr-text { margin: 0; font-family: var(--read); font-size: 1.12rem; line-height: 1.75; color: var(--ink); }
.stApp .qr[dir="rtl"] .qr-title, .stApp .qr[dir="rtl"] .qr-text { font-family: var(--arabic); }
.stApp .qr[dir="rtl"] .qr-text { font-size: 1.22rem; line-height: 1.95; }
/* Streamlit sets paragraphs left. Arabic reads from the right, so it aligns there. */
.stApp [dir="rtl"] p { text-align: right; }
.stApp [dir="rtl"] p[dir="ltr"] { text-align: left; }
.stApp .qr.blocked { border-top-color: var(--blocked); }
.stApp .qr-problem { margin: 0; color: var(--blocked); font-size: 1rem; line-height: 1.55; }
.stApp .empty {
  border: 2px dashed var(--rule); padding: 2.5rem 1.5rem; color: var(--graphite);
  font-size: 1rem; line-height: 1.6;
}

/* Length and time, quietly, under the quick read. */
.stApp .qr-meta { margin: 0.9rem 0 0; color: var(--graphite); font-size: 0.92rem; font-family: var(--ui); }

@media (max-width: 760px) {
  .stApp .mast-title { grid-template-columns: 1fr; gap: 0.25rem; white-space: normal; }
}
</style>
"""

MASTHEAD = """
<header>
  <div class="mast-title" role="heading" aria-level="1">
    <span lang="en">Quick read</span>
    <span lang="fr">Lecture rapide</span>
    <span lang="ar" dir="rtl">قراءة سريعة</span>
  </div>
  <p class="mast-lede">Paste a news article, or pick one of ours. You get a short summary
  in the article's own language, with every figure kept exactly.</p>
</header>
"""

st.markdown(STYLE, unsafe_allow_html=True)


def not_configured(detail: str) -> None:
    st.error(f"Demo not configured. {detail}")
    st.stop()


environ, secret_values = os.environ, bootstrap.read_streamlit_secrets()

try:
    daily_limit = logic.daily_limit(environ, secret_values)
except ValueError:
    not_configured("DEMO_DAILY_LIMIT must be a positive whole number.")

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

st.markdown(MASTHEAD, unsafe_allow_html=True)


def rtl(locale: str) -> str:
    return ' dir="rtl"' if locale == "ar" else ""


def heading(text: str) -> None:
    st.markdown(
        f'<div class="panel-head" role="heading" aria-level="2">{text}</div>',
        unsafe_allow_html=True,
    )


def article_html(locale: str, title: str, body_html: str) -> str:
    parts = [f'<div class="article" lang="{locale}"{rtl(locale)}>']
    if title:
        parts.append(f'<p class="article-title">{html.escape(title)}</p>')
    parts.extend(f"<p>{html.escape(p)}</p>" for p in logic.paragraphs(body_html))
    parts.append("</div>")
    return "".join(parts)


def meta_html(outcome: logic.RunOutcome) -> str:
    words = len(outcome.result.text.split())
    return f'<p class="qr-meta" dir="ltr">{words} words, {outcome.seconds:.1f} seconds</p>'


def quick_read_html(outcome: logic.RunOutcome, title: str) -> str:
    locale = outcome.locale
    _, reasons = logic.status_for(outcome)
    head = f'<p class="qr-lang">{NATIVE_NAMES[locale]}</p>'
    result = outcome.result

    if result is None or not result.deliverable:
        problem = " ".join(reasons) or logic.UNEXPECTED
        return (
            f'<div class="qr blocked" lang="{locale}"{rtl(locale)}>{head}'
            f'<p class="qr-problem" dir="ltr">{html.escape(problem)}</p></div>'
        )

    title_html = f'<p class="qr-title">{html.escape(title)}</p>' if title else ""
    # Model output is escaped before it reaches the page.
    return (
        f'<div class="qr" lang="{locale}"{rtl(locale)}>{head}{title_html}'
        f'<p class="qr-text">{html.escape(result.text)}</p>{meta_html(outcome)}</div>'
    )


def run(article_id: int, locale: str, client) -> dict:
    if not counter.try_consume(1):
        return {
            "notice": (
                f"The demo has reached its daily limit of {counter.limit} runs. "
                "It resets tomorrow."
            )
        }
    try:
        with st.spinner("Writing the quick read"):
            outcomes = logic.run_sync(logic.run_quick_reads(article_id, [locale], client))
    except Exception:
        logging.getLogger("newsai.demo").exception("run failed")
        return {"notice": logic.UNEXPECTED}
    return {"outcome": outcomes[0]}


def show_quick_read(result: dict | None, title: str, empty: str) -> None:
    heading("Quick read")
    if not result:
        st.markdown(f'<div class="empty">{empty}</div>', unsafe_allow_html=True)
    elif result.get("notice"):
        st.warning(result["notice"])
    else:
        st.markdown(quick_read_html(result["outcome"], title), unsafe_allow_html=True)


paste_tab, sample_tab = st.tabs(["Paste article", "Sample articles"])

with paste_tab:
    left, right = st.columns([1.1, 1], gap="large")

    with left:
        heading("Your article")
        title = st.text_input("Title", key="paste_title", placeholder="Optional")
        body = st.text_area(
            "Content",
            key="paste_body",
            height=380,
            placeholder="Paste the article text here, in English, French or Arabic.",
        )
        if st.button("Quick read", key="paste_go", type="primary"):
            check = logic.check_paste(body)
            if not check.ok:
                outcome = {"notice": check.message}
            else:
                client = logic.PastedClient({check.locale: body}, {check.locale: title})
                outcome = run(0, check.locale, client)
            st.session_state.paste_result = {"for": (title, body), **outcome}

    with right:
        saved = st.session_state.get("paste_result")
        # A quick read belongs to the text it was made from. Edit the article
        # and the old quick read is no longer shown against it.
        current = saved if saved and saved.get("for") == (title, body) else None
        show_quick_read(
            current, title.strip(), "Paste an article and press Quick read. "
            "The summary appears here, in the article's own language."
        )

with sample_tab:
    client, titles = samples()
    left, right = st.columns([1.1, 1], gap="large")

    with left:
        heading("The article")
        index = st.selectbox(
            "Article",
            range(len(titles)),
            format_func=lambda i: f"{i + 1}. {titles[i]}",
            key="sample_article",
        )
        choice = st.radio(
            "Language", list(SAMPLE_LANGUAGES), horizontal=True, key="sample_lang"
        )
        locale = SAMPLE_LANGUAGES[choice]
        version = client.articles[index]["locales"][locale]
        st.markdown(
            article_html(locale, version["title"], version["body_html"]), unsafe_allow_html=True
        )
        if st.button("Quick read", key="sample_go", type="primary"):
            st.session_state.sample_result = {
                "for": (index, locale), **run(index + 1, locale, client)
            }

    with right:
        saved = st.session_state.get("sample_result")
        current = saved if saved and saved.get("for") == (index, locale) else None
        show_quick_read(
            current, version["title"], "Press Quick read to summarise this article."
        )
