#!/usr/bin/env python3
"""PostToolUse: run `ruff format` on a Python file after Claude edits or writes it.

Formatting only (no lint autofix), so an import added in one edit isn't removed before the next
edit uses it. Never blocks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = str((payload.get("tool_input") or {}).get("file_path", ""))
    if not path.endswith(".py") or shutil.which("uv") is None:
        return 0
    subprocess.run(
        ["uv", "run", "--quiet", "ruff", "format", "--quiet", path],
        cwd=ROOT,
        capture_output=True,
        timeout=25,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
