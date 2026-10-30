#!/usr/bin/env python3
"""PreToolUse guard: block changes to docs/RULES_SPEC.md while its Status is APPROVED.

The user unlocks the spec by changing its Status line to AMENDING (and back to APPROVED after).
Covers Edit/Write on the file and Bash commands that would write, move or delete it.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SPEC_REL = "docs/RULES_SPEC.md"
SPEC_ABS = os.path.normpath(os.path.join(ROOT, SPEC_REL))
STATUS_APPROVED = re.compile(r"^\*\*Status:\*\*\s*APPROVED\b", re.MULTILINE)
BASH_WRITE = re.compile(
    r"(>|\btee\b|\bsed\s+-i|\bperl\s+-i|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bdd\b|"
    r"\bpython3?\b|\bgit\s+(checkout|restore|reset|rm|mv)\b)"
)
MESSAGE = (
    "docs/RULES_SPEC.md is APPROVED and locked. Don't change it. Propose the amendment to the user "
    "instead: rule ID, current text, proposed text, and why. Only the user unlocks it, by setting "
    "its Status line to AMENDING."
)


def spec_locked() -> bool:
    try:
        with open(SPEC_ABS, encoding="utf-8") as handle:
            head = handle.read(4000)
    except FileNotFoundError:
        return False
    return STATUS_APPROVED.search(head) is not None


def targets_spec(tool_name: str, tool_input: dict[str, object]) -> bool:
    if tool_name in ("Edit", "Write"):
        path = str(tool_input.get("file_path", ""))
        if not path:
            return False
        return os.path.normpath(os.path.join(ROOT, path)) == SPEC_ABS
    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        return "RULES_SPEC.md" in command and BASH_WRITE.search(command) is not None
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    if targets_spec(payload.get("tool_name", ""), tool_input) and spec_locked():
        print(MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
