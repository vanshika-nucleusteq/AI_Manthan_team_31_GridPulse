"""Rollback one IST day of gold to the version a run replaced, then republish that day.

Run: python -m gridpulse.maintenance.rollback --date 2026-08-14 [--run-id manual__2026-08-14]
The archive under run_id=X holds what run X overwrote, so restoring it undoes run X. The version
being replaced goes to run_id=rolled_back__X, so a rollback can itself be undone.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

from gridpulse.aggregate.run import part_name
from gridpulse.aggregate.tables import TABLES
from gridpulse.common.lake import Lake, lake_from_config


def latest_run(lake: Lake, day: date) -> str | None:
    """Most recently archived run that holds any partition of this day."""
    root = lake.root / "_archive"
    candidates = (
        [p.parent for p in root.glob(f"*/run_id=*/date={day.isoformat()}") if p.is_dir()]
        if root.exists()
        else []
    )
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return newest.name.removeprefix("run_id=")


def restore(lake: Lake, day: date, run_id: str) -> list[str]:
    restored = []
    for table in TABLES:
        part = part_name(table, day.replace(day=1) if table.partition == "month" else day)
        source = lake.archive(table.name, run_id, part)
        if not source.exists():
            continue
        target = lake.gold(table.name, part)
        if target.exists():
            undo = lake.archive(table.name, f"rolled_back__{run_id}", part)
            if undo.exists():
                import shutil

                shutil.rmtree(undo)
            undo.parent.mkdir(parents=True, exist_ok=True)
            target.rename(undo)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        restored.append(f"{table.name}/{part}")
    return restored


def rollback(day: date, run_id: str | None = None, lake: Lake | None = None) -> dict[str, Any]:
    lake = lake or lake_from_config()
    run_id = run_id or latest_run(lake, day)
    if run_id is None:
        raise ValueError(f"no archived gold for {day}; nothing to roll back")
    restored = restore(lake, day, run_id)
    if not restored:
        raise ValueError(f"run {run_id} archived nothing for {day}")
    from gridpulse.publish.postgres import publish

    published = publish(day, lake, days=[day], months=[day.replace(day=1)])
    return {
        "step": "rollback",
        "date": day.isoformat(),
        "run_id": run_id,
        "restored": restored,
        "published_rows": published["rows"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gridpulse.maintenance.rollback", description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(rollback(args.date, args.run_id), default=str))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
