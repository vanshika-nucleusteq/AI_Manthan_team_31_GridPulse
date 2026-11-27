"""Anomaly checks on crafted histories: spike, tamper and outage thresholds, merging and ids."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pytest

from gridpulse.anomalies.run import anomalies, detect
from gridpulse.common.lake import Lake, lake_from_config
from gridpulse.ingest.bronze import connect

DAY0 = date(2026, 8, 1)
IST_MIDNIGHT = datetime(2026, 7, 31, 18, 30, tzinfo=UTC)  # 00:00 IST on DAY0


def hour(day: int, h: int) -> datetime:
    return IST_MIDNIGHT + timedelta(days=day, hours=h)


def tables(con, hourly=(), daily=(), gaps=(), feeders=(("F01", 5),)) -> None:
    h = pa.table(
        {
            "meter_id": pa.array([r[0] for r in hourly], pa.string()),
            "feeder_id": pa.array([r[1] for r in hourly], pa.string()),
            "zone_id": pa.array(["Z1"] * len(hourly), pa.string()),
            "local_date": pa.array([r[2] for r in hourly], pa.date32()),
            "hour_start": pa.array([r[3] for r in hourly], pa.timestamp("us", tz="UTC")),
            "kwh": pa.array([r[4] for r in hourly], pa.float64()),
            "intervals_present": pa.array([r[5] for r in hourly], pa.int64()),
            "has_gap": pa.array([r[6] for r in hourly], pa.bool_()),
        }
    )
    con.register("h_src", h)
    con.execute(
        "CREATE TEMP TABLE h AS SELECT * REPLACE (CAST(kwh AS DECIMAL(18, 6)) AS kwh) FROM h_src"
    )
    d = pa.table(
        {
            "meter_id": pa.array([r[0] for r in daily], pa.string()),
            "local_date": pa.array([r[1] for r in daily], pa.date32()),
            "completeness_pct": pa.array([r[2] for r in daily], pa.float64()),
        }
    )
    con.register("daily", d)
    g = pa.table(
        {
            "meter_id": pa.array([r[0] for r in gaps], pa.string()),
            "feeder_id": pa.array([r[1] for r in gaps], pa.string()),
            "zone_id": pa.array(["Z1"] * len(gaps), pa.string()),
            "interval_start": pa.array([r[2] for r in gaps], pa.timestamp("us", tz="UTC")),
        }
    )
    con.register("g", g)
    con.register(
        "feeder_n",
        pa.table({"feeder_id": [f for f, _ in feeders], "meters": [n for _, n in feeders]}),
    )


def events(con) -> list[dict]:
    rel = con.sql("SELECT * FROM events ORDER BY window_start")
    return [dict(zip(rel.columns, row, strict=True)) for row in rel.fetchall()]


def spike_history(
    days: int, target: float, has_gap: bool = False, low: float = 0.5, high: float = 1.5
) -> list[tuple]:
    """Hour 10 IST each day: baseline alternates low / high kWh; the last day carries target."""
    rows = []
    for day in range(days):
        kwh = target if day == days - 1 else (low if day % 2 else high)
        gap = has_gap and day == days - 1
        rows.append(("MTR-00001", "F01", DAY0 + timedelta(days=day), hour(day, 10), kwh, 4, gap))
    return rows


BASELINE_SD = (14 * 0.25 / 13) ** 0.5  # sample sd of 14 values alternating 0.5 / 1.5 (mean 1.0)


def run_detect(con, last_day: date) -> list[dict]:
    detect(con, DAY0, last_day)
    return events(con)


def test_spike_flags_at_z4() -> None:
    con = connect()
    tables(con, hourly=spike_history(15, 1.0 + 4.001 * BASELINE_SD))
    (event,) = run_detect(con, DAY0 + timedelta(days=14))
    assert (event["type"], event["meter_id"], event["window_start"]) == (
        "spike",
        "MTR-00001",
        hour(14, 10),
    )
    assert 4.0 <= float(event["score"]) < 4.01


def test_spike_silent_just_under_z4() -> None:
    con = connect()
    tables(con, hourly=spike_history(15, 1.0 + 3.99 * BASELINE_SD))
    assert run_detect(con, DAY0 + timedelta(days=14)) == []


def test_spike_silent_when_below_2x_baseline_mean() -> None:
    con = connect()
    tables(con, hourly=spike_history(15, 1.5, low=0.99, high=1.01))  # z is about 48, ratio 1.5
    assert run_detect(con, DAY0 + timedelta(days=14)) == []


def test_spike_silent_with_13_baseline_samples() -> None:
    con = connect()
    tables(con, hourly=spike_history(14, 10.0))
    assert run_detect(con, DAY0 + timedelta(days=13)) == []


def test_spike_skips_gap_hours() -> None:
    con = connect()
    tables(con, hourly=spike_history(15, 10.0, has_gap=True))
    assert run_detect(con, DAY0 + timedelta(days=14)) == []


def tamper_rows(zero_hours: int, neighbours_kwh: float = 1.0) -> tuple[list, list]:
    hourly, daily = [], []
    for h in range(72):
        when, day = hour(0, h), DAY0 + timedelta(days=h // 24)
        kwh = 0.0 if 6 <= h < 6 + zero_hours else 0.5
        hourly.append(("MTR-00001", "F01", day, when, kwh, 4, False))
        for n in range(2, 6):
            hourly.append((f"MTR-0000{n}", "F01", day, when, neighbours_kwh, 4, False))
    for d in range(3):
        daily.append(("MTR-00001", DAY0 + timedelta(days=d), 100.0))
    return hourly, daily


def test_tamper_flags_at_48h_zero() -> None:
    con = connect()
    hourly, daily = tamper_rows(48)
    tables(con, hourly=hourly, daily=daily)
    (event,) = run_detect(con, DAY0 + timedelta(days=2))
    assert (event["type"], event["meter_id"]) == ("tamper", "MTR-00001")
    assert (event["window_start"], event["window_end"]) == (hour(0, 6), hour(0, 54))


def test_tamper_silent_at_47h() -> None:
    con = connect()
    hourly, daily = tamper_rows(47)
    tables(con, hourly=hourly, daily=daily)
    assert run_detect(con, DAY0 + timedelta(days=2)) == []


def test_tamper_silent_when_feeder_also_zero() -> None:
    con = connect()
    hourly, daily = tamper_rows(48, neighbours_kwh=0.0)
    tables(con, hourly=hourly, daily=daily)
    assert [e["meter_id"] for e in run_detect(con, DAY0 + timedelta(days=2))] == []


def test_tamper_silent_when_meter_incomplete() -> None:
    con = connect()
    hourly, daily = tamper_rows(48)
    daily[1] = ("MTR-00001", DAY0 + timedelta(days=1), 89.58)
    tables(con, hourly=hourly, daily=daily)
    assert run_detect(con, DAY0 + timedelta(days=2)) == []


def outage_gaps(intervals: list[int], meters: int) -> list[tuple]:
    start = hour(1, 10)
    return [
        (f"MTR-{m:05d}", "F01", start + timedelta(minutes=15 * k))
        for k in intervals
        for m in range(1, meters + 1)
    ]


def test_outage_flags_half_feeder_two_intervals() -> None:
    con = connect()
    tables(con, gaps=outage_gaps([0, 1], meters=5), feeders=(("F01", 10),))
    (event,) = run_detect(con, DAY0 + timedelta(days=1))
    assert (event["type"], event["feeder_id"], float(event["score"])) == ("outage", "F01", 0.5)


def test_outage_silent_single_interval() -> None:
    con = connect()
    tables(con, gaps=outage_gaps([0], meters=10), feeders=(("F01", 10),))
    assert run_detect(con, DAY0 + timedelta(days=1)) == []


def test_outage_silent_below_half_feeder() -> None:
    con = connect()
    tables(con, gaps=outage_gaps([0, 1, 2], meters=4), feeders=(("F01", 10),))
    assert run_detect(con, DAY0 + timedelta(days=1)) == []


def test_consecutive_outage_intervals_merge() -> None:
    con = connect()
    tables(con, gaps=outage_gaps([0, 1, 2, 3, 6, 7], meters=8), feeders=(("F01", 10),))
    found = run_detect(con, DAY0 + timedelta(days=1))
    assert [(e["window_start"], e["window_end"]) for e in found] == [
        (hour(1, 10), hour(1, 11)),
        (hour(1, 11) + timedelta(minutes=30), hour(1, 12)),
    ]


def test_anomaly_id_deterministic() -> None:
    con = connect()
    tables(con, gaps=outage_gaps([0, 1], meters=5), feeders=(("F01", 10),))
    (event,) = run_detect(con, DAY0 + timedelta(days=1))
    raw = f"outage|F01|{hour(1, 10):%Y-%m-%dT%H:%M:%SZ}"
    assert event["anomaly_id"] == hashlib.sha256(raw.encode()).hexdigest()[:16]


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lake:
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path))
    master = ["meter_id,feeder_id,zone_id,meter_type,reporting_unit,register_max_kwh,install_date"]
    master += [f"MTR-{m:05d},F01,Z1,residential,Wh,100000,2021-01-01" for m in range(1, 11)]
    (tmp_path / "meter_master.csv").write_text("\n".join(master) + "\n", encoding="utf-8")
    lake = lake_from_config()
    day = DAY0 + timedelta(days=1)
    folder = lake.silver("gaps", day) / "zone=Z1"
    folder.mkdir(parents=True)
    rows = [(m, "F01", ts, "not_received") for m, _, ts in outage_gaps([0, 1], meters=5)]
    rows += [
        (m, "F01", ts, "quarantined:NEGATIVE_READING") for m, _, ts in outage_gaps([2, 3], meters=9)
    ]
    con = connect()
    con.register(
        "src",
        pa.table(
            {
                "meter_id": [r[0] for r in rows],
                "feeder_id": [r[1] for r in rows],
                "interval_start": pa.array([r[2] for r in rows], pa.timestamp("us", tz="UTC")),
                "local_date": [day] * len(rows),
                "cause": [r[3] for r in rows],
            }
        ),
    )
    con.execute(f"COPY src TO '{(folder / 'part-0.parquet').as_posix()}' (FORMAT parquet)")
    return lake


def test_outage_ignores_quarantined_gaps(lake: Lake) -> None:
    result = anomalies(DAY0 + timedelta(days=1), lake, run_id="t")
    assert result["by_type"] == {
        "outage": 1
    }  # the quarantined intervals 2-3 do not extend or add one


def test_rerun_same_date_identical_output(lake: Lake) -> None:
    ds = DAY0 + timedelta(days=1)
    first = anomalies(ds, lake, run_id="t")
    path = lake.gold("anomalies", f"date={ds}")
    before = sorted(p.read_bytes() for p in path.rglob("*.parquet"))
    assert anomalies(ds, lake, run_id="t") == first
    assert sorted(p.read_bytes() for p in path.rglob("*.parquet")) == before
