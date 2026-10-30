#!/usr/bin/env python3
"""PreToolUse guard for the spec-test-writer agent: keep engine source out of its view.

Tests are meant to be an independent reading of docs/RULES_SPEC.md, so this is an allowlist:
Read/Grep/Glob may only touch docs/, tests/, PLAN.md, README.md, CLAUDE.md and pyproject.toml, and
Grep/Glob must say where to look (their default is the repo root, which contains the engine).
Bash is checked for any reference to the `kingisdead/` package or a recursive scan of the repo root.
Running the test suite (which imports the package) and `python -c 'import kingisdead'` still work.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "kingisdead"
ALLOWED_DIRS = ("docs", "tests")
ALLOWED_FILES = ("PLAN.md", "README.md", "CLAUDE.md", "pyproject.toml")

MESSAGE = (
    "spec-test-writer works from the spec only, so engine source under kingisdead/ is off-limits. "
    "Read only docs/, tests/, PLAN.md, README.md, CLAUDE.md and pyproject.toml. "
    "Use docs/RULES_SPEC.md, docs/ACTIONS.md, tests/harness.py and existing tests. If the harness "
    "is missing something, report it instead."
)
NEEDS_PATH_MESSAGE = (
    "Grep and Glob default to the repo root, which contains the engine. Pass `path` explicitly "
    "(for example `tests` or `docs`). " + MESSAGE
)

# A standalone `kingisdead` or `kingisdead/...` path argument, not `import kingisdead` or
# `kingisdead.module` (checked separately for the import forms).
PACKAGE_PATH = re.compile(rf"(?<![\w.:-])(?:\./)?{PACKAGE}(?![\w.-])|(?<!\w){PACKAGE}/")
IMPORT_CONTEXT = re.compile(r"\b(?:import|from)\s+(?:[\w.]+\s*,\s*)*$")
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n()`]|\$\(")
WRAPPERS = {"env", "time", "command", "sudo", "nice", "nohup", "exec", "xargs", "uv", "run"}
VALUE_FLAGS = {
    "-g", "--glob", "-t", "--type", "-T", "--type-not", "-A", "-B", "-C", "-m", "-j",
    "--include", "--exclude", "--exclude-dir", "--max-count", "--max-depth", "-d", "--maxdepth",
}  # fmt: skip
ROOT_LIKE = {".", "./", "..", "../", "*", "./*", "/", "~", "~/"}


def resolve(path: str) -> Path:
    return (ROOT / os.path.expanduser(path)).resolve()


def allowed_path(path: str) -> bool:
    if not path:
        return False
    target = resolve(path)
    if target in {ROOT / name for name in ALLOWED_FILES}:
        return True
    return any(target.is_relative_to(ROOT / name) for name in ALLOWED_DIRS)


def glob_ok(pattern: str) -> bool:
    """A glob/pattern is fine if it doesn't name the package, climb out, or point elsewhere."""
    if PACKAGE in pattern or ".." in pattern.split("/"):
        return False
    if pattern.startswith(("/", "~")):
        literal = re.split(r"[*?\[{]", pattern, maxsplit=1)[0]
        return allowed_path(literal)
    return True


def tool_blocked(tool_name: str, tool_input: dict[str, object]) -> str | None:
    if tool_name == "Read":
        return None if allowed_path(str(tool_input.get("file_path", ""))) else MESSAGE
    path = str(tool_input.get("path") or "")
    if not path:
        return NEEDS_PATH_MESSAGE
    if not allowed_path(path):
        return MESSAGE
    extras = [str(tool_input.get("glob") or "")]
    if tool_name == "Glob":
        extras.append(str(tool_input.get("pattern", "")))
    if not all(glob_ok(extra) for extra in extras if extra):
        return MESSAGE
    return None


def strip_root(command: str) -> str:
    root = str(ROOT)
    command = command.replace(root + "/", "")
    return re.sub(re.escape(root) + r"(?![\w.-])", ".", command)


def tokens_of(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def names_package(command: str) -> bool:
    for match in PACKAGE_PATH.finditer(command):
        if IMPORT_CONTEXT.search(command[: match.start()]) is None:
            return True
    return False


def scans_root(tokens: list[str]) -> bool:
    """True if a recursive search/listing command could walk the repo root (hence the engine)."""
    index = 0
    while index < len(tokens) and (
        tokens[index] in WRAPPERS or tokens[index].startswith("-") or "=" in tokens[index]
    ):
        index += 1
    if index >= len(tokens):
        return False
    command, args = os.path.basename(tokens[index]), tokens[index + 1 :]
    if command == "git" and "grep" in args:
        command, args = "git-grep", args[args.index("grep") + 1 :]
    flags: list[str] = []
    positional: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
        elif arg.startswith("-"):
            flags.append(arg)
            skip_next = arg in VALUE_FLAGS
        else:
            positional.append(arg)
    has_pattern_flag = any(re.match(r"-e|-f|--regexp|--file", f) for f in flags)
    if command in ("grep", "egrep", "fgrep"):
        recursive = any(
            f == "--recursive" or (not f.startswith("--") and re.search(r"[rR]", f)) for f in flags
        )
        if not recursive:
            return False
        paths = positional if has_pattern_flag else positional[1:]
    elif command in ("rg", "ag"):
        paths = positional if has_pattern_flag else positional[1:]
    elif command == "git-grep":
        # `git grep` takes pathspecs after `--`; without a restriction it searches the whole repo.
        paths = args[args.index("--") + 1 :] if "--" in args else []
    elif command == "find":
        paths = []
        for arg in args:
            if arg.startswith(("-", "(", "!")):
                break
            paths.append(arg)
    elif command in ("tree", "du"):
        paths = positional
    elif command == "ls":
        if not any(f == "--recursive" or (not f.startswith("--") and "R" in f) for f in flags):
            return False
        paths = positional
    else:
        return False
    return not paths or not all(p not in ROOT_LIKE and allowed_path(p) for p in paths)


def bash_blocked(command: str) -> str | None:
    command = strip_root(command)
    if names_package(command):
        return MESSAGE
    for segment in SEGMENT_SPLIT.split(command):
        if scans_root(tokens_of(segment)):
            return (
                "Recursive searches must name an allowed directory, for example "
                "`grep -rn R012 tests/`. " + MESSAGE
            )
    return None


def blocked(tool_name: str, tool_input: dict[str, object]) -> str | None:
    if tool_name in ("Read", "Grep", "Glob"):
        return tool_blocked(tool_name, tool_input)
    if tool_name == "Bash":
        return bash_blocked(str(tool_input.get("command", "")))
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    message = blocked(payload.get("tool_name", ""), payload.get("tool_input") or {})
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
