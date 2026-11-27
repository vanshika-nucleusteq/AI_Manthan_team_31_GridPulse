"""Generator: determinism, schema versions and injected problems match the answer key."""

from __future__ import annotations

import gzip
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import orjson
import pandas as pd
import pytest

from gridpulse.generator.run import generate

METERS, DAYS, START, SEED = 200, 3, date(2026, 8, 1), 7
IST = ZoneInfo("Asia/Kolkata")
V1_KEYS = {"meter_id", "ts", "energy_wh", "status"}
V2_REQUIRED = {"meter_id", "ts", "energy", "status", "voltage", "firmware_version"}


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    out = tmp_path_factory.mktemp("gen")
    key = generate(METERS, DAYS, START, SEED, out)
    return out, key


@pytest.fixture(scope="module")
def rows(run: tuple[Path, dict]) -> pd.DataFrame:
    out, _ = run
    records = []
    for path in sorted((out / "landing").rglob("*.jsonl.gz")):
        rel = path.relative_to(out / "landing").as_posix()
        for line in gzip.decompress(path.read_bytes()).splitlines():
            records.append({**orjson.loads(line), "_file": rel})
    return pd.DataFrame(records)


@pytest.fixture(scope="module")
def master(run: tuple[Path, dict]) -> pd.DataFrame:
    return pd.read_csv(run[0] / "meter_master.csv")


def _files(out: Path) -> dict[str, bytes]:
    return {
        p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()
    }


@pytest.fixture(scope="module")
def short_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    out = tmp_path_factory.mktemp("short")
    return out, generate(METERS, 1, START, SEED, out)


def test_same_seed_gives_identical_files_and_answer_key(
    short_run: tuple[Path, dict], tmp_path: Path
) -> None:
    generate(METERS, 1, START, SEED, tmp_path)
    assert _files(short_run[0]) == _files(tmp_path)


def test_existing_output_is_kept_unless_overwrite(tmp_path: Path) -> None:
    generate(METERS, 1, START, SEED, tmp_path)
    with pytest.raises(FileExistsError):
        generate(METERS, 1, START, SEED, tmp_path)
    generate(METERS, 1, START, SEED + 1, tmp_path, overwrite=True)
    assert (tmp_path / "answer_key.json").exists()


