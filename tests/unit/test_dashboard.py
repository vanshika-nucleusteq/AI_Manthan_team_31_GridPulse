"""Dashboard (MH7): HTML helpers apply the rules; the app fails soft without a database."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from gridpulse_ui import components as c  # noqa: E402
from gridpulse_ui.views import anomaly_rows  # noqa: E402


def test_heatmap_marks_low_and_missing_hours_as_hatched_gaps() -> None:
    cells = {("F07", 10): (12.0, True), ("F07", 11): (300.0, False)}
    html = c.heatmap(["F07"], cells, 300.0)
    assert html.count('class="c gap hatch"') == 23  # hour 10 (low completeness) + 22 missing hours
    assert "F07 · 10:00 · gap: readings missing" in html
    assert "F07 · 11:00 · 300 kWh" in html


def test_zone_at_exactly_90pct_is_flagged() -> None:
    html = c.zone_bars(
        [
            {"zone": "Z2", "pct": 90.0, "meters": 1000, "gaps": 9600},
            {"zone": "Z3", "pct": 90.6, "meters": 750, "gaps": 6768},
        ],
        90.0,
    )
    assert html.count("quality flag") == 1
    assert html.index("quality flag") < html.index("Z3")


def test_sparkline_needs_two_points_and_stays_in_viewbox() -> None:
    assert c.sparkline([1.0], True) == ""
    svg = c.sparkline([1.0, 3.0, 2.0], False)
    assert 'points="0.0,28.0 50.0,4.0 100.0,16.0"' in svg and "var(--warning)" in svg


def test_anomaly_rows_map_type_to_severity_and_metric() -> None:
    ts = pd.Timestamp("2026-08-11T05:30:00Z")
    df = pd.DataFrame(
        [
            {
                "type": "outage",
                "meter_id": None,
                "feeder_id": "F07",
                "zone_id": "Z2",
                "score": 0.8,
                "window_start": ts,
                "details": {"intervals": 8, "max_meters_missing": 200, "meters_on_feeder": 250},
            },
            {
                "type": "spike",
                "meter_id": "MTR-00001",
                "feeder_id": "F01",
                "zone_id": "Z1",
                "score": 12.5,
                "window_start": ts,
                "details": {"kwh": 2.4, "baseline_mean_kwh": 0.3, "baseline_samples": 20},
            },
            {
                "type": "tamper",
                "meter_id": "MTR-00002",
                "feeder_id": "F01",
                "zone_id": "Z1",
                "score": 60.0,
                "window_start": ts,
                "details": {"zero_hours": 60, "feeder_normal_share": 0.98},
            },
        ]
    )
    rows = anomaly_rows(df)
    assert [(r["target"], r["severity"], r["metric"]) for r in rows] == [
        ("Feeder F07", "critical", "80% silent"),
        ("MTR-00001", "high", "z = 12.5"),
        ("MTR-00002", "high", "60h zero"),
    ]
    assert rows[0]["detail"] == "200 of 250 meters silent for 120 min together"
    assert rows[0]["when"] == "11 Aug 11:00 IST · open"  # 05:30 UTC is 11:00 IST


def test_app_shows_backend_error_instead_of_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv(
        "GRIDPULSE_DB_URL", "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1"
    )
    app = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=60).run()
    assert not app.exception
    page = " ".join(m.value for m in app.markdown)
    assert "Cannot reach PostgreSQL" in page and "make.ps1 up" in page
