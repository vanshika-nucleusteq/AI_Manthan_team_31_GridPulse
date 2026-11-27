"""Retention (plan section 4): delete partitions older than their rule, counted from ds (not the
wall clock, so reruns agree), and the same range from the PostgreSQL copies."""

from __future__ import annotations

import os
import shutil
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from gridpulse.common.config import load_yaml
from gridpulse.common.lake import Lake, lake_from_config


def months_back(ds: date, months: int) -> date:
    total = ds.year * 12 + ds.month - 1 - months
    year, month = divmod(total, 12)
    return date(year, month + 1, min(ds.day, 28))


def old_partitions(root: Path, prefix: str, cutoff: date) -> list[Path]:
    """Folders root/<prefix><date> strictly older than cutoff (unfinished .tmp/.old skipped)."""
    if not root.exists():
        return []
    found = []
    for folder in root.glob(f"{prefix}*"):
        value = folder.name.removeprefix(prefix)
        if folder.is_dir() and len(value) == 10 and date.fromisoformat(value) < cutoff:
            found.append(folder)
    return sorted(found)


def plan(ds: date, lake: Lake) -> dict[str, tuple[list[Path], date]]:
    r = load_yaml("pipeline")["retention"]
    raw = ds - timedelta(days=int(r["raw_days"]))
    bronze = ds - timedelta(days=int(r["bronze_days"]))
    quarantine = ds - timedelta(days=int(r["quarantine_days"]))
    silver = months_back(ds, int(r["silver_months"]))
    hourly = months_back(ds, int(r["hourly_months"]))
    targets = {
        "landing": (old_partitions(lake.landing, "arrival_date=", raw), raw),
        "bronze": (old_partitions(lake.root / "bronze", "arrival_date=", bronze), bronze),
        "quarantine": (old_partitions(lake.root / "quarantine", "date=", quarantine), quarantine),
    }
    for table in ("readings", "gaps"):
        targets[f"silver/{table}"] = (
            old_partitions(lake.root / "silver" / table, "date=", silver),
            silver,
        )
    for table in ("consumption_hourly", "consumption_hourly_feeder", "consumption_hourly_zone"):
        targets[f"gold/{table}"] = (
            old_partitions(lake.root / "gold" / table, "date=", hourly),
            hourly,
        )
    return targets


def old_archives(lake: Lake, days: int) -> list[Path]:
    """Archived run folders older than archive_days by modification time (rollback window)."""
    root = lake.root / "_archive"
    if not root.exists():
        return []
    limit = time.time() - days * 86400
    return sorted(p for p in root.glob("*/run_id=*") if p.stat().st_mtime < limit)


def retention(ds: date, lake: Lake | None = None) -> dict[str, Any]:
    lake = lake or lake_from_config()
    deleted: dict[str, int] = {}
    for name, (folders, _) in plan(ds, lake).items():
        for folder in folders:
            shutil.rmtree(folder)
        deleted[name] = len(folders)
    archives = old_archives(lake, int(load_yaml("pipeline")["retention"]["archive_days"]))
    for folder in archives:
        shutil.rmtree(folder)
    deleted["_archive"] = len(archives)
    pg_deleted = delete_postgres(ds)
    return {
        "step": "retention",
        "ds": ds.isoformat(),
        "deleted_partitions": deleted,
        "postgres_rows_deleted": pg_deleted,
    }


def delete_postgres(ds: date) -> dict[str, int]:
    """Same hourly cutoff in the PostgreSQL copies; skipped when no database is configured."""
    url = os.environ.get("GRIDPULSE_DB_URL")
    if not url:
        return {}
    import psycopg

    cutoff = months_back(ds, int(load_yaml("pipeline")["retention"]["hourly_months"]))
    deleted = {}
    with psycopg.connect(url) as conn:
        for table in ("consumption_hourly", "consumption_hourly_feeder", "consumption_hourly_zone"):
            deleted[table] = conn.execute(
                f"DELETE FROM {table} WHERE local_date < %s", (cutoff,)
            ).rowcount
    return deleted
