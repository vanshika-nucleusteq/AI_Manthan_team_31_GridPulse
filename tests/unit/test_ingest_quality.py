"""Ingest and quality on crafted landing files: schema detection, each rule, precedence, reruns."""

from __future__ import annotations

import gzip
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import orjson
import pyarrow.parquet as pq
import pytest

from gridpulse.common.lake import PART_FILE, Lake, lake_from_config
from gridpulse.ingest.bronze import ingest
from gridpulse.ingest.landing import arrival_time
from gridpulse.quality.rules import checked_rows, quality

DS = date(2026, 8, 1)
BASE = datetime(2026, 7, 31, 18, 30, tzinfo=UTC)  # 00:00 IST on DS
FILE = "F01_h20260731T1830Z_a20260801T0005Z.jsonl.gz"  # arrives 05:35 IST on DS
MASTER = """meter_id,feeder_id,zone_id,meter_type,reporting_unit,register_max_kwh,install_date
MTR-00001,F01,Z1,residential,Wh,100000,2021-01-01
MTR-00002,F01,Z1,commercial,kWh,100000,2022-01-01
MTR-00003,F01,Z1,residential,Wh,100000,2023-01-01
"""


def ts(k: int, seconds: int = 0) -> str:
    return (BASE + timedelta(minutes=15 * k, seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def v1(meter: str, k: int, wh: float, status: str = "OK") -> dict:
    return {"meter_id": meter, "ts": ts(k), "energy_wh": wh, "status": status}


def v2(meter: str, k: int, energy: float, unit: str | None = "Wh", **extra: object) -> dict:
    msg = {
        "meter_id": meter,
        "ts": ts(k),
        "energy": energy,
        "unit": unit,
        "status": "OK",
        "voltage": 231.0,
        "firmware_version": "2.4.1",
    }
    if unit is None:
        del msg["unit"]
    return {**msg, **extra}


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lake:
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path))
    (tmp_path / "meter_master.csv").write_text(MASTER, encoding="utf-8")
    return lake_from_config()


def land(lake: Lake, lines: list, name: str = FILE, payload: bytes | None = None) -> None:
    folder = lake.landing / f"arrival_date={DS}" / "feeder=F01"
    folder.mkdir(parents=True, exist_ok=True)
    if payload is None:
        text = "\n".join(
            line if isinstance(line, str) else orjson.dumps(line).decode() for line in lines
        )
        payload = gzip.compress((text + "\n").encode())
    (folder / name).write_bytes(payload)


def run(lake: Lake) -> list[dict]:
    ingest(DS, lake)
    return checked_rows(DS, lake).to_pylist()


def rule_of(rows: list[dict], meter: str, k: int) -> str | None:
    return next(r["rule"] for r in rows if r["meter_id"] == meter and r["ts_text"] == ts(k))


def bronze(lake: Lake) -> list[dict]:
    return pq.read_table(lake.bronze(DS) / PART_FILE).to_pylist()


def test_v1_v2_detected_and_version_recorded(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000), v2("MTR-00003", 0, 2_000_000)])
    rows = {r["meter_id"]: r for r in (ingest(DS, lake) and bronze(lake))}
    assert (rows["MTR-00001"]["schema_version"], rows["MTR-00001"]["version_source"]) == (
        1,
        "detected",
    )
    assert (rows["MTR-00003"]["schema_version"], rows["MTR-00003"]["energy_unit"]) == (2, "Wh")
    assert all(r["raw_json"] and r["source_file"].endswith(FILE) for r in rows.values())


def test_explicit_schema_version_wins(lake: Lake) -> None:
    land(lake, [{**v1("MTR-00001", 0, 1_000_000), "schema_version": 1, "voltage": 230.0}])
    ingest(DS, lake)
    (row,) = bronze(lake)
    assert (row["schema_version"], row["version_source"]) == (1, "explicit")


def test_missing_unit_falls_back_to_master(lake: Lake) -> None:
    land(lake, [v2("MTR-00002", 0, 1234.5, unit=None), v1("MTR-00001", 0, 1_234_500)])
    rows = {r["meter_id"]: r for r in run(lake)}
    assert rows["MTR-00002"]["rule"] is None
    assert rows["MTR-00002"]["unit_source_resolved"] == "master"
    assert (
        float(rows["MTR-00002"]["energy_kwh"]) == float(rows["MTR-00001"]["energy_kwh"]) == 1234.5
    )


def test_unknown_meter_quarantined(lake: Lake) -> None:
    land(lake, [v1("MTR-09001", 0, 1_000_000)])
    assert rule_of(run(lake), "MTR-09001", 0) == "UNKNOWN_METER"


def test_unknown_meter_without_unit_is_unknown_meter_not_bad_unit(lake: Lake) -> None:
    land(lake, [v2("MTR-09002", 0, 12.5, unit=None)])
    assert rule_of(run(lake), "MTR-09002", 0) == "UNKNOWN_METER"


def test_unknown_unit_quarantined_as_bad_unit(lake: Lake) -> None:
    land(lake, [v2("MTR-00003", 0, 1.2, unit="MWh")])
    assert rule_of(run(lake), "MTR-00003", 0) == "BAD_UNIT"


def test_negative_reading_quarantined(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, -2500)])
    assert rule_of(run(lake), "MTR-00001", 0) == "NEGATIVE_READING"


def test_status_error_quarantined_as_meter_error(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000, status="ERROR")])
    assert rule_of(run(lake), "MTR-00001", 0) == "METER_ERROR"


