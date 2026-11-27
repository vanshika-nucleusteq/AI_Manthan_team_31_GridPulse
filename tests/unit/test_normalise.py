"""Normalise on crafted meter histories: units, gaps, dedup, order, rollover, IST days."""

from __future__ import annotations

import gzip
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import orjson
import pytest

from gridpulse.common.lake import Lake, lake_from_config
from gridpulse.ingest.bronze import ingest, to_arrow
from gridpulse.normalise.readings import normalise

DS = date(2026, 8, 3)
BASE = datetime(2026, 8, 2, 18, 30, tzinfo=UTC)  # 00:00 IST on DS
MASTER = """meter_id,feeder_id,zone_id,meter_type,reporting_unit,register_max_kwh,install_date
MTR-00001,F01,Z1,residential,Wh,100000,2021-01-01
MTR-00002,F01,Z1,commercial,kWh,100000,2022-01-01
"""


def ts(k: int, seconds: int = 0) -> str:
    return (BASE + timedelta(minutes=15 * k, seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def v1(meter: str, k: int, wh: int, status: str = "OK") -> dict:
    return {"meter_id": meter, "ts": ts(k), "energy_wh": wh, "status": status}


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lake:
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path))
    (tmp_path / "meter_master.csv").write_text(MASTER, encoding="utf-8")
    return lake_from_config()


def land(lake: Lake, lines: list, arrival: str = "20260803T1000") -> None:
    folder = lake.landing / f"arrival_date={DS}" / "feeder=F01"
    folder.mkdir(parents=True, exist_ok=True)
    payload = b"".join(orjson.dumps(line) + b"\n" for line in lines)
    (folder / f"F01_h20260802T1830Z_a{arrival}Z.jsonl.gz").write_bytes(gzip.compress(payload))


def silver(lake: Lake, table: str) -> list[dict]:
    pattern = (lake.root / "silver" / table).as_posix() + "/*/*/*.parquet"
    rel = duckdb.sql(f"SELECT * FROM read_parquet('{pattern}', hive_partitioning = true)")
    return to_arrow(rel).to_pylist()


def run(lake: Lake) -> dict:
    ingest(DS, lake)
    return normalise(DS, lake)


def reading(rows: list[dict], meter: str, k: int) -> dict:
    (row,) = [
        r
        for r in rows
        if r["meter_id"] == meter and r["interval_start"] == BASE + timedelta(minutes=15 * k)
    ]
    return row


def gap_cells(lake: Lake, meter: str) -> dict[datetime, str]:
    return {g["interval_start"]: g["cause"] for g in silver(lake, "gaps") if g["meter_id"] == meter}


def test_wh_divided_by_1000(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_234_567)])
    run(lake)
    assert reading(silver(lake, "readings"), "MTR-00001", 0)["register_kwh"] == Decimal("1234.567")


def test_v2_kwh_unchanged(lake: Lake) -> None:
    msg = {
        "meter_id": "MTR-00002",
        "ts": ts(0),
        "energy": 1234.567,
        "unit": "kWh",
        "status": "OK",
        "voltage": 230.1,
        "firmware_version": "2.5.0",
    }
    land(lake, [msg])
    run(lake)
    row = reading(silver(lake, "readings"), "MTR-00002", 0)
    assert (row["register_kwh"], row["schema_version"]) == (Decimal("1234.567"), 2)


def test_missing_interval_written_to_gaps(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000), v1("MTR-00001", 2, 1_000_300)])
    run(lake)
    assert gap_cells(lake, "MTR-00001")[BASE + timedelta(minutes=15)] == "not_received"


def test_gap_never_filled(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000), v1("MTR-00001", 2, 1_000_300)])
    run(lake)
    rows = [r for r in silver(lake, "readings") if r["meter_id"] == "MTR-00001"]
    assert [r["interval_start"] for r in rows] == [BASE, BASE + timedelta(minutes=30)]
    assert reading(rows, "MTR-00001", 2)["consumption_kwh"] == Decimal("0.3")


def test_reading_after_gap_spans_two_intervals(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000), v1("MTR-00001", 2, 1_000_300)])
    run(lake)
    row = reading(silver(lake, "readings"), "MTR-00001", 2)
    assert (row["spans_gap"], row["intervals_spanned"]) == (True, 2)


def test_exact_duplicate_dropped(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000)], arrival="20260803T1000")
    land(lake, [v1("MTR-00001", 0, 1_000_000)], arrival="20260803T1015")
    stats = run(lake)
    row = reading(silver(lake, "readings"), "MTR-00001", 0)
    assert (row["dup_conflict"], row["exact_dups_dropped"], stats["exact_dups_dropped"]) == (
        False,
        1,
        1,
    )


