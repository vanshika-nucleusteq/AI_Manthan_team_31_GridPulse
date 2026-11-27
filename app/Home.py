"""Streamlit home page for GridPulse Network Operations: placeholder until P11 builds the pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from gridpulse.common.db import sqlalchemy_url

st.set_page_config(page_title="GridPulse · Network Operations", layout="wide")
st.title("GridPulse · Network Operations")
st.caption(
    "Placeholder page. The five dashboard pages (Overview, Completeness, Anomalies, Billing, "
    "Pipeline health) arrive in P11; the design is in docs/ui-design.md."
)


@st.cache_resource
def engine() -> Engine:
    return create_engine(sqlalchemy_url(), pool_pre_ping=True)


@st.cache_data(ttl=60)
def meters_per_zone() -> pd.DataFrame:
    query = text(
        "SELECT zone_id, count(*) AS meters, count(DISTINCT feeder_id) AS feeders "
        "FROM meter_master GROUP BY zone_id ORDER BY zone_id"
    )
    with engine().connect() as conn:
        return pd.read_sql(query, conn)


try:
    zones = meters_per_zone()
except Exception as exc:  # shown to the user instead of a stack trace
    st.error(f"Cannot read meter_master from PostgreSQL. Check that the stack is up. ({exc})")
else:
    if zones.empty:
        st.info("meter_master is empty. Run `make.ps1 generate`, then `make.ps1 seed`.")
    else:
        left, right = st.columns(2)
        left.metric("Meters in meter_master", f"{int(zones['meters'].sum()):,}")
        right.metric("Zones · feeders", f"{len(zones)} · {int(zones['feeders'].sum())}")
        st.dataframe(zones, hide_index=True, use_container_width=True)
