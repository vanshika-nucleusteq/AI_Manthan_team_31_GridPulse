# GridPulse handoff (after P8)

Status on `main` (`50a2349`, pushed): P0 to P8 done, `make.ps1 check` green with 100 unit tests.
Full step-by-step history: `docs/claude-journal.md` (one entry per step, with corrections). Rules: `CLAUDE.md`.
How to run: `README.md`.

## What was done

| Step | Result | Key evidence |
| --- | --- | --- |
| P0 Bootstrap | Repo layout, CLAUDE.md filled, plan split into `docs/plan-*.md`, make.ps1 + Makefile, CI, `/step` skill, prompt pack `docs/prompts/` | CI: ruff, black, pytest, compose config |
| P1 Generator | Seeded, vectorised generator with every injected problem and `answer_key.json` | Same seed gives byte-identical files; 14 days in ~100 s |
| P2 UI wireframe | `docs/ui/wireframe.html` (5 pages), screenshots in `docs/ui/screens/`, `docs/ui-design.md` | 14/14 charts have metric tooltips; IST on time axes |
| P3 Stack | Docker Compose: PostgreSQL 16, Airflow 2.10 (LocalExecutor), Streamlit placeholder, init job | Clean start from empty volumes healthy in ~145 s |
| P4 Ingest + quality | Landing to bronze (schema v1/v2 detection), 8 quality rules to quarantine | Bronze rows = answer key; quarantine counts match exactly |
| P5 Normalise | Silver readings (kWh, dedup, ordering, consumption, rollover) and gaps with cause | 16/16 answer-key checks; consumption sum = register difference |
| P6 Gold + publish | 8 gold tables incl. billing (READY/REVIEW), archive on overwrite, publish to PostgreSQL in one transaction, reconciliation CLI | Silver = gold zone = gold meter = gold hourly, difference 0 every day |
| P7 Anomalies | Spike, tamper, outage checks, `anomalies` table, evaluation CLI | 21-day data: spike 10/10, tamper 3/3, outage 1/1; 580 spike false positives |
| P8 Orchestration | `gridpulse_daily` DAG (9 tasks), `pipeline_runs` logging, compaction, retention, run-day / backfill / rollback | Airflow run 9/9 tasks in 74 s; rollback restored 9 partitions in 11 s |

## Decisions made (and where they are recorded)

- **Stack:** files (no Kafka), DuckDB on Parquet, Airflow 2.10, PostgreSQL 16, **Streamlit instead of Superset** (deviation from card must-have 7; needs the mentor's nod; LLD note).
- **Airflow isolation:** GridPulse runs in its own venv `/opt/gridpulse-venv` inside the Airflow image; DAG calls `python -m gridpulse.cli <step> --ds {{ ds }}` and imports nothing from `gridpulse` (CLAUDE.md, `docs/lld.md`).
- **Units and time:** kWh DECIMAL(18,6); store UTC; IST days, hours, months; see the "UTC vs IST pitfalls" table in `docs/lld.md`.
- **Completeness flag:** `quality_flag = NOT (completeness_pct > 90)` (card wording).
- **Hourly per feeder and zone** gold tables added (card must-have 3; not in the plan's gold list).
- **Quality rules:** 8 rules, first failure wins, order in `config/quality.yaml`; quarantine is the dead-letter destination.
- **Late data:** daily run reprocesses a 3-day lookback; backfill reads arrivals up to ds + 4 days; files later than that need a wider backfill (ADR 0001 to be written).
- **Writes:** partition overwrite via temp folder + swap with retries; gold replaced partitions go to `_archive/<table>/run_id=` for rollback; PostgreSQL delete-then-insert per date in one transaction.
- **Go-live clamp:** `go_live_date: 2026-08-01`; no window reaches earlier (otherwise every feeder looks like an outage).
- **DAG schedule:** `schedule: null` and paused at creation, because the demo data is dated Aug 2026 (see incident below). Use `make.ps1 run-day` and `backfill`.
- **Demo dataset:** `data/` is now the **21-day** dataset (seed 42), processed and published for 1 to 21 Aug.

## Incident during P8 (for the RCA and runbook)

A DAG left unpaused (P3 setting) ran for the wall-clock date 2026-11-26; retention applied the 30-day rule from November and deleted the August landing, bronze and quarantine of the 14-day data. Fixes: ingest fails when the landing folder is missing; DAG unscheduled and paused by default. Recovery: broken folder kept as `data-broken-14d/` (git-ignored, delete when no longer needed), 21-day data became `data/`, PostgreSQL republished. Details: journal entry 9.

## Files changed (main areas)

- `src/gridpulse/`: `generator/`, `ingest/`, `quality/`, `normalise/`, `aggregate/` (incl. `reconcile.py`), `anomalies/` (incl. `evaluate.py`), `publish/`, `maintenance/` (compact, retention, rollback), `common/` (config, lake, db, runlog), `cli.py`
- `config/`: `pipeline.yaml`, `quality.yaml`, `anomalies.yaml`, `aggregate.yaml`, `generator.yaml`
- `db/init/`: `010_meter_master.sql`, `020_gold.sql`, `030_anomalies.sql`, `040_pipeline_runs.sql`
- `dags/gridpulse_daily.py`, `deploy/` (compose, Dockerfiles), `scripts/make.ps1`, `Makefile`, `.github/workflows/ci.yml`
- `docs/`: `lld.md` (Airflow isolation, UTC vs IST), `ui-design.md`, `ui/`, `prompts/`, `plan-*.md`, `claude-journal.md`
- `tests/unit/` (9 files, 100 tests), `tests/integration/` (stack and publish)

## What's next

1. **Decision pending (team):** spike guard `kWh >= 2x baseline mean` on top of z >= 4. Measured on 21 days: keeps 10/10 true spikes, false positives 580 to 0. Without it the Anomalies page is dominated by false positives.
2. **P9 QA: done.** All 26 plan test names exist; 106 unit tests pass; `docs/test-plan.md` (Test Cases table, boundary table) and `docs/test-results.md` (hit table, reconciliation, drill results, defect log DEF-01..11, DEF-08 open = spike guard).
3. **P10 SRE:** `metrics` task (still a TODO in the DAG), `ops_alerts`, completeness alert, `docs/runbook.md`; the P8 incident is ready-made material.
4. **P11 UI:** Streamlit pages from `docs/ui-design.md`; default date range 1 to 21 Aug; user will guide the design.
5. **ADRs:** `docs/adr/0001-late-data.md`, `0002-storage-layout.md` are still stubs.
6. **P12/P13:** slides outline and demo script; sprint status.

## Resume checklist

- `make.ps1 up` (stack), DAG stays paused; `make.ps1 run-day 2026-08-21` reruns one day.
- `python -m gridpulse.aggregate.reconcile --from 2026-08-01 --to 2026-08-21` and `python -m gridpulse.anomalies.evaluate` re-prove the numbers.
- `docs/chat-export.md` is a raw transcript, left untracked on purpose.