def test_register_decrease_quarantined(lake: Lake) -> None:
    land(
        lake,
        [v1("MTR-00001", 0, 1_000_000), v1("MTR-00001", 1, 999_000), v1("MTR-00001", 2, 1_002_000)],
    )
    rows = run(lake)
    assert [rule_of(rows, "MTR-00001", k) for k in (0, 1, 2)] == [None, "REGISTER_DECREASED", None]


def test_rollover_allowed(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 99_999_000), v1("MTR-00001", 1, 500, status="ROLLOVER")])
    rows = run(lake)
    assert rule_of(rows, "MTR-00001", 1) is None


def test_conflicting_duplicate_not_flagged_as_decrease(lake: Lake) -> None:
    land(
        lake,
        [
            v1("MTR-00001", 0, 1_000_000),
            v1("MTR-00001", 0, 1_000_004),
            v1("MTR-00001", 1, 1_000_020),
        ],
    )
    assert all(r["rule"] is None for r in run(lake))


def test_previous_reading_comes_from_context_day(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", -1, 1_000_000), v1("MTR-00001", 0, 990_000)])
    assert rule_of(run(lake), "MTR-00001", 0) == "REGISTER_DECREASED"


def test_malformed_line_quarantined_without_crash(lake: Lake) -> None:
    bad = [
        "not json",
        "[1, 2]",
        {"meter_id": "MTR-00001", "ts": ts(1), "status": "OK"},
        {**v1("MTR-00001", 2, 0), "energy_wh": "abc"},
    ]
    land(lake, [v1("MTR-00001", 0, 1_000_000), *bad])
    rows = run(lake)
    reasons = sorted(r["reason"] for r in rows if r["rule"] == "MALFORMED_RECORD")
    assert reasons == [
        "JSON is not an object",
        "energy not numeric: abc",
        "invalid JSON",
        "missing energy",
    ]
    assert rule_of(rows, "MTR-00001", 0) is None


def test_corrupt_file_quarantined(lake: Lake) -> None:
    land(lake, [], payload=b"this is not gzip")
    ingest(DS, lake)
    rows = checked_rows(DS, lake).to_pylist()
    assert [(r["rule"], r["line_no"]) for r in rows] == [("CORRUPT_FILE", 0)]


def test_off_grid_timestamp_quarantined_within_tolerance_kept(lake: Lake) -> None:
    near, far = v1("MTR-00001", 0, 1_000_000), v1("MTR-00003", 0, 1_000_000)
    near["ts"], far["ts"] = ts(0, seconds=45), ts(0, seconds=120)
    land(lake, [near, far])
    rows = {r["meter_id"]: r for r in run(lake)}
    assert rows["MTR-00001"]["rule"] is None
    assert (rows["MTR-00003"]["rule"], rows["MTR-00003"]["reason"]) == (
        "BAD_TIMESTAMP",
        "ts 120 s off the 15-minute grid",
    )


def test_naive_timestamp_quarantined(lake: Lake) -> None:
    msg = {**v1("MTR-00001", 0, 1_000_000), "ts": "2026-07-31T18:30:00"}
    land(lake, [msg])
    (row,) = run(lake)
    assert row["rule"] == "BAD_TIMESTAMP" and row["reason"].startswith("ts has no time zone")


def test_offset_timestamp_converted_to_utc(lake: Lake) -> None:
    land(lake, [{**v1("MTR-00001", 1, 1_000_000), "ts": "2026-08-01T00:15:00+05:30"}])
    (row,) = run(lake)
    assert row["rule"] is None and row["ts"] == BASE + timedelta(minutes=15)


def test_ingested_at_comes_from_arrival_stamp(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000)])
    ingest(DS, lake)
    (row,) = bronze(lake)
    assert row["ingested_at"] == arrival_time(FILE) == datetime(2026, 8, 1, 0, 5, tzinfo=UTC)


def test_rerun_same_date_identical_output(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000), v1("MTR-09001", 0, 5), "garbage"])
    first = [ingest(DS, lake), quality(DS, lake)]
    snapshot = [
        pq.read_table(lake.bronze(DS) / PART_FILE),
        pq.read_table(lake.quarantine(DS) / PART_FILE),
    ]
    assert [ingest(DS, lake), quality(DS, lake)] == first
    again = [
        pq.read_table(lake.bronze(DS) / PART_FILE),
        pq.read_table(lake.quarantine(DS) / PART_FILE),
    ]
    assert all(a.equals(b) for a, b in zip(snapshot, again, strict=True))
    assert first[1]["by_rule"] == {"MALFORMED_RECORD": 1, "UNKNOWN_METER": 1}


def test_late_file_after_lookback_found_by_backfill(lake: Lake) -> None:
    late_day = DS + timedelta(days=3)
    folder = lake.landing / f"arrival_date={late_day}" / "feeder=F01"
    folder.mkdir(parents=True)
    payload = orjson.dumps(v1("MTR-09001", 0, 5)) + b"\n"
    (folder / "F01_h20260731T1830Z_a20260803T1900Z.jsonl.gz").write_bytes(gzip.compress(payload))
    ingest(late_day, lake)
    daily = quality(late_day, lake)
    assert daily["by_rule"] == {}
    backfill = quality(DS, lake)
    assert backfill["by_rule"] == {"UNKNOWN_METER": 1}


def test_missing_landing_folder_fails_instead_of_emptying_bronze(lake: Lake) -> None:
    land(lake, [v1("MTR-00001", 0, 1_000_000)])
    ingest(DS, lake)
    for path in sorted(lake.landing.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    with pytest.raises(FileNotFoundError, match="refusing to rebuild bronze"):
        ingest(DS, lake)
    assert len(bronze(lake)) == 1  # the good partition is untouched
