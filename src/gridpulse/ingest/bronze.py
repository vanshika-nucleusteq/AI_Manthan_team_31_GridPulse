"""Landing to bronze for one arrival date: parse JSON, detect schema version, keep raw_json."""

from __future__ import annotations

from datetime import date
from typing import Any

import duckdb
import pyarrow as pa

from gridpulse.common.lake import Lake, lake_from_config, overwrite_partition
from gridpulse.ingest.landing import read_landing

# Schema detection: an explicit schema_version wins; otherwise voltage or firmware_version means v2.
BRONZE_SQL = """
WITH src AS (
    SELECT *, file_rule IS NULL AND raw_json IS NOT NULL AND json_valid(raw_json) AS ok_json
    FROM raw
), parsed AS (
    SELECT *, try_cast(CASE WHEN ok_json THEN raw_json END AS JSON) AS jv FROM src
), obj AS (
    SELECT *, CASE WHEN json_type(jv) = 'OBJECT' THEN jv END AS j FROM parsed
), fields AS (
    SELECT
        *,
        json_exists(j, '$.schema_version') AS has_version,
        try_cast(j->>'schema_version' AS INTEGER) AS explicit_version,
        json_exists(j, '$.voltage') OR json_exists(j, '$.firmware_version') AS has_v2_fields,
        j->>'ts' AS ts_text,
        regexp_matches(j->>'ts', '(Z|[+-][0-9]{2}:?[0-9]{2})$') AS ts_has_zone
    FROM obj
), typed AS (
    SELECT
        *,
        CASE
            WHEN j IS NULL THEN NULL
            WHEN has_version THEN explicit_version
            WHEN has_v2_fields THEN 2
            ELSE 1
        END AS schema_version
    FROM fields
), energy AS (
    SELECT
        *,
        CASE WHEN schema_version = 1 THEN j->>'energy_wh' ELSE j->>'energy' END AS energy_text
    FROM typed
)
SELECT
    source_file,
    line_no,
    $arrival_date::DATE AS arrival_date,
    ingested_at,
    schema_version,
    CASE WHEN has_version THEN 'explicit' WHEN j IS NOT NULL THEN 'detected' END AS version_source,
    j->>'meter_id' AS meter_id,
    ts_text,
    CASE WHEN ts_has_zone THEN try_cast(ts_text AS TIMESTAMPTZ) END AS ts,
    energy_text,
    try_cast(energy_text AS DECIMAL(18, 6)) AS energy_value,
    CASE WHEN schema_version = 1 THEN 'Wh' ELSE j->>'unit' END AS energy_unit,
    CASE
        WHEN schema_version = 1 THEN 'v1'
        WHEN j->>'unit' IS NOT NULL THEN 'message'
    END AS unit_source,
    j->>'status' AS status,
    try_cast(j->>'voltage' AS DOUBLE) AS voltage,
    j->>'firmware_version' AS firmware_version,
    raw_json,
    CASE
        WHEN file_rule IS NOT NULL THEN file_rule
        WHEN NOT ok_json OR j IS NULL OR schema_version IS NULL
            OR schema_version NOT IN (1, 2)
            OR j->>'meter_id' IS NULL OR ts_text IS NULL OR energy_text IS NULL
            OR try_cast(energy_text AS DECIMAL(18, 6)) IS NULL OR j->>'status' IS NULL
            THEN 'MALFORMED_RECORD'
    END AS parse_rule,
    CASE
        WHEN file_rule IS NOT NULL THEN file_reason
        WHEN NOT ok_json THEN 'invalid JSON'
        WHEN j IS NULL THEN 'JSON is not an object'
        WHEN schema_version IS NULL OR schema_version NOT IN (1, 2)
            THEN 'unsupported schema_version ' || coalesce(j->>'schema_version', 'null')
        WHEN j->>'meter_id' IS NULL THEN 'missing meter_id'
        WHEN ts_text IS NULL THEN 'missing ts'
        WHEN energy_text IS NULL THEN 'missing energy'
        WHEN try_cast(energy_text AS DECIMAL(18, 6)) IS NULL
            THEN 'energy not numeric: ' || energy_text
        WHEN j->>'status' IS NULL THEN 'missing status'
    END AS parse_reason
FROM energy
"""


def to_arrow(result: Any) -> pa.Table:
    """DuckDB 2 renamed fetch_arrow_table to to_arrow_table; accept either."""
    fetch = getattr(result, "to_arrow_table", None) or result.fetch_arrow_table
    return fetch()


def connect() -> Any:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    return con


def ingest(ds: date, lake: Lake | None = None) -> dict[str, Any]:
    """Rebuild bronze/arrival_date=ds from every landing file that arrived on ds (IST date)."""
    lake = lake or lake_from_config()
    raw = read_landing(lake.landing, ds)
    con = connect()
    con.register("raw", raw)
    sql = BRONZE_SQL.replace("$arrival_date", f"DATE '{ds.isoformat()}'")
    rows = overwrite_partition(con, sql, lake.bronze(ds), "source_file, line_no")
    files = len(set(raw.column("source_file").to_pylist()))
    return {"step": "ingest", "ds": ds.isoformat(), "files": files, "rows": rows}
