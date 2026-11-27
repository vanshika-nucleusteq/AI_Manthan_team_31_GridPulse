"""Daily kWh and completeness per meter, feeder and zone (IST days), silent meters included."""

from __future__ import annotations

# completeness_pct is rounded for display; quality_flag uses the exact ratio:
# flagged unless intervals_present * 100 > flag_pct * expected (card: above 90%, else a flag).
DAILY_SQL = """
CREATE OR REPLACE TEMP TABLE daily_meter AS
SELECT
    m.meter_id, m.feeder_id, m.zone_id, d.local_date,
    CAST(coalesce(sum(r.consumption_kwh), 0) AS DECIMAL(18, 6)) AS kwh,
    count(r.meter_id) AS intervals_present,
    CAST(round(count(r.meter_id) * 100.0 / {per_day}, 2) AS DECIMAL(5, 2)) AS completeness_pct,
    NOT (count(r.meter_id) * 100 > {flag_pct} * {per_day}) AS quality_flag
FROM master_full AS m
CROSS JOIN days AS d
LEFT JOIN r ON r.meter_id = m.meter_id AND r.local_date = d.local_date
WHERE m.install_date <= d.local_date
GROUP BY m.meter_id, m.feeder_id, m.zone_id, d.local_date;

CREATE OR REPLACE TEMP TABLE daily_feeder AS
SELECT
    feeder_id, any_value(zone_id) AS zone_id, local_date,
    CAST(sum(kwh) AS DECIMAL(18, 6)) AS kwh,
    count(*) FILTER (WHERE intervals_present > 0) AS meters_reporting,
    count(*) AS meters_expected,
    CAST(sum(intervals_present) AS BIGINT) AS intervals_present,
    CAST(round(sum(intervals_present) * 100.0 / (count(*) * {per_day}), 2) AS DECIMAL(5, 2))
        AS completeness_pct,
    NOT (sum(intervals_present) * 100 > {flag_pct} * count(*) * {per_day}) AS quality_flag
FROM daily_meter
GROUP BY feeder_id, local_date;

CREATE OR REPLACE TEMP TABLE daily_zone AS
SELECT
    zone_id, local_date,
    CAST(sum(kwh) AS DECIMAL(18, 6)) AS kwh,
    count(*) FILTER (WHERE intervals_present > 0) AS meters_reporting,
    count(*) AS meters_expected,
    CAST(sum(intervals_present) AS BIGINT) AS intervals_present,
    CAST(round(sum(intervals_present) * 100.0 / (count(*) * {per_day}), 2) AS DECIMAL(5, 2))
        AS completeness_pct,
    NOT (sum(intervals_present) * 100 > {flag_pct} * count(*) * {per_day}) AS quality_flag
FROM daily_meter
GROUP BY zone_id, local_date;
"""
