"""Playtest reports: one JSON file per report, later turned into a regression test."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_REPORTS_DIR = Path("playtest/reports")


def new_report_id(now: datetime | None = None) -> str:
    """Sortable unique id: UTC timestamp plus a short random suffix (filename-safe)."""
    now = now or datetime.now(UTC)
    return f"{now:%Y%m%dT%H%M%S}-{secrets.token_hex(3)}"


def write_report(directory: Path, payload: dict[str, Any]) -> tuple[str, Path]:
    """Write `payload` (plus id and created_at) to `<directory>/<id>.json`."""
    now = datetime.now(UTC)
    report_id = new_report_id(now)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{report_id}.json"
    body = {"report_id": report_id, "created_at": now.isoformat(), **payload}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return report_id, path
