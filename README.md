# GridPulse: smart meter telemetry platform

AI Manthan Wave 2, Track B, team 31. A batch platform that ingests synthetic smart meter telemetry,
normalises it to kWh on a 15-minute UTC grid, produces billing-ready consumption and flags spike,
tamper and outage anomalies. Scope: `docs/card.md`. Design: `docs/gridpulse-plan.md`.
Team rules: `CLAUDE.md`.

## How to run

Windows has no `make`, so every target runs through PowerShell:
`powershell -ExecutionPolicy Bypass -File scripts/make.ps1 <target>` (shortened to `make.ps1 <target>` below).
On Linux and macOS use `make <target>`.

### Prerequisites
Python 3.12 and Docker Desktop with Compose v2. Ports 5432, 8080 and 8501 free (change them in `.env`).

### 1. Local dev (tests and lint)
```
make.ps1 venv      # .venv with Python 3.12 and pip install -e ".[dev]"
make.ps1 check     # ruff, black --check, pytest (unit tests)
```

### 2. Synthetic data
```
make.ps1 generate --days 14 --overwrite   # about 100 s: data/landing, data/meter_master.csv, data/answer_key.json
```
Use `--days 21` when you need the spike check to fire (it needs 14 days of history).

### 3. Stack (one command)
```
make.ps1 up
```
Creates `.env` from `.env.example` on first run (with generated Airflow keys), builds the images and waits
until every service is healthy. Expected `docker compose ps`:

| Service | State | URL |
| --- | --- | --- |
| postgres | healthy | localhost:5432 (`gridpulse` and `airflow` databases) |
| gridpulse-init | exited (0) | creates tables from `db/init/`, upserts `meter_master` |
| airflow-init | exited (0) | migrates the Airflow DB, creates the admin user |
| airflow-webserver | healthy | http://localhost:8080 (user and password from `.env`) |
| airflow-scheduler | healthy | |
| streamlit | healthy | http://localhost:8501 (placeholder page with meter counts) |

If `make.ps1 up` ran before `generate`, load the meter master afterwards with `make.ps1 seed` (safe to repeat).

### Other targets
| Target | Does |
| --- | --- |
| `make.ps1 down` | stop the stack, keep the database volume |
| `make.ps1 reset` | stop and **delete** the database and log volumes (`data/` is kept) |
| `make.ps1 logs [service]` | last 200 log lines, e.g. `make.ps1 logs airflow-scheduler` |
| `make.ps1 seed` | re-run table creation and the meter master upsert |
| `make.ps1 run-day 2026-08-14` | run the whole `gridpulse_daily` DAG for one IST day (Airflow backfill) |
| `make.ps1 backfill 2026-08-01 2026-08-21` | the same for a date range, one run at a time |
| `make.ps1 rollback 2026-08-14 [RUN_ID]` | restore that day's gold from the archive of the latest (or given) run and republish; the replaced version is kept as `rolled_back__<run>` |

### Integration tests (stack must be up)
```
.venv\Scripts\python -m pytest -m integration tests/integration
```

### Airflow and our code
Airflow keeps its own Python. GridPulse is installed in a separate virtualenv inside the Airflow image
(`/opt/gridpulse-venv`), and DAG tasks call `/opt/gridpulse-venv/bin/python -m gridpulse.cli <step> --ds {{ ds }}`.
`src/` is mounted into the containers, so code changes apply without a rebuild.

### Airflow schedule
`gridpulse_daily` is scheduled daily at 00:00 UTC (05:30 IST; Airflow's `ds` is then the IST day) but stays
**paused** by default, because the demo data is dated August 2026. Run it with `make.ps1 run-day` and
`backfill`, which work on a paused DAG. Do not unpause it for the demo data. Every task writes a row to
the PostgreSQL table `pipeline_runs`.
