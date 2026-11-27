"""Synthetic topology (meters, feeders, zones) and the seeded meter master table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

MASTER_COLUMNS = [
    "meter_id",
    "feeder_id",
    "zone_id",
    "meter_type",
    "reporting_unit",
    "register_max_kwh",
    "install_date",
]


@dataclass(frozen=True)
class Topology:
    meter_ids: list[str]
    feeder_ids: list[str]
    zone_of_feeder: list[str]
    feeder_of_meter: np.ndarray  # feeder index per meter
    meters_per_feeder: int

    def feeder_slice(self, feeder: int) -> slice:
        lo = feeder * self.meters_per_feeder
        return slice(lo, lo + self.meters_per_feeder)


def build_topology(n_meters: int, cfg: dict[str, Any]) -> Topology:
    n_feeders = int(cfg["topology"]["feeders"])
    zone_feeders: dict[str, int] = cfg["topology"]["zone_feeders"]
    if sum(zone_feeders.values()) != n_feeders:
        raise ValueError("topology.zone_feeders must add up to topology.feeders")
    if n_meters <= 0 or n_meters % n_feeders:
        raise ValueError(f"--meters must be a positive multiple of {n_feeders}")
    if n_meters >= int(cfg["injections"]["unknown_meter_id_start"]):
        raise ValueError("--meters must stay below injections.unknown_meter_id_start")
    per_feeder = n_meters // n_feeders
    return Topology(
        meter_ids=[f"MTR-{i:05d}" for i in range(1, n_meters + 1)],
        feeder_ids=[f"F{i:02d}" for i in range(1, n_feeders + 1)],
        zone_of_feeder=[zone for zone, count in zone_feeders.items() for _ in range(count)],
        feeder_of_meter=np.repeat(np.arange(n_feeders), per_feeder),
        meters_per_feeder=per_feeder,
    )


def build_meter_master(
    topo: Topology, kwh_meter: np.ndarray, cfg: dict[str, Any], rng: np.random.Generator
) -> pd.DataFrame:
    n = len(topo.meter_ids)
    mcfg = cfg["meters"]
    is_commercial = rng.random(n) >= float(mcfg["residential_share"])
    first, last = (int(y) for y in mcfg["install_years"])
    day0 = date(first, 1, 1)
    span = (date(last, 12, 31) - day0).days
    offsets = rng.integers(0, span + 1, size=n)
    return pd.DataFrame(
        {
            "meter_id": topo.meter_ids,
            "feeder_id": [topo.feeder_ids[f] for f in topo.feeder_of_meter],
            "zone_id": [topo.zone_of_feeder[f] for f in topo.feeder_of_meter],
            "meter_type": np.where(is_commercial, "commercial", "residential"),
            "reporting_unit": np.where(kwh_meter, "kWh", "Wh"),
            "register_max_kwh": int(mcfg["register_max_kwh"]),
            "install_date": [(day0 + timedelta(days=int(o))).isoformat() for o in offsets],
        },
        columns=MASTER_COLUMNS,
    )
