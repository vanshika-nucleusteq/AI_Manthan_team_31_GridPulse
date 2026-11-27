"""Gold aggregates and billing on crafted 3-day histories run through ingest and normalise."""

from __future__ import annotations

import gzip
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import orjson
import pytest

from gridpulse.aggregate.reconcile import reconcile
from gridpulse.aggregate.run import aggregate
from gridpulse.aggregate.tables import BY_NAME
from gridpulse.common.lake import Lake, lake_from_config
from gridpulse.ingest.bronze import ingest
from gridpulse.normalise.readings import normalise
from gridpulse.publish.postgres import statements

DS = date(2026, 8, 3)
BASE = datetime(2026, 8, 2, 18, 30, tzinfo=UTC)  # 00:00 IST on DS
FIRST_K = -2 * 96  # 00:00 IST on 1 Aug, the first day of the window and of the month
MASTER = """meter_id,feeder_id,zone_id,meter_type,reporting_unit,register_max_kwh,install_date
MTR-00001,F01,Z1,residential,Wh,100000,2021-01-01
MTR-00002,F01,Z1,residential,Wh,100000,2021-01-01
MTR-00003,F02,Z1,residential,Wh,1000,2021-01-01
"""


def ts(k: int) -> str:
    return (BASE + timedelta(minutes=15 * k)).strftime("%Y-%m-%dT%H:%M:%SZ")


def history(meter: str, start_wh: int, step_wh: int = 100, skip: frozenset[int] = frozenset()):
    """One reading every 15 minutes for the 3 window days, minus the intervals in skip."""
    wh = start_wh
    for k in range(FIRST_K, 96):
        wh += step_wh
        if k not in skip:
            yield {"meter_id": meter, "ts": ts(k), "energy_wh": wh, "status": "OK"}


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lake:
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path))
    (tmp_path / "meter_master.csv").write_text(MASTER, encoding="utf-8")
    return lake_from_config()


def land(lake: Lake, lines: list[dict]) -> None:
    folder = lake.landing / f"arrival_date={DS}" / "feeder=F01"
    folder.mkdir(parents=True, exist_ok=True)
    payload = b"".join(orjson.dumps(line) + b"\n" for line in lines)
    (folder / "F01_h20260802T1830Z_a20260803T1900Z.jsonl.gz").write_bytes(gzip.compress(payload))


def build(lake: Lake, lines: list[dict], run_id: str = "r1") -> dict:
    land(lake, lines)
    ingest(DS, lake)
    normalise(DS, lake)
    return aggregate(DS, lake, run_id=run_id)


def gold(lake: Lake, table: str) -> list[dict]:
    pattern = (lake.root / "gold" / table).as_posix() + "/**/*.parquet"
    rel = duckdb.sql(f"SELECT * FROM read_parquet('{pattern}', hive_partitioning = false)")
    return [dict(zip(rel.columns, row, strict=True)) for row in rel.fetchall()]


def bill(lake: Lake, meter: str) -> dict:
    (row,) = [b for b in gold(lake, "billing_monthly") if b["meter_id"] == meter]
    return row


SKIP_TEN = frozenset(range(10, 20))  # 10 intervals missing on DS -> 86 of 96


def test_gold_daily_equals_silver_sum(lake: Lake) -> None:
    build(lake, [*history("MTR-00001", 1_000_000), *history("MTR-00002", 2_000_000, skip=SKIP_TEN)])
    rows = reconcile(DS - timedelta(days=2), DS, lake)
    assert len(rows) == 3 and all(r["max_abs_diff"] == 0 for r in rows)


def test_day_under_90pct_flagged(lake: Lake) -> None:
    almost = frozenset(range(10, 19))  # 87 of 96 = 90.6%: above 90, not flagged
    build(
        lake,
        [
            *history("MTR-00001", 1_000_000, skip=almost),
            *history("MTR-00002", 2_000_000, skip=SKIP_TEN),
        ],
    )
    day = {r["meter_id"]: r for r in gold(lake, "consumption_daily_meter") if r["local_date"] == DS}
    assert (day["MTR-00001"]["intervals_present"], day["MTR-00001"]["quality_flag"]) == (87, False)
    assert (day["MTR-00002"]["completeness_pct"], day["MTR-00002"]["quality_flag"]) == (
        Decimal("89.58"),
        True,
    )


