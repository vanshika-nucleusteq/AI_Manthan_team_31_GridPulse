"""CLI: python -m gridpulse.generator --meters 5000 --days 14 --start 2026-08-01 --seed 42."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import orjson

from gridpulse.common.config import load_yaml
from gridpulse.generator.run import generate


def main(argv: Sequence[str] | None = None) -> int:
    defaults = load_yaml("generator")["defaults"]
    parser = argparse.ArgumentParser(prog="gridpulse.generator", description=__doc__)
    parser.add_argument("--meters", type=int, default=int(defaults["meters"]))
    parser.add_argument("--days", type=int, default=int(defaults["days"]))
    parser.add_argument(
        "--start", type=date.fromisoformat, default=date.fromisoformat(str(defaults["start"]))
    )
    parser.add_argument("--seed", type=int, default=int(defaults["seed"]))
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument(
        "--overwrite", action="store_true", help="delete previous landing/, answer key, master"
    )
    args = parser.parse_args(argv)
    began = time.perf_counter()
    try:
        key = generate(args.meters, args.days, args.start, args.seed, args.out, args.overwrite)
    except (FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = {
        "seconds": round(time.perf_counter() - began, 1),
        "totals": key["totals"],
        "skipped": key["skipped"],
    }
    print(orjson.dumps(summary, option=orjson.OPT_INDENT_2).decode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
