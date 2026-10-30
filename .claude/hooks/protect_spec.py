#!/usr/bin/env python3
"""PreToolUse guard: block changes to docs/RULES_SPEC.md while its Status is APPROVED.

The user unlocks the spec by changing its Status line to AMENDING (and back to APPROVED after).
Covers Edit/Write on the file, Bash commands that write, move or delete it, and git commands that
could revert it wholesale (broad checkout/restore, reset --hard, stash, clean).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_REL = "docs/RULES_SPEC.md"
SPEC_ABS = ROOT / SPEC_REL
STATUS_APPROVED = re.compile(r"^\*\*Status:\*\*\s*APPROVED\b", re.MULTILINE)
SPEC_REDIRECT = re.compile(r">\s*\S*RULES_SPEC")
BASH_WRITE = re.compile(
    r"\btee\b|\bsed\b[^;&|\n]*\s(?:-[A-Za-z]*i\S*|--in-place)(?:\s|=|$)"
    r"|\bperl\b[^;&|\n]*\s-[A-Za-z]*i\S*"
    r"|\b(?:mv|cp|rm|truncate|dd|install|ln|rsync|patch|python3?)\b"
    r"|\bgit\s+(?:-\S+\s+)*(?:checkout|restore|reset|rm|mv)\b"
)
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n()`]|\$\(")
GIT_GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree"}
MESSAGE = (
    "docs/RULES_SPEC.md is APPROVED and locked. Don't change it. Propose the amendment to the user "
    "instead: rule ID, current text, proposed text, and why. Only the user unlocks it, by setting "
    "its Status line to AMENDING."
)


def spec_locked() -> bool:
    try:
        head = SPEC_ABS.read_text(encoding="utf-8")[:4000]
    except FileNotFoundError:
        return False
    return STATUS_APPROVED.search(head) is not None


def mentions_spec(command: str) -> bool:
    """True if the command names the spec, directly or through a glob that would match it."""
    if "RULES_SPEC" in command:
        return True
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        if not any(char in token for char in "*?["):
            continue
        normalized = token.removeprefix("./")
        if fnmatch.fnmatch(SPEC_REL, normalized) or fnmatch.fnmatch("RULES_SPEC.md", normalized):
            return True
        if fnmatch.fnmatch(SPEC_REL, normalized.rstrip("/") + "/*"):
            return True
    return False


def broad_pathspec(token: str) -> bool:
    """A pathspec wide enough to cover the spec: `.`, `docs`, `docs/...`, a glob, `:/`."""
    normalized = token.removeprefix("./").rstrip("/")
    return (
        token in {".", "./", "..", ":/", ":/*"}
        or normalized == "docs"
        or normalized.startswith("docs/")
        or any(char in token for char in "*?[")
        or normalized.endswith("RULES_SPEC.md")
    )


def git_command(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Return (subcommand, args) if the segment runs git."""
    index = 0
    while index < len(tokens) and (
        tokens[index] in {"env", "sudo", "time", "command"} or "=" in tokens[index]
    ):
        index += 1
    if index >= len(tokens) or os.path.basename(tokens[index]) != "git":
        return None
    index += 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 2 if tokens[index] in GIT_GLOBAL_WITH_VALUE else 1
    if index >= len(tokens):
        return None
    return tokens[index], tokens[index + 1 :]


def git_reverts_spec(sub: str, args: list[str]) -> bool:
    if sub == "clean" or (sub == "reset" and "--hard" in args):
        return True
    if sub == "stash":
        return not args or args[0] not in {"list", "show"}
    if sub not in {"checkout", "restore", "switch"}:
        return False
    if any(a in {"-f", "--force", "--discard-changes"} for a in args):
        return True
    if sub == "switch":
        return False
    paths = [a for a in args if not a.startswith("-")]
    if any(broad_pathspec(a) for a in paths):
        return True
    if sub == "restore":
        # `git restore --source=<rev> <path>`: pulling files from another revision.
        return bool(paths) and any(a.startswith("--source") or a == "-s" for a in args)
    # `git checkout <rev> -- <path>`: branch-to-path form.
    if "--" in args:
        before, after = args[: args.index("--")], args[args.index("--") + 1 :]
        return bool(after) and any(not a.startswith("-") for a in before)
    return False


def bash_writes_spec(command: str) -> bool:
    for segment in SEGMENT_SPLIT.split(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        git = git_command(tokens)
        if git is not None and git_reverts_spec(*git):
            return True
    if SPEC_REDIRECT.search(command):
        return True
    return mentions_spec(command) and BASH_WRITE.search(command) is not None


def targets_spec(tool_name: str, tool_input: dict[str, object]) -> bool:
    if tool_name in ("Edit", "Write"):
        path = str(tool_input.get("file_path", ""))
        if not path:
            return False
        return (ROOT / path).resolve() == SPEC_ABS.resolve()
    if tool_name == "Bash":
        return bash_writes_spec(str(tool_input.get("command", "")))
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
