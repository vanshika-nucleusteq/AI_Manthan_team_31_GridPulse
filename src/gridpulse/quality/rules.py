"""Quality rules over the lookback window; failing bronze rows go to quarantine with a reason."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pyarrow as pa

from gridpulse.common.config import load_yaml
from gridpulse.common.lake import (
    Lake,
    existing_parts,
    lake_from_config,
    overwrite_partition,
    sql_path,
)
from gridpulse.ingest.bronze import BRONZE_SQL, connect, to_arrow
from gridpulse.ingest.landing import SCHEMA

RULES = [
    "CORRUPT_FILE",
    "MALFORMED_RECORD",
    "BAD_TIMESTAMP",
    "UNKNOWN_METER",
    "BAD_UNIT",
    "METER_ERROR",
    "NEGATIVE_READING",
    "REGISTER_DECREASED",
]

CHECK_SQL = """
CREATE OR REPLACE TEMP TABLE enriched AS
SELECT
    b.*,
    m.meter_id IS NOT NULL AS known_meter,
    m.reporting_unit AS master_unit,
    coalesce(b.energy_unit, m.reporting_unit) AS unit_resolved,
    CASE
        WHEN b.energy_unit IS NOT NULL THEN b.unit_source
        WHEN m.reporting_unit IS NOT NULL THEN 'master'
    END AS unit_source_resolved,
    -- IST day of the snapped interval, not the raw ts: 18:29:40Z snaps to 18:30Z (next IST day).
    CASE
        WHEN b.ts IS NOT NULL
            THEN (to_timestamp(round(epoch(b.ts) / {step}) * {step}) AT TIME ZONE '{tz}')::DATE
        ELSE b.arrival_date
    END AS reading_date,
    CAST(epoch(b.ts) AS BIGINT) % {step} AS grid_rem,
    to_timestamp(round(epoch(b.ts) / {step}) * {step}) AS interval_start
FROM bronze AS b
LEFT JOIN master AS m USING (meter_id);

-- Only readings dated context_start..ds matter; later arrivals for other days are skipped here.
DELETE FROM enriched WHERE reading_date NOT BETWEEN DATE '{context_start}' AND DATE '{ds}';

CREATE OR REPLACE TEMP TABLE pre AS
SELECT
    *,
    CASE
        WHEN unit_resolved = 'Wh' THEN CAST(energy_value * 0.001 AS DECIMAL(18, 6))
        WHEN unit_resolved = 'kWh' THEN CAST(energy_value AS DECIMAL(18, 6))
    END AS energy_kwh,
    CASE
        WHEN parse_rule IS NOT NULL THEN parse_rule
        WHEN status NOT IN ({statuses}) THEN 'MALFORMED_RECORD'
        WHEN ts IS NULL THEN 'BAD_TIMESTAMP'
        WHEN least(grid_rem, {step} - grid_rem) > {tolerance} THEN 'BAD_TIMESTAMP'
        WHEN ts > ingested_at + INTERVAL {tolerance} SECOND THEN 'BAD_TIMESTAMP'
        WHEN NOT known_meter THEN 'UNKNOWN_METER'
        WHEN unit_resolved IS NULL OR unit_resolved NOT IN ({units}) THEN 'BAD_UNIT'
        WHEN status = 'ERROR' THEN 'METER_ERROR'
        WHEN energy_value < 0 THEN 'NEGATIVE_READING'
    END AS rule_pre,
    CASE
        WHEN parse_rule IS NOT NULL THEN parse_reason
        WHEN status NOT IN ({statuses}) THEN 'unknown status ' || status
        WHEN ts IS NULL AND ts_text IS NOT NULL
            AND NOT regexp_matches(ts_text, '(Z|[+-][0-9]{{2}}:?[0-9]{{2}})$')
            THEN 'ts has no time zone: ' || ts_text
        WHEN ts IS NULL THEN 'unparseable ts: ' || coalesce(ts_text, 'null')
        WHEN least(grid_rem, {step} - grid_rem) > {tolerance}
            THEN 'ts ' || least(grid_rem, {step} - grid_rem) || ' s off the {minutes}-minute grid'
        WHEN ts > ingested_at + INTERVAL {tolerance} SECOND THEN 'ts is after file arrival'
        WHEN NOT known_meter THEN 'meter_id ' || meter_id || ' not in meter_master'
        WHEN unit_resolved IS NULL THEN 'no unit in message or meter_master'
        WHEN unit_resolved NOT IN ({units}) THEN 'unknown unit ' || unit_resolved
        WHEN status = 'ERROR' THEN 'meter reported status ERROR'
        WHEN energy_value < 0 THEN 'energy ' || energy_text || ' ' || unit_resolved || ' < 0'
    END AS reason_pre
FROM enriched;

CREATE OR REPLACE TEMP TABLE prev AS
WITH per_interval AS (
    SELECT meter_id, interval_start, max(energy_kwh) AS kwh
    FROM pre WHERE rule_pre IS NULL
    GROUP BY meter_id, interval_start
)
SELECT
    meter_id,
    interval_start,
    lag(kwh) OVER (PARTITION BY meter_id ORDER BY interval_start) AS prev_kwh
FROM per_interval;

