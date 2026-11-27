"""Create PostgreSQL tables from db/init/*.sql, then upsert meter_master from its CSV."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import psycopg

from gridpulse.common.db import db_url
from gridpulse.generator.meter_master import MASTER_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[3]
COLUMNS = ", ".join(MASTER_COLUMNS)
UPDATES = ", ".join(f"{c} = EXCLUDED.{c}" for c in MASTER_COLUMNS if c != "meter_id")
UPSERT = (
    f"INSERT INTO meter_master ({COLUMNS}) SELECT {COLUMNS} FROM meter_master_stage "
    f"ON CONFLICT (meter_id) DO UPDATE SET {UPDATES}, updated_at = now()"
)


def sql_dir() -> Path:
    return Path(os.environ.get("GRIDPULSE_SQL_DIR", REPO_ROOT / "db" / "init"))


def master_csv() -> Path:
    return Path(os.environ.get("GRIDPULSE_DATA_DIR", REPO_ROOT / "data")) / "meter_master.csv"


def sql_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.sql"), key=lambda p: p.name)


def run_sql_files(conn: Any, files: list[Path]) -> None:
    for path in files:
        conn.execute(path.read_text(encoding="utf-8"))


def seed_meter_master(conn: Any, csv_path: Path) -> int | None:
    """Keyed upsert on meter_id, so re-seeding never duplicates rows. None if the CSV is missing."""
    if not csv_path.exists():
        return None
    conn.execute(
        "CREATE TEMP TABLE meter_master_stage (LIKE meter_master INCLUDING DEFAULTS) ON COMMIT DROP"
    )
    copy_sql = f"COPY meter_master_stage ({COLUMNS}) FROM STDIN WITH (FORMAT csv, HEADER true)"
    with conn.cursor() as cur, cur.copy(copy_sql) as copy:
        copy.write(csv_path.read_bytes())
    staged = conn.execute("SELECT count(*) FROM meter_master_stage").fetchone()[0]
    conn.execute(UPSERT)
    return int(staged)


def main() -> int:
    files = sql_files(sql_dir())
    with psycopg.connect(db_url()) as conn:
        run_sql_files(conn, files)
        seeded = seed_meter_master(conn, master_csv())
        total = conn.execute("SELECT count(*) FROM meter_master").fetchone()[0]
    print(f"init_db: ran {len(files)} SQL file(s): {', '.join(p.name for p in files)}")
    if seeded is None:
        print(f"init_db: {master_csv()} not found; run make.ps1 generate, then make.ps1 seed")
    else:
        print(f"init_db: upserted {seeded} meters; meter_master now has {total} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
