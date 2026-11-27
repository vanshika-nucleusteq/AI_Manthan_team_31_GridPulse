"""Interval grid and vectorised per-interval consumption (integer Wh) for every meter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Grid:
    start: date  # local date of the first interval
    tz_local: str
    step_s: int  # interval length in seconds
    epochs: np.ndarray  # interval_start, UTC epoch seconds [T]
    local_day: np.ndarray  # local day index since start [T]
    local_hour: np.ndarray  # local hour of day [T]
    per_day: int
    per_hour: int

    @property
    def days(self) -> int:
        return len(self.epochs) // self.per_day


def iso_utc(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_date(epoch: int, tz_local: str) -> date:
    return datetime.fromtimestamp(int(epoch), tz=ZoneInfo(tz_local)).date()


def build_grid(start: date, days: int, tz_local: str, interval_minutes: int) -> Grid:
    if days <= 0:
        raise ValueError("--days must be positive")
    per_hour = 60 // interval_minutes
    per_day = 24 * per_hour
    t0 = datetime.combine(start, time(0), tzinfo=ZoneInfo(tz_local))
    step_s = interval_minutes * 60
    epochs = int(t0.timestamp()) + np.arange(days * per_day, dtype=np.int64) * step_s
    local = pd.to_datetime(epochs, unit="s", utc=True).tz_convert(tz_local)
    local_dates = np.asarray(local.date, dtype="datetime64[D]")
    local_day = (local_dates - np.datetime64(start, "D")).astype(np.int64)
    return Grid(
        start=start,
        tz_local=tz_local,
        step_s=step_s,
        epochs=epochs,
        local_day=np.asarray(local_day),
        local_hour=np.asarray(local.hour, dtype=np.int64),
        per_day=per_day,
        per_hour=per_hour,
    )


def consumption_wh(
    is_commercial: np.ndarray, grid: Grid, cfg: dict[str, Any], rng: np.random.Generator
) -> np.ndarray:
    """Integer Wh consumed in each interval, shape [meters, intervals]."""
    ccfg = cfg["consumption"]
    base = (
        np.where(
            is_commercial,
            float(ccfg["base_kwh_per_interval"]["commercial"]),
            float(ccfg["base_kwh_per_interval"]["residential"]),
        )
        * 1000.0
    )
    scale = rng.lognormal(0.0, float(cfg["meters"]["scale_sigma"]), size=len(is_commercial))
    profile_res = np.asarray(ccfg["hourly_profile"]["residential"], dtype=np.float64)
    profile_com = np.asarray(ccfg["hourly_profile"]["commercial"], dtype=np.float64)
    shape = np.where(
        is_commercial[:, None], profile_com[grid.local_hour], profile_res[grid.local_hour]
    )
    noise = rng.standard_normal(size=shape.shape, dtype=np.float32)
    wh = (base * scale)[:, None] * shape * (1.0 + float(ccfg["noise_sd"]) * noise)
    return np.maximum(np.rint(wh), int(ccfg["min_interval_wh"])).astype(np.int64)
