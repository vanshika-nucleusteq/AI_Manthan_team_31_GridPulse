"""Copy the gold partitions a run touched into PostgreSQL: delete-then-insert, one transaction."""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg

from gridpulse.aggregate.run import part_name, window
from gridpulse.aggregate.tables import TABLES, GoldTable
from gridpulse.common.db import db_url
from gridpulse.common.lake import Lake, lake_from_config
from gridpulse.ingest.bronze import connect


def statements(table: GoldTable) -> tuple[str, str]:
    """DELETE for one partition key, then COPY of the partition's rows (explicit column list)."""
    key = "month" if table.partition == "month" else "local_date"
    columns = ", ".join(table.columns)
    return (
        f"DELETE FROM {table.name} WHERE {key} = %s",
        f"COPY {table.name} ({columns}) FROM STDIN",
    )


def partition_rows(duck: Any, lake: Lake, table: GoldTable, key: date) -> list[tuple]:
    folder = lake.gold(table.name, part_name(table, key))
    files = [f.as_posix() for f in sorted(folder.rglob("*.parquet"))] if folder.exists() else []
    if not files:
        return []
    # Hive detection off: the month=2026-08 folder name would replace the file's DATE column.
    source = f"read_parquet({files!r}, hive_partitioning = false)"
    sql = f"SELECT {', '.join(table.columns)} FROM {source}"
    return duck.sql(sql).fetchall()


def publish(ds: date, lake: Lake | None = None, conninfo: str | None = None) -> dict[str, Any]:
    """Every touched partition is replaced inside one transaction: readers never see half a run,
    and publishing the same run twice leaves the same rows."""
    lake = lake or lake_from_config()
    days, months = window(ds)
    duck = connect()
    rows: dict[str, int] = {}
    with psycopg.connect(conninfo or db_url()) as pg:
        with pg.transaction():
            for table in TABLES:
                delete, copy_sql = statements(table)
                rows[table.name] = 0
                for key in months if table.partition == "month" else days:
                    pg.execute(delete, (key,))
                    data = partition_rows(duck, lake, table, key)
                    if data:
                        with pg.cursor() as cur, cur.copy(copy_sql) as copy:
                            for row in data:
                                copy.write_row(row)
                    rows[table.name] += len(data)
    return {"step": "publish", "ds": ds.isoformat(), "rows": rows}
