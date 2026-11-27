"""Compaction: rewrite any touched silver or gold partition holding more than one Parquet file into
a single file sorted for row-group skipping, and report file counts before and after."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from gridpulse.aggregate.run import part_name, window
from gridpulse.aggregate.tables import TABLES
from gridpulse.common.lake import Lake, lake_from_config, overwrite_partition
from gridpulse.ingest.bronze import connect

SILVER_ORDER = {"readings": "meter_id, interval_start", "gaps": "meter_id, interval_start"}


def leaves(folder: Path) -> list[Path]:
    """Folders under folder (itself included) that directly hold Parquet files."""
    if not folder.exists():
        return []
    found = {p.parent for p in folder.rglob("*.parquet")}
    return sorted(found)


def compact_leaf(con: Any, leaf: Path, order_by: str) -> tuple[int, int]:
    files = sorted(leaf.glob("*.parquet"))
    if len(files) <= 1:
        return len(files), len(files)
    paths = [f.as_posix() for f in files]
    overwrite_partition(
        con, f"SELECT * FROM read_parquet({paths!r}, hive_partitioning = false)", leaf, order_by
    )
    return len(files), 1


def compact(ds: date, lake: Lake | None = None) -> dict[str, Any]:
    lake = lake or lake_from_config()
    days, months = window(ds)
    con = connect()
    targets: list[tuple[Path, str]] = []
    for day in days:
        targets += [(lake.silver(t, day), order) for t, order in SILVER_ORDER.items()]
        targets += [
            (lake.gold(t.name, part_name(t, day)), t.order_by)
            for t in TABLES
            if t.partition == "date"
        ]
    targets += [
        (lake.gold(t.name, part_name(t, m)), t.order_by)
        for t in TABLES
        if t.partition == "month"
        for m in months
    ]
    before = after = rewritten = 0
    for folder, order_by in targets:
        for leaf in leaves(folder):
            b, a = compact_leaf(con, leaf, order_by)
            before, after = before + b, after + a
            rewritten += int(b > a)
    return {
        "step": "compact",
        "ds": ds.isoformat(),
        "files_before": before,
        "files_after": after,
        "partitions_rewritten": rewritten,
    }
