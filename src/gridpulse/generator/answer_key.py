"""Answer key: every injected problem with meter or feeder, time window and expected outcome."""

from __future__ import annotations

from typing import Any

import numpy as np

from gridpulse.generator.meter_master import Topology
from gridpulse.generator.readings import Grid, iso_utc
from gridpulse.generator.scenarios import Injected, Rollout


def build_answer_key(
    params: dict[str, Any],
    topo: Topology,
    grid: Grid,
    rollout: Rollout,
    inj: Injected,
    stats: dict[str, Any],
) -> dict[str, Any]:
    ids = topo.meter_ids

    def cells(arr: np.ndarray) -> list[list[str]]:
        return [[ids[m], iso_utc(grid.epochs[j])] for m, j in arr[:, :2].tolist()]

    by_type: dict[str, int] = {}
    for s in inj.scenarios:
        by_type[s["type"]] = by_type.get(s["type"], 0) + 1
    outage_missing = sum(
        s["meters_missing"] * s["intervals"] for s in inj.scenarios if s["type"] == "outage"
    )
    half_missing = by_type.get("half_day_missing", 0) * (grid.per_day // 2)
    n_neg = by_type.get("negative_reading", 0)
    n_dec = by_type.get("decreasing_register", 0)
    missing_unit = np.argwhere(inj.missing_unit)
    totals = {
        "meters": len(ids),
        "intervals_expected": len(ids) * len(grid.epochs),
        "files": stats["files"],
        "resend_files": stats["resend_files"],
        "late_files": len(stats["late_files"]),
        "rows_written": stats["rows"],
        "primary_readings": int(inj.present.sum()),
        "v1_rows": stats["v1_rows"],
        "v2_rows": stats["v2_rows"],
        "kwh_rows": stats["kwh_rows"],
        "missing_unit_rows": len(missing_unit),
        "exact_duplicates": len(inj.exact_dups),
        "conflicting_duplicates": len(inj.conflict_dups),
        "unknown_meter_rows": len(inj.unknown_rows),
        "random_gap_intervals": len(inj.random_gaps),
        "outage_gap_intervals": outage_missing,
        "half_day_gap_intervals": half_missing,
        "expected_gap_intervals": len(inj.random_gaps)
        + outage_missing
        + half_missing
        + n_neg
        + n_dec,
        "expected_quarantine": {
            "UNKNOWN_METER": len(inj.unknown_rows),
            "NEGATIVE_READING": n_neg,
            "REGISTER_DECREASED": n_dec,
            "BAD_TIMESTAMP": 0,
        },
        "scenarios_by_type": by_type,
    }
    return {
        "generator": {
            **params,
            "start_utc": iso_utc(grid.epochs[0]),
            "timezone_local": grid.tz_local,
            "v2_switch_day": rollout.switch_day,
        },
        "totals": totals,
        "scenarios": inj.scenarios,
        "skipped": inj.skipped,
        "bulk": {
            "random_gaps": {
                "expected": "written to silver/gaps; never filled",
                "items": cells(inj.random_gaps),
            },
            "exact_duplicates": {
                "expected": "dropped and counted; one row kept",
                "items": cells(inj.exact_dups),
            },
            "conflicting_duplicates": {
                "expected": "dup_conflict = true; keeps the resend row (latest ingested_at)",
                "columns": ["meter_id", "interval_start", "delta_wh"],
                "items": [
                    [ids[m], iso_utc(grid.epochs[j]), int(d)]
                    for m, j, d in inj.conflict_dups.tolist()
                ],
            },
            "unknown_meter_rows": {
                "expected": "quarantine: UNKNOWN_METER",
                "columns": ["meter_id", "interval_start"],
                "items": [
                    [f"MTR-{fake:05d}", iso_utc(grid.epochs[j])]
                    for _, j, fake in inj.unknown_rows.tolist()
                ],
            },
            "missing_unit": {
                "expected": "unit taken from meter_master.reporting_unit (kWh)",
                "items": cells(missing_unit),
            },
            "late_files": {
                "expected": "inside lookback_days: daily run picks it up; later: needs backfill",
                "items": stats["late_files"],
            },
            "v2_meters": [ids[m] for m in np.flatnonzero(rollout.v2_meter)],
            "kwh_meters": [ids[m] for m in np.flatnonzero(rollout.kwh_meter)],
        },
    }
