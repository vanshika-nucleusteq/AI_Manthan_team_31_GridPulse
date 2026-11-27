"""Airflow DAG gridpulse_daily: one run per IST day (ds); each task runs our CLI in its own venv.

Imports nothing from gridpulse: Airflow's Python only parses this file (CLAUDE.md, Stack).
The DAG runs in UTC on purpose: Airflow formats {{ ds }} from a UTC logical date, so a schedule
in IST (02:00 IST = 20:30 UTC the day before) would hand every task the previous day. With a
00:00 UTC schedule, ds is the IST day being processed and the run starts at 05:30 IST.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pendulum
import yaml
from airflow import DAG
from airflow.operators.bash import BashOperator

CONFIG_DIR = Path(os.environ.get("GRIDPULSE_CONFIG_DIR", "/opt/gridpulse/config"))
PYTHON = os.environ.get("GRIDPULSE_PYTHON", "/opt/gridpulse-venv/bin/python")
TASKS = [
    "ingest",
    "quality",
    "normalise",
    "aggregate",
    "anomalies",
    "publish",
    "compact",
    "retention",
    "metrics",
]

settings = yaml.safe_load((CONFIG_DIR / "pipeline.yaml").read_text(encoding="utf-8"))
orchestration = settings["orchestration"]
go_live = pendulum.parse(str(settings["go_live_date"]), tz="UTC")

with DAG(
    dag_id=orchestration["dag_id"],
    description="GridPulse daily batch: landing -> bronze -> silver -> gold -> PostgreSQL",
    schedule=orchestration.get("schedule"),
    start_date=go_live,
    catchup=False,
    max_active_runs=int(orchestration["max_active_runs"]),
    default_args={
        "retries": int(orchestration["retries"]),
        "retry_delay": timedelta(minutes=int(orchestration["retry_delay_minutes"])),
    },
    tags=["gridpulse"],
) as dag:
    previous = None
    for name in TASKS:
        task = BashOperator(
            task_id=name,
            bash_command=f"{PYTHON} -m gridpulse.cli {name} --ds {{{{ ds }}}}",
        )
        if previous is not None:
            previous >> task
        previous = task
