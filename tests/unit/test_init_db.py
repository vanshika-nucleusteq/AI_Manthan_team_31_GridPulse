"""init_db: SQL files run in name order; seeding is skipped when the master CSV is missing."""

from __future__ import annotations

from pathlib import Path

from gridpulse.common import db
from gridpulse.publish.init_db import UPSERT, run_sql_files, seed_meter_master, sql_files


class RecordingConn:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


def test_init_db_runs_sql_files_in_name_order(tmp_path: Path) -> None:
    for name in ("020_gold.sql", "010_meter_master.sql", "100_ops.sql"):
        (tmp_path / name).write_text(f"-- {name}", encoding="utf-8")
    conn = RecordingConn()
    run_sql_files(conn, sql_files(tmp_path))
    assert conn.statements == ["-- 010_meter_master.sql", "-- 020_gold.sql", "-- 100_ops.sql"]


def test_seed_skipped_when_master_csv_missing(tmp_path: Path) -> None:
    conn = RecordingConn()
    assert seed_meter_master(conn, tmp_path / "meter_master.csv") is None
    assert conn.statements == []


def test_meter_master_upsert_is_keyed_on_meter_id() -> None:
    assert "ON CONFLICT (meter_id) DO UPDATE" in UPSERT


def test_sqlalchemy_url_uses_psycopg3_driver(monkeypatch) -> None:
    monkeypatch.setenv("GRIDPULSE_DB_URL", "postgresql://u:p@postgres:5432/gridpulse")
    assert db.sqlalchemy_url() == "postgresql+psycopg://u:p@postgres:5432/gridpulse"
