"""Late files at the lookback edge, reconciliation from raw to gold, tolerance boundary, replay."""

from __future__ import annotations

import gzip
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import orjson
import pyarrow.parquet as pq
import pytest

from gridpulse.aggregate.run import aggregate
from gridpulse.common.lake import PART_FILE, Lake, lake_from_config
from gridpulse.ingest.bronze import ingest, to_arrow
from gridpulse.normalise.readings import normalise
from gridpulse.quality.rules import checked_rows, quality

D = date(2026, 8, 3)  # reading date of the late reading
BASE = datetime(2026, 8, 2, 18, 30, tzinfo=UTC)  # 00:00 IST on D
MASTER = """meter_id,feeder_id,zone_id,meter_type,reporting_unit,register_max_kwh,install_date
MTR-00001,F01,Z1,residential,Wh,100000,2021-01-01
MTR-00002,F01,Z1,residential,Wh,100000,2021-01-01
"""


def ts(k: int, seconds: int = 0) -> str:
    return (BASE + timedelta(minutes=15 * k, seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def v1(meter: str, k: int, wh: int, status: str = "OK", seconds: int = 0) -> dict:
    return {"meter_id": meter, "ts": ts(k, seconds), "energy_wh": wh, "status": status}


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lake:
    monkeypatch.setenv("GRIDPULSE_DATA_DIR", str(tmp_path))
    (tmp_path / "meter_master.csv").write_text(MASTER, encoding="utf-8")
    return lake_from_config()


def land(lake: Lake, arrival_day: date, stamp: str, lines: list[dict]) -> None:
    """One gateway file in landing/arrival_date=<arrival_day>/; stamp is its UTC arrival time."""
    folder = lake.landing / f"arrival_date={arrival_day}" / "feeder=F01"
    folder.mkdir(parents=True, exist_ok=True)
    payload = b"".join(orjson.dumps(line) + b"\n" for line in lines)
    (folder / f"F01_h20260802T1830Z_a{stamp}Z.jsonl.gz").write_bytes(gzip.compress(payload))


def empty_arrival(lake: Lake, day: date) -> None:
    (lake.landing / f"arrival_date={day}").mkdir(parents=True, exist_ok=True)


def daily_run(lake: Lake, ds: date) -> None:
    """What the DAG does for ds, up to silver."""
    ingest(ds, lake)
    normalise(ds, lake)


def silver(lake: Lake, table: str) -> list[dict]:
    pattern = (lake.root / "silver" / table).as_posix() + "/*/*/*.parquet"
    rel = duckdb.sql(f"SELECT * FROM read_parquet('{pattern}', hive_partitioning = true)")
    return to_arrow(rel).to_pylist()


ON_TIME = [v1("MTR-00001", k, 1_000_000 + 100 * k) for k in (0, 1, 2, 3, 5)]  # k=4 comes late
LATE = [v1("MTR-00001", 4, 1_000_400)]
K4 = BASE + timedelta(minutes=60)


def has_reading(lake: Lake) -> bool:
    return any(
        r["meter_id"] == "MTR-00001" and r["interval_start"] == K4 for r in silver(lake, "readings")
    )


def has_gap(lake: Lake) -> bool:
    return any(
        g["meter_id"] == "MTR-00001" and g["interval_start"] == K4 for g in silver(lake, "gaps")
    )


def test_late_file_inside_lookback_included(lake: Lake) -> None:
    land(lake, D, "20260803T0500", ON_TIME)
    daily_run(lake, D)
    assert has_gap(lake) and not has_reading(lake)
    empty_arrival(lake, D + timedelta(days=1))
    daily_run(lake, D + timedelta(days=1))
    land(lake, D + timedelta(days=2), "20260805T0400", LATE)  # D+2: last day D is in the window
    daily_run(lake, D + timedelta(days=2))
    assert has_reading(lake) and not has_gap(lake)


def test_late_file_after_lookback_needs_backfill(lake: Lake) -> None:
    land(lake, D, "20260803T0500", ON_TIME)
    for offset in range(3):  # daily runs for D, D+1, D+2: the file has not arrived yet
        if offset:
            empty_arrival(lake, D + timedelta(days=offset))
        daily_run(lake, D + timedelta(days=offset))
    land(lake, D + timedelta(days=3), "20260806T0400", LATE)  # D+3: D left the window
    daily_run(lake, D + timedelta(days=3))
    assert has_gap(lake) and not has_reading(lake)  # the daily run cannot fix D
    normalise(D + timedelta(days=2), lake)  # backfill of a ds whose window still holds D
    assert has_reading(lake) and not has_gap(lake)


def test_records_in_equal_kept_plus_quarantined_plus_duplicates(lake: Lake) -> None:
    good = [v1("MTR-00001", k, 1_000_000 + 100 * k) for k in range(4)]
    bad = [v1("MTR-09001", 0, 5), v1("MTR-00002", 0, -1)]
    land(lake, D, "20260803T0500", good + bad)
    land(lake, D, "20260803T0515", [good[1], {**good[2], "energy_wh": good[2]["energy_wh"] + 4}])
    ingest(D, lake)
    records_in = pq.read_table(lake.bronze(D) / PART_FILE).num_rows
    quarantined = sum(quality(D, lake)["by_rule"].values())
    normalise(D, lake)
    kept = silver(lake, "readings")
    duplicates = sum(r["dup_count"] for r in kept)
    assert (records_in, len(kept), quarantined, duplicates) == (8, 4, 2, 2)
    assert records_in == len(kept) + quarantined + duplicates


def history(days: int = 3) -> list[dict]:
    start_k = -(days - 1) * 96  # 00:00 IST on D-2
    return [v1("MTR-00001", k, 1_000_000 + 100 * (k - start_k)) for k in range(start_k, 96)]


def build_gold(lake: Lake, lines: list[dict]) -> None:
    land(lake, D, "20260803T1900", lines)
    ingest(D, lake)
    quality(D, lake)
    normalise(D, lake)
    aggregate(D, lake, run_id="replay")


def test_gold_daily_equals_raw_register_difference(lake: Lake) -> None:
    lines = history()
    build_gold(lake, lines)
    pattern = (lake.root / "gold" / "consumption_daily_meter").as_posix() + "/**/*.parquet"
    gold_kwh = duckdb.sql(
        f"SELECT sum(kwh) FROM read_parquet('{pattern}', hive_partitioning = false) "
        "WHERE meter_id = 'MTR-00001'"
    ).fetchall()[0][0]
    raw_kwh = Decimal(lines[-1]["energy_wh"] - lines[0]["energy_wh"]) / 1000
    assert gold_kwh == raw_kwh == Decimal("28.7")


def test_ts_60s_off_grid_kept_61s_quarantined(lake: Lake) -> None:
    land(
        lake,
        D,
        "20260803T0500",
        [v1("MTR-00001", 0, 1_000_000, seconds=60), v1("MTR-00002", 0, 1_000_000, seconds=61)],
    )
    ingest(D, lake)
    rules = {r["meter_id"]: r["rule"] for r in checked_rows(D, lake).to_pylist()}
    assert rules == {"MTR-00001": None, "MTR-00002": "BAD_TIMESTAMP"}


def snapshot(lake: Lake) -> dict[str, list]:
    layers = {}
    for name in ("bronze", "quarantine", "silver", "gold"):
        files = sorted((lake.root / name).rglob("*.parquet"))
        layers[name] = [
            (f.relative_to(lake.root).as_posix(), pq.read_table(f).to_pylist()) for f in files
        ]
    return layers


def test_rerun_same_date_identical_output_end_to_end(lake: Lake) -> None:
    lines = history() + [v1("MTR-09001", 0, 5), v1("MTR-00002", 0, -1)]
    build_gold(lake, lines)
    first = snapshot(lake)
    ingest(D, lake)
    quality(D, lake)
    normalise(D, lake)
    aggregate(D, lake, run_id="replay")
    assert snapshot(lake) == first
    assert all(first[layer] for layer in ("bronze", "quarantine", "silver", "gold"))
