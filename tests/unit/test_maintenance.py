"""Compaction, retention, rollback, run logging and the DAG file."""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import duckdb
import pytest

from gridpulse import cli
from gridpulse.common.lake import Lake, lake_from_config
from gridpulse.common.runlog import counts
from gridpulse.maintenance import rollback as rollback_module
from gridpulse.maintenance.compact import compact_leaf
from gridpulse.maintenance.retention import months_back, retention

DS = date(2026, 9, 15)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lake:
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GRIDPULSE_DB_URL", raising=False)
    return lake_from_config()


def write_parquet(path: Path, sql: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    duckdb.execute(f"COPY ({sql}) TO '{path.as_posix()}' (FORMAT parquet)")


def test_compaction_merges_files_into_one_sorted_file(tmp_path: Path) -> None:
    leaf = tmp_path / "zone=Z1"
    for i, meter in enumerate(["MTR-00003", "MTR-00001", "MTR-00002"]):
        write_parquet(
            leaf / f"part-{i}.parquet", f"SELECT '{meter}' AS meter_id, {i} AS interval_start"
        )
    assert compact_leaf(duckdb.connect(), leaf, "meter_id, interval_start") == (3, 1)
    rows = duckdb.sql(
        f"SELECT meter_id FROM read_parquet('{leaf.as_posix()}/*.parquet')"
    ).fetchall()
    assert [r[0] for r in rows] == ["MTR-00001", "MTR-00002", "MTR-00003"]
    assert [p.name for p in leaf.glob("*.parquet")] == ["part-0.parquet"]


def test_compaction_leaves_single_file_partition_alone(tmp_path: Path) -> None:
    write_parquet(tmp_path / "part-0.parquet", "SELECT 1 AS meter_id")
    assert compact_leaf(duckdb.connect(), tmp_path, "meter_id") == (1, 1)


def test_retention_deletes_only_partitions_past_their_rule(lake: Lake) -> None:
    keep_raw, drop_raw = (
        lake.landing / "arrival_date=2026-08-20",
        lake.landing / "arrival_date=2026-08-15",
    )
    keep_hourly = lake.root / "gold" / "consumption_hourly" / "date=2025-09-01"
    drop_hourly = lake.root / "gold" / "consumption_hourly" / "date=2025-08-01"
    keep_daily = lake.root / "gold" / "consumption_daily_zone" / "date=2024-01-01"
    for folder in (keep_raw, drop_raw, keep_hourly, drop_hourly, keep_daily):
        folder.mkdir(parents=True)
    result = retention(DS, lake)
    assert [keep_raw.exists(), drop_raw.exists()] == [True, False]  # raw: 30 days
    assert [keep_hourly.exists(), drop_hourly.exists()] == [True, False]  # hourly: 13 months
    assert keep_daily.exists()  # daily gold is kept
    assert result["deleted_partitions"]["landing"] == 1


def test_months_back_handles_year_boundary() -> None:
    assert months_back(date(2026, 1, 31), 13) == date(2024, 12, 28)


def test_rollback_restores_archived_gold_and_keeps_undo(
    lake: Lake, monkeypatch: pytest.MonkeyPatch
) -> None:
    day = date(2026, 8, 14)
    gold = lake.gold("consumption_daily_zone", f"date={day}") / "zone=Z1" / "part-0.parquet"
    archived = lake.archive("consumption_daily_zone", "bad_run", f"date={day}")
    write_parquet(gold, "SELECT 'bad' AS version")
    write_parquet(archived / "zone=Z1" / "part-0.parquet", "SELECT 'good' AS version")
    published = {}
    monkeypatch.setattr(
        "gridpulse.publish.postgres.publish",
        lambda ds, lake, days, months: published.update(days=days) or {"rows": {}},
    )
    result = rollback_module.rollback(day, lake=lake)
    assert result["run_id"] == "bad_run" and published["days"] == [day]
    assert duckdb.sql(f"SELECT version FROM '{gold.as_posix()}'").fetchall() == [("good",)]
    undo = lake.archive("consumption_daily_zone", "rolled_back__bad_run", f"date={day}")
    assert duckdb.sql(
        f"SELECT version FROM '{(undo / 'zone=Z1' / 'part-0.parquet').as_posix()}'"
    ).fetchall() == [("bad",)]


def test_rollback_without_archive_is_an_error(lake: Lake) -> None:
    with pytest.raises(ValueError, match="nothing to roll back"):
        rollback_module.rollback(date(2026, 8, 14), lake=lake)


def test_pipeline_runs_counts_per_task() -> None:
    assert counts("quality", {"by_rule": {"UNKNOWN_METER": 3}, "passed_rows": 97}) == (
        100,
        97,
        None,
    )
    assert counts("normalise", {"readings": 90, "exact_dups_dropped": 4}) == (None, 90, 4)
    assert counts("aggregate", {"rows": {"a": 2, "b": 3}}) == (None, 5, None)


def test_failed_step_is_recorded_then_reraised(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(cli, "record", lambda *a, **k: calls.append(a[5]))

    def boom(step, ds):
        raise RuntimeError("disk full")

    monkeypatch.setattr(cli, "run_step", boom)
    with pytest.raises(RuntimeError):
        cli.main(["ingest", "--ds", "2026-08-14"])
    assert calls == ["failed"]


def test_dag_imports_nothing_from_gridpulse_and_runs_every_cli_step_in_order() -> None:
    tree = ast.parse((ROOT / "dags" / "gridpulse_daily.py").read_text(encoding="utf-8"))
    modules = [
        alias.name if isinstance(node, ast.Import) else node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else [node])
    ]
    assert not any(m and m.startswith("gridpulse") for m in modules)
    tasks = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "TASKS"
    )
    assert tasks == list(cli.STEPS)
