#!/usr/bin/env python3
"""Stop / SubagentStop gate: don't let a turn end with failing lint, types or tests.

Runs the same checks as CI (ruff check, ruff format --check, pyright, pytest) when watched files
have uncommitted changes or HEAD differs from the last green state (`.git/kid-last-green`), so
conversational turns stay instant. On failure it exits 2 with the tail of the output on stderr,
which Claude Code shows to the agent and keeps it working. Pending/regression tests (xfail) don't
count as failures.

Also a backstop for protect_spec.py: an APPROVED docs/RULES_SPEC.md must not differ from HEAD in
anything but its Status line.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCHED_DIRS = ("kingisdead/", "tests/", "tools/", "typings/")
WATCHED_FILES = ("pyproject.toml", "uv.lock")
SPEC_REL = "docs/RULES_SPEC.md"
STATUS_LINE = re.compile(r"^\*\*Status:\*\*.*$", re.MULTILINE)
TAIL_LINES = 40
TIMEOUT_SECONDS = 240
NO_TESTS_COLLECTED = 5

CHECKS: list[tuple[str, list[str]]] = [
    ("ruff check", ["uv", "run", "--quiet", "ruff", "check", "."]),
    ("ruff format", ["uv", "run", "--quiet", "ruff", "format", "--check", "."]),
    ("pyright", ["uv", "run", "--quiet", "pyright"]),
    (
        "pytest",
        ["uv", "run", "--quiet", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
    ),
]


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def is_watched(path: str) -> bool:
    return path.startswith(WATCHED_DIRS) or path in WATCHED_FILES


def uncommitted_watched() -> list[str] | None:
    """Watched paths with uncommitted changes, or None if `git status` failed."""
    result = git("status", "--porcelain", "-z", "--untracked-files=all")
    if result.returncode != 0:
        return None
    entries = result.stdout.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        paths.append(entry[3:])
        if entry[0] in "RC" and index < len(entries):  # rename/copy: next entry is the old path
            paths.append(entries[index])
            index += 1
    return [p for p in paths if is_watched(p)]


def head_sha() -> str | None:
    result = git("rev-parse", "--verify", "--quiet", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def stamp_path() -> Path:
    result = git("rev-parse", "--git-path", "kid-last-green")
    relative = result.stdout.strip() or ".git/kid-last-green"
    return ROOT / relative


def read_stamp() -> str | None:
    try:
        return stamp_path().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def needs_run(changed: list[str] | None, head: str | None, stamp: str | None) -> bool:
    """Run unless git says nothing watched changed and HEAD is the last green commit."""
    if changed is None or changed:
        return True
    return head is not None and head != stamp


def spec_violation() -> bool:
    """True if the working-copy spec is APPROVED and differs from HEAD beyond its Status line."""
    path = ROOT / SPEC_REL
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if re.search(r"^\*\*Status:\*\*\s*APPROVED\b", current[:4000], re.MULTILINE) is None:
        return False
    committed = git("show", f"HEAD:{SPEC_REL}")
    if committed.returncode != 0:
        return False
    return STATUS_LINE.sub("", current, count=1) != STATUS_LINE.sub("", committed.stdout, count=1)


def run_checks() -> tuple[str, list[str], int, str] | None:
    """Run the checks in CI order; return the first failure as (name, cmd, code, output)."""
    for name, cmd in CHECKS:
        try:
            proc = subprocess.run(
                cmd, cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            return name, cmd, 1, f"`{' '.join(cmd)}` timed out after {TIMEOUT_SECONDS}s"
        if name == "pytest" and proc.returncode == NO_TESTS_COLLECTED:
            continue
        if proc.returncode != 0:
            return name, cmd, proc.returncode, proc.stdout + proc.stderr
    return None


def main() -> int:
    sys.stdin.read()  # hook input is not needed; drain it
    if spec_violation():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from protect_spec import MESSAGE

        print(f"RULES_SPEC.md changed while APPROVED. {MESSAGE}", file=sys.stderr)
        return 2

    changed = uncommitted_watched()
    if changed is None:
        print("check.py: `git status` failed; running the checks anyway", file=sys.stderr)
    head = head_sha()
    if not needs_run(changed, head, read_stamp()):
        return 0
    if shutil.which("uv") is None:
        print("check.py: uv not found; skipping lint/test gate", file=sys.stderr)
        return 0

    failure = run_checks()
    if failure is not None:
        name, cmd, code, output = failure
        tail = "\n".join(output.strip().splitlines()[-TAIL_LINES:])
        print(
            f"{name} failed (exit {code}). Fix it before finishing; "
            f"don't weaken or skip tests.\n$ {' '.join(cmd)}\n{tail}",
            file=sys.stderr,
        )
        return 2
    if changed == [] and head is not None:
        stamp_path().write_text(head + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