CREATE OR REPLACE TEMP TABLE checked AS
SELECT
    pre.*,
    prev.prev_kwh,
    CASE
        WHEN rule_pre IS NOT NULL THEN rule_pre
        WHEN prev.prev_kwh IS NOT NULL AND energy_kwh < prev.prev_kwh AND status <> 'ROLLOVER'
            THEN 'REGISTER_DECREASED'
    END AS rule,
    CASE
        WHEN rule_pre IS NOT NULL THEN reason_pre
        WHEN prev.prev_kwh IS NOT NULL AND energy_kwh < prev.prev_kwh AND status <> 'ROLLOVER'
            THEN 'register ' || energy_kwh || ' kWh < previous ' || prev.prev_kwh || ' kWh'
    END AS reason
FROM pre
LEFT JOIN prev USING (meter_id, interval_start);
"""

QUARANTINE_COLUMNS = """
    reading_date AS quarantine_date, rule, reason, source_file, line_no, arrival_date, ingested_at,
    schema_version, meter_id, ts_text, ts, energy_text, energy_value, unit_resolved AS energy_unit,
    unit_source_resolved AS unit_source, energy_kwh, status, voltage, firmware_version, raw_json
"""


def _settings() -> dict[str, Any]:
    quality, pipeline = load_yaml("quality"), load_yaml("pipeline")
    if list(quality["rules_in_order"]) != RULES:
        raise ValueError("config/quality.yaml rules_in_order does not match the rules in code")
    return {"quality": quality, "pipeline": pipeline}


def bronze_parts_from(lake: Lake, first: date) -> list[str]:
    """Bronze partitions with arrival_date >= first. Reading later arrivals is what lets a
    backfill of an old ds pick up files that landed after its lookback window had closed."""
    root = lake.root / "bronze"
    folders = sorted(root.glob("arrival_date=*")) if root.exists() else []
    keep = [
        f
        for f in folders
        if not f.name.endswith((".tmp", ".old"))
        and date.fromisoformat(f.name.removeprefix("arrival_date=")) >= first
    ]
    return existing_parts(keep)


def check_window(ds: date, lake: Lake, settings: dict[str, Any]) -> tuple[Any, date]:
    """Build table `checked` for reading dates first..ds plus context days; returns (con, first)."""
    q, p = settings["quality"], settings["pipeline"]
    first = ds - timedelta(days=int(q["lookback_days"]) - 1)
    context_start = first - timedelta(days=int(q["context_days"]))
    con = connect()
    parts = bronze_parts_from(lake, context_start)
    if parts:
        con.execute(f"CREATE TEMP VIEW bronze AS SELECT * FROM read_parquet({parts!r})")
    else:
        con.register("raw", SCHEMA.empty_table())
        empty = BRONZE_SQL.replace("$arrival_date", f"DATE '{ds.isoformat()}'")
        con.execute(f"CREATE TEMP TABLE bronze AS {empty}")
    con.execute(
        "CREATE TEMP TABLE master AS SELECT meter_id, reporting_unit FROM read_csv("
        f"{sql_path(lake.meter_master)}, header = true, all_varchar = true)"
    )
    quote = lambda items: ", ".join(f"'{i}'" for i in items)  # noqa: E731
    minutes = int(p["interval_minutes"])
    con.execute(
        CHECK_SQL.format(
            tz=p["timezone_local"],
            step=minutes * 60,
            minutes=minutes,
            tolerance=int(q["timestamp_tolerance_seconds"]),
            statuses=quote(q["allowed_status"]),
            units=quote(q["allowed_units"]),
            context_start=context_start,
            ds=ds,
        )
    )
    return con, first


def checked_rows(ds: date, lake: Lake | None = None) -> pa.Table:
    """Every row of the window with its rule (NULL = passed); used by tests and P5 checks."""
    con, first = check_window(ds, lake or lake_from_config(), _settings())
    result = con.sql(
        f"SELECT * FROM checked WHERE reading_date BETWEEN DATE '{first}' AND DATE '{ds}' "
        "ORDER BY source_file, line_no"
    )
    return to_arrow(result)


def quality(ds: date, lake: Lake | None = None) -> dict[str, Any]:
    """Rewrite quarantine/date=D for each reading date in the lookback window ending at ds."""
    lake = lake or lake_from_config()
    con, first = check_window(ds, lake, _settings())
    written: dict[str, int] = {}
    day = first
    while day <= ds:
        sql = (
            f"SELECT {QUARANTINE_COLUMNS} FROM checked "
            f"WHERE rule IS NOT NULL AND reading_date = DATE '{day.isoformat()}'"
        )
        written[day.isoformat()] = overwrite_partition(
            con, sql, lake.quarantine(day), "source_file, line_no"
        )
        day += timedelta(days=1)
    by_rule = dict(
        con.execute(
            f"SELECT rule, count(*) FROM checked WHERE rule IS NOT NULL "
            f"AND reading_date BETWEEN DATE '{first}' AND DATE '{ds}' GROUP BY rule ORDER BY rule"
        ).fetchall()
    )
    passed = con.execute(
        f"SELECT count(*) FROM checked WHERE rule IS NULL "
        f"AND reading_date BETWEEN DATE '{first}' AND DATE '{ds}'"
    ).fetchone()[0]
    return {
        "step": "quality",
        "ds": ds.isoformat(),
        "quarantine_rows_by_date": written,
        "by_rule": by_rule,
        "passed_rows": int(passed),
    }
