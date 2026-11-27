"""Lake layout under the data directory, and atomic overwrite of one Parquet partition."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from gridpulse.common.config import load_yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PART_FILE = "part-0.parquet"


@dataclass(frozen=True)
class Lake:
    data_dir: Path
    paths: dict[str, str]

    @property
    def landing(self) -> Path:
        return self.data_dir / self.paths["landing"]

    @property
    def root(self) -> Path:
        return self.data_dir / self.paths["lake"]

    @property
    def meter_master(self) -> Path:
        return self.data_dir / self.paths["meter_master"]

    def bronze(self, arrival_date: date) -> Path:
        return self.root / "bronze" / f"arrival_date={arrival_date.isoformat()}"

    def silver(self, table: str, day: date) -> Path:
        return self.root / "silver" / table / f"date={day.isoformat()}"

    def quarantine(self, day: date) -> Path:
        return self.root / "quarantine" / f"date={day.isoformat()}"


def lake_from_config() -> Lake:
    paths = load_yaml("pipeline")["paths"]
    data_dir = Path(os.environ.get("GRIDPULSE_DATA_DIR") or REPO_ROOT / paths["data_dir"])
    return Lake(data_dir=data_dir, paths=paths)


def sql_path(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def _fresh_tmp(target: Path) -> Path:
    for leftover in (
        target.with_name(target.name + ".tmp"),
        target.with_name(target.name + ".old"),
    ):
        if leftover.exists():
            shutil.rmtree(leftover)
    tmp = target.with_name(target.name + ".tmp")
    tmp.mkdir(parents=True)
    return tmp


def _rename(src: Path, dst: Path, attempts: int = 6) -> None:
    """Rename with retries: on Windows a scanner or a bind mount can hold a new file briefly."""
    for attempt in range(attempts):
        try:
            src.rename(dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.25 * 2**attempt)


def _swap(tmp: Path, target: Path) -> None:
    """Put tmp in place of target. If that fails, the previous version is restored first."""
    old = target.with_name(target.name + ".old")
    if target.exists():
        _rename(target, old)
    try:
        _rename(tmp, target)
    except OSError:
        if old.exists() and not target.exists():
            _rename(old, target)
        raise
    if old.exists():
        shutil.rmtree(old)


def overwrite_partition(con: Any, select_sql: str, target: Path, order_by: str) -> int:
    """Write select_sql to target/part-0.parquet via a temp folder, then swap it in."""
    tmp = _fresh_tmp(target)
    rows = con.execute(
        f"COPY ({select_sql} ORDER BY {order_by}) TO {sql_path(tmp / PART_FILE)} "
        "(FORMAT parquet, COMPRESSION zstd)"
    ).fetchone()[0]
    _swap(tmp, target)
    return int(rows)


def overwrite_partitioned(
    con: Any, select_sql: str, target: Path, order_by: str, partition_by: str
) -> int:
    """Like overwrite_partition, with Hive sub-folders (e.g. zone=Z1/) swapped in as one unit, so
    a sub-partition that comes out empty cannot leave stale files behind."""
    tmp = _fresh_tmp(target)
    rows = con.execute(
        f"COPY ({select_sql} ORDER BY {order_by}) TO {sql_path(tmp)} (FORMAT parquet, "
        f"COMPRESSION zstd, PARTITION_BY ({partition_by}), FILENAME_PATTERN 'part-{{i}}', "
        "OVERWRITE_OR_IGNORE true)"
    ).fetchone()[0]
    _swap(tmp, target)
    return int(rows)


def existing_parts(folders: list[Path]) -> list[str]:
    return [(f / PART_FILE).as_posix() for f in folders if (f / PART_FILE).exists()]
