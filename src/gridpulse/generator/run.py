"""Generate meter master, landing files and answer key for one seed."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import orjson

from gridpulse.common.config import load_yaml
from gridpulse.generator.answer_key import build_answer_key
from gridpulse.generator.meter_master import build_meter_master, build_topology
from gridpulse.generator.readings import build_grid
from gridpulse.generator.scenarios import assign_rollout, inject
from gridpulse.generator.writer import write_landing

GENERATED = ("landing", "answer_key.json", "meter_master.csv")


def prepare_output(out: Path, overwrite: bool) -> None:
    """Refuse to mix runs; with overwrite, delete only the generator's own synthetic outputs."""
    existing = [out / name for name in GENERATED if (out / name).exists()]
    if existing and not overwrite:
        names = ", ".join(str(p) for p in existing)
        raise FileExistsError(f"generator output already exists ({names}); pass --overwrite")
    for path in existing:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    out.mkdir(parents=True, exist_ok=True)


def generate(
    meters: int, days: int, start: date, seed: int, out: Path, overwrite: bool = False
) -> dict[str, Any]:
    cfg = load_yaml("generator")
    pipeline = load_yaml("pipeline")
    anomalies = load_yaml("anomalies")
    topo = build_topology(meters, cfg)
    grid = build_grid(start, days, pipeline["timezone_local"], int(pipeline["interval_minutes"]))
    prepare_output(out, overwrite)

    rng = np.random.default_rng(seed)
    rollout = assign_rollout(meters, days, cfg, rng)
    master = build_meter_master(topo, rollout.kwh_meter, cfg, rng)
    is_commercial = (master["meter_type"] == "commercial").to_numpy()
    inj = inject(
        topo, grid, is_commercial, rollout, cfg, int(anomalies["spike"]["min_samples"]), rng
    )

    master.to_csv(out / "meter_master.csv", index=False, lineterminator="\n")
    stats = write_landing(
        out / "landing", topo, grid, rollout, inj, cfg, np.random.default_rng([seed, 1])
    )
    params = {"meters": meters, "days": days, "start": start.isoformat(), "seed": seed}
    key = build_answer_key(params, topo, grid, rollout, inj, stats)
    (out / "answer_key.json").write_bytes(orjson.dumps(key, option=orjson.OPT_INDENT_2))
    return key
