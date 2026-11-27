"""Normalise passed readings: kWh, dedup with dup_conflict, order, interval consumption, gaps."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from gridpulse.common.lake import (
    Lake,
    go_live,
    lake_from_config,
    overwrite_partitioned,
    sql_path,
)
from gridpulse.normalise.gaps import build_gaps, first_day
from gridpulse.quality.rules import _settings, check_window

KEPT_SQL = """
CREATE OR REPLACE TEMP TABLE master_full AS
SELECT
    meter_id, feeder_id, zone_id AS zone,
    CAST(register_max_kwh AS DECIMAL(18, 6)) AS register_max_kwh,
    CAST(install_date AS DATE) AS install_date
FROM read_csv({master}, header = true, all_varchar = true);

-- Steps 1-2 come from quality: only rows that passed every rule, already converted to kWh.
CREATE OR REPLACE TEMP TABLE passed AS
SELECT
    meter_id, interval_start, energy_kwh, status, ingested_at, source_file, line_no,
    schema_version, unit_source_resolved, ts
FROM checked
WHERE rule IS NULL AND reading_date BETWEEN DATE '{context}' AND DATE '{ds}';

-- Step 3: one row per (meter_id, interval_start). Identical copies are dropped and counted;
-- different values keep the latest ingested_at and set dup_conflict.
CREATE OR REPLACE TEMP TABLE kept AS
WITH keys AS (
    SELECT
        meter_id, interval_start,
        count(*) AS copies,
        count(DISTINCT row(energy_kwh, status)) AS variants
    FROM passed
    GROUP BY meter_id, interval_start
), ranked AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY meter_id, interval_start
            ORDER BY ingested_at DESC, source_file DESC, line_no DESC
        ) AS rn
    FROM passed
)
SELECT
    r.*,
    k.variants > 1 AS dup_conflict,
    k.copies - 1 AS dup_count,
    k.copies - k.variants AS exact_dups_dropped
FROM ranked AS r
JOIN keys AS k USING (meter_id, interval_start)
WHERE r.rn = 1;

-- Step 4: order by meter and interval; consumption is the register difference.
CREATE OR REPLACE TEMP TABLE sequenced AS
WITH seq AS (
    SELECT
        k.*, m.feeder_id, m.zone, m.register_max_kwh,
        lag(k.energy_kwh) OVER w AS prev_kwh,
        lag(k.interval_start) OVER w AS prev_interval
    FROM kept AS k
    JOIN master_full AS m USING (meter_id)
    WINDOW w AS (PARTITION BY k.meter_id ORDER BY k.interval_start)
)
SELECT
    *,
    (interval_start AT TIME ZONE '{tz}')::DATE AS local_date,
    status = 'ROLLOVER' AND energy_kwh < prev_kwh AS is_rollover,
    status = 'ROLLOVER' AND energy_kwh >= prev_kwh AS rollover_without_wrap,
    CAST(
        CASE
            WHEN prev_kwh IS NULL THEN NULL
            WHEN status = 'ROLLOVER' AND energy_kwh < prev_kwh
                THEN register_max_kwh - prev_kwh + energy_kwh
            ELSE energy_kwh - prev_kwh
        END AS DECIMAL(18, 6)
    ) AS consumption_kwh,
    CAST((epoch(interval_start) - epoch(prev_interval)) / {step} AS INTEGER) AS intervals_spanned
FROM seq;
"""

READINGS_COLUMNS = """
    meter_id, interval_start, local_date, feeder_id, zone,
    energy_kwh AS register_kwh, consumption_kwh,
    intervals_spanned, coalesce(intervals_spanned > 1, false) AS spans_gap,
    prev_kwh IS NOT NULL AS has_previous,
    coalesce(is_rollover, false) AS is_rollover,
    coalesce(rollover_without_wrap, false) AS rollover_without_wrap,
    status, dup_conflict, dup_count, exact_dups_dropped,
    schema_version, unit_source_resolved AS unit_source, source_file, line_no, ingested_at, ts
"""


def normalise(ds: date, lake: Lake | None = None) -> dict[str, Any]:
    """Rewrite silver/readings and silver/gaps for each IST day of the window ending at ds."""
    lake = lake or lake_from_config()
    settings = _settings()
    q, p = settings["quality"], settings["pipeline"]
    con, _ = check_window(ds, lake, settings)
    first = max(first_day(ds, int(q["lookback_days"])), go_live())
    context = first - timedelta(days=int(q["context_days"]))
    tz, step = p["timezone_local"], int(p["interval_minutes"]) * 60
    con.execute(
        KEPT_SQL.format(
            master=sql_path(lake.meter_master), context=context, ds=ds, tz=tz, step=step
        )
    )
    days = [first + timedelta(days=i) for i in range((ds - first).days + 1)]
    build_gaps(con, days, tz, int(p["intervals_per_day"]), step)

    written: dict[str, dict[str, int]] = {}
    for day in days:
        where = f"local_date = DATE '{day}'"
        written[day.isoformat()] = {
            "readings": overwrite_partitioned(
                con,
                f"SELECT {READINGS_COLUMNS} FROM sequenced WHERE {where}",
                lake.silver("readings", day),
                "meter_id, interval_start",
                "zone",
            ),
            "gaps": overwrite_partitioned(
                con,
                f"SELECT * FROM gaps WHERE {where}",
                lake.silver("gaps", day),
                "meter_id, interval_start",
                "zone",
            ),
        }
    window = f"local_date BETWEEN DATE '{first}' AND DATE '{ds}'"
    stats = con.execute(f"""
        SELECT
            count(*), sum(exact_dups_dropped), count(*) FILTER (WHERE dup_conflict),
            count(*) FILTER (WHERE is_rollover), count(*) FILTER (WHERE intervals_spanned > 1),
            count(*) FILTER (WHERE consumption_kwh < 0)
        FROM sequenced WHERE {window}
        """).fetchone()
    gaps = dict(
        con.execute(
            f"SELECT cause, count(*) FROM gaps WHERE {window} GROUP BY cause ORDER BY cause"
        ).fetchall()
    )
    keys = ["readings", "exact_dups_dropped", "dup_conflicts", "rollovers", "spans_gap"]
    return {
        "step": "normalise",
        "ds": ds.isoformat(),
        "written": written,
        **{k: int(v or 0) for k, v in zip(keys, stats[:5], strict=True)},
        "negative_consumption": int(stats[5] or 0),
        "gaps_by_cause": gaps,
    }
