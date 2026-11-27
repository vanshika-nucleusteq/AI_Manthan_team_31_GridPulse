"""Expected 15-minute grid per meter and IST day; a grid cell with no kept reading is a gap."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo


def day_start_utc(day: date, tz: str) -> str:
    """UTC instant of local midnight, e.g. 2026-08-01 IST -> 2026-07-31 18:30:00+00."""
    start = datetime.combine(day, time(0), tzinfo=ZoneInfo(tz)).astimezone(UTC)
    return start.strftime("%Y-%m-%d %H:%M:%S+00")


def build_gaps(con: Any, days: list[date], tz: str, per_day: int, step_s: int) -> None:
    """Create temp table `gaps` from `master_full`, `kept` and the quarantined rows in `checked`."""
    values = ", ".join(f"(DATE '{d}', TIMESTAMPTZ '{day_start_utc(d, tz)}')" for d in days)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE grid AS
        SELECT
            m.meter_id, m.feeder_id, m.zone, d.local_date,
            d.day_start + to_seconds(r.i * {step_s}) AS interval_start
        FROM master_full AS m
        CROSS JOIN (VALUES {values}) AS d(local_date, day_start)
        CROSS JOIN range({per_day}) AS r(i)
        WHERE m.install_date <= d.local_date;

        CREATE OR REPLACE TEMP TABLE quarantined_cells AS
        SELECT meter_id, interval_start, min(rule) AS rule
        FROM checked
        WHERE rule IS NOT NULL AND interval_start IS NOT NULL
        GROUP BY meter_id, interval_start;

        CREATE OR REPLACE TEMP TABLE gaps AS
        SELECT
            g.meter_id, g.interval_start, g.local_date, g.feeder_id, g.zone,
            CASE WHEN q.rule IS NULL THEN 'not_received' ELSE 'quarantined:' || q.rule END AS cause
        FROM grid AS g
        ANTI JOIN kept AS k USING (meter_id, interval_start)
        LEFT JOIN quarantined_cells AS q USING (meter_id, interval_start);
        """)


def first_day(ds: date, lookback_days: int) -> date:
    return ds - timedelta(days=lookback_days - 1)
