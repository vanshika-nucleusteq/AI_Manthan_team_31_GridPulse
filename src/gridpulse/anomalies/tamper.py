"""Suspected tamper: a reporting meter reads 0 kWh for >= zero_hours while its feeder is normal."""

from __future__ import annotations

# A zero hour has readings (intervals_present > 0) and kwh = 0, so outages (no rows) never count.
# Consecutive zero hours form a run; a missing hour ends it. The meter must be at least
# min_completeness_pct complete on every IST day the run touches, and at least
# feeder_normal_share of the other meters on its feeder must have kwh > 0 over the same window.
TAMPER_SQL = """
CREATE OR REPLACE TEMP TABLE tamper_events AS
WITH zero AS (
    SELECT
        *,
        CAST(floor(epoch(hour_start) / 3600) AS BIGINT)  -- floor: IST hours start at :30 UTC
            - row_number() OVER (PARTITION BY meter_id ORDER BY hour_start) AS run_key
    FROM h
    WHERE intervals_present > 0 AND kwh = 0
), runs AS (
    SELECT
        meter_id, any_value(feeder_id) AS feeder_id, any_value(zone_id) AS zone_id,
        min(hour_start) AS window_start, max(hour_start) + INTERVAL 1 HOUR AS window_end,
        count(*) AS zero_hours,
        min(local_date) AS first_day, max(local_date) AS last_day
    FROM zero
    GROUP BY meter_id, run_key
    HAVING count(*) >= {zero_hours}
), complete AS (
    SELECT r.meter_id, r.window_start, min(d.completeness_pct) AS min_completeness
    FROM runs AS r
    JOIN daily AS d ON d.meter_id = r.meter_id AND d.local_date BETWEEN r.first_day AND r.last_day
    GROUP BY r.meter_id, r.window_start
), neighbours AS (
    SELECT r.meter_id, r.window_start, o.meter_id AS other, sum(o.kwh) AS kwh
    FROM runs AS r
    JOIN h AS o
        ON o.feeder_id = r.feeder_id AND o.meter_id <> r.meter_id
        AND o.hour_start >= r.window_start AND o.hour_start < r.window_end
    GROUP BY r.meter_id, r.window_start, o.meter_id
), normal AS (
    SELECT
        r.meter_id, r.window_start,
        count(n.other) FILTER (WHERE n.kwh > 0) * 1.0 / (f.meters - 1) AS normal_share
    FROM runs AS r
    JOIN feeder_n AS f ON f.feeder_id = r.feeder_id
    LEFT JOIN neighbours AS n USING (meter_id, window_start)
    GROUP BY r.meter_id, r.window_start, f.meters
)
SELECT
    'tamper' AS type, r.meter_id, r.feeder_id, r.zone_id, r.window_start, r.window_end,
    CAST(r.zero_hours AS DOUBLE) AS score,
    json_object('zero_hours', r.zero_hours, 'min_completeness_pct', c.min_completeness,
                'feeder_normal_share', round(n.normal_share, 4)) AS details
FROM runs AS r
JOIN complete AS c USING (meter_id, window_start)
JOIN normal AS n USING (meter_id, window_start)
WHERE c.min_completeness >= {min_completeness_pct}
  AND n.normal_share >= {feeder_normal_share}
  AND (r.window_start AT TIME ZONE '{tz}')::DATE BETWEEN DATE '{scan_start}' AND DATE '{ds}';
"""
