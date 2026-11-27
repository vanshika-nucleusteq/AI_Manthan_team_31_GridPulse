"""HTML helpers: Lucide-style icons, hero, KPI cards, sparkline, feed, heatmap, bars, tables, stepper."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

ICONS = {
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/>'
    '<path d="M3 10h18"/>',
    "bell": '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0'
    ' .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
    "trending-up": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "shield-alert": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0'
    ' 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
    '<path d="M12 8v4"/><path d="M12 16h.01"/>',
    "zap-off": '<path d="M10.513 4.856 13.12 2.17a.5.5 0 0 1 .86.46l-1.377 4.317"/><path d="M15.656'
    ' 10H20a1 1 0 0 1 .78 1.63l-1.72 1.773"/><path d="M16.273 16.273 10.88 21.83a.5.5 0 0 1-.86-.46l1.92'
    '-6.02A1 1 0 0 0 11 14H4a1 1 0 0 1-.78-1.63l4.507-4.643"/><path d="m2 2 20 20"/>',
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "circle-x": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "triangle-alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0'
    ' 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "loader": '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
    '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "up": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "down": '<path d="m7 7 10 10"/><path d="M17 7v10H7"/>',
}

PULSE = (
    "M0 60 L120 60 L140 60 L152 22 L166 96 L178 60 L300 60 L318 60 L328 40 L340 78 L350 60 L470 60"
    " L490 60 L502 14 L516 104 L528 60 L650 60 L668 60 L678 44 L690 74 L700 60 L820 60 L840 60"
    " L852 26 L866 92 L878 60 L1000 60"
)


def icon(name: str, size: int = 16, cls: str = "", width: float = 2) -> str:
    return (
        f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{ICONS[name]}</svg>'
    )


def render(markup: str) -> None:
    """st.markdown treats indented lines as code blocks, so flatten the markup first."""
    st.markdown("".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def e(value: Any) -> str:
    return escape(str(value))


def panel_head(eyebrow: str | None, title: str, action: str = "") -> str:
    eb = f'<p class="eyebrow">{e(eyebrow)}</p>' if eyebrow else ""
    return f'<div class="panel-head"><div>{eb}<h2>{e(title)}</h2></div>{action}</div>'


def empty(message: str) -> str:
    return f'<div class="empty">{e(message)}</div>'


def logo() -> str:
    return (
        '<div class="logo"><div class="logo-mark glow">'
        f'{icon("activity", 20, width=2.5)}</div><div><b>GridPulse</b><small>AI Manthan</small></div></div>'
    )


def status_card(title: str, detail: str, pct: float, live: bool) -> str:
    dot = '<span class="live"></span>' if live else ""
    return (
        f'<div class="status-card"><p class="t">{dot}{e(title)}</p><p class="d">{detail}</p>'
        f'<div class="track"><i style="width:{max(0, min(100, pct)):.0f}%"></i></div></div>'
    )


def crumb(label: str) -> str:
    return f'<div class="crumb"><p class="eyebrow">Network operations / {e(label)}</p><h1>{e(label)}</h1></div>'


def header_chips(live_text: str) -> str:
    return (
        '<div class="hdr-right">'
        f'<span class="chip live-chip"><span class="live" style="width:6px;height:6px"></span>{e(live_text)}</span>'
        f'<span class="bell" role="img" aria-label="Notifications">{icon("bell", 16)}<i></i></span></div>'
    )


def hero(mwh: float, delta_pct: float | None, label: str, tiles: list[tuple[str, str]]) -> str:
    if delta_pct is None:
        pill = ""
    else:
        tone, arrow = ("tone-success", "up") if delta_pct >= 0 else ("tone-warning", "down")
        pill = (
            f'<span class="delta {tone}" style="font-size:12px;padding:4px 10px;margin-bottom:8px">'
            f"{icon(arrow, 14)}{abs(delta_pct):.1f}% vs previous day</span>"
        )
    tile_html = "".join(
        f'<div class="tile"><dt>{e(lbl)}</dt><dd>{e(v)}</dd></div>' for v, lbl in tiles
    )
    return f"""
    <section class="hero"><div class="bg-grid"></div><div class="blob"></div>
    <svg class="pulse" viewBox="0 0 1000 120" preserveAspectRatio="none" aria-hidden="true">
    <path d="{PULSE}" fill="none" stroke="var(--border)" stroke-width="1.5"/>
    <path d="{PULSE}" fill="none" stroke="var(--primary)" stroke-width="2.5" class="pulse-line"/></svg>
    <div class="inner"><div><p class="eyebrow" style="letter-spacing:.18em">{e(label)}</p>
    <div style="margin-top:12px;display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap">
    <p class="big" style="margin:0">{mwh:,.1f}<span> MWh</span></p>{pill}</div>
    <p class="lead">Telemetry from every smart meter is ingested, normalised to kWh, deduplicated and
    checked for spikes, tampering and feeder outages before it reaches billing.</p></div>
    <dl class="tiles" style="margin:0">{tile_html}</dl></div></section>
    """


def sparkline(values: list[float], positive: bool) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    pts = " ".join(
        f"{i / (len(values) - 1) * 100:.1f},{28 - (v - lo) / span * 24:.1f}"
        for i, v in enumerate(values)
    )
    color = "var(--primary)" if positive else "var(--warning)"
    return (
        '<svg viewBox="0 0 100 30" width="96" height="32" preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>'
    )


def kpi_strip(kpis: list[dict[str, Any]]) -> str:
    cards = []
    for k in kpis:
        good = k["good"]
        tone, arrow = (
            ("tone-success", "up" if k["up"] else "down")
            if good
            else ("tone-warning", "up" if k["up"] else "down")
        )
        delta = (
            f'<span class="delta {tone}">{icon(arrow, 12)}{e(k["delta"])}</span>'
            if k["delta"]
            else ""
        )
        cards.append(
            f'<div class="card kpi"><div class="top"><p class="lbl" style="margin:0">{e(k["label"])}</p>'
            f'{delta}</div><div class="row"><p class="val" style="margin:0">{e(k["value"])}</p>'
            f'{sparkline(k["spark"], good)}</div><p class="sub" style="margin:8px 0 0">{e(k["sub"])}</p></div>'
        )
    return f'<div class="kpis">{"".join(cards)}</div>'


TYPE_META = {
    "spike": ("Spike", "trending-up", "tone-chart2"),
    "tamper": ("Suspected tamper", "shield-alert", "tone-warning"),
    "outage": ("Outage", "zap-off", "tone-destructive"),
}


def anomaly_summary(counts: dict[str, int], rules: dict[str, str]) -> str:
    cards = []
    for t, (label, ic, tone) in TYPE_META.items():
        cards.append(
            f'<div class="card"><div style="display:flex;align-items:center;gap:12px">'
            f'<span class="ico {tone}" style="width:40px;height:40px;border-radius:12px">{icon(ic, 20)}</span>'
            f'<div><p style="margin:0;font-size:14px;font-weight:500">{e(label)}</p>'
            f'<p class="muted" style="margin:0;font-size:12px">{e(rules[t])}</p></div></div>'
            f'<p class="mono" style="margin:16px 0 0;font-size:30px;font-weight:600">{counts.get(t, 0)} '
            f'<span class="muted" style="font-size:14px;font-weight:400">detected</span></p></div>'
        )
    return f'<div class="kpis" style="grid-template-columns:repeat(3,minmax(0,1fr))">{"".join(cards)}</div>'


def anomaly_feed(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return empty("No anomalies in this window.")
    items = []
    for a in rows:
        label, ic, tone = TYPE_META[a["type"]]
        items.append(
            f'<li class="feed-row" style="{"opacity:.6" if a.get("resolved") else ""}">'
            f'<span class="ico {tone}" style="width:36px;height:36px">{icon(ic, 16)}</span>'
            '<div style="min-width:0;flex:1"><div style="display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px">'
            f'<p class="mono" style="margin:0;font-size:14px;font-weight:600">{e(a["target"])}</p>'
            f'<span class="muted" style="font-size:12px">{e(a["where"])}</span>'
            f'<span class="sev {a["severity"]}">{e(a["severity"])}</span></div>'
            f'<p class="muted trunc" style="margin:2px 0 0;font-size:12px">{e(a["detail"])}</p></div>'
            f'<div style="text-align:right;flex:none"><p class="mono" style="margin:0;font-size:14px">'
            f'{e(a["metric"])}</p><p class="mono muted" style="margin:0;font-size:11px">{e(a["when"])}</p></div></li>'
        )
    return f'<ul class="feed" style="list-style:none;margin:0;padding:0">{"".join(items)}</ul>'


def heatmap(
    feeders: list[str], cells: dict[tuple[str, int], tuple[float | None, bool]], vmax: float
) -> str:
    parts = ['<div class="scroll-x"><div class="heat"><span></span>']
    parts += [
        f'<span class="hr">{h:02d}</span>' if h % 3 == 0 else "<span></span>" for h in range(24)
    ]
    for f in feeders:
        parts.append(f'<span class="lab">{e(f)}</span>')
        for h in range(24):
            kwh, gap = cells.get((f, h), (None, True))
            if gap or kwh is None:
                title = f"{f} · {h:02d}:00 · gap: readings missing"
                parts.append(f'<span class="c gap hatch" title="{e(title)}"></span>')
            else:
                pct = round(12 + kwh / (vmax or 1) * 88)
                title = f"{f} · {h:02d}:00 · {kwh:,.0f} kWh"
                parts.append(
                    f'<span class="c" title="{e(title)}" style="background:color-mix(in srgb, '
                    f'var(--primary) {pct}%, var(--muted))"></span>'
                )
    parts.append("</div></div>")
    return "".join(parts)


def heatmap_legend() -> str:
    return (
        '<div class="legend"><span>Low <span style="height:8px;width:64px;border-radius:999px;'
        'background:linear-gradient(to right,var(--muted),var(--primary))"></span> High</span>'
        '<span><span class="hatch" style="width:12px;height:12px;border-radius:3px;border:1px solid '
        'color-mix(in srgb,var(--destructive) 40%,transparent)"></span>Gap (not filled)</span></div>'
    )


def zone_bars(rows: list[dict[str, Any]], threshold: float) -> str:
    items = []
    for z in rows:
        low = not z["pct"] > threshold
        color = (
            "var(--destructive)" if low else "var(--warning)" if z["pct"] < 95 else "var(--primary)"
        )
        flag = (
            '<span class="delta tone-destructive" style="font-size:10px">quality flag</span>'
            if low
            else ""
        )
        items.append(
            f'<li><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;'
            f'font-size:14px;margin-bottom:6px"><span style="display:flex;align-items:center;gap:8px;'
            f'font-weight:500">{e(z["zone"])}{flag}</span><span class="mono" style="color:'
            f'{"var(--destructive)" if low else "var(--foreground)"}">{z["pct"]:.1f}%</span></div>'
            f'<div class="bar"><i style="width:{min(z["pct"], 100):.1f}%;background:{color}"></i>'
            f'<b style="left:{threshold}%"></b></div><p class="mono muted" style="margin:4px 0 0;'
            f'font-size:11px">{z["meters"]:,} meters · {z["gaps"]:,} gap intervals</p></li>'
        )
    note = (
        f'<p class="muted" style="margin:20px 0 0;padding-top:16px;border-top:1px solid var(--border);'
        f'font-size:12px">Marker shows the {threshold:.0f}% per meter-day threshold (flag unless above it). '
        "Missing intervals are flagged as gaps and never interpolated.</p>"
    )
    body = "".join(items)
    return f'<ul style="list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:16px">{body}</ul>{note}'


def schema_mix(parts: list[dict[str, Any]]) -> str:
    colors = ["var(--chart-2)", "var(--primary)", "var(--chart-3)", "var(--chart-5)"]
    bar = "".join(
        f'<div style="width:{p["pct"]:.1f}%;background:{colors[i % 4]}"></div>'
        for i, p in enumerate(parts)
    )
    rows = "".join(
        f'<li style="display:flex;align-items:flex-start;gap:12px"><span style="margin-top:6px;width:10px;'
        f'height:10px;border-radius:999px;flex:none;background:{colors[i % 4]}"></span>'
        f'<div style="flex:1;min-width:0"><p style="margin:0;font-size:14px;font-weight:500">{e(p["name"])}</p>'
        f'<p class="mono muted" style="margin:0;font-size:11px">{e(p["note"])}</p></div>'
        f'<span class="mono" style="font-size:14px">{"&lt;1" if 0 < p["pct"] < 0.5 else format(p["pct"], ".0f")}%</span></li>'
        for i, p in enumerate(parts)
    )
    return (
        f'<div style="display:flex;height:16px;overflow:hidden;border-radius:999px">{bar}</div>'
        f'<ul style="list-style:none;margin:20px 0 0;padding:0;display:flex;flex-direction:column;gap:12px">'
        f'{rows}</ul><p class="note-box" style="margin:20px 0 0">raw payload preserved · '
        '<span style="color:var(--foreground)">schema_version</span> tagged on every event</p>'
    )


def quality_rules(rows: list[dict[str, Any]]) -> str:
    icons = {
        "pass": icon("circle-check", 16, width=2).replace(
            "<svg", '<svg style="color:var(--success);flex:none"'
        ),
        "warn": icon("triangle-alert", 16).replace(
            "<svg", '<svg style="color:var(--warning);flex:none"'
        ),
        "fail": icon("circle-x", 16).replace(
            "<svg", '<svg style="color:var(--destructive);flex:none"'
        ),
    }
    items = []
    for i, r in enumerate(rows):
        total = r["passed"] + r["failed"]
        rate = r["passed"] / total * 100 if total else 100.0
        note = f' · {e(r["note"])}' if r.get("note") else ""
        border = "border-top:1px solid var(--border);" if i else ""
        items.append(
            f'<li style="display:flex;align-items:center;gap:12px;padding:12px 0;{border}">{icons[r["status"]]}'
            f'<div style="flex:1;min-width:0"><p style="margin:0;font-size:14px;font-weight:500">{e(r["rule"])}</p>'
            f'<p class="mono muted" style="margin:0;font-size:11px">{r["failed"]:,} failed{note}</p></div>'
            f'<span class="mono" style="font-size:14px">{rate:.2f}%</span></li>'
        )
    return f'<ul style="list-style:none;margin:0;padding:0">{"".join(items)}</ul>'


STEP_STYLE = {
    "success": (
        "circle-check",
        "",
        "var(--primary)",
        "color-mix(in srgb,var(--primary) 50%,transparent)",
    ),
    "running": (
        "loader",
        "spin",
        "var(--chart-2)",
        "color-mix(in srgb,var(--chart-2) 50%,transparent)",
    ),
    "retrying": (
        "refresh",
        "spin-slow",
        "var(--warning)",
        "color-mix(in srgb,var(--warning) 60%,transparent)",
    ),
    "failed": (
        "circle-x",
        "",
        "var(--destructive)",
        "color-mix(in srgb,var(--destructive) 60%,transparent)",
    ),
    "queued": ("clock", "", "var(--muted-foreground)", "var(--border)"),
}


def stepper(steps: list[dict[str, Any]]) -> str:
    items = []
    for i, s in enumerate(steps):
        ic, cls, color, ring = STEP_STYLE[s["status"]]
        conn = ""
        if i < len(steps) - 1:
            bg = "var(--primary)" if s["status"] == "success" else "var(--border)"
            conn = f'<span class="conn" style="background:{bg}"></span>'
        box = {"retrying": " retry", "failed": " fail"}.get(s["status"], "")
        items.append(
            f'<li class="step"><div style="display:flex;align-items:center;margin-bottom:12px">'
            f'<span class="ring" style="border-color:{ring};color:{color}">{icon(ic, 16, cls)}</span>{conn}</div>'
            f'<div class="box{box}"><p class="mono" style="margin:0;font-size:12px;font-weight:600">{e(s["name"])}</p>'
            f'<p class="muted" style="margin:2px 0 0;font-size:11px;line-height:1.4">{e(s["desc"])}</p>'
            f'<div class="mono muted" style="margin-top:8px;display:flex;justify-content:space-between;'
            f'font-size:11px"><span>{e(s["duration"])}</span><span>{e(s["records"])}</span></div></div></li>'
        )
    return f'<ol class="steps">{"".join(items)}</ol>'


def table(headers: list[tuple[str, bool]], rows: list[list[str]]) -> str:
    head = "".join(f'<th class="{"r" if right else ""}">{e(h)}</th>' for h, right in headers)
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{"r" if headers[i][1] else ""}">{cell}</td>' for i, cell in enumerate(r)
        )
        + "</tr>"
        for r in rows
    )
    return f'<div class="scroll-x"><table class="gp"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def status_pill(status: str) -> str:
    tone = {"ready": "tone-success", "review": "tone-warning", "held": "tone-destructive"}[status]
    return f'<span class="delta {tone}" style="padding:2px 10px;text-transform:capitalize">{e(status)}</span>'
