#!/usr/bin/env python3
"""Stop / SubagentStop gate: don't let a turn end with failing lint or tests.

Runs only when Python files or project config have uncommitted changes, so conversational turns
stay instant. On failure it exits 2 with the tail of the output on stderr, which Claude Code shows
to the agent and keeps it working. Pending tests (xfail) don't count as failures.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
WATCHED_SUFFIXES = (".py", "pyproject.toml", "uv.lock")
TAIL_LINES = 40
NO_TESTS_COLLECTED = 5


def changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    paths = [line[3:].split(" -> ")[-1].strip('"') for line in result.stdout.splitlines()]
    return [p for p in paths if p.endswith(WATCHED_SUFFIXES)]


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return 1, f"`{' '.join(cmd)}` timed out after 240s"
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    sys.stdin.read()  # hook input is not needed; drain it
    if not changed_files():
        return 0
    if shutil.which("uv") is None:
        print("check.py: uv not found; skipping lint/test gate", file=sys.stderr)
        return 0

    pytest_cmd = ["uv", "run", "--quiet", "pytest", "-q", "-x", "--no-header"]
    checks = [
        ("ruff", ["uv", "run", "--quiet", "ruff", "check", "."]),
        ("pytest", [*pytest_cmd, "-p", "no:cacheprovider"]),
    ]
    for name, cmd in checks:
        code, output = run(cmd)
        if name == "pytest" and code == NO_TESTS_COLLECTED:
            continue
        if code != 0:
            tail = "\n".join(output.strip().splitlines()[-TAIL_LINES:])
            print(
                f"{name} failed (exit {code}). Fix it before finishing; "
                f"don't weaken or skip tests.\n$ {' '.join(cmd)}\n{tail}",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
