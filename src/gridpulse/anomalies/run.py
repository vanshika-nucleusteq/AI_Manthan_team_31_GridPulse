"""anomalies(ds): spike, tamper and outage checks over gold hourly and silver gaps."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from gridpulse.aggregate.run import run_id_for
from gridpulse.aggregate.tables import BY_NAME
from gridpulse.anomalies.outage import OUTAGE_SQL
from gridpulse.anomalies.spike import SPIKE_SQL
from gridpulse.anomalies.tamper import TAMPER_SQL
from gridpulse.common.config import load_yaml
from gridpulse.common.lake import Lake, go_live, lake_from_config, overwrite_partitioned, sql_path
from gridpulse.ingest.bronze import connect

EVENTS_SQL = """
CREATE OR REPLACE TEMP TABLE events AS
SELECT
    left(sha256(type || '|' || coalesce(meter_id, feeder_id) || '|'
        || strftime(window_start, '%Y-%m-%dT%H:%M:%SZ')), 16) AS anomaly_id,
    type, meter_id, feeder_id, zone_id,
    (window_start AT TIME ZONE '{tz}')::DATE AS local_date,
    window_start, window_end, CAST(round(score, 4) AS DECIMAL(12, 4)) AS score,
    CAST(details AS VARCHAR) AS details
FROM (
    SELECT * FROM spike_events
    UNION ALL SELECT * FROM tamper_events
    UNION ALL SELECT * FROM outage_events
);
"""


def scan_window(ds: date) -> tuple[date, list[date]]:
    """First IST day whose events this run (re)writes, and the days in [first, ds]."""
    lookback = int(load_yaml("quality")["lookback_days"])
    context = int(load_yaml("anomalies")["scan_context_days"])
    first = max(ds - timedelta(days=lookback - 1 + context), go_live())
    return first, [first + timedelta(days=i) for i in range((ds - first).days + 1)]


def detect(con: Any, scan_start: date, ds: date) -> None:
    """Create temp table `events` from temp tables h, daily, g and feeder_n."""
    a, p = load_yaml("anomalies"), load_yaml("pipeline")
    common = {"tz": p["timezone_local"], "scan_start": scan_start, "ds": ds}
    con.execute(SPIKE_SQL.format(**common, **a["spike"]))
    con.execute(TAMPER_SQL.format(**common, **a["tamper"]))
    con.execute(OUTAGE_SQL.format(**common, step=int(p["interval_minutes"]) * 60, **a["outage"]))
    con.execute(EVENTS_SQL.format(tz=p["timezone_local"]))


def load_inputs(con: Any, lake: Lake, scan_start: date, ds: date) -> None:
    baseline = int(load_yaml("anomalies")["spike"]["baseline_days"])
    history = max(scan_start - timedelta(days=baseline), go_live())
    hourly = lake.files("gold", "consumption_hourly", history, ds)
    daily = lake.files("gold", "consumption_daily_meter", history, ds)
    gaps = lake.files("silver", "gaps", scan_start - timedelta(days=1), ds)
    src = "read_parquet({}, hive_partitioning = false)"
    con.execute(
        "CREATE TEMP TABLE h AS SELECT meter_id, feeder_id, zone_id, local_date, hour_start, kwh, "
        f"intervals_present, has_gap FROM {src.format(repr(hourly))}"
        if hourly
        else "CREATE TEMP TABLE h (meter_id VARCHAR, feeder_id VARCHAR, zone_id VARCHAR, "
        "local_date DATE, hour_start TIMESTAMPTZ, kwh DECIMAL(18, 6), intervals_present BIGINT, "
        "has_gap BOOLEAN)"
    )
    con.execute(
        "CREATE TEMP TABLE daily AS SELECT meter_id, local_date, completeness_pct "
        f"FROM {src.format(repr(daily))}"
        if daily
        else "CREATE TEMP TABLE daily (meter_id VARCHAR, local_date DATE, "
        "completeness_pct DECIMAL(5, 2))"
    )
    con.execute(
        "CREATE TEMP TABLE g AS SELECT meter_id, feeder_id, zone AS zone_id, interval_start "
        f"FROM read_parquet({gaps!r}, hive_partitioning = true, "
        "hive_types = {'zone': 'VARCHAR', 'date': 'DATE'}) WHERE cause = 'not_received'"
        if gaps
        else "CREATE TEMP TABLE g (meter_id VARCHAR, feeder_id VARCHAR, zone_id VARCHAR, "
        "interval_start TIMESTAMPTZ)"
    )
    con.execute(
        "CREATE TEMP TABLE feeder_n AS SELECT feeder_id, count(*) AS meters "
        f"FROM read_csv({sql_path(lake.meter_master)}, header = true, all_varchar = true) "
        f"WHERE CAST(install_date AS DATE) <= DATE '{ds}' GROUP BY feeder_id"
    )


def anomalies(ds: date, lake: Lake | None = None, run_id: str | None = None) -> dict[str, Any]:
    lake = lake or lake_from_config()
    run_id = run_id_for(ds, run_id)
    scan_start, days = scan_window(ds)
    con = connect()
    load_inputs(con, lake, scan_start, ds)
    detect(con, scan_start, ds)
    table = BY_NAME["anomalies"]
    columns = ", ".join(table.columns)
    written = 0
    for day in days:
        part = f"date={day.isoformat()}"
        written += overwrite_partitioned(
            con,
            f"SELECT {columns}, zone_id AS zone FROM events WHERE local_date = DATE '{day}'",
            lake.gold(table.name, part),
            table.order_by,
            "zone",
            lake.archive(table.name, run_id, part),
        )
    by_type = dict(con.execute("SELECT type, count(*) FROM events GROUP BY type").fetchall())
    return {
        "step": "anomalies",
        "ds": ds.isoformat(),
        "scan_start": scan_start.isoformat(),
        "events": written,
        "by_type": by_type,
    }
