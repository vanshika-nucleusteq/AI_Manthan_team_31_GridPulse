# Low-level design

## Architecture diagram

## Components

## Data flow and DAG tasks

## Data model (bronze, silver, gold)

## Schema evolution (v1, v2)

## Partitioning and retention

## Idempotency, late data and backfill

## Deviations from the card (Streamlit instead of Superset)

## UTC vs IST pitfalls

Storage is UTC; days, hours, months and billing are Asia/Kolkata (UTC+05:30, no DST). Places where a reading can land on the wrong day, and what the code does:

| Pitfall | Wrong | Right (what we do) |
| --- | --- | --- |
| IST day starts at 18:30 UTC | `ts::DATE` in a UTC DuckDB session puts 2026-07-31T18:30Z on 31 Jul | `(interval_start AT TIME ZONE 'Asia/Kolkata')::DATE` gives 1 Aug |
| Snapping near midnight | Bucketing the raw `ts` 18:29:40Z into the previous day | Snap to the 15-minute grid first (18:30Z), then take the IST day; quality and normalise both bucket by the snapped interval |
| IST hours start at :30 UTC | `date_trunc('hour', interval_start)` in UTC splits each IST hour in two | Truncate in IST (P6): `date_trunc('hour', interval_start AT TIME ZONE 'Asia/Kolkata')` |
| Arrival date is not reading date | Treating `arrival_date=D` as readings of D (the 23:00 IST hour arrives at 00:05 on D+1) | Bronze is partitioned by arrival; silver and quarantine by the reading's IST day |
| Month and billing boundaries | Month from UTC: 1 Aug 00:00-05:29 IST counted in July | Month = IST calendar month: starts 18:30Z on the last day of the previous month (P6) |
| Grid of expected intervals | 96 intervals from UTC midnight | 96 intervals from IST midnight (`day_start_utc` in `normalise/gaps.py`) |
| Naive timestamps | Assuming UTC (or local) for `2026-07-31T18:30:00` | Quarantined as `BAD_TIMESTAMP` ("ts has no time zone") |

## Note: Airflow dependency isolation

Decision (P0): Airflow 2.10 pins older SQLAlchemy, pandas and numpy than our package needs, and we do not downgrade to its pins.

- The Airflow image (built in P3) has a separate virtualenv at `/opt/gridpulse-venv` with the `gridpulse` package installed.
- Every DAG task is a `BashOperator` running `/opt/gridpulse-venv/bin/python -m gridpulse.cli <step> --ds {{ ds }}`.
- Airflow's own Python only parses `dags/gridpulse_daily.py`, which imports nothing from `gridpulse`.
- Trade-off: a slightly larger image and a subprocess per task, in exchange for no dependency conflicts and a CLI we can run and test without Airflow.

## Security and secrets

