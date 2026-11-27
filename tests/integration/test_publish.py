"""Publish integration: stack up and gold built for 2026-08-14. Run: pytest -m integration."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import psycopg
import pytest

from gridpulse.aggregate.run import part_name, window
from gridpulse.aggregate.tables import TABLES
from gridpulse.common.lake import lake_from_config
from gridpulse.ingest.bronze import connect
from gridpulse.publish.postgres import publish

pytestmark = pytest.mark.integration
DS = date(2026, 8, 14)
ROOT = Path(__file__).resolve().parents[2]


def _db_url() -> str:
    if os.environ.get("GRIDPULSE_DB_URL"):
        return os.environ["GRIDPULSE_DB_URL"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GRIDPULSE_DB_URL="):
                return line.split("=", 1)[1]
    pytest.skip("GRIDPULSE_DB_URL not set and no .env; run make.ps1 up first")


def _pg_counts(url: str) -> dict[str, int]:
    days, months = window(DS)
    counts = {}
    with psycopg.connect(url, connect_timeout=3) as pg:
        for t in TABLES:
            key, values = ("month", months) if t.partition == "month" else ("local_date", days)
            counts[t.name] = pg.execute(
                f"SELECT count(*) FROM {t.name} WHERE {key} = ANY(%s)", (values,)
            ).fetchone()[0]
    return counts


def _parquet_counts() -> dict[str, int]:
    lake, duck = lake_from_config(), connect()
    days, months = window(DS)
    counts = {}
    for t in TABLES:
        files = [
            f.as_posix()
            for key in (months if t.partition == "month" else days)
            for f in sorted(lake.gold(t.name, part_name(t, key)).rglob("*.parquet"))
        ]
        counts[t.name] = (
            duck.sql(f"SELECT count(*) FROM read_parquet({files!r})").fetchall()[0][0]
            if files
            else 0
        )
    return counts


def test_publish_twice_leaves_same_rows_as_gold_parquet() -> None:
    url = _db_url()
    expected = _parquet_counts()
    if not expected["billing_monthly"]:
        pytest.skip("no gold for 2026-08-14; run aggregate first")
    try:
        publish(DS, conninfo=url)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    first = _pg_counts(url)
    publish(DS, conninfo=url)
    assert _pg_counts(url) == first == expected
