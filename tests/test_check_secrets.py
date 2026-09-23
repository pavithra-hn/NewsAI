import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_secrets.py"
spec = importlib.util.spec_from_file_location("check_secrets", SCRIPT)
check_secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_secrets)
find_secrets = check_secrets.find_secrets

# Shaped like real keys but assembled from short repeats at runtime, so no line
# of this file is itself key-shaped. An earlier version joined two long halves,
# and the scan correctly refused to commit it.
FAKE_SK = "sk_" + "tB7rOq" * 5
FAKE_OPENAI = "sk-" + "projA1b2C3" * 3
FAKE_GITHUB = "ghp_" + "A1b2C3" * 6
LONG_TOKEN = "Zx9Qw7" * 6


@pytest.mark.parametrize(
    "text",
    [
        f"PROVIDER_API_KEY={FAKE_SK}",
        f'key = "{FAKE_OPENAI}"',
        f"GITHUB_TOKEN={FAKE_GITHUB}",
        f"api_key: {LONG_TOKEN}",
        f"password = '{LONG_TOKEN}'",
        "https://user:" + LONG_TOKEN + "@github.com/org/repo",
        f"token={LONG_TOKEN}",
    ],
)
def test_key_shaped_strings_are_found(text):
    assert find_secrets(text)


@pytest.mark.parametrize(
    "text",
    [
        "PROVIDER_API_KEY=",
        "DEMO_PASSWORD=",
        'MODELS={"en": "qwen-3-32b", "ar": "qwen-3-32b", "fr": "qwen-3-32b"}',
        "PROVIDER_BASE_URL=https://api.oxlo.ai/v1",
        "api_key = settings.provider_api_key",
        "password = st.text_input('Password', type='password')",
        "https://d9z1tpn605xsl.cloudfront.net/news_site_uploads/ckeditor/pictures/1888/x.webp",
        "sk_ is a prefix some providers use",
    ],
)
def test_ordinary_text_is_not_flagged(text):
    assert find_secrets(text) == []


def test_the_vendored_corpus_is_clean():
    corpus = Path(__file__).resolve().parents[1] / "data" / "corpus.json"
    assert find_secrets(corpus.read_text(encoding="utf-8")) == []


def test_a_finding_reports_the_line_but_not_the_whole_secret():
    findings = find_secrets(f"a = 1\nPROVIDER_API_KEY={FAKE_SK}\n")
    assert findings[0][0] == 2
    assert FAKE_SK not in findings[0][1]
