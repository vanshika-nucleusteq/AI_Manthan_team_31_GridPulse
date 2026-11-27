# Low-level design

## Architecture diagram

## Components

## Data flow and DAG tasks

## Data model (bronze, silver, gold)

## Schema evolution (v1, v2)

## Partitioning and retention

## Idempotency, late data and backfill

## Deviations from the card (Streamlit instead of Superset)

## Note: Airflow dependency isolation

Decision (P0): Airflow 2.10 pins older SQLAlchemy, pandas and numpy than our package needs, and we do not downgrade to its pins.

- The Airflow image (built in P3) has a separate virtualenv at `/opt/gridpulse-venv` with the `gridpulse` package installed.
- Every DAG task is a `BashOperator` running `/opt/gridpulse-venv/bin/python -m gridpulse.cli <step> --ds {{ ds }}`.
- Airflow's own Python only parses `dags/gridpulse_daily.py`, which imports nothing from `gridpulse`.
- Trade-off: a slightly larger image and a subprocess per task, in exchange for no dependency conflicts and a CLI we can run and test without Airflow.

## Security and secrets

