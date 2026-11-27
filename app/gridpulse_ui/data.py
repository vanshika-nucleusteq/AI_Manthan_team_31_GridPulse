"""Dashboard data from the GridPulse backend: PostgreSQL gold tables and pipeline_runs, plus
read-only lake reads (bronze) for schema mix, ingest lag and storage sizes. Cached for 60 s."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from gridpulse.common.config import load_yaml
from gridpulse.common.db import sqlalchemy_url
from gridpulse.common.lake import go_live, lake_from_config

TZ = "Asia/Kolkata"


@st.cache_resource
def engine() -> Engine:
    return create_engine(sqlalchemy_url(), pool_pre_ping=True)


@st.cache_data(ttl=60, show_spinner=False)
def query(sql: str, **params: Any) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def database_error() -> str | None:
    try:
        query("SELECT 1 AS ok")
        return None
    except Exception as exc:  # shown as an error panel instead of a stack trace
        return str(exc).splitlines()[0]


# ---------- calendar ----------
def days() -> list[date]:
    df = query(
        "SELECT local_date FROM consumption_daily_zone GROUP BY local_date "
        "HAVING sum(intervals_present) > 0 ORDER BY local_date DESC"
    )
    return [d for d in pd.to_datetime(df["local_date"]).dt.date]


def network() -> dict[str, int]:
    row = query(
        "SELECT count(*) AS meters, count(DISTINCT feeder_id) AS feeders, "
        "count(DISTINCT zone_id) AS zones FROM meter_master"
    ).iloc[0]
    return {k: int(row[k]) for k in ("meters", "feeders", "zones")}


def zones() -> list[str]:
    return list(query("SELECT DISTINCT zone_id FROM meter_master ORDER BY zone_id")["zone_id"])


# ---------- consumption ----------
def daily_totals(day: date, n: int = 30) -> pd.DataFrame:
    return query(
        "SELECT local_date, sum(kwh) AS kwh, sum(intervals_present) AS present, "
        "sum(meters_expected) * 96 AS expected, bool_or(quality_flag) AS flagged "
        "FROM consumption_daily_zone WHERE local_date BETWEEN :start AND :day "
        "GROUP BY local_date ORDER BY local_date",
        start=day - timedelta(days=n - 1),
        day=day,
    )


def hourly(zone: str | None, day: date) -> pd.DataFrame:
    where = "AND zone_id = :zone" if zone else ""
    df = query(
        "SELECT local_date, extract(hour FROM hour_start AT TIME ZONE 'Asia/Kolkata')::int AS hour, "
        f"sum(kwh) AS kwh FROM consumption_hourly_zone WHERE local_date IN (:day, :prev) {where} "
        "GROUP BY 1, 2 ORDER BY 2",
        day=day,
        prev=day - timedelta(days=1),
        zone=zone,
    )
    df["local_date"] = pd.to_datetime(df["local_date"]).dt.date
    out = pd.DataFrame({"hour": range(24)})
    for name, d in (("today", day), ("yesterday", day - timedelta(days=1))):
        part = df[df["local_date"] == d][["hour", "kwh"]].rename(columns={"kwh": name})
        out = out.merge(part, on="hour", how="left")
    return out


def zone_completeness(day: date) -> pd.DataFrame:
    return query(
        "SELECT zone_id, completeness_pct, meters_expected, quality_flag, "
        "meters_expected * 96 - intervals_present AS gap_intervals "
        "FROM consumption_daily_zone WHERE local_date = :day ORDER BY zone_id",
        day=day,
    )


def heatmap(day: date) -> pd.DataFrame:
    df = query(
        "SELECT feeder_id, extract(hour FROM hour_start AT TIME ZONE 'Asia/Kolkata')::int AS hour, "
        "kwh, completeness_pct FROM consumption_hourly_feeder WHERE local_date = :day",
        day=day,
    )
    return df


def billing(day: date) -> tuple[pd.DataFrame, dict[str, int]]:
    month = day.replace(day=1)
    summary = query(
        "SELECT billing_status, count(*) AS n FROM billing_monthly WHERE month = :m GROUP BY 1",
        m=month,
    )
    rows = query(
        "(SELECT * FROM billing_monthly WHERE month = :m AND billing_status = 'REVIEW' "
        " ORDER BY days_flagged DESC, kwh DESC LIMIT 4) UNION ALL "
        "(SELECT * FROM billing_monthly WHERE month = :m AND billing_status = 'READY' "
        " ORDER BY kwh DESC LIMIT 4)",
        m=month,
    )
    return rows, dict(zip(summary["billing_status"], summary["n"].astype(int), strict=True))


# ---------- anomalies ----------
def anomalies(day: date, since: date) -> pd.DataFrame:
    df = query(
        "SELECT a.*, m.zone_id AS mzone FROM anomalies a LEFT JOIN meter_master m USING (meter_id) "
        "WHERE local_date BETWEEN :since AND :day ORDER BY window_start DESC, score DESC",
        since=since,
        day=day,
    )
    if df.empty:
        return df
    df["details"] = df["details"].apply(lambda d: d if isinstance(d, dict) else json.loads(d))
    return df


def rules() -> dict[str, Any]:
    return load_yaml("anomalies")


# ---------- data quality ----------
def quality_counts(day: date) -> dict[str, Any]:
    failures = query(
        "SELECT rule, failures FROM data_quality_daily WHERE local_date = :day", day=day
    )
    kept = query(
        "SELECT sum(intervals_present) AS kept FROM consumption_daily_zone WHERE local_date = :day",
        day=day,
    ).iloc[0]["kept"]
    meter_days = query(
        "SELECT count(*) AS n, count(*) FILTER (WHERE quality_flag) AS flagged "
        "FROM consumption_daily_meter WHERE local_date = :day",
        day=day,
    ).iloc[0]
    return {
        "failures": dict(zip(failures["rule"], failures["failures"].astype(int), strict=True)),
        "kept": int(kept or 0),
        "meter_days": int(meter_days["n"]),
        "meter_days_flagged": int(meter_days["flagged"]),
    }


def quarantine_rules(day: date) -> pd.DataFrame:
    return query(
        "SELECT rule, failures FROM data_quality_daily WHERE local_date = :day ORDER BY failures DESC",
        day=day,
    )


def quarantined_by_day(day: date, n: int = 12) -> pd.DataFrame:
    return query(
        "SELECT local_date, sum(failures) AS failures FROM data_quality_daily "
        "WHERE local_date BETWEEN :start AND :day GROUP BY 1 ORDER BY 1",
        start=day - timedelta(days=n - 1),
        day=day,
    )


# ---------- pipeline ----------
def runs(n: int, day: date) -> pd.DataFrame:
    """Latest run per ds up to day (runs for other dates, e.g. tests of the wall clock, excluded)."""
    return query(
        "SELECT DISTINCT ON (ds) run_id, ds, started, finished, failed FROM ("
        " SELECT run_id, min(ds) AS ds, min(started_at) AS started, max(finished_at) AS finished, "
        " bool_or(status = 'failed') AS failed FROM pipeline_runs GROUP BY run_id) r "
        "WHERE ds BETWEEN :first AND :day ORDER BY ds DESC, finished DESC LIMIT :n",
        n=n,
        day=day,
        first=go_live(),
    )


def duplicates_by_day(day: date, n: int = 12) -> pd.DataFrame:
    return query(
        "SELECT n.ds, n.duplicates, n.rows_out AS kept FROM pipeline_runs n "
        "WHERE n.task = 'normalise' AND n.ds BETWEEN :start AND :day "
        "AND n.finished_at = (SELECT max(finished_at) FROM pipeline_runs x "
        "WHERE x.task = 'normalise' AND x.ds = n.ds) ORDER BY n.ds",
        start=day - timedelta(days=n - 1),
        day=day,
    )


# ---------- lake (read-only) ----------
def _bronze(day: date) -> str | None:
    path = lake_from_config().bronze(day) / "part-0.parquet"
    return path.as_posix() if path.exists() else None


@st.cache_data(ttl=300, show_spinner=False)
def schema_mix(day: date) -> pd.DataFrame | None:
    path = _bronze(day)
    if not path:
        return None
    import duckdb

    return duckdb.sql(
        "SELECT schema_version, coalesce(energy_unit, 'missing') AS unit, count(*) AS n "
        f"FROM read_parquet('{path}') WHERE schema_version IS NOT NULL GROUP BY 1, 2"
    ).df()


@st.cache_data(ttl=300, show_spinner=False)
def ingest_lag(day: date) -> pd.DataFrame | None:
    """Gateway to raw landing: file arrival (ingested_at) minus reading time, by IST hour."""
    path = _bronze(day)
    if not path:
        return None
    import duckdb

    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    return con.sql(
        "SELECT hour(ts AT TIME ZONE 'Asia/Kolkata') AS hour, "
        "quantile_cont(epoch(ingested_at) - epoch(ts), 0.5) / 60 AS p50, "
        "quantile_cont(epoch(ingested_at) - epoch(ts), 0.95) / 60 AS p95 "
        f"FROM read_parquet('{path}') WHERE ts IS NOT NULL "
        f"AND (ts AT TIME ZONE 'Asia/Kolkata')::DATE = DATE '{day}' GROUP BY 1 ORDER BY 1"
    ).df()
