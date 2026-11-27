"""Reconciliation: silver kWh per IST day must equal gold daily (zone, meter) and hourly sums.

Run: python -m gridpulse.aggregate.reconcile --from 2026-08-01 --to 2026-08-14
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from gridpulse.common.lake import Lake, lake_from_config
from gridpulse.ingest.bronze import connect

SOURCES = {
    "silver_kwh": ("silver", "readings", "consumption_kwh"),
    "gold_zone_kwh": ("gold", "consumption_daily_zone", "kwh"),
    "gold_meter_kwh": ("gold", "consumption_daily_meter", "kwh"),
    "gold_hourly_kwh": ("gold", "consumption_hourly", "kwh"),
}


def reconcile(first: date, last: date, lake: Lake | None = None) -> list[dict[str, Any]]:
    lake = lake or lake_from_config()
    con = connect()
    per_source: dict[str, dict[date, Decimal]] = {}
    for name, (layer, table, column) in SOURCES.items():
        files = lake.files(layer, table, first, last)
        per_source[name] = (
            dict(
                con.sql(
                    f"SELECT local_date, sum({column}) FROM read_parquet({files!r}) GROUP BY 1"
                ).fetchall()
            )
            if files
            else {}
        )
    days = sorted(set().union(*per_source.values()))
    result = []
    for day in days:
        row: dict[str, Any] = {"local_date": day}
        for name in SOURCES:
            row[name] = per_source[name].get(day, Decimal(0)) or Decimal(0)
        row["max_abs_diff"] = max(abs(row[n] - row["silver_kwh"]) for n in SOURCES)
        result.append(row)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gridpulse.aggregate.reconcile", description=__doc__)
    parser.add_argument("--from", dest="first", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="last", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    rows = reconcile(args.first, args.last)
    header = ["local_date", *SOURCES, "max_abs_diff"]
    print(" | ".join(f"{h:>15}" for h in header))
    for row in rows:
        print(" | ".join(f"{str(row[h]):>15}" for h in header))
    bad = [r for r in rows if r["max_abs_diff"] != 0]
    print(f"{len(rows)} days, {len(bad)} with a difference: {'FAIL' if bad else 'PASS'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
