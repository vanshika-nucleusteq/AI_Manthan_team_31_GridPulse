"""Command-line entry point the DAG calls: python -m gridpulse.cli <step> --ds YYYY-MM-DD."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

from gridpulse.common.runlog import record

STEPS: dict[str, str] = {
    "ingest": "P4",
    "quality": "P4",
    "normalise": "P5",
    "aggregate": "P6",
    "anomalies": "P7",
    "publish": "P6",
    "compact": "P8",
    "retention": "P8",
    "metrics": "P10",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gridpulse.cli", description="Run one gridpulse_daily step for one date."
    )
    sub = parser.add_subparsers(dest="step", required=True)
    for step in STEPS:
        step_parser = sub.add_parser(step, help=f"Run the {step} task.")
        step_parser.add_argument(
            "--ds",
            required=True,
            type=date.fromisoformat,
            help="Processing date YYYY-MM-DD (Airflow {{ ds }}).",
        )
    return parser


def run_step(step: str, ds: date) -> dict[str, Any] | None:
    """Run a built step and return its counts; None for steps still to be built."""
    if step == "ingest":
        from gridpulse.ingest.bronze import ingest

        return ingest(ds)
    if step == "quality":
        from gridpulse.quality.rules import quality

        return quality(ds)
    if step == "normalise":
        from gridpulse.normalise.readings import normalise

        return normalise(ds)
    if step == "aggregate":
        from gridpulse.aggregate.run import aggregate

        return aggregate(ds)
    if step == "publish":
        from gridpulse.publish.postgres import publish

        return publish(ds)
    if step == "anomalies":
        from gridpulse.anomalies.run import anomalies

        return anomalies(ds)
    if step == "compact":
        from gridpulse.maintenance.compact import compact

        return compact(ds)
    if step == "retention":
        from gridpulse.maintenance.retention import retention

        return retention(ds)
    return None


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = os.environ.get("AIRFLOW_CTX_DAG_RUN_ID") or f"manual__{args.ds.isoformat()}"
    started = datetime.now(UTC)
    try:
        result = run_step(args.step, args.ds)
    except Exception as exc:
        record(run_id, args.step, args.ds, started, datetime.now(UTC), "failed", None, repr(exc))
        raise
    if result is not None:
        record(run_id, args.step, args.ds, started, datetime.now(UTC), "success", result)
    if result is None:
        print(f"TODO: {args.step} for ds={args.ds.isoformat()} built in {STEPS[args.step]}")
    else:
        print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
