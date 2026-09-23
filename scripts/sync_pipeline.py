"""Copy the quick read pipeline from news-ai-helper into this repo, at one commit.

    python scripts/sync_pipeline.py <commit>
    python scripts/sync_pipeline.py <commit> --repo D:/P&E/news-ai-helper

The demo is hosted on Streamlit Community Cloud, which cannot install a private
company repository without a token in requirements.txt. So the pipeline is
vendored instead: an exact snapshot of app/ at a named commit, taken from git
rather than from the working tree, so uncommitted edits never leak in.
PIPELINE_VERSION records which commit it is, and the page shows it.

Never edit app/ here. Change the pipeline in news-ai-helper, commit it there,
and run this again.
"""

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = ROOT.parent / "news-ai-helper"

# The FastAPI server. The demo never imports it, and leaving it out keeps
# fastapi out of the demo's requirements.
EXCLUDED = {"app/main.py"}


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True
    ).stdout


def sync(commit: str, repo: Path) -> str:
    full = git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    subject = git(repo, "log", "-1", "--format=%s", full).decode().strip()
    archive = git(repo, "archive", "--format=tar", full, "app")

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            members = [m for m in tar.getmembers() if m.name not in EXCLUDED]
            tar.extractall(staging, members=members, filter="data")

        target = ROOT / "app"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(staging / "app", target)

    (ROOT / "PIPELINE_VERSION").write_text(
        f"{full}\nnews-ai-helper: {subject}\n", encoding="utf-8", newline="\n"
    )
    return full


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("commit", help="commit, branch or tag in news-ai-helper")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    args = parser.parse_args(argv)

    if not (args.repo / ".git").exists():
        print(f"not a git repository: {args.repo}", file=sys.stderr)
        return 2

    full = sync(args.commit, args.repo)
    print(f"app/ now matches news-ai-helper at {full}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
