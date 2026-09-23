"""A straight copy of .env.example must start the app with no secrets in it."""

from pathlib import Path

from dotenv import dotenv_values

from app.config import Settings
from demo import logic

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"


def test_the_example_file_parses_as_settings():
    settings = Settings(_env_file=EXAMPLE)
    assert set(settings.models) == {"en", "ar", "fr"}


def test_the_example_file_uses_the_default_daily_limit():
    values = dotenv_values(EXAMPLE)
    assert logic.daily_limit(values, {}) == logic.DEFAULT_DAILY_LIMIT


def test_the_example_file_holds_no_secrets():
    values = dotenv_values(EXAMPLE)
    assert values["PROVIDER_API_KEY"] == ""
    assert "DEMO_PASSWORD" not in values


def test_secrets_are_ignored_by_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored
    assert ".streamlit/secrets.toml" in ignored
