"""Refuse a commit that stages anything shaped like a key.

A key pushed to GitHub is scraped within minutes, and deleting it afterwards
does not help because it stays in history. So this runs before every commit:

    python scripts/check_secrets.py

It scans the staged version of each staged file and exits 1 on any finding.
Installed as .git/hooks/pre-commit, it runs automatically.
"""

import re
import subprocess
import sys

PATTERNS = [
    ("provider key", re.compile(r"\bsk[_-][A-Za-z0-9_-]{16,}")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}")),
    (
        "assigned secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"]?"
            r"(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{12,}"
        ),
    ),
    ("credentials in a url", re.compile(r"://[^/\s:@]+:[^/\s@]{8,}@")),
    (
        "long token",
        re.compile(
            r"(?<![A-Za-z0-9_\-/.])(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[a-z])"
            r"(?=[A-Za-z0-9_\-]*[A-Z])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9_\-/.])"
        ),
    ),
]


def find_secrets(text: str) -> list[tuple[int, str]]:
    """Return (line number, masked description) for each suspicious line."""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS:
            match = pattern.search(line)
            if match:
                found = match.group(0)
                findings.append((number, f"{name}: {found[:6]}...{len(found)} chars"))
                break
    return findings


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def staged_content(path: str) -> str | None:
    out = subprocess.run(["git", "show", f":{path}"], capture_output=True, check=True)
    try:
        return out.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def main() -> int:
    files = staged_files()
    total = 0
    for path in files:
        content = staged_content(path)
        if content is None:
            continue
        for number, description in find_secrets(content):
            print(f"  {path}:{number}  {description}")
            total += 1

    if total:
        print(f"REFUSED: {total} possible secret(s) in {len(files)} staged file(s).")
        return 1
    print(f"clean: {len(files)} staged file(s) scanned, 0 possible secrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
