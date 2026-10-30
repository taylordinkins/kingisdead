#!/usr/bin/env python3
"""PreToolUse guard for the spec-test-writer agent: keep engine source out of its view.

Tests are meant to be an independent reading of docs/RULES_SPEC.md, so this blocks Read/Grep/Glob
on the `kingisdead/` package and Bash commands that name files inside it. Running the test suite
(which imports the package) is still allowed.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.normpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
PACKAGE = "kingisdead"
MESSAGE = (
    "spec-test-writer works from the spec only, so engine source under kingisdead/ is off-limits. "
    "Use docs/RULES_SPEC.md, docs/ACTIONS.md, tests/harness.py and existing tests. If the harness "
    "is missing something, report it instead."
)


def relative(path: str) -> str:
    absolute = os.path.normpath(os.path.join(ROOT, path))
    return os.path.relpath(absolute, ROOT)


def in_package(path: str) -> bool:
    rel = relative(path)
    return rel == PACKAGE or rel.startswith(PACKAGE + os.sep)


def blocked(tool_name: str, tool_input: dict[str, object]) -> bool:
    if tool_name == "Read":
        return in_package(str(tool_input.get("file_path", "")))
    if tool_name in ("Grep", "Glob"):
        path = str(tool_input.get("path") or "")
        pattern = str(tool_input.get("pattern", "")) if tool_name == "Glob" else ""
        return (bool(path) and in_package(path)) or pattern.lstrip("./").startswith(PACKAGE + "/")
    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).replace(ROOT + os.sep, "")
        return re.search(rf"(^|[\s'\"=]){PACKAGE}/", command) is not None
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if blocked(payload.get("tool_name", ""), payload.get("tool_input") or {}):
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
