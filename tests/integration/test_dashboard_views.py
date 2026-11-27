"""Dashboard integration: every view renders against the real database without an exception."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
VIEWS = ["overview", "consumption", "anomalies", "quality", "pipeline"]


def _db_url() -> str:
    if os.environ.get("GRIDPULSE_DB_URL"):
        return os.environ["GRIDPULSE_DB_URL"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GRIDPULSE_DB_URL="):
                return line.split("=", 1)[1]
    pytest.skip("GRIDPULSE_DB_URL not set and no .env; run make.ps1 up first")


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_view_renders_without_exception(
    view: str, theme: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("GRIDPULSE_DB_URL", _db_url())
    monkeypatch.syspath_prepend(str(ROOT / "app"))
    app = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=120)
    app.query_params["view"] = view
    app.query_params["theme"] = theme
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    page = " ".join(m.value for m in app.markdown)
    assert "Cannot reach PostgreSQL" not in page and "No gold data yet" not in page