def test_conflicting_duplicate_keeps_latest_and_flags(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000)], arrival="20260803T1000")
    land(lake, [v1("MTR-00001", 0, 1_000_004)], arrival="20260803T1015")
    run(lake)
    row = reading(silver(lake, "readings"), "MTR-00001", 0)
    assert (row["register_kwh"], row["dup_conflict"], row["dup_count"]) == (
        Decimal("1000.004"),
        True,
        1,
    )
    assert row["source_file"].endswith("_a20260803T1015Z.jsonl.gz")


def test_out_of_order_readings_sorted_before_delta(lake: Lake) -> None:
    land(
        lake,
        [
            v1("MTR-00001", 2, 1_000_500),
            v1("MTR-00001", 0, 1_000_000),
            v1("MTR-00001", 1, 1_000_100),
        ],
    )
    run(lake)
    rows = silver(lake, "readings")
    assert [reading(rows, "MTR-00001", k)["consumption_kwh"] for k in (1, 2)] == [
        Decimal("0.1"),
        Decimal("0.4"),
    ]


def test_rollover_consumption_uses_register_max(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 99_999_000), v1("MTR-00001", 1, 500, status="ROLLOVER")])
    run(lake)
    row = reading(silver(lake, "readings"), "MTR-00001", 1)
    assert (row["consumption_kwh"], row["is_rollover"]) == (Decimal("1.5"), True)


def test_rollover_status_without_wrap_uses_plain_delta(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000), v1("MTR-00001", 1, 1_000_200, status="ROLLOVER")])
    run(lake)
    row = reading(silver(lake, "readings"), "MTR-00001", 1)
    assert (row["consumption_kwh"], row["is_rollover"], row["rollover_without_wrap"]) == (
        Decimal("0.2"),
        False,
        True,
    )


def test_quarantined_interval_is_a_gap_with_cause(lake: Lake) -> None:
    land(
        lake, [v1("MTR-00001", 0, 1_000_000), v1("MTR-00001", 1, -5), v1("MTR-00001", 2, 1_000_300)]
    )
    run(lake)
    assert (
        gap_cells(lake, "MTR-00001")[BASE + timedelta(minutes=15)] == "quarantined:NEGATIVE_READING"
    )
    row = reading(silver(lake, "readings"), "MTR-00001", 2)
    assert (row["consumption_kwh"], row["intervals_spanned"]) == (Decimal("0.3"), 2)


def test_interval_at_1830_utc_belongs_to_next_ist_day(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000)])
    run(lake)
    assert reading(silver(lake, "readings"), "MTR-00001", 0)["local_date"] == DS
    assert (lake.silver("readings", DS) / "zone=Z1").is_dir()


def test_reading_snapped_across_ist_midnight_lands_next_day(lake: Lake) -> None:
    land(lake, [{**v1("MTR-00001", 0, 1_000_000), "ts": ts(0, seconds=-20)}])
    run(lake)
    row = reading(silver(lake, "readings"), "MTR-00001", 0)
    assert row["local_date"] == DS and row["ts"] == BASE - timedelta(seconds=20)


def test_first_window_reading_uses_context_day(lake: Lake) -> None:
    first_k = -2 * 96  # 00:00 IST on DS-2, the first day of the window
    land(lake, [v1("MTR-00001", first_k - 1, 1_000_000), v1("MTR-00001", first_k, 1_000_250)])
    run(lake)
    row = reading(silver(lake, "readings"), "MTR-00001", first_k)
    assert (row["has_previous"], row["consumption_kwh"], row["local_date"]) == (
        True,
        Decimal("0.25"),
        DS - timedelta(days=2),
    )
    assert all(r["local_date"] >= DS - timedelta(days=2) for r in silver(lake, "readings"))


def test_rerun_same_date_identical_output(lake: Lake) -> None:
    land(
        lake, [v1("MTR-00001", 0, 1_000_000), v1("MTR-00001", 2, 1_000_300), v1("MTR-00002", 0, 7)]
    )
    first = run(lake)
    snapshot = (silver(lake, "readings"), silver(lake, "gaps"))
    assert normalise(DS, lake) == first
    assert (silver(lake, "readings"), silver(lake, "gaps")) == snapshot


def test_failed_swap_restores_previous_partition(
    lake: Lake, monkeypatch: pytest.MonkeyPatch
) -> None:
    from gridpulse.common import lake as lake_module

    land(lake, [v1("MTR-00001", 0, 1_000_000)])
    run(lake)
    before = silver(lake, "readings")
    real_rename = Path.rename

    def deny_tmp(self: Path, target: Path) -> Path:
        if self.name.endswith(".tmp"):
            raise PermissionError("locked")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", deny_tmp)
    monkeypatch.setattr(lake_module.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        normalise(DS, lake)
    monkeypatch.setattr(Path, "rename", real_rename)
    assert silver(lake, "readings") == before
