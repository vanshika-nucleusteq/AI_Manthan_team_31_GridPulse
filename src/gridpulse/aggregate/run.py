"""aggregate(ds): rebuild gold for the lookback window and the billing month(s) it touches."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

from gridpulse.aggregate.billing import BILLING_SQL
from gridpulse.aggregate.daily import DAILY_SQL
from gridpulse.aggregate.hourly import HOURLY_SQL
from gridpulse.aggregate.quality_daily import QUALITY_DAILY_SQL
from gridpulse.aggregate.tables import TABLES, GoldTable
from gridpulse.common.config import load_yaml
from gridpulse.common.lake import (
    Lake,
    lake_from_config,
    overwrite_partition,
    overwrite_partitioned,
    sql_path,
)
from gridpulse.ingest.bronze import connect

SOURCE = {
    "consumption_hourly": "hourly",
    "consumption_hourly_feeder": "hourly_feeder",
    "consumption_hourly_zone": "hourly_zone",
    "consumption_daily_meter": "daily_meter",
    "consumption_daily_feeder": "daily_feeder",
    "consumption_daily_zone": "daily_zone",
    "data_quality_daily": "quality_daily",
    "billing_monthly": "billing",
}
EMPTY_SILVER = """
CREATE TEMP TABLE r (meter_id VARCHAR, interval_start TIMESTAMPTZ, local_date DATE,
    feeder_id VARCHAR, zone_id VARCHAR, register_kwh DECIMAL(18, 6),
    consumption_kwh DECIMAL(18, 6), spans_gap BOOLEAN, is_rollover BOOLEAN)
"""


def month_end(month: date) -> date:
    return (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def window(ds: date) -> tuple[list[date], list[date]]:
    """IST days rebuilt by this run (the lookback window) and the months they fall in."""
    lookback = int(load_yaml("quality")["lookback_days"])
    days = [ds - timedelta(days=i) for i in range(lookback - 1, -1, -1)]
    return days, sorted({d.replace(day=1) for d in days})


def part_name(table: GoldTable, key: date) -> str:
    return f"month={key:%Y-%m}" if table.partition == "month" else f"date={key.isoformat()}"


def run_id_for(ds: date, run_id: str | None) -> str:
    return run_id or os.environ.get("AIRFLOW_CTX_DAG_RUN_ID") or f"manual__{ds.isoformat()}"


def load_inputs(con: Any, lake: Lake, ds: date, days: list[date], months: list[date]) -> None:
    q, p, a = load_yaml("quality"), load_yaml("pipeline"), load_yaml("aggregate")
    read_first = months[0] - timedelta(days=int(a["billing_start_lookup_days"]))
    files = lake.files("silver", "readings", read_first, ds)
    if files:
        con.execute(
            "CREATE TEMP TABLE r AS SELECT * EXCLUDE (zone, date), zone AS zone_id "
            f"FROM read_parquet({files!r}, hive_partitioning = true, "
            "hive_types = {'zone': 'VARCHAR', 'date': 'DATE'})"
        )
    else:
        con.execute(EMPTY_SILVER)
    con.execute(
        "CREATE TEMP TABLE master_full AS SELECT meter_id, feeder_id, zone_id, "
        "CAST(register_max_kwh AS DECIMAL(18, 6)) AS register_max_kwh, "
        "CAST(install_date AS DATE) AS install_date "
        f"FROM read_csv({sql_path(lake.meter_master)}, header = true, all_varchar = true)"
    )
    calc_first = min(months[0], days[0])
    calc_days = [calc_first + timedelta(days=i) for i in range((ds - calc_first).days + 1)]
    con.execute(
        "CREATE TEMP TABLE days AS SELECT * FROM (VALUES "
        + ", ".join(f"(DATE '{d}')" for d in calc_days)
        + ") AS t(local_date)"
    )
    con.execute(
        "CREATE TEMP TABLE month_bounds AS SELECT * FROM (VALUES "
        + ", ".join(f"(DATE '{m}', DATE '{month_end(m)}', {month_end(m) <= ds})" for m in months)
        + ") AS t(month, month_end, period_complete)"
    )
    quarantine = lake.files("", "quarantine", days[0], ds)
    if quarantine:
        con.execute(f"CREATE TEMP TABLE quarantine AS SELECT * FROM read_parquet({quarantine!r})")
    else:
        con.execute(
            "CREATE TEMP TABLE quarantine (quarantine_date DATE, rule VARCHAR, meter_id VARCHAR)"
        )
    fmt = {
        "tz": p["timezone_local"],
        "per_day": int(p["intervals_per_day"]),
        "per_hour": 60 // int(p["interval_minutes"]),
        "flag_pct": int(q["completeness_flag_pct"]),
        "first": days[0],
        "ds": ds,
        "lookup_days": int(a["billing_start_lookup_days"]),
        "tolerance": float(a["billing_tolerance_kwh"]),
    }
    for sql in (DAILY_SQL, HOURLY_SQL, BILLING_SQL, QUALITY_DAILY_SQL):
        con.execute(sql.format(**fmt))


def aggregate(ds: date, lake: Lake | None = None, run_id: str | None = None) -> dict[str, Any]:
    lake = lake or lake_from_config()
    run_id = run_id_for(ds, run_id)
    days, months = window(ds)
    con = connect()
    load_inputs(con, lake, ds, days, months)
    rows: dict[str, int] = {}
    for table in TABLES:
        keys = months if table.partition == "month" else days
        column = "month" if table.partition == "month" else "local_date"
        rows[table.name] = 0
        for key in keys:
            part = part_name(table, key)
            extra = ", zone_id AS zone" if table.zone_partitioned else ""
            select = (
                f"SELECT {', '.join(table.columns)}{extra} "
                f"FROM {SOURCE[table.name]} WHERE {column} = DATE '{key}'"
            )
            target, archive = lake.gold(table.name, part), lake.archive(table.name, run_id, part)
            if table.zone_partitioned:
                rows[table.name] += overwrite_partitioned(
                    con, select, target, table.order_by, "zone", archive
                )
            else:
                rows[table.name] += overwrite_partition(
                    con, select, target, table.order_by, archive
                )
    review = con.execute(
        "SELECT count(*) FILTER (WHERE billing_status = 'REVIEW'), count(*) FROM billing"
    ).fetchone()
    return {
        "step": "aggregate",
        "ds": ds.isoformat(),
        "run_id": run_id,
        "rows": rows,
        "bills_review": int(review[0]),
        "bills_total": int(review[1]),
    }
