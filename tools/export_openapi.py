"""Export the FastAPI OpenAPI schema to web/openapi.json (use --check to verify freshness)."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from server.app import create_app

OUT = Path(__file__).resolve().parent.parent / "web" / "openapi.json"


def render_schema() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(dev_mode=True, reports_dir=tmp)
        schema = app.openapi()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if the file is out of date")
    args = ap.parse_args()
    text = render_schema()
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT} is out of date; run: uv run python tools/export_openapi.py")
            return 1
        return 0
    OUT.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
