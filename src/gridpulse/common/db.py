"""PostgreSQL connection settings, read from GRIDPULSE_DB_URL (set in .env or by Compose)."""

from __future__ import annotations

import os


def db_url() -> str:
    url = os.environ.get("GRIDPULSE_DB_URL")
    if not url:
        raise RuntimeError("GRIDPULSE_DB_URL is not set; copy .env.example to .env")
    return url


def sqlalchemy_url() -> str:
    """Same database, addressed for SQLAlchemy 2 with the psycopg 3 driver."""
    url = db_url()
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url
