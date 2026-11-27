"""One function per view; every panel reads the GridPulse backend (gold tables, pipeline_runs, lake)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gridpulse.common.config import load_yaml
from gridpulse.common.lake import go_live
from gridpulse_ui import components as c
from gridpulse_ui import data
from gridpulse_ui.theme import PLOTLY_CONFIG, THEMES, plotly_layout


def fmt_day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def short_day(d: date) -> str:
    return f"{d:%b} {d.day}"


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def human_bytes(n: int | None) -> str:
    if n is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return "—"


def duration(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return "—"
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def compact(n: Any) -> str:
    if n is None or pd.isna(n):
        return "—"
    n = float(n)
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.1f}k" if n >= 1e3 else f"{n:,.0f}"


def chart(fig: go.Figure, theme: str, height: int, **layout: Any) -> None:
    base = plotly_layout(theme, height)
    for axis in ("xaxis", "yaxis"):
        base[axis] = {**base[axis], **layout.pop(axis, {})}
    fig.update_layout(**base, **layout)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


# ---------- panels ----------
def hero(ctx: dict[str, Any]) -> None:
    day, totals, net = ctx["day"], ctx["totals"], data.network()
    today = totals[totals["local_date"] == day]
    prev = totals[totals["local_date"] == day - timedelta(days=1)]
    kwh = float(today["kwh"].iloc[0]) if not today.empty else 0.0
    delta = (
        (kwh / float(prev["kwh"].iloc[0]) - 1) * 100
        if not prev.empty and prev["kwh"].iloc[0]
        else None
    )
    tiles = [
        (f'{net["meters"]:,}', "Smart meters"),
        (str(net["feeders"]), "Feeders"),
        (str(net["zones"]), "Zones"),
        ("15 min", "Read interval"),
    ]
    c.render(c.hero(kwh / 1000, delta, f"Energy delivered · {fmt_day(day)} · IST day", tiles))


def kpi_strip(ctx: dict[str, Any]) -> None:
    day, totals = ctx["day"], ctx["totals"].tail(12)
    kpis: list[dict[str, Any]] = []
    present = totals["present"].astype(float).tolist()
    expected = totals["expected"].astype(float).tolist()
    if present:
        d_pct = (present[-1] / present[-2] - 1) * 100 if len(present) > 1 and present[-2] else 0
        kpis.append(
            {
                "label": "Readings received",
                "value": f"{present[-1]:,.0f}",
                "sub": f"of {expected[-1]:,.0f} expected · {fmt_day(day)}",
                "delta": f"{d_pct:+.1f}%",
                "up": d_pct >= 0,
                "good": d_pct >= 0,
                "spark": present,
            }
        )
        comp = [p / x * 100 if x else 0 for p, x in zip(present, expected, strict=True)]
        d_pts = comp[-1] - comp[-2] if len(comp) > 1 else 0
        kpis.append(
            {
                "label": "Network completeness",
                "value": f"{comp[-1]:.1f}%",
                "sub": "flag unless > 90% per meter-day",
                "delta": f"{d_pts:+.1f} pts",
                "up": d_pts >= 0,
                "good": d_pts >= 0,
                "spark": comp,
            }
        )
    dups = data.duplicates_by_day(day)
    if not dups.empty:
        rate = (dups["duplicates"] / (dups["kept"] + dups["duplicates"]) * 100).fillna(0).tolist()
        d_rate = rate[-1] - rate[-2] if len(rate) > 1 else 0
        last = dups.iloc[-1]
        kpis.append(
            {
                "label": "Duplicate rate",
                "value": f"{rate[-1]:.2f}%",
                "sub": f"{int(last['duplicates']):,} duplicates dropped · 3-day window",
                "delta": f"{d_rate:+.2f} pts",
                "up": d_rate >= 0,
                "good": d_rate <= 0,
                "spark": rate,
            }
        )
    q = data.quarantined_by_day(day)
    if not q.empty:
        vals = q["failures"].astype(float).tolist()
        d_q = vals[-1] - vals[-2] if len(vals) > 1 else 0
        kpis.append(
            {
                "label": "Quarantined rows",
                "value": f"{vals[-1]:,.0f}",
                "sub": "dead-letter with rule and reason",
                "delta": f"{d_q:+,.0f}",
                "up": d_q >= 0,
                "good": d_q <= 0,
                "spark": vals,
            }
        )
    c.render(c.kpi_strip(kpis))


def feeder_consumption(ctx: dict[str, Any]) -> None:
    day, theme = ctx["day"], ctx["theme"]
    t = THEMES[theme]
    with st.container(key="panel_feeder"):
        left, right = st.columns([1, 1.3])
        with left:
            c.render(c.panel_head("Hourly kWh · day vs previous day", "Feeder consumption"))
        with right:
            options = ["All", *data.zones()]
            st.pills("Zone", options, key="zone_filter", label_visibility="collapsed")
        zone = st.session_state.get("zone_filter") or "All"
        df = data.hourly(None if zone == "All" else zone, day)
        total = df["today"].fillna(0).sum()
        c.render(
            f'<div style="display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 24px">'
            f'<p class="mono" style="margin:0;font-size:24px;font-weight:600">{total:,.0f} '
            f'<span class="muted" style="font-size:14px">kWh on {fmt_day(day)}</span></p>'
            '<div class="legend"><span><span style="height:2px;width:16px;background:var(--primary)"></span>'
            f'{short_day(day)}</span><span><span style="width:16px;border-top:2px dashed var(--muted-foreground)">'
            f"</span>{short_day(day - timedelta(days=1))}</span></div></div>"
        )
        labels = [f"{h:02d}:00" for h in df["hour"]]
        fig = go.Figure()
        fig.add_scatter(
            x=labels,
            y=df["yesterday"],
            name="previous day",
            mode="lines",
            line={"color": t["muted-foreground"], "width": 1.5, "dash": "dash", "shape": "spline"},
            hovertemplate="%{y:,.0f} kWh",
        )
        fig.add_scatter(
            x=labels,
            y=df["today"],
            name=short_day(day),
            mode="lines",
            fill="tozeroy",
            line={"color": t["primary"], "width": 2.5, "shape": "spline"},
            connectgaps=False,
            fillgradient={
                "type": "vertical",
                "colorscale": [[0, rgba(t["primary"], 0)], [1, rgba(t["primary"], 0.45)]],
            },
            hovertemplate="%{y:,.0f} kWh",
        )
        chart(
            fig,
            theme,
            288,
            xaxis={"tickmode": "array", "tickvals": labels[::3]},
            yaxis={"tickformat": "~s"},
        )


def daily_consumption(ctx: dict[str, Any]) -> None:
    day, theme, totals = ctx["day"], ctx["theme"], ctx["totals"]
    t = THEMES[theme]
    legend = (
        '<span class="legend"><span><span style="width:8px;height:8px;border-radius:2px;'
        'background:var(--warning)"></span>Day with quality flag</span></span>'
    )
    with st.container(key="panel_daily"):
        first = totals["local_date"].min() if not totals.empty else day
        c.render(
            c.panel_head(
                f"Daily kWh · {short_day(first)} – {short_day(day)}",
                "Network daily consumption",
                legend,
            )
        )
        colors = [t["warning"] if f else t["chart-2"] for f in totals["flagged"]]
        fig = go.Figure(
            go.Bar(
                x=[short_day(d) for d in totals["local_date"]],
                y=totals["kwh"],
                marker={"color": colors},
                hovertemplate="%{y:,.0f} kWh<extra></extra>",
            )
        )
        chart(fig, theme, 256, barcornerradius=6, yaxis={"tickformat": "~s"})


def zone_completeness(ctx: dict[str, Any]) -> None:
    df = data.zone_completeness(ctx["day"])
    threshold = float(load_yaml("quality")["completeness_flag_pct"])
    rows = [
        {
            "zone": r.zone_id,
            "pct": float(r.completeness_pct),
            "meters": int(r.meters_expected),
            "gaps": int(r.gap_intervals),
        }
        for r in df.itertuples()
    ]
    with st.container(key="panel_zones"):
        c.render(
            c.panel_head(
                "Readings received / expected", f"Completeness by zone · {short_day(ctx['day'])}"
            )
        )
        c.render(c.zone_bars(rows, threshold) if rows else c.empty("No data for this day."))


def anomaly_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for a in df.itertuples():
        d = a.details
        if a.type == "spike":
            detail = (
                f"Hourly {d['kwh']:.2f} kWh vs own baseline {d['baseline_mean_kwh']:.2f} kWh "
                f"({d['baseline_samples']} days at this hour)"
            )
            metric, sev = f"z = {float(a.score):.1f}", "high" if float(a.score) >= 10 else "medium"
        elif a.type == "tamper":
            detail = (
                f"0 kWh for {d['zero_hours']}h while {float(d['feeder_normal_share']):.0%} of "
                f"feeder {a.feeder_id} reports normally"
            )
            metric, sev = f"{d['zero_hours']}h zero", "high"
        else:
            detail = (
                f"{d['max_meters_missing']} of {d['meters_on_feeder']} meters silent for "
                f"{int(d['intervals']) * 15} min together"
            )
            metric, sev = f"{float(a.score):.0%} silent", "critical"
        start = pd.Timestamp(a.window_start).tz_convert(data.TZ)
        rows.append(
            {
                "type": a.type,
                "severity": sev,
                "detail": detail,
                "metric": metric,
                "target": a.meter_id if isinstance(a.meter_id, str) else f"Feeder {a.feeder_id}",
                "where": f"{a.feeder_id} · {a.zone_id}",
                "when": f"{start:%d %b %H:%M} IST · open",
            }
        )
    return rows


def anomaly_list(ctx: dict[str, Any], limit: int | None, key: str) -> None:
    day = ctx["day"]
    since = day - timedelta(days=6) if limit else go_live()
    df = data.anomalies(day, since)
    with st.container(key=f"panel_{key}"):
        left, right = st.columns([1, 1])
        with left:
            eyebrow = f"Detected {short_day(since)} – {short_day(day)}"
            c.render(c.panel_head(eyebrow, "Anomaly feed"))
        with right:
            st.pills(
                "Type",
                ["all", "spike", "tamper", "outage"],
                key=f"anomaly_filter_{key}",
                default="all",
                label_visibility="collapsed",
            )
        choice = st.session_state.get(f"anomaly_filter_{key}") or "all"
        if choice != "all" and not df.empty:
            df = df[df["type"] == choice]
        rows = anomaly_rows(df)
        c.render(c.anomaly_feed(rows[:limit] if limit else rows))


def anomaly_summary(ctx: dict[str, Any]) -> None:
    df = data.anomalies(ctx["day"], go_live())
    counts = df["type"].value_counts().to_dict() if not df.empty else {}
    cfg = data.rules()
    s, t, o = cfg["spike"], cfg["tamper"], cfg["outage"]
    rules = {
        "spike": f"z ≥ {s['z_threshold']:g} and ≥ {s['min_ratio_to_mean']:g}× own baseline",
        "tamper": f"0 kWh ≥ {t['zero_hours']}h, ≥ {t['feeder_normal_share']:.0%} of feeder normal",
        "outage": f"≥ {o['feeder_missing_share']:.0%} of a feeder silent ≥ {o['min_consecutive_intervals']} intervals",
    }
    c.render(c.anomaly_summary(counts, rules))


def feeder_heatmap(ctx: dict[str, Any]) -> None:
    day = ctx["day"]
    df = data.heatmap(day)
    with st.container(key="panel_heatmap"):
        c.render(
            c.panel_head(
                f"Feeder × hour · kWh intensity · {short_day(day)}",
                "Load heatmap with interval gaps",
                c.heatmap_legend(),
            )
        )
        if df.empty:
            c.render(c.empty("No hourly feeder data for this day."))
            return
        cells = {
            (r.feeder_id, int(r.hour)): (float(r.kwh), float(r.completeness_pct) < 50)
            for r in df.itertuples()
        }
        feeders = sorted(df["feeder_id"].unique())
        c.render(c.heatmap(feeders, cells, float(df["kwh"].max())))
        c.render(
            '<p class="muted" style="margin:0;font-size:12px">A cell is a gap when fewer than half '
            "of the feeder's expected readings arrived in that hour.</p>"
        )


def schema_mix(ctx: dict[str, Any]) -> None:
    df = data.schema_mix(ctx["day"])
    with st.container(key="panel_schema"):
        c.render(
            c.panel_head("Schema evolution", f"Event versions · {short_day(ctx['day'])} arrivals")
        )
        if df is None or df.empty:
            c.render(c.empty("Bronze for this day is not available to the dashboard."))
            return
        total = df["n"].sum()
        groups = [
            ("Schema v1", "meter_id · ts · energy_wh · status", (df["schema_version"] == 1)),
            (
                "Schema v2 (Wh)",
                "+ voltage · firmware_version",
                (df["schema_version"] == 2) & (df["unit"] == "Wh"),
            ),
            (
                "Schema v2 (kWh)",
                "kWh as sent · Wh ÷ 1000 everywhere else",
                (df["schema_version"] == 2) & (df["unit"] == "kWh"),
            ),
            (
                "Schema v2 (no unit)",
                "unit taken from meter_master",
                (df["schema_version"] == 2) & (df["unit"] == "missing"),
            ),
        ]
        parts = [
            {"name": n, "note": note, "pct": df[mask]["n"].sum() / total * 100}
            for n, note, mask in groups
            if df[mask]["n"].sum()
        ]
        c.render(c.schema_mix(parts))


def quality_rules(ctx: dict[str, Any]) -> None:
    q = data.quality_counts(ctx["day"])
    f, kept = q["failures"], q["kept"]

    def status(failed: int, total: int) -> str:
        return "pass" if failed == 0 else "warn" if failed / max(total, 1) < 0.005 else "fail"

    parsed = f.get("MALFORMED_RECORD", 0) + f.get("BAD_TIMESTAMP", 0) + f.get("CORRUPT_FILE", 0)
    rows = [
        {
            "rule": "Meter ID exists in meter master",
            "passed": kept,
            "failed": f.get("UNKNOWN_METER", 0),
        },
        {
            "rule": "Energy reading is non-negative",
            "passed": kept,
            "failed": f.get("NEGATIVE_READING", 0),
        },
        {
            "rule": "Cumulative register never decreases",
            "passed": kept,
            "failed": f.get("REGISTER_DECREASED", 0),
            "note": "ROLLOVER status allowed",
        },
        {"rule": "Record parses with a valid timestamp", "passed": kept, "failed": parsed},
        {
            "rule": "Completeness per meter-day > 90%",
            "passed": q["meter_days"] - q["meter_days_flagged"],
            "failed": q["meter_days_flagged"],
            "note": f"{q['meter_days_flagged']:,} meter-days flagged",
        },
    ]
    for r in rows:
        r["status"] = status(r["failed"], r["passed"] + r["failed"])
    if q["meter_days_flagged"]:
        rows[-1]["status"] = "fail"
    with st.container(key="panel_rules"):
        c.render(
            c.panel_head("Validated on every run", f"Data quality rules · {short_day(ctx['day'])}")
        )
        c.render(c.quality_rules(rows))


def billing_table(ctx: dict[str, Any]) -> None:
    day = ctx["day"]
    rows, summary = data.billing(day)
    action = (
        f'<span class="mono muted" style="font-size:12px">{summary.get("READY", 0):,} ready · '
        f'{summary.get("REVIEW", 0):,} review</span>'
    )
    with st.container(key="panel_billing"):
        c.render(
            c.panel_head(
                f"billing_month = {day:%Y-%m}", "Billing-ready consumption per meter", action
            )
        )
        if rows.empty:
            c.render(c.empty("No bills for this month yet."))
            return
        body = []
        for r in rows.itertuples():
            flagged = (
                f'<span style="color:var(--warning)">{r.days_flagged}</span>'
                if r.days_flagged
                else "0"
            )
            body.append(
                [
                    f'<span class="mono" style="font-weight:600">{c.e(r.meter_id)}</span>',
                    f'<span class="muted">{c.e(r.feeder_id)} · {c.e(r.zone_id)}</span>',
                    f'<span class="mono">{float(r.kwh):,.1f}</span>',
                    f'<span class="mono">{round(int(r.readings) / 96)}/{day.day}</span>',
                    f'<span class="mono">{flagged}</span>',
                    c.status_pill(r.billing_status.lower()),
                ]
            )
        c.render(
            c.table(
                [
                    ("Meter", False),
                    ("Feeder / zone", False),
                    ("kWh", True),
                    ("Days", True),
                    ("Flagged", True),
                    ("Status", True),
                ],
                body,
            )
        )
        c.render(
            '<p class="muted" style="margin:0;font-size:12px">kWh = register difference '
            "(rollover-adjusted), reconciled to the sum of intervals; any flagged day sets REVIEW.</p>"
        )


TASK_DESC = {
    "ingest": "Landing → bronze, schema v1/v2",
    "quality": "8 rules → quarantine",
    "normalise": "kWh · dedup · order · gaps",
    "aggregate": "Hourly · daily · billing",
    "anomalies": "Spike · tamper · outage",
    "publish": "Gold → PostgreSQL",
    "compact": "One file per partition",
    "retention": "Raw 30 d · hourly 13 mo",
    "metrics": "SRE metrics and alert (P10)",
}


def pipeline_flow(ctx: dict[str, Any]) -> None:
    day = ctx["day"]
    run_id = data.run_for(day)
    with st.container(key="panel_pipeline"):
        if run_id is None:
            c.render(c.panel_head("dag: gridpulse_daily", "Orchestrated daily run"))
            c.render(
                c.empty(
                    f"No Airflow run recorded for {fmt_day(day)}. "
                    f"Run: make.ps1 run-day {day.isoformat()}"
                )
            )
            return
        tasks = data.run_tasks(run_id)
        started = pd.Timestamp(tasks["started_at"].min()).tz_convert(data.TZ)
        elapsed = pd.Timestamp(tasks["finished_at"].max()) - pd.Timestamp(tasks["started_at"].min())
        action = (
            f'<span class="mono muted" style="font-size:12px">started {started:%d %b %H:%M} IST · '
            f"elapsed {duration(elapsed.total_seconds())}</span>"
        )
        c.render(
            c.panel_head(
                f"dag: gridpulse_daily · run {day.isoformat()}", "Orchestrated daily run", action
            )
        )
        by_task = {r.task: r for r in tasks.itertuples()}
        steps = []
        for name in data.DAG_TASKS:
            r = by_task.get(name)
            if r is None:
                steps.append(
                    {
                        "name": name,
                        "desc": TASK_DESC[name],
                        "status": "queued",
                        "duration": "—",
                        "records": "not built" if name == "metrics" else "—",
                    }
                )
                continue
            steps.append(
                {
                    "name": name,
                    "desc": TASK_DESC[name],
                    "status": "success" if r.status == "success" else "failed",
                    "duration": duration(float(r.duration_s)),
                    "records": compact(r.rows_out),
                }
            )
        c.render(c.stepper(steps))


def run_history(ctx: dict[str, Any]) -> None:
    theme, t = ctx["theme"], THEMES[ctx["theme"]]
    runs = data.runs(14, ctx["day"]).sort_values("ds")
    with st.container(key="panel_runs"):
        c.render(c.panel_head("Run duration · minutes", f"Last {len(runs)} daily runs"))
        if runs.empty:
            c.render(c.empty("No runs recorded in pipeline_runs yet."))
            return
        minutes = (
            pd.to_datetime(runs["finished"]) - pd.to_datetime(runs["started"])
        ).dt.total_seconds() / 60
        colors = [t["destructive"] if f else t["primary"] for f in runs["failed"]]
        fig = go.Figure(
            go.Bar(
                x=[short_day(pd.Timestamp(d).date()) for d in runs["ds"]],
                y=minutes.round(1),
                marker={"color": colors},
                hovertemplate="%{y:.1f} min<extra></extra>",
            )
        )
        chart(fig, theme, 224, barcornerradius=6)
        failed = int(runs["failed"].sum())
        orch = load_yaml("pipeline")["orchestration"]
        note = (
            f"{failed} run(s) had a failed task."
            if failed
            else f"All {len(runs)} runs succeeded · retries {orch['retries']} × {orch['retry_delay_minutes']} min."
        )
        c.render(f'<p class="muted" style="margin:0;font-size:12px">{note}</p>')


def ingest_lag(ctx: dict[str, Any]) -> None:
    theme, t = ctx["theme"], THEMES[ctx["theme"]]
    df = data.ingest_lag(ctx["day"])
    action = (
        '<span class="delta tone-warning" style="padding:4px 10px">'
        "hourly files · late arrivals lift p95</span>"
    )
    with st.container(key="panel_lag"):
        c.render(c.panel_head("Reading time → raw landing · minutes", "Ingest lag", action))
        if df is None or df.empty:
            c.render(c.empty("Bronze for this day is not available to the dashboard."))
            return
        labels = [f"{int(h):02d}:00" for h in df["hour"]]
        fig = go.Figure()
        fig.add_scatter(
            x=labels,
            y=df["p95"].round(1),
            name="p95",
            mode="lines",
            line={"color": t["chart-3"], "width": 2.5, "shape": "spline"},
            hovertemplate="%{y:,.0f} min",
        )
        fig.add_scatter(
            x=labels,
            y=df["p50"].round(1),
            name="p50",
            mode="lines",
            line={"color": t["chart-2"], "width": 2, "shape": "spline"},
            hovertemplate="%{y:,.0f} min",
        )
        chart(fig, theme, 224, xaxis={"tickmode": "array", "tickvals": labels[::4]})


def backfill(ctx: dict[str, Any]) -> None:
    day = ctx["day"]
    orch = load_yaml("pipeline")["orchestration"]
    with st.container(key="panel_backfill"):
        c.render(c.panel_head("Re-run for a date range", "Backfill"))
        a, b = st.columns(2)
        start = a.date_input(
            "From",
            value=day - timedelta(days=2),
            key="backfill_from",
            min_value=go_live(),
            max_value=day,
        )
        end = b.date_input("To", value=day, key="backfill_to", min_value=go_live(), max_value=day)
        if st.button("↺  Queue backfill", key="queue_backfill"):
            if start > end:
                st.session_state["backfill_msg"] = "From must be on or before To."
            else:
                st.session_state["backfill_msg"] = (
                    f"Run on the driver laptop: make.ps1 backfill {start} {end} · "
                    "idempotent overwrite of date partitions"
                )
        msg = st.session_state.get("backfill_msg") or (
            f"Retries: {orch['retries']} · {orch['retry_delay_minutes']} min apart · "
            f"max {orch['max_active_runs']} active run"
        )
        c.render(
            f'<p class="mono muted" style="margin:0;font-size:11px;min-height:16px">{c.e(msg)}</p>'
        )


def storage_policy(ctx: dict[str, Any]) -> None:
    r, sizes = data.retention(), data.folder_sizes()
    rows = [
        (
            "landing",
            "arrival_date / feeder",
            "gateway files kept as received",
            f"{r['raw_days']} days",
        ),
        ("bronze", "arrival_date", "one Parquet per arrival day", f"{r['bronze_days']} days"),
        (
            "quarantine",
            "date",
            "one Parquet per day, rule + reason",
            f"{r['quarantine_days']} days",
        ),
        (
            "silver",
            "date / zone",
            "one file per zone, sorted meter_id, interval_start",
            f"{r['silver_months']} months",
        ),
        (
            "gold",
            "date / zone · month",
            "nightly compaction to one file",
            f"hourly {r['hourly_months']} months",
        ),
        (
            "_archive",
            "table / run_id",
            "replaced gold partitions for rollback",
            f"{r['archive_days']} days",
        ),
    ]
    body = [
        [
            f'<span class="mono" style="font-weight:600">{name}</span>',
            f'<span class="mono muted" style="font-size:12px">{c.e(part)}</span>',
            f'<span class="muted" style="font-size:12px">{c.e(comp)}</span>',
            f'<span class="delta" style="background:var(--accent);color:var(--accent-foreground)">{c.e(ret)}</span>',
            f'<span class="mono">{human_bytes(sizes.get(name))}</span>',
        ]
        for name, part, comp, ret in rows
    ]
    with st.container(key="panel_storage"):
        c.render(c.panel_head("Time-series storage layout", "Partitioning, compaction & retention"))
        c.render(
            c.table(
                [
                    ("Layer", False),
                    ("Partition", False),
                    ("Compaction", False),
                    ("Retention", False),
                    ("Size", True),
                ],
                body,
            )
        )


# ---------- views ----------
def overview(ctx: dict[str, Any]) -> None:
    hero(ctx)
    kpi_strip(ctx)
    a, b = st.columns([2, 1], gap="large")
    with a:
        feeder_consumption(ctx)
    with b:
        zone_completeness(ctx)
    a, b = st.columns([2, 1], gap="large")
    with a:
        anomaly_list(ctx, 5, "feed_overview")
    with b:
        schema_mix(ctx)
    feeder_heatmap(ctx)
    pipeline_flow(ctx)


def consumption(ctx: dict[str, Any]) -> None:
    feeder_consumption(ctx)
    daily_consumption(ctx)
    billing_table(ctx)


def anomalies(ctx: dict[str, Any]) -> None:
    anomaly_summary(ctx)
    anomaly_list(ctx, None, "feed_all")
    feeder_heatmap(ctx)


def quality(ctx: dict[str, Any]) -> None:
    kpi_strip(ctx)
    a, b, d = st.columns(3, gap="large")
    with a:
        zone_completeness(ctx)
    with b:
        quality_rules(ctx)
    with d:
        schema_mix(ctx)
    feeder_heatmap(ctx)


def pipeline(ctx: dict[str, Any]) -> None:
    pipeline_flow(ctx)
    a, b, d = st.columns(3, gap="large")
    with a:
        run_history(ctx)
    with b:
        ingest_lag(ctx)
    with d:
        backfill(ctx)
    storage_policy(ctx)


VIEWS = {
    "overview": ("Overview", ":material/dashboard:", overview),
    "consumption": ("Consumption", ":material/bolt:", consumption),
    "anomalies": ("Anomalies", ":material/warning:", anomalies),
    "quality": ("Data quality", ":material/verified_user:", quality),
    "pipeline": ("Pipeline health", ":material/account_tree:", pipeline),
}
