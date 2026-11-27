"""Outage: many meters on one feeder missing the same intervals; consecutive intervals merge."""

from __future__ import annotations

# Input g: not-received gaps (meter_id, feeder_id, zone_id, interval_start). Quarantined readings
# are a data-quality matter, not an outage. feeder_n: meters expected per feeder.
OUTAGE_SQL = """
CREATE OR REPLACE TEMP TABLE outage_events AS
WITH per_interval AS (
    SELECT feeder_id, any_value(zone_id) AS zone_id, interval_start, count(*) AS missing
    FROM g
    GROUP BY feeder_id, interval_start
), hit AS (
    SELECT p.*, f.meters, p.missing * 1.0 / f.meters AS share
    FROM per_interval AS p
    JOIN feeder_n AS f USING (feeder_id)
    WHERE p.missing * 1.0 / f.meters >= {feeder_missing_share}
), runs AS (
    SELECT
        *,
        CAST(floor(epoch(interval_start) / {step}) AS BIGINT)
            - row_number() OVER (PARTITION BY feeder_id ORDER BY interval_start) AS run_key
    FROM hit
)
SELECT
    'outage' AS type, NULL::VARCHAR AS meter_id, feeder_id, any_value(zone_id) AS zone_id,
    min(interval_start) AS window_start,
    max(interval_start) + to_seconds({step}) AS window_end,
    max(share) AS score,
    json_object('intervals', count(*), 'max_meters_missing', max(missing),
                'meters_on_feeder', any_value(meters)) AS details
FROM runs
GROUP BY feeder_id, run_key
HAVING count(*) >= {min_consecutive_intervals}
   AND (min(interval_start) AT TIME ZONE '{tz}')::DATE BETWEEN DATE '{scan_start}' AND DATE '{ds}';
"""
