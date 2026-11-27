"""Write gateway files: one gzip JSONL per feeder per hour, in arrival_date=/feeder=/ folders."""

from __future__ import annotations

import gzip
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import orjson

from gridpulse.generator.meter_master import Topology
from gridpulse.generator.readings import Grid, iso_utc, local_date
from gridpulse.generator.scenarios import STATUS_ROLLOVER, Injected, Rollout

STATUS_TEXT = {0: "OK", STATUS_ROLLOVER: "ROLLOVER"}


def _stamp(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), tz=UTC).strftime("%Y%m%dT%H%MZ")


def file_name(feeder: str, hour_epoch: int, arrival_epoch: int) -> str:
    return f"{feeder}_h{_stamp(hour_epoch)}_a{_stamp(arrival_epoch)}.jsonl.gz"


def _group_by_file(cells: np.ndarray, topo: Topology, per_hour: int) -> dict[tuple[int, int], list]:
    groups: dict[tuple[int, int], list] = defaultdict(list)
    for row in cells.tolist():
        groups[(int(topo.feeder_of_meter[row[0]]), row[1] // per_hour)].append(row)
    return groups


def write_landing(
    landing: Path,
    topo: Topology,
    grid: Grid,
    rollout: Rollout,
    inj: Injected,
    cfg: dict[str, Any],
    rng: np.random.Generator,
) -> dict[str, Any]:
    fcfg, scfg = cfg["files"], cfg["schema_v2"]
    v_lo, v_hi = (float(v) for v in scfg["voltage_volts"])
    v_null = float(scfg["voltage_null_share"])
    level = int(fcfg["gzip_level"])
    hour_s = grid.per_hour * grid.step_s
    delay_s = int(fcfg["arrival_delay_minutes"]) * 60
    resend_s = int(fcfg["resend_delay_minutes"]) * 60
    ts_text = [iso_utc(e) for e in grid.epochs]
    ids = topo.meter_ids
    unknown = _group_by_file(inj.unknown_rows, topo, grid.per_hour)
    exact = _group_by_file(inj.exact_dups, topo, grid.per_hour)
    conflict = _group_by_file(inj.conflict_dups, topo, grid.per_hour)
    stats = {"files": 0, "resend_files": 0, "rows": 0, "v1_rows": 0, "v2_rows": 0, "kwh_rows": 0}
    late_records: list[dict[str, Any]] = []

    def message(meter_id: str, m: int, j: int, wh: int, volt: float | None) -> dict[str, Any]:
        status = STATUS_TEXT[int(inj.status[m, j])]
        if not inj.v2_cell[m, j]:
            stats["v1_rows"] += 1
            return {"meter_id": meter_id, "ts": ts_text[j], "energy_wh": wh, "status": status}
        stats["v2_rows"] += 1
        msg: dict[str, Any] = {"schema_version": 2} if rollout.explicit_version[m] else {}
        msg["meter_id"] = meter_id
        msg["ts"] = ts_text[j]
        if rollout.kwh_meter[m]:
            stats["kwh_rows"] += 1
            msg["energy"], unit = round(wh / 1000, 3), "kWh"
        else:
            msg["energy"], unit = wh, "Wh"
        if not inj.missing_unit[m, j]:
            msg["unit"] = unit
        msg["status"] = status
        msg["voltage"] = volt
        msg["firmware_version"] = rollout.firmware[m]
        return msg

    def emit(
        rows: list[tuple[str, int, int, int]], folder_feeder: str, hour_epoch: int, arrival: int
    ) -> str:
        volts = np.round(rng.uniform(v_lo, v_hi, size=len(rows)), 1)
        nulls = rng.random(len(rows)) < v_null
        msgs = [
            message(mid, m, j, wh, None if nulls[i] else float(volts[i]))
            for i, (mid, m, j, wh) in enumerate(rows)
        ]
        order = rng.permutation(len(msgs))
        payload = b"".join(orjson.dumps(msgs[i]) + b"\n" for i in order)
        day = local_date(arrival, grid.tz_local).isoformat()
        folder = landing / f"arrival_date={day}" / f"feeder={folder_feeder}"
        folder.mkdir(parents=True, exist_ok=True)
        name = file_name(folder_feeder, hour_epoch, arrival)
        (folder / name).write_bytes(gzip.compress(payload, compresslevel=level, mtime=0))
        stats["rows"] += len(msgs)
        return f"arrival_date={day}/feeder={folder_feeder}/{name}"

    for f, feeder in enumerate(topo.feeder_ids):
        sl = topo.feeder_slice(f)
        for h in range(grid.days * 24):
            j0 = h * grid.per_hour
            sub = inj.present[sl, j0 : j0 + grid.per_hour]
            mm, jj = np.nonzero(sub)
            mm = mm + sl.start
            jj = jj + j0
            rows = [
                (ids[m], m, j, int(wh))
                for m, j, wh in zip(
                    mm.tolist(), jj.tolist(), inj.emitted_wh[mm, jj].tolist(), strict=True
                )
            ]
            rows += [
                (f"MTR-{fake:05d}", m, j, int(inj.emitted_wh[m, j]))
                for m, j, fake in unknown.get((f, h), [])
            ]
            hour_epoch = int(grid.epochs[j0])
            days_late = inj.late_files.get((f, h), 0)
            arrival = hour_epoch + hour_s + delay_s + days_late * 86400
            path = emit(rows, feeder, hour_epoch, arrival)
            stats["files"] += 1
            if days_late:
                late_records.append({"file": path, "days_late": days_late})
            resend = [(ids[m], m, j, int(inj.emitted_wh[m, j])) for m, j in exact.get((f, h), [])]
            resend += [
                (ids[m], m, j, int(inj.emitted_wh[m, j]) + d)
                for m, j, d in conflict.get((f, h), [])
            ]
            if resend:
                emit(resend, feeder, hour_epoch, arrival + resend_s)
                stats["resend_files"] += 1
    stats["late_files"] = late_records
    return stats
