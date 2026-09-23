"""Streamlit secrets must reach the environment before the pipeline is imported.

The pipeline reads its settings from the environment once, when app.config is
first imported. On Streamlit Community Cloud the key lives in the Secrets box,
so it has to be copied across first or the page reports the key as missing.
"""

import json
import subprocess
import sys
from pathlib import Path

from demo import bootstrap

ROOT = Path(__file__).resolve().parents[1]


def test_root_secrets_are_copied_into_the_environment():
    environ = {}
    bootstrap.export_secrets({"PROVIDER_API_KEY": "k", "DEMO_DAILY_LIMIT": 50}, environ)
    assert environ == {"PROVIDER_API_KEY": "k", "DEMO_DAILY_LIMIT": "50"}


def test_a_real_environment_variable_wins_over_a_secret():
    environ = {"PROVIDER_API_KEY": "from-env"}
    bootstrap.export_secrets({"PROVIDER_API_KEY": "from-secrets"}, environ)
    assert environ["PROVIDER_API_KEY"] == "from-env"


def test_a_table_is_written_as_json_so_models_can_be_either_form():
    environ = {}
    bootstrap.export_secrets({"MODELS": {"en": "a", "ar": "b", "fr": "c"}}, environ)
    assert json.loads(environ["MODELS"]) == {"en": "a", "ar": "b", "fr": "c"}


def test_the_bootstrap_does_not_import_the_pipeline():
    code = "import sys; import demo.bootstrap; print('app.config' in sys.modules)"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


def test_a_key_that_exists_only_in_streamlit_secrets_opens_the_page(tmp_path):
    # A fresh interpreter, so app.config has not been imported yet, exactly as
    # on the cloud. No environment variables: the secrets are the only source.
    script = f"""
import os
for name in ("PROVIDER_API_KEY", "DEMO_DAILY_LIMIT", "MODELS"):
    os.environ.pop(name, None)
os.chdir({str(tmp_path)!r})
from streamlit.testing.v1 import AppTest
at = AppTest.from_file({str(ROOT / "demo" / "streamlit_app.py")!r}, default_timeout=60)
at.secrets["PROVIDER_API_KEY"] = "secret-only-key"
at.run()
text = " ".join(str(e.value) for e in list(at.error) + list(at.exception))
if "key is missing" in text:
    print("KEY MISSING")
elif text:
    print("ERROR " + text)
else:
    print("OPEN" if len(at.tabs) == 2 else "NO TABS")
"""
    out = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=120, check=False
    )
    assert out.stdout.strip().splitlines()[-1] == "OPEN", out.stdout + out.stderr
