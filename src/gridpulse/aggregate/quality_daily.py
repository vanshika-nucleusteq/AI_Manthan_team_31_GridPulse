"""Quarantine failures per IST day and rule, with up to five sample meter IDs."""

from __future__ import annotations

QUALITY_DAILY_SQL = """
CREATE OR REPLACE TEMP TABLE quality_daily AS
SELECT
    quarantine_date AS local_date,
    rule,
    count(*) AS failures,
    list_slice(list_sort(list_distinct(list(meter_id) FILTER (WHERE meter_id IS NOT NULL))), 1, 5)
        AS sample_meter_ids
FROM quarantine
GROUP BY quarantine_date, rule;
"""
