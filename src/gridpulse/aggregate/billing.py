"""Monthly billing per meter: register difference (rollover-adjusted), reconciled to intervals."""

from __future__ import annotations

# Billed kWh = last register in the IST month - last register before the month, plus one
# register_max per wrap. With no earlier reading in silver, the first register in the month is
# the start and its own consumption is left out of the interval sum, so both sides cover the
# same span. A mismatch above tolerance or any flagged day sets REVIEW.
BILLING_SQL = """
CREATE OR REPLACE TEMP TABLE billing AS
WITH in_month AS (
    SELECT r.*, b.month
    FROM r JOIN month_bounds AS b ON r.local_date BETWEEN b.month AND b.month_end
), before_month AS (
    SELECT r.meter_id, b.month, arg_max(r.register_kwh, r.interval_start) AS start_reg
    FROM r JOIN month_bounds AS b
        ON r.local_date < b.month AND r.local_date >= b.month - INTERVAL {lookup_days} DAY
    GROUP BY r.meter_id, b.month
), per_meter AS (
    SELECT
        meter_id, month,
        any_value(feeder_id) AS feeder_id, any_value(zone_id) AS zone_id,
        count(*) AS readings,
        arg_max(register_kwh, interval_start) AS last_reg,
        arg_min(register_kwh, interval_start) AS first_reg,
        arg_min(coalesce(consumption_kwh, 0), interval_start) AS first_consumption,
        arg_min(CAST(is_rollover AS INTEGER), interval_start) AS first_is_rollover,
        count(*) FILTER (WHERE is_rollover) AS wraps,
        coalesce(sum(consumption_kwh), 0) AS sum_all
    FROM in_month
    GROUP BY meter_id, month
), flagged AS (
    SELECT d.meter_id, b.month, count(*) FILTER (WHERE d.quality_flag) AS days_flagged
    FROM daily_meter AS d JOIN month_bounds AS b ON d.local_date BETWEEN b.month AND b.month_end
    GROUP BY d.meter_id, b.month
), billed AS (
    SELECT
        p.*, m.register_max_kwh, s.start_reg, coalesce(f.days_flagged, 0) AS days_flagged,
        CASE
            WHEN s.start_reg IS NOT NULL
                THEN p.last_reg - s.start_reg + p.wraps * m.register_max_kwh
            ELSE p.last_reg - p.first_reg + (p.wraps - p.first_is_rollover) * m.register_max_kwh
        END AS kwh,
        CASE
            WHEN s.start_reg IS NOT NULL THEN p.sum_all
            ELSE p.sum_all - p.first_consumption
        END AS sum_of_intervals_kwh
    FROM per_meter AS p
    JOIN master_full AS m USING (meter_id)
    LEFT JOIN before_month AS s USING (meter_id, month)
    LEFT JOIN flagged AS f USING (meter_id, month)
)
SELECT
    b.meter_id, b.feeder_id, b.zone_id, b.month,
    CAST(b.kwh AS DECIMAL(18, 6)) AS kwh,
    CAST(b.sum_of_intervals_kwh AS DECIMAL(18, 6)) AS sum_of_intervals_kwh,
    CASE WHEN b.start_reg IS NOT NULL THEN 'previous_month' ELSE 'first_in_month' END
        AS start_reading_source,
    b.readings, b.days_flagged, mb.period_complete,
    CASE
        WHEN abs(b.kwh - b.sum_of_intervals_kwh) > {tolerance} OR b.days_flagged > 0 THEN 'REVIEW'
        ELSE 'READY'
    END AS billing_status
FROM billed AS b
JOIN month_bounds AS mb USING (month);
"""
