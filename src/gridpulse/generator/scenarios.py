"""Schema v2 rollout plus every injected problem from plan section 3, applied to the arrays."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import numpy as np

from gridpulse.generator.meter_master import Topology
from gridpulse.generator.readings import Grid, consumption_wh, iso_utc

STATUS_OK = 0
STATUS_ROLLOVER = 1


@dataclass(frozen=True)
class Rollout:
    v2_meter: np.ndarray  # bool [M]
    kwh_meter: np.ndarray  # bool [M], subset of v2_meter
    explicit_version: np.ndarray  # bool [M], v2 messages carry schema_version
    firmware: list[str]  # per meter
    switch_day: int  # local day index from which v2 meters send v2


@dataclass
class Injected:
    present: np.ndarray  # bool [M, T]: a primary reading is sent
    emitted_wh: np.ndarray  # int64 [M, T]: register value sent, in Wh
    status: np.ndarray  # uint8 [M, T]
    v2_cell: np.ndarray  # bool [M, T]
    missing_unit: np.ndarray  # bool [M, T]
    random_gaps: np.ndarray  # [k, 2] (meter, interval)
    exact_dups: np.ndarray  # [k, 2]
    conflict_dups: np.ndarray  # [k, 3] (meter, interval, delta_wh)
    unknown_rows: np.ndarray  # [k, 3] (source meter, interval, fake id number)
    late_files: dict[tuple[int, int], int]  # (feeder, hour index) -> days late
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)


def assign_rollout(
    n_meters: int, days: int, cfg: dict[str, Any], rng: np.random.Generator
) -> Rollout:
    scfg = cfg["schema_v2"]
    v2_idx = rng.choice(n_meters, size=round(float(scfg["meter_share"]) * n_meters), replace=False)
    kwh_idx = rng.choice(
        v2_idx, size=round(float(scfg["kwh_meter_share"]) * len(v2_idx)), replace=False
    )
    explicit_idx = rng.choice(
        v2_idx, size=round(float(scfg["explicit_version_meter_share"]) * len(v2_idx)), replace=False
    )
    v2, kwh, explicit = (np.zeros(n_meters, dtype=bool) for _ in range(3))
    v2[v2_idx] = True
    kwh[kwh_idx] = True
    explicit[explicit_idx] = True
    versions = list(scfg["firmware_versions"])
    firmware = [versions[i] for i in rng.integers(0, len(versions), size=n_meters)]
    configured = int(scfg["switch_day"])
    switch_day = configured if days > configured else max(1, days // 2)
    return Rollout(v2, kwh, explicit, firmware, switch_day)


def sample_cells(
    rng: np.random.Generator, meters: np.ndarray, n_intervals: int, k: int, blocked: np.ndarray
) -> np.ndarray:
    """k distinct (meter, interval) cells from `meters` that are not `blocked`, in random order."""
    if k <= 0:
        return np.empty((0, 2), dtype=np.int64)
    available = int((~blocked[meters]).sum())
    if available < k:
        raise ValueError(f"need {k} cells but only {available} are eligible")
    chosen = np.empty(0, dtype=np.int64)
    while len(chosen) < k:
        draw = rng.integers(0, len(meters) * n_intervals, size=max(2 * (k - len(chosen)), 16))
        flat = np.concatenate([chosen, draw])
        _, first = np.unique(flat, return_index=True)
        flat = flat[np.sort(first)]
        flat = flat[~blocked[meters[flat // n_intervals], flat % n_intervals]]
        chosen = flat[:k]
    return np.column_stack([meters[chosen // n_intervals], chosen % n_intervals])


def inject(
    topo: Topology,
    grid: Grid,
    is_commercial: np.ndarray,
    rollout: Rollout,
    cfg: dict[str, Any],
    spike_min_samples: int,
    rng: np.random.Generator,
) -> Injected:
    inj = cfg["injections"]
    n_meters, n_int = len(topo.meter_ids), len(grid.epochs)
    days, per_day, per_hour = grid.days, grid.per_day, grid.per_hour
    ids, feeders = topo.meter_ids, topo.feeder_ids
    scenarios: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    def window(start: int, length: int) -> dict[str, str]:
        return {
            "window_start": iso_utc(grid.epochs[start]),
            "window_end": iso_utc(grid.epochs[start] + length * grid.step_s),
        }

    def meter_ref(m: int) -> dict[str, str]:
        f = int(topo.feeder_of_meter[m])
        return {"meter_id": ids[m], "feeder_id": feeders[f], "zone_id": topo.zone_of_feeder[f]}

    # Disjoint meter sets, none on the outage feeder.
    outage_f = feeders.index(inj["outage"]["feeder"])
    tamper_len = int(inj["tamper"]["zero_hours"]) * per_hour
    n_tamper = int(inj["tamper"]["meters"])
    if n_int < tamper_len:
        skipped.append(
            {
                "type": "tamper",
                "reason": f"needs {inj['tamper']['zero_hours']} h, window has {days} days",
            }
        )
        n_tamper = 0
    sizes = [
        int(inj["spike"]["meters"]),
        n_tamper,
        int(inj["rollover_meters"]),
        int(inj["half_day_missing_meters"]),
        int(inj["negative_readings"]),
        int(inj["decreasing_readings"]),
    ]
    candidates = np.flatnonzero(topo.feeder_of_meter != outage_f)
    if sum(sizes) > len(candidates):
        raise ValueError(f"need {sum(sizes)} scenario meters, only {len(candidates)} available")
    picked = rng.choice(candidates, size=sum(sizes), replace=False)
    spike_m, tamper_m, roll_m, half_m, neg_m, dec_m = np.split(picked, np.cumsum(sizes)[:-1])
    special = np.zeros(n_meters, dtype=bool)
    special[picked] = True

    cons = consumption_wh(is_commercial, grid, cfg, rng)

    for m in tamper_m:
        s = int(rng.integers(0, n_int - tamper_len + 1))
        s -= s % per_hour
        cons[m, s : s + tamper_len] = 0
        scenarios.append(
            {
                "type": "tamper",
                **meter_ref(m),
                **window(s, tamper_len),
                "zero_hours": int(inj["tamper"]["zero_hours"]),
                "expected": "flag: suspected tamper",
            }
        )

    lo_h, hi_h = (int(h) for h in inj["spike"]["local_hours"])
    spike_len = int(inj["spike"]["hours"]) * per_hour
    f_lo, f_hi = (float(x) for x in inj["spike"]["factor"])
    last_day = days - 1
    baseline = last_day
    spike_expected = (
        "flag: spike"
        if baseline >= spike_min_samples
        else f"silent: baseline {baseline} < {spike_min_samples} samples"
    )
    for m in spike_m:
        s = last_day * per_day + int(rng.integers(lo_h, hi_h)) * per_hour
        factor = float(rng.uniform(f_lo, f_hi))
        cons[m, s : s + spike_len] = np.rint(cons[m, s : s + spike_len] * factor).astype(np.int64)
        scenarios.append(
            {
                "type": "spike",
                **meter_ref(m),
                **window(s, spike_len),
                "factor": round(factor, 2),
                "baseline_days": baseline,
                "expected": spike_expected,
            }
        )

    # Cumulative registers in Wh; rollover meters start just below register_max.
    max_wh = int(cfg["meters"]["register_max_kwh"]) * 1000
    r_lo, r_hi = (int(x) * 1000 for x in cfg["meters"]["start_register_kwh"])
    start = rng.integers(r_lo, r_hi, size=n_meters)
    cum = np.cumsum(cons, axis=1)
    status = np.zeros((n_meters, n_int), dtype=np.uint8)
    for m in roll_m:
        w = int(rng.integers(max(1, n_int // 4), max(2, 3 * n_int // 4)))
        start[m] = max_wh - cum[m, w - 1] - 1
        status[m, w] = STATUS_ROLLOVER
        scenarios.append(
            {
                "type": "rollover",
                **meter_ref(m),
                **window(w, 1),
                "expected": "allowed: ROLLOVER; consumption = register_max - previous + register",
            }
        )
    registers = start[:, None] + cum
    if (registers[~np.isin(np.arange(n_meters), roll_m)] >= max_wh).any():
        raise ValueError("start_register_kwh too high: a non-rollover meter would wrap")
    emitted = registers % max_wh
    del cum, registers

    d_lo, d_hi = (int(x) for x in inj["decrease_wh"])
    for m in neg_m:
        j = int(rng.integers(1, n_int))
        emitted[m, j] = -int(rng.integers(d_lo, d_hi))
        scenarios.append(
            {
                "type": "negative_reading",
                **meter_ref(m),
                **window(j, 1),
                "expected": "quarantine: NEGATIVE_READING; interval becomes a gap",
            }
        )
    for m in dec_m:
        j = int(rng.integers(1, n_int))
        emitted[m, j] = emitted[m, j - 1] - int(rng.integers(d_lo, d_hi))
        scenarios.append(
            {
                "type": "decreasing_register",
                **meter_ref(m),
                **window(j, 1),
                "expected": "quarantine: REGISTER_DECREASED; interval becomes a gap",
            }
        )

    present = np.ones((n_meters, n_int), dtype=bool)
    outage_block = np.zeros((n_meters, n_int), dtype=bool)
    o_cfg = inj["outage"]
    o_len = int(o_cfg["hours"]) * per_hour
    f_meters = np.arange(n_meters)[topo.feeder_slice(outage_f)]
    o_meters = np.sort(
        rng.choice(f_meters, size=round(float(o_cfg["meter_share"]) * len(f_meters)), replace=False)
    )
    o_lo, o_hi = (int(h) for h in o_cfg["local_hours"])
    o_start = (days // 2) * per_day + int(rng.integers(o_lo, o_hi)) * per_hour
    present[np.ix_(o_meters, np.arange(o_start, o_start + o_len))] = False
    outage_block[f_meters, o_start : o_start + o_len] = True
    scenarios.append(
        {
            "type": "outage",
            "feeder_id": feeders[outage_f],
            "zone_id": topo.zone_of_feeder[outage_f],
            **window(o_start, o_len),
            "intervals": o_len,
            "meters_missing": len(o_meters),
            "meters_on_feeder": len(f_meters),
            "missing_meter_ids": [ids[m] for m in o_meters],
            "expected": "flag: outage (one merged event)",
        }
    )

    half = per_day // 2
    half_day = days // 2
    for m in half_m:
        s = half_day * per_day + int(rng.integers(0, 2)) * half
        present[m, s : s + half] = False
        day = grid.start + timedelta(days=half_day)
        scenarios.append(
            {
                "type": "half_day_missing",
                **meter_ref(m),
                **window(s, half),
                "local_date": day.isoformat(),
                "expected": f"{half} gaps; completeness 50% -> quality_flag on {day.isoformat()}",
            }
        )

    normal = np.flatnonzero(~special)
    random_gaps = sample_cells(
        rng,
        normal,
        n_int,
        round(float(inj["random_missing_share"]) * n_meters * n_int),
        ~present | outage_block,
    )
    present[random_gaps[:, 0], random_gaps[:, 1]] = False

    n_primary = int(present.sum())
    exact = sample_cells(
        rng, normal, n_int, round(float(inj["exact_duplicate_share"]) * n_primary), ~present
    )
    blocked = ~present
    blocked[exact[:, 0], exact[:, 1]] = True
    blocked[:, -1] = True
    conflict = sample_cells(
        rng, normal, n_int, round(float(inj["conflict_duplicate_share"]) * n_primary), blocked
    )
    c_lo, c_hi = (int(x) for x in inj["conflict_delta_wh"])
    if c_hi >= int(cfg["consumption"]["min_interval_wh"]):
        raise ValueError("conflict_delta_wh must stay below consumption.min_interval_wh")
    deltas = rng.integers(c_lo, c_hi + 1, size=len(conflict))
    conflict_dups = np.column_stack([conflict, deltas])

    unknown = sample_cells(
        rng, normal, n_int, round(float(inj["unknown_meter_share"]) * n_primary), ~present
    )
    id_start = int(inj["unknown_meter_id_start"])
    fake = rng.integers(id_start, id_start + 999, size=len(unknown))
    unknown_rows = np.column_stack([unknown, fake])

    v2_cell = rollout.v2_meter[:, None] & (grid.local_day >= rollout.switch_day)[None, :]
    kwh_meters = np.flatnonzero(rollout.kwh_meter)
    kwh_v2 = ~present | (grid.local_day < rollout.switch_day)[None, :]
    eligible = int((~kwh_v2[kwh_meters]).sum())
    missing = sample_cells(
        rng,
        kwh_meters,
        n_int,
        round(float(cfg["schema_v2"]["missing_unit_share"]) * eligible),
        kwh_v2,
    )
    missing_unit = np.zeros((n_meters, n_int), dtype=bool)
    missing_unit[missing[:, 0], missing[:, 1]] = True
    scenarios.append(
        {
            "type": "schema_v2_rollout",
            "v2_meters": int(rollout.v2_meter.sum()),
            "kwh_meters": int(rollout.kwh_meter.sum()),
            "switch_day": rollout.switch_day,
            "switch_date": (grid.start + timedelta(days=rollout.switch_day)).isoformat(),
            "expected": "v2 meters send schema v2 from switch_date; kWh meters need no / 1000",
        }
    )

    n_hours = days * 24
    n_files = len(feeders) * n_hours
    late_idx = rng.choice(
        n_files, size=round(float(inj["late_file_share"]) * n_files), replace=False
    )
    l_lo, l_hi = (int(d) for d in inj["late_days"])
    late_days = rng.integers(l_lo, l_hi + 1, size=len(late_idx))
    late_files = {
        (int(i // n_hours), int(i % n_hours)): int(d)
        for i, d in zip(late_idx, late_days, strict=True)
    }

    return Injected(
        present=present,
        emitted_wh=emitted,
        status=status,
        v2_cell=v2_cell,
        missing_unit=missing_unit,
        random_gaps=random_gaps,
        exact_dups=exact,
        conflict_dups=conflict_dups,
        unknown_rows=unknown_rows,
        late_files=late_files,
        scenarios=scenarios,
        skipped=skipped,
    )
