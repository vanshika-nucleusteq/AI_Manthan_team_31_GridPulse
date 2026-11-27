"""GridPulse · Network Operations dashboard (Streamlit). Run: streamlit run app/app.py"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="GridPulse · Smart Meter Telemetry | AI Manthan",
    page_icon=":zap:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from gridpulse_ui import components as c  # noqa: E402
from gridpulse_ui import data  # noqa: E402
from gridpulse_ui.theme import css  # noqa: E402
from gridpulse_ui.views import VIEWS, fmt_day  # noqa: E402

DEFAULTS = {"view": "overview", "theme": "dark", "zone_filter": "All", "backfill_msg": None}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)
if (
    "query_applied" not in st.session_state
):  # deep links: ?view=anomalies&theme=light&day=2026-08-11
    params = st.query_params
    if params.get("view") in VIEWS:
        st.session_state["view"] = params["view"]
    if params.get("theme") in ("dark", "light"):
        st.session_state["theme"] = params["theme"]
    if params.get("day"):
        try:
            st.session_state["day_select"] = date.fromisoformat(params["day"])
        except ValueError:
            pass
    st.session_state["query_applied"] = True


def set_view(view: str) -> None:
    st.session_state["view"] = view


def set_theme() -> None:
    choice = st.session_state.get("theme_ctl")
    if choice:
        st.session_state["theme"] = choice.lower()


view = st.session_state["view"]
theme = st.session_state["theme"]
error = data.database_error()
day_options: list[date] = [] if error else data.days()
recent = 0
if day_options:
    day = st.session_state.get("day_select") or day_options[0]
    recent_df = data.anomalies(day, day - timedelta(days=6))
    recent = len(recent_df)

badge = (
    f'.st-key-nav_anomalies button::after {{ content: "{recent}"; margin-left: auto; border-radius: 999px;'
    " padding: 1px 8px; font-family: var(--mono); font-size: 10px; font-weight: 600;"
    " background: color-mix(in srgb, var(--destructive) 15%, transparent); color: var(--destructive); }"
    f" .st-key-nav_{view} [data-testid='stIconMaterial'] {{ color: var(--primary) !important; }}"
)
st.markdown(css(theme, view) + f"<style>{badge if recent else ''}</style>", unsafe_allow_html=True)

# ---------- sidebar ----------
with st.sidebar:
    c.render(c.logo())
    c.render(
        '<p class="eyebrow" style="padding:0 12px;letter-spacing:.18em;margin-bottom:8px">Operations</p>'
    )
    for key, (label, material, _) in VIEWS.items():
        st.button(label, key=f"nav_{key}", icon=material, on_click=set_view, args=(key,))

# ---------- header ----------
label = VIEWS[view][0]
with st.container(key="header"):
    left, mid, right, toggle = st.columns([3.4, 1.4, 1.5, 1.1], vertical_alignment="center")
    with left:
        c.render(c.crumb(label))
    with mid:
        if day_options:
            st.selectbox(
                "Day",
                day_options,
                key="day_select",
                label_visibility="collapsed",
                format_func=lambda d: f"{fmt_day(d)} · IST",
            )
    with right:
        live = "Database unreachable"
        if not error and day_options:
            published = data.query(
                "SELECT max(finished_at) AS t FROM pipeline_runs WHERE task = 'publish'"
            ).iloc[0]["t"]
            if published is not None and not pd.isna(published):
                age = (
                    datetime.now(tz=pd.Timestamp(published).tz)
                    - pd.Timestamp(published).to_pydatetime()
                )
                mins = int(age.total_seconds() // 60)
                live = (
                    f"Data published · {mins}m ago"
                    if mins < 120
                    else f"Data published · {mins // 60}h ago"
                )
            else:
                live = "Live · PostgreSQL"
        c.render(c.header_chips(live))
    with toggle:
        st.segmented_control(
            "Theme",
            ["Light", "Dark"],
            key="theme_ctl",
            default=theme.title(),
            on_change=set_theme,
            label_visibility="collapsed",
        )

# ---------- content ----------
if error:
    with st.container(key="panel_error"):
        c.render(c.panel_head("Backend", "Cannot reach PostgreSQL"))
        c.render(c.empty(f"{error}. Start the stack with make.ps1 up, then reload."))
    st.stop()
if not day_options:
    with st.container(key="panel_empty"):
        c.render(c.panel_head("Backend", "No gold data yet"))
        c.render(c.empty("Run make.ps1 generate, then make.ps1 backfill 2026-08-01 2026-08-21."))
    st.stop()

day = st.session_state.get("day_select") or day_options[0]
ctx = {"day": day, "theme": theme, "totals": data.daily_totals(day)}
ctx["totals"]["local_date"] = pd.to_datetime(ctx["totals"]["local_date"]).dt.date
VIEWS[view][2](ctx)
