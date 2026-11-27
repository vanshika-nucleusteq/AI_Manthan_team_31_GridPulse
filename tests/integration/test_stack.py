"""Stack integration (needs make.ps1 up and data). Run: pytest -m integration tests/integration."""

from __future__ import annotations

import csv
import os
import subprocess
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "--env-file", ".env", "-f", "deploy/docker-compose.yml"]


def _db_url() -> str:
    if os.environ.get("GRIDPULSE_DB_URL"):
        return os.environ["GRIDPULSE_DB_URL"]
    env = ROOT / ".env"
    if not env.exists():
        pytest.skip(".env missing; run make.ps1 up first")
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("GRIDPULSE_DB_URL="):
            return line.split("=", 1)[1]
    pytest.skip("GRIDPULSE_DB_URL not in .env")


def _count() -> int:
    try:
        with psycopg.connect(_db_url(), connect_timeout=3) as conn:
            return conn.execute("SELECT count(*) FROM meter_master").fetchone()[0]
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL not reachable: {exc}")


def test_meter_master_seeded_with_5000_rows_and_reseed_is_idempotent() -> None:
    master = ROOT / "data" / "meter_master.csv"
    if not master.exists():
        pytest.skip("data/meter_master.csv missing; run make.ps1 generate")
    with master.open(encoding="utf-8") as fh:
        expected = sum(1 for _ in csv.DictReader(fh))
    assert _count() == expected == 5000
    subprocess.run(
        [*COMPOSE, "run", "--rm", "gridpulse-init"], cwd=ROOT, check=True, capture_output=True
    )
    assert _count() == expected
