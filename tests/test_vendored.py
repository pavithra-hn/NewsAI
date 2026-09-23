"""The pipeline is a snapshot of news-ai-helper at one commit, not an edited copy.

scripts/sync_pipeline.py writes it. These tests prove the snapshot is exactly
that commit, so the demo always shows real pipeline behaviour.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_REPO = Path(os.environ.get("NEWS_AI_HELPER_REPO", ROOT.parent / "news-ai-helper"))
EXCLUDED = {"app/main.py"}


def commit():
    return (ROOT / "PIPELINE_VERSION").read_text(encoding="utf-8").split()[0]


def test_the_version_file_names_a_full_commit():
    assert re.fullmatch(r"[0-9a-f]{40}", commit())


def test_the_web_server_is_left_out_so_fastapi_is_not_needed():
    assert not (ROOT / "app" / "main.py").exists()
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "fastapi" not in requirements


def test_no_private_repository_is_installed_by_requirements():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "git+" not in requirements


def _git(*args):
    return subprocess.run(
        ["git", "-C", str(PIPELINE_REPO), *args], capture_output=True, check=True
    ).stdout


@pytest.mark.skipif(not (PIPELINE_REPO / ".git").exists(), reason="news-ai-helper not present")
def test_every_vendored_file_matches_that_commit_exactly():
    listed = _git("ls-tree", "-r", "--name-only", commit(), "app/").decode().split()
    expected = {p for p in listed if p not in EXCLUDED}
    present = {
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "app").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    assert present == expected

    for path in sorted(expected):
        # Compare with line endings folded, so a Windows checkout does not
        # look like an edit.
        at_commit = _git("show", f"{commit()}:{path}").replace(b"\r\n", b"\n")
        on_disk = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        assert on_disk == at_commit, path
