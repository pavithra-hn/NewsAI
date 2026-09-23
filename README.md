# NewsAI quick read demo

A password-protected page for trying the NewsAiHelper quick read pipeline. Paste
a news article in English, Arabic or French, or pick one of 25 published sample
articles, and get a short quick read in that same language.

**This is a demo. It is not connected to MakinatyNews.** It runs the real
pipeline from `news-ai-helper` against text you give it.

Nothing is translated. Each language is summarised from its own text, so a box
refuses text in a different language rather than silently translating it.

## Requirements

- Python 3.11
- A checkout of `news-ai-helper` on branch `feat/quick-read-pipeline`
- A key for an OpenAI-compatible model provider

## Install

```bash
python -m venv .venv
.venv\Scripts\activate                       # macOS or Linux: source .venv/bin/activate

pip install -e D:\P&E\news-ai-helper         # the pipeline, editable
pip install -r requirements-dev.txt          # the page, plus test tools
```

The pipeline is installed from its own checkout rather than copied into this
repository. `requirements.txt` carries the pinned GitHub install line, commented
out until the pipeline branch is pushed.

## Configure

```bash
copy .env.example .env                       # macOS or Linux: cp
```

| Variable | Purpose |
|---|---|
| `DEMO_PASSWORD` | Password for the page. If unset, the page refuses to open |
| `DEMO_DAILY_LIMIT` | Runs allowed per day across all visitors. Default 200 |
| `PROVIDER_BASE_URL` | Model provider endpoint |
| `PROVIDER_API_KEY` | Model provider key. Secret |
| `MODELS` | Model per language, as one JSON object with `en`, `ar` and `fr` |

Values can also come from `.streamlit/secrets.toml`. The environment wins when
both are set. Both `.env` and `secrets.toml` are ignored by git.

## Run

From the repository root:

```bash
streamlit run demo/streamlit_app.py
```

Each language box, or each language of a sample, counts as one run against the
daily limit. The count lives in memory and resets when the app restarts.

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
demo/logic.py          everything the page does: checks, running, limits, settings
data/corpus.json       the sample articles
scripts/               the secret scan
tests/                 logic tests and headless page tests
```
