"""Lake layout under the data directory, and atomic overwrite of one Parquet partition."""

from __future__ import annotations

import os
import shutil
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

    def quarantine(self, day: date) -> Path:
        return self.root / "quarantine" / f"date={day.isoformat()}"


def lake_from_config() -> Lake:
    paths = load_yaml("pipeline")["paths"]
    data_dir = Path(os.environ.get("GRIDPULSE_DATA_DIR") or REPO_ROOT / paths["data_dir"])
    return Lake(data_dir=data_dir, paths=paths)


def sql_path(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def overwrite_partition(con: Any, select_sql: str, target: Path, order_by: str) -> int:
    """Write select_sql to target/part-0.parquet via a temp folder, then swap it in."""
    tmp = target.with_name(target.name + ".tmp")
    old = target.with_name(target.name + ".old")
    for leftover in (tmp, old):
        if leftover.exists():
            shutil.rmtree(leftover)
    tmp.mkdir(parents=True)
    rows = con.execute(
        f"COPY ({select_sql} ORDER BY {order_by}) TO {sql_path(tmp / PART_FILE)} "
        "(FORMAT parquet, COMPRESSION zstd)"
    ).fetchone()[0]
    if target.exists():
        target.rename(old)
    tmp.rename(target)
    if old.exists():
        shutil.rmtree(old)
    return int(rows)


def existing_parts(folders: list[Path]) -> list[str]:
    return [(f / PART_FILE).as_posix() for f in folders if (f / PART_FILE).exists()]
