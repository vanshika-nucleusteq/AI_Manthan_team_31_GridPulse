# CLAUDE.md — AI Manthan, Wave 2, Track B (team 31, GridPulse)

## Project
Problem: A power distribution utility collects 15-minute readings from 5,000 smart meters (20 feeders, 6 zones) through field gateways. Data arrives late, duplicated and in two schema versions, so billing disputes are common and tampering or outages are found only after complaints. We build a batch platform that ingests meter telemetry, normalises it, produces billing-ready consumption and flags anomalies.
Consumers: billing analyst, network operations engineer, revenue-protection team.
Must-haves (numbered, from the card, `docs/card.md`):
1. Ingestion of both schema versions with raw data preserved and a record of which version each event used.
2. A normalisation layer that converts units to kWh, removes duplicates, orders events, and marks missing intervals as gaps instead of silently filling them.
3. A consumption layer: hourly and daily kWh per meter, per feeder and per zone, and a monthly billing-ready table per meter.
4. Anomaly detection with three checks: spike (z-score against the meter's own history), suspected tamper (zero consumption for 48 hours while neighbours on the same feeder are normal), and outage (many meters on one feeder missing readings at the same time).
5. A storage layout designed for time-series access: date and zone partitioning, a file compaction approach and a retention rule (raw 30 days, hourly 13 months), with the reason for each choice written in an ADR.
6. Orchestrated daily runs with retry and a backfill option for a date range.
7. A dashboard with feeder consumption, anomaly list, data completeness percentage per zone and a pipeline-health tab (the card names Superset; we use Streamlit, see Stack).

Data quality rules (failures go to `quarantine/` with `rule` and `reason`; quarantine is our dead-letter destination):
- Meter ID exists in `meter_master`, else `UNKNOWN_METER`.
- Energy reading not negative, else `NEGATIVE_READING`.
- Cumulative register never decreases unless status is `ROLLOVER`, else `REGISTER_DECREASED`.
- Unparseable timestamp or one off the 15-minute grid by more than `timestamp_tolerance_seconds`: `BAD_TIMESTAMP`.
- Completeness must be above 90%, otherwise a quality flag: `quality_flag = NOT (completeness_pct > completeness_flag_pct)` with `completeness_flag_pct: 90` in `config/quality.yaml`. Applies to meter-days and to feeder and zone aggregates. Exactly 90% is flagged; it cannot occur for a full meter-day (86.4 of 96 intervals), but the rule is written this way.

Design source of truth: `docs/gridpulse-plan.md`, split into `docs/plan-*.md` for @-mentions.

## Stack (open-source only)
- Ingestion: JSONL.gz files landed per gateway per hour (the card allows files or Kafka; we use no Kafka).
- Compute: DuckDB inside Python tasks, on Parquet (medallion lake under `data/lake/`).
- Orchestration: Apache Airflow 2.10 (LocalExecutor), one DAG `gridpulse_daily`.
- Serving DB: PostgreSQL 16 (gold copies and Airflow metadata).
- Dashboard: Streamlit (team decision; the card names Superset. This is a deviation: record it in an LLD note and get the mentor's nod).
- Docker Compose (`deploy/`), GitHub Actions CI (remote: GitHub `AI_Manthan_team_31_GridPulse`).
- Airflow isolation (decision): Airflow 2.10 pins old SQLAlchemy, pandas and numpy; we do not downgrade our package to its pins. The Airflow image (P3) gets a separate virtualenv at `/opt/gridpulse-venv` with our package installed. The DAG runs each task with a BashOperator calling `/opt/gridpulse-venv/bin/python -m gridpulse.cli <step> --ds {{ ds }}`. Airflow's own Python only parses the DAG file, which must import nothing from `gridpulse`.

## Hard rules
- Synthetic data only. Never generate real or realistic personal or card data; use tokens and fake IDs.
- No secrets in the repo. Config via `.env` (git-ignored) and `.env.example` with dummy values.
- Plan first: for any task bigger than one file, propose a numbered plan and wait for approval.
- One task per session. Small changes; one commit per change; prefixes feat, fix, test, docs, ci, chore.
- Every must-have gets a test. Test names state the rule and the result, e.g. `test_velocity_rule_fires_on_sixth_txn_in_minute`.
- Writes to the database are idempotent upserts keyed on a natural key. Replaying input must not duplicate rows.
- Bad records never crash the pipeline: they go to a dead-letter destination with a reason.
- Thresholds and rule settings live in config (YAML or a table), never hard-coded.
- If unsure about a requirement, ask; do not invent scope.

## Unit rules
- All energy is stored in kWh as DECIMAL(18,6). Nothing after bronze stores Wh.
- Conversion: kWh = Wh / 1000, exact decimal division with no float rounding before storage.
- Never mix units in one column. An energy column without a unit suffix holds kWh.
- Unit source: v1 is always Wh; v2 uses the `unit` field, falling back to `meter_master.reporting_unit` if it is missing.

## Time rules
- Store every timestamp in UTC as a timezone-aware value (`TIMESTAMPTZ`, tz-aware pandas, `datetime` with `tzinfo`). Never use naive datetimes.
- Readings map to 15-minute intervals aligned to :00/:15/:30/:45 (`interval_start`, UTC): 96 intervals per meter per day.
- Daily, monthly and billing boundaries are in Asia/Kolkata (IST, UTC+05:30): a local day runs from 18:30 UTC to 18:30 UTC. `local_date`, `hour_start` (IST) and `month` are derived in IST.
- Dashboards state IST on time axes.

## Data rules
- Never fill gaps silently. Missing intervals go to `silver/gaps`; the next reading carries `spans_gap` and `intervals_spanned`, and its consumption is never spread across the gap.
- Raw data is immutable. `landing/` files are never edited, and bronze keeps `raw_json`.
- Every write is idempotent: partition overwrite in the lake; in PostgreSQL, delete-then-insert per date in one transaction, or a keyed upsert. Rerunning a date gives identical output.
- Daily runs reprocess a 3-day lookback (`lookback_days`); later data needs an explicit backfill (ADR 0001).
- Billing uses the rollover-adjusted register difference, reconciled against the sum of intervals; a mismatch sets `REVIEW`.

## Repo layout
```
CLAUDE.md, README.md, Makefile, scripts/make.ps1, pyproject.toml, .env.example
.claude/skills/            team skills (do not modify)
.github/workflows/ci.yml   lint + unit tests
config/                    pipeline.yaml, quality.yaml, anomalies.yaml
src/gridpulse/
  cli.py                   python -m gridpulse.cli <step> --ds YYYY-MM-DD (one step per DAG task)
  common/                  config, paths, time (UTC/IST), units, db, run logging
  generator/               meter_master, readings, scenarios, answer_key
  ingest/                  landing -> bronze, schema detection
  quality/                 rules -> quarantine
  normalise/               kWh, dedup, order, consumption, gaps
  aggregate/               hourly, daily, billing, completeness
  anomalies/               spike, tamper, outage
  publish/                 gold -> PostgreSQL, archive for rollback
  maintenance/             compaction, retention, rollback, backfill helper
dags/gridpulse_daily.py
db/init/                   PostgreSQL schema for gold and ops tables
app/                       Streamlit: Home.py + pages/
deploy/                    docker-compose.yml, Dockerfile.airflow
tests/unit/, tests/integration/
data/                      git-ignored: landing, lake, answer_key.json
docs/                      artifacts, adr/, plan-*.md, claude-journal.md
```

## Message / data schema
Events are JSON lines in `data/landing/arrival_date=YYYY-MM-DD/feeder=Fxx/<file>.jsonl.gz`. Readings are cumulative registers.

Schema v1:

| Field | Type | Allowed values / notes |
| --- | --- | --- |
| meter_id | string | `MTR-00001` to `MTR-05000`; must exist in meter master |
| ts | string, ISO-8601 UTC | should sit on a 15-minute boundary |
| energy_wh | number | cumulative register in Wh, ≥ 0 |
| status | string | `OK`, `ROLLOVER`, `ERROR` |

Schema v2:

| Field | Type | Allowed values / notes |
| --- | --- | --- |
| meter_id | string | as v1 |
| ts | string, ISO-8601 UTC | as v1 |
| energy | number | cumulative register, ≥ 0 |
| unit | string | `Wh` or `kWh` (assumption, to confirm with the mentor); missing means `meter_master.reporting_unit` |
| status | string | `OK`, `ROLLOVER`, `ERROR` |
| voltage | number, nullable | volts |
| firmware_version | string | e.g. `2.4.1` |

Detection: an explicit `schema_version` field wins; otherwise the presence of `voltage` or `firmware_version` means v2. Every bronze row keeps `schema_version`, `source_file`, `ingested_at` and `raw_json`.
Natural key after normalisation: (`meter_id`, `interval_start`).
Meter master (`meter_master`): meter_id, feeder_id (`F01`–`F20`, 250 meters each), zone_id (`Z1`–`Z6`, 3 or 4 feeders each), meter_type (`residential` or `commercial`), reporting_unit, register_max_kwh, install_date.

## Commands
Windows (no make): `powershell -ExecutionPolicy Bypass -File scripts/make.ps1 <target>`. Linux, macOS and CI: `make <target>`.

| Target | Does |
| --- | --- |
| venv | create `.venv` with Python 3.12 and run `pip install -e ".[dev]"` |
| lint | `ruff check .` and `black --check .` |
| test | `pytest -q` (unit tests) |
| check | lint + test; run before every commit |
| generate | synthetic data (built in P1) |
| up / down / reset / logs | Docker Compose stack (built in P3) |
| run-day DATE / backfill START END / rollback DATE | Airflow runs (built in P8) |

## Style
Python: Black + Ruff, snake_case, type hints. SQL: snake_case, explicit column lists. No commented-out code.

## Skills in this repo
/kickoff-card · /adr · /claude-journal · /data-tests · /stack-deploy · /sre-drill
