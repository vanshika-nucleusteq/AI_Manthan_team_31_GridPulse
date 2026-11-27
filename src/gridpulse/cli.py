"""Command-line entry point the DAG calls: python -m gridpulse.cli <step> --ds YYYY-MM-DD."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

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
    return None


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_step(args.step, args.ds)
    if result is None:
        print(f"TODO: {args.step} for ds={args.ds.isoformat()} built in {STEPS[args.step]}")
    else:
        print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
