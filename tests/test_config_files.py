"""A straight copy of .env.example must start the app, safely closed."""

from pathlib import Path

from app.config import Settings
from dotenv import dotenv_values

from demo import logic

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"


def test_the_example_file_parses_as_settings():
    settings = Settings(_env_file=EXAMPLE)
    assert set(settings.models) == {"en", "ar", "fr"}


def test_the_example_file_leaves_the_demo_closed():
    values = dotenv_values(EXAMPLE)
    assert logic.demo_password(values, {}) is None
    assert logic.daily_limit(values, {}) == logic.DEFAULT_DAILY_LIMIT


def test_the_example_file_holds_no_secrets():
    values = dotenv_values(EXAMPLE)
    assert values["DEMO_PASSWORD"] == ""
    assert values["PROVIDER_API_KEY"] == ""


def test_secrets_are_ignored_by_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored
    assert ".streamlit/secrets.toml" in ignored