def test_meter_master_splits_meters_evenly_and_zones_have_3_or_4_feeders(
    master: pd.DataFrame,
) -> None:
    assert len(master) == METERS and master["meter_id"].is_unique
    assert set(master.groupby("feeder_id").size()) == {METERS // 20}
    assert master["feeder_id"].nunique() == 20
    assert set(master.groupby("zone_id")["feeder_id"].nunique()) == {3, 4}
    assert master.groupby("feeder_id")["zone_id"].nunique().max() == 1


def test_kwh_reporting_meters_are_v2_meters(run: tuple[Path, dict], master: pd.DataFrame) -> None:
    bulk = run[1]["bulk"]
    kwh = set(master.loc[master["reporting_unit"] == "kWh", "meter_id"])
    assert kwh == set(bulk["kwh_meters"]) and kwh <= set(bulk["v2_meters"])


def test_v1_has_energy_wh_and_v2_has_energy_unit_voltage_firmware(
    run: tuple[Path, dict], rows: pd.DataFrame
) -> None:
    key = run[1]
    missing_unit = {tuple(i) for i in key["bulk"]["missing_unit"]["items"]}
    switch = datetime.combine(
        START + timedelta(days=key["generator"]["v2_switch_day"]), datetime.min.time(), IST
    )
    seen_v1 = seen_v2 = 0
    for rec in rows.drop(columns="_file").to_dict("records"):
        present = {k for k, v in rec.items() if not (isinstance(v, float) and pd.isna(v))}
        present |= {"voltage"} if "energy" in present else set()
        if "energy_wh" in present:
            seen_v1 += 1
            assert present == V1_KEYS
        else:
            seen_v2 += 1
            assert V2_REQUIRED <= present
            assert datetime.fromisoformat(rec["ts"]) >= switch
            assert ("unit" in present) != ((rec["meter_id"], rec["ts"]) in missing_unit)
    assert seen_v1 == key["totals"]["v1_rows"] and seen_v2 == key["totals"]["v2_rows"] > 0


def test_answer_key_counts_match_written_rows(
    run: tuple[Path, dict], rows: pd.DataFrame, master: pd.DataFrame
) -> None:
    totals = run[1]["totals"]
    assert len(rows) == totals["rows_written"]
    unknown = rows[~rows["meter_id"].isin(master["meter_id"])]
    assert len(unknown) == totals["unknown_meter_rows"]
    known = rows[rows["meter_id"].isin(master["meter_id"])]
    assert known.duplicated(["meter_id", "ts"]).sum() == (
        totals["exact_duplicates"] + totals["conflicting_duplicates"]
    )
    assert known[["meter_id", "ts"]].drop_duplicates().shape[0] == totals["primary_readings"]
    assert totals["primary_readings"] == totals["intervals_expected"] - (
        totals["random_gap_intervals"]
        + totals["outage_gap_intervals"]
        + totals["half_day_gap_intervals"]
    )


def test_unknown_meter_ids_are_outside_master(run: tuple[Path, dict], master: pd.DataFrame) -> None:
    fake = {i[0] for i in run[1]["bulk"]["unknown_meter_rows"]["items"]}
    assert fake and not fake & set(master["meter_id"])
    assert all(f.startswith("MTR-") and len(f) == 9 for f in fake)


def test_register_never_decreases_except_injected_and_rollover(
    run: tuple[Path, dict], rows: pd.DataFrame, master: pd.DataFrame
) -> None:
    key = run[1]
    unit_of = master.set_index("meter_id")["reporting_unit"]
    df = rows[rows["meter_id"].isin(master["meter_id"])].copy()
    is_kwh = df["unit"].eq("kWh") | (
        df["unit"].isna() & df["energy"].notna() & df["meter_id"].map(unit_of).eq("kWh")
    )
    df["wh"] = df["energy_wh"].where(
        df["energy_wh"].notna(), df["energy"] * is_kwh.map({True: 1000, False: 1})
    )
    df["wh"] = df["wh"].round().astype("int64")
    df = df.groupby(["meter_id", "ts"], as_index=False)["wh"].max().sort_values(["meter_id", "ts"])
    df["diff"] = df.groupby("meter_id")["wh"].diff()
    drops = set(map(tuple, df.loc[df["diff"] < 0, ["meter_id", "ts"]].to_numpy().tolist()))
    expected = {
        (s["meter_id"], s["window_start"])
        for s in key["scenarios"]
        if s["type"] in {"negative_reading", "decreasing_register", "rollover"}
    }
    assert drops == expected


def test_late_files_land_in_later_arrival_date_folder(run: tuple[Path, dict]) -> None:
    out, key = run
    late = key["bulk"]["late_files"]["items"]
    assert len(late) == key["totals"]["late_files"] > 0
    for item in late:
        folder, _, name = item["file"].split("/")
        arrival_day = date.fromisoformat(folder.removeprefix("arrival_date="))
        hour = datetime.strptime(name.split("_")[1], "h%Y%m%dT%H%MZ").replace(
            tzinfo=ZoneInfo("UTC")
        )
        assert arrival_day >= hour.astimezone(IST).date() + timedelta(days=item["days_late"])
        assert (out / "landing" / item["file"]).exists()


def test_scenario_meter_sets_do_not_overlap(run: tuple[Path, dict]) -> None:
    scenarios = run[1]["scenarios"]
    outage = next(s for s in scenarios if s["type"] == "outage")
    per_meter = [s for s in scenarios if "meter_id" in s]
    meters = [s["meter_id"] for s in per_meter]
    assert len(meters) == len(set(meters))
    assert all(s["feeder_id"] != outage["feeder_id"] for s in per_meter)


def test_spike_on_short_history_is_expected_silent(run: tuple[Path, dict]) -> None:
    spikes = [s for s in run[1]["scenarios"] if s["type"] == "spike"]
    assert len(spikes) == 10
    assert all(
        s["expected"].startswith("silent") and s["baseline_days"] == DAYS - 1 for s in spikes
    )


def test_tamper_skipped_when_window_shorter_than_60_hours(short_run: tuple[Path, dict]) -> None:
    key = short_run[1]
    assert [s["type"] for s in key["skipped"]] == ["tamper"]
    assert key["totals"]["scenarios_by_type"].get("tamper", 0) == 0
