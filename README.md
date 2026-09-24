# NewsAI quick read demo

A page for trying the NewsAiHelper quick read pipeline. Paste a news article, with
a title if it has one, in English, Arabic or French, or pick one of 25 published
sample articles and read it first. The quick read appears beside the article, in
that article's own language.

**This is a demo. It is not connected to MakinatyNews.** It runs the real
pipeline from `news-ai-helper` against text you give it. The page shows which
pipeline version it runs.

Nothing is translated. The language of a pasted article is detected from its
text, and it is summarised in that language.

## Requirements

- Python 3.11
- A key for an OpenAI-compatible model provider

## Install

```bash
python -m venv .venv
.venv\Scriptsctivate                       # macOS or Linux: source .venv/bin/activate
pip install -r requirements-dev.txt          # the page, the pipeline's needs, test tools
```

## The pipeline in `app/`

`app/` is an exact snapshot of `app/` in `news-ai-helper` at one commit, named
in `PIPELINE_VERSION`. It is vendored because the demo is hosted on Streamlit
Community Cloud, which cannot install a private company repository without a
token in `requirements.txt`. `app/main.py`, the FastAPI server, is left out
because the demo never imports it.

**Never edit `app/` here.** Change the pipeline in `news-ai-helper`, commit it
there, then refresh the snapshot:

```bash
python scripts/sync_pipeline.py <commit>
```

It copies from git at that commit, not from the working tree, so uncommitted
edits never leak in. A test checks every file still matches the commit.

## Configure

```bash
copy .env.example .env                       # macOS or Linux: cp
```

| Variable | Purpose |
|---|---|
| `DEMO_DAILY_LIMIT` | Runs allowed per day across all visitors. Default 200 |
| `PROVIDER_BASE_URL` | Model provider endpoint |
| `PROVIDER_API_KEY` | Model provider key. Secret |
| `MODELS` | Model per language, as one JSON object with `en`, `ar` and `fr` |
| `DEEPINFRA_API_KEY` | DeepInfra key. Secret. Adds Gemma 4 31B, GLM-5.3 Flash and GLM-5.2 to the Model menu; without it only GLM-5 is offered |

Values can also come from `.streamlit/secrets.toml`, which is how Streamlit
Community Cloud supplies them. They are copied into the environment before the
pipeline is imported, because the pipeline reads its settings once, at import.
A real environment variable wins when both are set. Both `.env` and
`secrets.toml` are ignored by git.

Settings are read once, when the app starts. After changing secrets on
Streamlit Community Cloud, reboot the app.

## Run

From the repository root:

```bash
streamlit run demo/streamlit_app.py
```

Each quick read counts as one run against the daily limit. The count lives in memory and resets when the app restarts.

## Tests

```bash
pytest
ruff check .
```

The tests use a stub in place of the model, so they make no AI calls and cost
nothing.

## Before committing

A key committed to GitHub is scraped within minutes and stays in history even
after it is deleted. Every commit is scanned first:

```bash
python scripts/check_secrets.py
```

To run it automatically, install it as a git hook once:

```bash
printf '#!/bin/sh\nexec python scripts/check_secrets.py\n' > .git/hooks/pre-commit
```

## Sample articles

`data/corpus.json` is a copy of `benchmark/corpus.json` from `news-ai-helper`
at commit `fd606cd` (the committed file, LF line endings), SHA-256
`5541e5e1b8ad89cdb68add45fe62bf4705f0532b6bbadb0dc392e147aeb2705c`. It holds 25
articles already published on plantandequipment.com, each in English, Arabic
and French. It is vendored because the installed pipeline package does not
include it.

## Layout

```
demo/streamlit_app.py  the page
.streamlit/config.toml the page's colours and chrome (not a secret)
demo/logic.py          everything the page does: checks, running, limits, settings
demo/bootstrap.py      copies Streamlit secrets into the environment, first
app/                   the pipeline snapshot, see PIPELINE_VERSION
data/corpus.json       the sample articles
scripts/               the secret scan and the pipeline sync
tests/                 logic tests and headless page tests
```
