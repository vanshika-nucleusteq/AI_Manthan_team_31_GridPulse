"""Record each CLI step in PostgreSQL pipeline_runs (keyed upsert on run_id, task)."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from typing import Any

UPSERT = """
INSERT INTO pipeline_runs (run_id, task, ds, started_at, finished_at, duration_s, status,
                           rows_in, rows_out, duplicates, details)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (run_id, task) DO UPDATE SET
    ds = EXCLUDED.ds, started_at = EXCLUDED.started_at, finished_at = EXCLUDED.finished_at,
    duration_s = EXCLUDED.duration_s, status = EXCLUDED.status, rows_in = EXCLUDED.rows_in,
    rows_out = EXCLUDED.rows_out, duplicates = EXCLUDED.duplicates, details = EXCLUDED.details
"""


def _total(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        numbers = [_total(v) for v in value.values()]
        return sum(n for n in numbers if n is not None) if numbers else None
    return None


def counts(task: str, result: dict[str, Any] | None) -> tuple[int | None, int | None, int | None]:
    """(rows_in, rows_out, duplicates) from a step's result dict."""
    if not result:
        return None, None, None
    if task == "quality":
        quarantined = _total(result.get("by_rule", {})) or 0
        passed = result.get("passed_rows")
        return (passed + quarantined if passed is not None else None), passed, None
    if task == "normalise":
        return None, result.get("readings"), result.get("exact_dups_dropped")
    for key in ("rows", "events", "deleted_partitions", "files_after"):
        if key in result:
            return None, _total(result[key]), None
    return None, None, None


def record(
    run_id: str,
    task: str,
    ds: date,
    started: datetime,
    finished: datetime,
    status: str,
    result: dict[str, Any] | None,
    error: str | None = None,
) -> bool:
    """Best effort: never hides the step's own outcome. Returns True when the row was written."""
    url = os.environ.get("GRIDPULSE_DB_URL")
    if not url:
        return False
    rows_in, rows_out, duplicates = counts(task, result)
    details = dict(result or {})
    if error:
        details["error"] = error
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=5) as conn:
            conn.execute(
                UPSERT,
                (
                    run_id,
                    task,
                    ds,
                    started,
                    finished,
                    round((finished - started).total_seconds(), 2),
                    status,
                    rows_in,
                    rows_out,
                    duplicates,
                    json.dumps(details, default=str),
                ),
            )
        return True
    except Exception as exc:  # logging must not turn a good step into a failed one
        print(f"warning: pipeline_runs not written: {exc}", file=sys.stderr)
        return False
