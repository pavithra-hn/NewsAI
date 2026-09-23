"""The page must start in a fresh interpreter, the way `streamlit run` starts it.

The other page tests import the pipeline before AppTest runs the page, so the
real `app` package is already in sys.modules. That once hid a crash: a page file
named app.py shadowed the pipeline's `app` package on a real start, and the page
imported itself half-initialised. These tests start from nothing.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "demo" / "streamlit_app.py"

PROBE = """
import sys
from streamlit.testing.v1 import AppTest
assert "app" not in sys.modules, "pipeline already imported, the probe proves nothing"
at = AppTest.from_file(sys.argv[1], default_timeout=60)
at.run()
problems = [e.message for e in at.exception]
print("EXCEPTIONS", problems)
print("TABS", len(at.tabs))
sys.exit(1 if problems or len(at.tabs) != 2 else 0)
"""


def test_the_page_starts_in_a_fresh_interpreter(tmp_path):
    env = {**os.environ, "PROVIDER_API_KEY": "fresh-start-check", "PYTHONIOENCODING": "utf-8"}
    env.pop("PYTHONPATH", None)

    run = subprocess.run(
        [sys.executable, "-c", PROBE, str(PAGE)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120, check=False,
    )

    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    assert "TABS 2" in run.stdout


def test_nothing_in_demo_can_shadow_the_pipeline_package():
    """Streamlit puts demo/ on sys.path, so a demo/app.py would be `import app`."""
    clashes = [p.name for p in (ROOT / "demo").iterdir() if p.stem == "app"]
    assert clashes == []
