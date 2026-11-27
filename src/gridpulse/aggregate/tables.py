"""Gold table specs shared by aggregate (Parquet), publish (PostgreSQL) and the db/init schema."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldTable:
    name: str
    columns: tuple[str, ...]  # column order in Parquet and PostgreSQL
    order_by: str
    partition: str  # "date" (local_date) or "month"
    zone_partitioned: bool  # adds a zone=Zn/ sub-folder under the date folder


HOURLY = ("kwh", "intervals_present")
GROUP = ("kwh", "meters_reporting", "meters_expected", "intervals_present", "completeness_pct")

TABLES: tuple[GoldTable, ...] = (
    GoldTable(
        "consumption_hourly",
        ("meter_id", "feeder_id", "zone_id", "local_date", "hour_start", *HOURLY, "has_gap"),
        "meter_id, hour_start",
        "date",
        True,
    ),
    GoldTable(
        "consumption_hourly_feeder",
        ("feeder_id", "zone_id", "local_date", "hour_start", *GROUP),
        "feeder_id, hour_start",
        "date",
        True,
    ),
    GoldTable(
        "consumption_hourly_zone",
        ("zone_id", "local_date", "hour_start", *GROUP),
        "zone_id, hour_start",
        "date",
        True,
    ),
    GoldTable(
        "consumption_daily_meter",
        (
            "meter_id",
            "feeder_id",
            "zone_id",
            "local_date",
            "kwh",
            "intervals_present",
            "completeness_pct",
            "quality_flag",
        ),
        "meter_id",
        "date",
        True,
    ),
    GoldTable(
        "consumption_daily_feeder",
        ("feeder_id", "zone_id", "local_date", *GROUP, "quality_flag"),
        "feeder_id",
        "date",
        True,
    ),
    GoldTable(
        "consumption_daily_zone",
        ("zone_id", "local_date", *GROUP, "quality_flag"),
        "zone_id",
        "date",
        True,
    ),
    GoldTable(
        "data_quality_daily",
        ("local_date", "rule", "failures", "sample_meter_ids"),
        "rule",
        "date",
        False,
    ),
    GoldTable(
        "billing_monthly",
        (
            "meter_id",
            "feeder_id",
            "zone_id",
            "month",
            "kwh",
            "sum_of_intervals_kwh",
            "start_reading_source",
            "readings",
            "days_flagged",
            "period_complete",
            "billing_status",
        ),
        "meter_id",
        "month",
        False,
    ),
)
BY_NAME = {t.name: t for t in TABLES}
