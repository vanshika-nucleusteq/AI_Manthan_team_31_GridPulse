"""Spike: hourly kWh z-score >= threshold against the same meter's same IST hour on earlier days."""

from __future__ import annotations

# Input h: meter_id, feeder_id, zone_id, local_date, hour_start, kwh, intervals_present, has_gap.
# Baseline: same meter, same IST hour of day, the previous baseline_days days, gap hours excluded.
SPIKE_SQL = """
CREATE OR REPLACE TEMP TABLE spike_events AS
WITH hod AS (
    SELECT *, hour(hour_start AT TIME ZONE '{tz}') AS hour_of_day, CAST(kwh AS DOUBLE) AS x
    FROM h
), stats AS (
    SELECT
        *,
        avg(x) FILTER (WHERE NOT has_gap) OVER w AS mean,
        stddev_samp(x) FILTER (WHERE NOT has_gap) OVER w AS sd,
        count(x) FILTER (WHERE NOT has_gap) OVER w AS samples
    FROM hod
    WINDOW w AS (
        PARTITION BY meter_id, hour_of_day ORDER BY local_date
        RANGE BETWEEN INTERVAL {baseline_days} DAY PRECEDING AND INTERVAL 1 DAY PRECEDING
    )
)
SELECT
    'spike' AS type, meter_id, feeder_id, zone_id,
    hour_start AS window_start, hour_start + INTERVAL 1 HOUR AS window_end,
    (x - mean) / sd AS score,
    json_object('kwh', x, 'baseline_mean_kwh', round(mean, 6), 'baseline_sd_kwh', round(sd, 6),
                'baseline_samples', samples) AS details
FROM stats
WHERE NOT has_gap
  AND local_date BETWEEN DATE '{scan_start}' AND DATE '{ds}'
  AND samples >= {min_samples}
  AND sd > 0
  AND (x - mean) / sd >= {z_threshold}
  AND x >= {min_ratio_to_mean} * mean;
"""
