"""Hourly kWh per meter, feeder and zone. Hours are IST hours (they start at :30 UTC)."""

from __future__ import annotations

# date_trunc runs on the IST wall-clock time; timezone() turns it back into a UTC instant.
HOURLY_SQL = """
CREATE OR REPLACE TEMP TABLE hourly AS
SELECT
    meter_id, feeder_id, zone_id, local_date,
    timezone('{tz}', date_trunc('hour', interval_start AT TIME ZONE '{tz}')) AS hour_start,
    CAST(coalesce(sum(consumption_kwh), 0) AS DECIMAL(18, 6)) AS kwh,
    count(*) AS intervals_present,
    count(*) < {per_hour} OR bool_or(spans_gap) AS has_gap
FROM r
WHERE local_date BETWEEN DATE '{first}' AND DATE '{ds}'
GROUP BY ALL;

CREATE OR REPLACE TEMP TABLE hourly_feeder AS
SELECT
    h.feeder_id, any_value(h.zone_id) AS zone_id, h.local_date, h.hour_start,
    CAST(sum(h.kwh) AS DECIMAL(18, 6)) AS kwh,
    count(*) AS meters_reporting,
    any_value(e.meters_expected) AS meters_expected,
    CAST(sum(h.intervals_present) AS BIGINT) AS intervals_present,
    CAST(round(sum(h.intervals_present) * 100.0 / (any_value(e.meters_expected) * {per_hour}), 2)
        AS DECIMAL(5, 2)) AS completeness_pct
FROM hourly AS h
JOIN daily_feeder AS e USING (feeder_id, local_date)
GROUP BY h.feeder_id, h.local_date, h.hour_start;

CREATE OR REPLACE TEMP TABLE hourly_zone AS
SELECT
    h.zone_id, h.local_date, h.hour_start,
    CAST(sum(h.kwh) AS DECIMAL(18, 6)) AS kwh,
    count(*) AS meters_reporting,
    any_value(e.meters_expected) AS meters_expected,
    CAST(sum(h.intervals_present) AS BIGINT) AS intervals_present,
    CAST(round(sum(h.intervals_present) * 100.0 / (any_value(e.meters_expected) * {per_hour}), 2)
        AS DECIMAL(5, 2)) AS completeness_pct
FROM hourly AS h
JOIN daily_zone AS e USING (zone_id, local_date)
GROUP BY h.zone_id, h.local_date, h.hour_start;
"""