def test_silent_meter_counts_as_zero_completeness(lake: Lake) -> None:
    build(lake, list(history("MTR-00001", 1_000_000)))
    day = {r["meter_id"]: r for r in gold(lake, "consumption_daily_meter") if r["local_date"] == DS}
    assert (day["MTR-00002"]["intervals_present"], day["MTR-00002"]["quality_flag"]) == (0, True)
    zone = [r for r in gold(lake, "consumption_daily_zone") if r["local_date"] == DS][0]
    assert (zone["meters_reporting"], zone["meters_expected"]) == (1, 3)


def test_hourly_bucket_uses_ist_hour(lake: Lake) -> None:
    build(lake, list(history("MTR-00001", 1_000_000)))
    hours = {r["hour_start"]: r for r in gold(lake, "consumption_hourly") if r["local_date"] == DS}
    first = hours[BASE]  # 00:00 IST = 18:30 UTC, not 18:00 or 19:00 UTC
    assert (first["intervals_present"], first["kwh"], first["has_gap"]) == (
        4,
        Decimal("0.4"),
        False,
    )
    assert len(hours) == 24


def test_billing_month_uses_ist_boundary(lake: Lake) -> None:
    build(lake, list(history("MTR-00001", 1_000_000)))
    row = bill(lake, "MTR-00001")
    assert row["month"] == date(2026, 8, 1) and row["readings"] == 3 * 96  # 31 Jul 18:30Z is August


def test_billing_register_diff_matches_interval_sum_without_gaps(lake: Lake) -> None:
    build(lake, list(history("MTR-00001", 1_000_000)))
    row = bill(lake, "MTR-00001")
    assert row["kwh"] == row["sum_of_intervals_kwh"] == Decimal("28.7")  # 287 steps of 0.1 kWh
    assert (row["start_reading_source"], row["billing_status"]) == ("first_in_month", "READY")


def test_billing_with_gap_still_matches_and_flagged_day_sets_review(lake: Lake) -> None:
    build(lake, list(history("MTR-00002", 2_000_000, skip=SKIP_TEN)))
    row = bill(lake, "MTR-00002")
    assert row["kwh"] == row["sum_of_intervals_kwh"] == Decimal("28.7")
    assert (row["days_flagged"], row["billing_status"]) == (1, "REVIEW")


def test_rollover_in_month_billed_correctly(lake: Lake) -> None:
    max_wh = 1_000 * 1000  # MTR-00003 register_max_kwh = 1000
    lines = list(history("MTR-00003", max_wh - 20_000))
    wrap = next(i for i, line in enumerate(lines) if line["energy_wh"] >= max_wh)
    for i, line in enumerate(lines[wrap:]):
        line["energy_wh"] -= max_wh
        line["status"] = "ROLLOVER" if i == 0 else "OK"
    build(lake, lines)
    row = bill(lake, "MTR-00003")
    assert row["kwh"] == row["sum_of_intervals_kwh"] == Decimal("28.7")
    assert row["billing_status"] == "READY"


def test_replaced_gold_partition_moved_to_archive(lake: Lake) -> None:
    build(lake, list(history("MTR-00001", 1_000_000)), run_id="first")
    aggregate(DS, lake, run_id="second")
    archived = lake.archive("consumption_daily_zone", "second", f"date={DS}")
    assert archived.is_dir() and any(archived.rglob("*.parquet"))
    assert not lake.archive("consumption_daily_zone", "first", f"date={DS}").exists()


def test_rerun_same_date_identical_output(lake: Lake) -> None:
    first = build(lake, list(history("MTR-00001", 1_000_000)))
    snapshot = {t: gold(lake, t) for t in BY_NAME}
    assert aggregate(DS, lake, run_id="r1") == first
    assert {t: gold(lake, t) for t in BY_NAME} == snapshot


def test_publish_deletes_partition_then_copies_explicit_columns() -> None:
    delete, copy = statements(BY_NAME["billing_monthly"])
    assert delete == "DELETE FROM billing_monthly WHERE month = %s"
    assert copy.startswith("COPY billing_monthly (meter_id, feeder_id, zone_id, month, kwh,")
    delete, _ = statements(BY_NAME["consumption_hourly"])
    assert delete == "DELETE FROM consumption_hourly WHERE local_date = %s"
