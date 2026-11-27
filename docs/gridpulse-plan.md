# GridPulse Build Plan

Nov 27, 2026 · @Tulika

Today's card is GridPulse: smart-meter telemetry, a batch platform rather than a stream. One laptop drives the code in a git repo while the rest of the team builds the artifacts in parallel; the sprint sheet (Excel) tracks both. UI design starts in hour one, not at the end.

## 0. Start here

Do these on the driving laptop before pasting the prompt. Team repo: https://github.com/vanshika-nucleusteq/AI\_Manthan\_team\_31\_GridPulse (clone with `git clone https://github.com/vanshika-nucleusteq/AI_Manthan_team_31_GridPulse.git`, then `cd AI_Manthan_team_31_GridPulse`). Then:

1. Copy the kit's `CLAUDE.md` and `.claude/` folder into the repo root (mentor OK first, as it is a process asset, not code). Do not copy anything from the StreamGuard practice project.
2. Save today's card as `docs/card.md` (paste the card text) and this plan as `docs/gridpulse-plan.md` (doc menu → Export → Markdown).
3. Open the repo folder in VS Code, open Claude Code, switch to plan mode, paste:

```text
This session is repo bootstrap only. No pipeline logic yet.

ROLE
Act as our tech lead and senior data platform architect for a 4.5-hour, Track B hackathon build. We work in this git
repo on one laptop; teammates write artifacts in parallel.

CONTEXT
- @CLAUDE.md: team rules. Keep every existing rule.
- @docs/card.md: the use case card (GridPulse, smart meter telemetry). Source of truth for scope.
- @docs/gridpulse-plan.md: our agreed build plan. Source of truth for design.
- .claude/skills/: our six team skills. Do not modify them.
- Laptop: Windows, Python 3.12, Docker + Compose installed, no make.

TASKS
1. Split the plan into files later prompts will @-mention (keep the original):
   docs/plan-architecture.md (sections 1-2), plan-data.md (3), plan-storage.md (4),
   plan-model-logic.md (5), plan-ui.md (6), plan-tests-sre.md (10).
2. Fill CLAUDE.md:
   - Project: problem, consumers, the 7 must-haves from the card, data quality rules.
   - Stack: Airflow 2.10 (LocalExecutor), DuckDB on Parquet, PostgreSQL 16, Streamlit (team decision; card names Superset),
     Docker Compose, GitHub Actions (remote is GitHub: AI_Manthan_team_31_GridPulse).
   - Unit rules: all energy stored in kWh as DECIMAL; Wh / 1000; never mix units in a column.
   - Time rules: store UTC; 15-minute intervals aligned to :00/:15/:30/:45; daily, monthly and
     billing boundaries in Asia/Kolkata; never use naive datetimes.
   - Data rules: never fill gaps silently; raw data is immutable; every write is idempotent
     (partition overwrite or keyed upsert).
   - Schema v1 and v2 field tables from plan section 3.
   - Commands: scripts/make.ps1 targets (and Makefile equivalents).
3. Scaffold the repo layout from plan section 7 with placeholders only (one-line docstrings),
   config/*.yaml copied from the plan, data/ git-ignored, .env.example with dummy values,
   pyproject.toml (duckdb, pyarrow, pandas, numpy, pydantic, PyYAML, psycopg[binary],
   SQLAlchemy, orjson; dev: pytest, ruff, black; requires-python >=3.11, target py311),
   Makefile + scripts/make.ps1 with: venv, check, test, lint, up, down, reset, generate,
   run-day, backfill, logs. Targets not yet buildable print "TODO: built in P<n>".
4. Artifact stubs with headings only, one per deliverable: docs/ideation.md, docs/lld.md,
   docs/test-plan.md, docs/test-results.md, docs/ui-design.md, docs/runbook.md,
   docs/demo-script.md, docs/adr/0001-late-data.md, docs/adr/0002-storage-layout.md.
   Keep docs/claude-journal.md.
5. CI skeleton: lint + unit tests on push and PR. tests/unit/test_smoke.py imports the package.
6. Verify and show output: venv with py -3.12, pip install -e ".[dev]", tree (no .venv/data),
   ruff, black --check, pytest -q, YAML parse of every config file, docker compose version.

CONSTRAINTS
- Plan first: list every file and command, then wait for approval.
- Before planning, list gaps or contradictions between card and plan as numbered questions
  with your suggested answer each.
- No generator, SQL, DAG, Compose or Streamlit content yet (P1-P9 build those).
- Synthetic data only.

OUTPUT
1. Summary of what was created and anything that failed.
2. Proposed commit: "chore: scaffold GridPulse repo from plan". Commit only when I say so.
3. Run /claude-journal for this session, then stop.
```

## 1. Architecture

A batch medallion pipeline on one laptop, started by `make.ps1 up`: four containers (PostgreSQL, Airflow webserver and scheduler, Streamlit) plus a one-shot init. Every task reads and overwrites whole date partitions, which is what makes reruns, late data and backfill safe.

&#91;embedded content: GridPulse architecture · 6 components, 8 DAG tasks\]

The generator plays the field gateways, and its answer key is the team's ground truth for every check. Commit this picture to `docs/lld.md` (Claude Code can redraw it in Mermaid) as the architecture artifact.

## 2. Key decisions

The card asks for two ADRs by name: late data and storage layout. The rest are short LLD notes. Run /adr on each so the trade-offs come from Claude and the decision from the team.

| # | Decision | Our choice | Why | Trade-off we accept |
| --- | --- | --- | --- | --- |
| ADR 0001 | Late data | Each daily run reprocesses a 3-day lookback window (D-2 to D) by overwriting those date partitions; anything later goes through backfill | Late and duplicate gateway files are the card's core pain; partition overwrite is idempotent, so re-running never double-counts | Slightly more compute per run; data arriving after 3 days waits for an explicit backfill |
| ADR 0002 | Storage layout | Parquet in a medallion lake (raw, bronze, silver, gold), Hive-partitioned by `date` then `zone`; nightly compaction to one file per partition; retention raw 30 days, hourly 13 months | Matches the card's access pattern (a day or month, one zone or feeder) and makes retention a folder delete | Feeder queries scan a whole zone partition; fine at 5,000 meters |
| Note | Ingestion mode | Landed JSONL.gz files, one per gateway per hour | Batch daily runs, easy backfill by date, files are the natural raw archive | No real-time view; the card does not ask for one |
| Note | Compute | DuckDB in Python tasks | Reads JSON and Parquet natively, fast on one laptop, plain SQL is testable | Single-node only |
| Note | Serving | Gold tables published to PostgreSQL for Streamlit | Simple cached SQL reads from the app; small tables | One extra copy of gold data |
| Note | Orchestrator | Apache Airflow 2.10, LocalExecutor, one DAG `gridpulse_daily` | Retries and date-range backfill are built in, which the card asks for | Heaviest container in the stack (about 2 GB) |
| Note | Dashboard | Streamlit (team decision) | Team knows Python; pages are code, so they are versioned, reviewed and testable | The card names Superset for must-have 7: record the switch in an LLD note and say it in the demo |

Tell the mentor once at kick-off: "We read the card as allowing files rather than Kafka, and DuckDB as the compute engine, and we are using Streamlit instead of Superset." The first two fit the card's "team's choice" wording; the Streamlit switch is a deviation, so get the mentor's nod.

## 3. Sources, schemas and the generator

The readings are cumulative register values (the card's "register never decreases" rule implies it), so interval consumption is the difference between consecutive readings for a meter.

| Field | v1 | v2 | Notes |
| --- | --- | --- | --- |
| meter\_id | ✓ | ✓ | `MTR-00001` to `MTR-05000`; must exist in meter master |
| ts | ✓ | ✓ | ISO-8601 UTC, should sit on a 15-minute boundary |
| energy\_wh | ✓ | – | Cumulative register in Wh |
| energy + unit | – | ✓ | Cumulative register; unit `Wh` or `kWh` (assumption, see below) |
| status | ✓ | ✓ | `OK`, `ROLLOVER` (register wrapped), `ERROR` |
| voltage | – | ✓ | Volts, nullable |
| firmware\_version | – | ✓ | For example `2.4.1` |

Schema detection: an explicit `schema_version` field wins; otherwise the presence of `voltage` or `firmware_version` means v2. Every bronze row keeps `schema_version`, `source_file` and `ingested_at`, which is must-have 1.

Assumption to confirm with the mentor: the card says some v2 meters report in kWh but names no unit field. We generate a `unit` field; if it is missing, we fall back to `reporting_unit` in the meter master.

Meter master (`meter_master`, seeded): meter\_id, feeder\_id (`F01`–`F20`, 250 meters each), zone\_id (`Z1`–`Z6`, 3 or 4 feeders each), meter\_type (residential or commercial), reporting\_unit, register\_max\_kwh, install\_date.

The generator (`make generate`) writes JSONL.gz files to `data/landing/arrival_date=YYYY-MM-DD/feeder=Fxx/<file>.jsonl.gz` (folders are by arrival date, so a late file holds readings from an earlier day, exactly like a slow gateway) and, alongside, `data/answer_key.json` listing every injected problem. That file is how the team proves each anomaly and quality check, as the card asks.

| Injected on purpose | Rate or count | Proves |
| --- | --- | --- |
| Schema v2 rollout | 40% of meters switch from day 45 | Must-have 1 |
| kWh-reporting meters | 15% of v2 meters | Unit conversion |
| Duplicate readings | 2% (exact) plus 0.2% (same key, different value) | Dedup and conflict flag |
| Late files | 3% of files land 1–2 days late | ADR 0001 lookback |
| Missing intervals | 1% random, plus one meter missing half a day | Gap marking and completeness flag |
| Spikes | 10 meters, one hour at 6–10× normal | Spike check |
| Tamper | 3 meters reading zero for 60 hours, feeder normal | Tamper check |
| Feeder outage | F07, 2 hours, 80% of meters silent | Outage check |
| Unknown meter IDs | 0.1% | Meter master rule |
| Negative or decreasing register | 20 readings each | Quality rules |
| Rollovers | 5 meters wrap with status ROLLOVER | Allowed decrease |

Scale: the card's full size is 5,000 meters × 96 readings × 90 days, about 43 million readings. Develop on `--days 14` (6.7 million), then run the full 90 days once in the background for the performance story. Generation must be vectorised (NumPy, orjson) and seeded, so every run produces the same answer key.

## 4. Storage layout

All layers live under `data/lake/` on a Docker volume shared by Airflow and the scripts. Every layer except raw is written by overwriting whole partitions, so a rerun or backfill replaces data instead of adding to it.

| Layer | Path and partitioning | Contents | Written by | Retention |
| --- | --- | --- | --- | --- |
| Raw | `landing/arrival_date=/feeder=/` | Gateway files exactly as received | Generator (stands in for gateways) | 30 days, then deleted |
| Bronze | `bronze/arrival_date=/` | One row per message: parsed fields, `raw_json`, `schema_version`, `source_file`, `ingested_at` | `ingest` | 30 days |
| Quarantine | `quarantine/date=/` | Rows failing a quality rule, with `rule` and `reason` | `quality` | 30 days |
| Silver | `silver/readings/date=/zone=/` | Normalised readings: kWh, UTC 15-minute interval, deduplicated, ordered, interval consumption, flags | `normalise` | 13 months |
| Silver | `silver/gaps/date=/zone=/` | One row per missing meter interval | `normalise` | 13 months |
| Gold | `gold/<table>/date=/zone=/` (monthly tables by `month=`) | Hourly, daily, billing, completeness, anomalies | `aggregate`, `anomalies` | Hourly 13 months; daily and monthly kept |
| Archive | `_archive/<table>/run_id=/` | The previous version of each overwritten gold partition | `publish` | 7 days; enables rollback |

Compaction: ingest writes many small files (one per gateway file). The nightly `compact` task rewrites each touched silver and gold partition into a single Parquet file of roughly 64–128 MB, sorted by `meter_id, interval_start` so DuckDB can skip row groups. Record file counts before and after: that is the ADR's evidence.

Retention: a `retention` task deletes `arrival_date` folders older than 30 days in raw and bronze, and `date` folders older than 13 months in hourly gold, and deletes the same range from the PostgreSQL copies. It logs what it deleted to `pipeline_runs`.

## 5. Data model and logic

### Normalisation, in order

1. Parse, detect schema version, convert to kWh (Wh ÷ 1000).
2. Quality rules; failures go to quarantine with a reason: `UNKNOWN_METER`, `NEGATIVE_READING`, `REGISTER_DECREASED` (lower than the previous reading and status is not `ROLLOVER`), `BAD_TIMESTAMP`.
3. Deduplicate on (meter\_id, interval\_start): exact copies are dropped and counted; same key with a different value keeps the latest `ingested_at` and sets `dup_conflict`.
4. Order by meter and interval, then interval consumption = register − previous register (on rollover: register\_max − previous + register).
5. Gaps: build the expected grid of 96 intervals per meter per day, anti-join the readings, write each missing interval to `silver/gaps`. The reading after a gap carries `spans_gap = true` and `intervals_spanned`; its consumption is never spread over the missing intervals.

### Gold tables (Parquet, also published to PostgreSQL)

| Table | Key | Main columns |
| --- | --- | --- |
| `consumption_hourly` | meter\_id, hour\_start (IST) | kwh, intervals\_present, has\_gap |
| `consumption_daily_meter` | meter\_id, local\_date | kwh, intervals\_present, completeness\_pct, quality\_flag (completeness < 90%) |
| `consumption_daily_feeder` | feeder\_id, local\_date | kwh, meters\_reporting, completeness\_pct |
| `consumption_daily_zone` | zone\_id, local\_date | kwh, meters\_reporting, completeness\_pct |
| `billing_monthly` | meter\_id, month | kwh (register at month end − at month start, rollover-adjusted), sum\_of\_intervals\_kwh, days\_flagged, billing\_status (`READY` or `REVIEW`) |
| `anomalies` | anomaly\_id = hash(type, entity, window\_start) | type, meter\_id or feeder\_id, window\_start, window\_end, score, details JSON |
| `data_quality_daily` | local\_date, rule | failures, sample\_meter\_ids |
| `pipeline_runs` | run\_id, task | ds, rows\_in, rows\_out, duplicates, duration\_s, status |
| `ops_alerts` | alert\_name, fired\_at | value, threshold, message |

Billing uses register difference, not the sum of intervals, so a gap never under-bills; the two are compared as a reconciliation check and a mismatch sets `REVIEW`. That directly answers the card's "billing disputes" pain.

### Anomaly checks

| Check | Flags when | Guard against false alarms |
| --- | --- | --- |
| Spike | Hourly kWh z-score ≥ 4 against the same meter's same hour-of-day over the trailing 28 days | Needs at least 14 baseline samples; hours with `has_gap` are skipped |
| Suspected tamper | Meter reports (completeness ≥ 90%) but consumption is 0 for ≥ 48 consecutive hours, while ≥ 80% of other meters on its feeder are non-zero in the same window | Zeros are readings, not gaps, so outages never look like tamper |
| Outage | ≥ 50% of a feeder's meters have a gap in the same interval, for ≥ 2 consecutive intervals; consecutive intervals merge into one event | Single-meter gaps never trigger it |

```yaml
# config/anomalies.yaml
spike:   {z_threshold: 4.0, baseline_days: 28, min_samples: 14}
tamper:  {zero_hours: 48, min_completeness_pct: 90, feeder_normal_share: 0.8}
outage:  {feeder_missing_share: 0.5, min_consecutive_intervals: 2}
# config/quality.yaml
completeness_flag_pct: 90
lookback_days: 3
timestamp_tolerance_seconds: 60
```

## 6. UI design

The UI owner designs the dashboard from minute 20, before any data exists, so the gold tables are built to feed it, not the other way round. Hour one ends with a wireframe (prompt P2 makes a static HTML mockup with fake numbers; screenshot it) and the metric definitions below; both go into `docs/ui-design.md` as the UI design artifact. The Streamlit app is built to match once gold data lands.

Dashboard "GridPulse · Network Operations", a multi-page Streamlit app (one page per tab below, port 8501) with sidebar filters for date range, zone and feeder on every page:

| Tab | Charts | Answers the question |
| --- | --- | --- |
| Overview | KPI tiles (yesterday's kWh, meters reporting %, open anomalies, zones under 90%); feeder consumption bar for the selected day; daily kWh line per zone, last 30 days | "Is the network normal today?" |
| Completeness | Zone × day heatmap of completeness %; table of meter-days flagged under 90% | "Where is data missing, and is it a field or a pipeline problem?" |
| Anomalies | Anomaly list (type, meter or feeder, window, score), anomalies per day by type, outage events on a feeder timeline | "What should revenue protection and network ops look at first?" |
| Billing | Monthly billing table with READY or REVIEW, count of REVIEW by reason | "Which bills are safe to send?" |
| Pipeline health | Run duration per task, ingest lag, duplicate rate, quarantine rows by rule, fired ops alerts | "Can we trust today's numbers?" |

Metric definitions (also shown as the help tooltip on each chart):

| Metric | Definition | Source |
| --- | --- | --- |
| Consumption (kWh) | Sum of interval consumption for the period; readings spanning a gap count in the interval they arrive | `consumption_daily_*` |
| Completeness % | Intervals received ÷ intervals expected (96 per meter per day) × 100 | `consumption_daily_*` |
| Meters reporting % | Meters with at least one reading that day ÷ active meters in master | `consumption_daily_zone` |
| Open anomalies | Anomalies in the selected window, by type | `anomalies` |
| Duplicate rate | Duplicates dropped ÷ readings received, per run | `pipeline_runs` |
| Ingest lag | Run start time − latest `ingested_at` in bronze for that run | `pipeline_runs` |
| Run duration | End − start of each task in the latest run | `pipeline_runs` |

Design rules for points: units in every axis title, IST stated on time axes, a colour-blind-safe palette with red used only for alerts, and an explanatory empty state ("No anomalies in this window") rather than a blank chart. The answer key gives known counts, so the team checks each chart's number against it before the demo, as the card asks.

## 7. Team, git and artifacts

One laptop drives the code; everyone else works on artifacts on their own laptops and reviews on the big screen at each checkpoint. Teammates can open Airflow (port 8080) and Streamlit (port 8501) from their laptops at `http://<driver-laptop-ip>:<port>` if the venue network allows.

| Role | Does | Owns these artifacts |
| --- | --- | --- |
| Driver (tech lead) | Runs Claude Code, reviews every plan before approving, merges | Code base, README |
| Navigator (data engineer) | Reads plans and diffs with the driver, checks outputs against the answer key, writes the next prompt | LLD, ADRs |
| UI owner | Wireframe from 0:20, metric definitions, builds the Streamlit pages from about 2:00 | UI designs |
| QA | Test plan, test cases in the sheet, reviews generated tests, adds boundary cases, defect log | Test plan, test results |
| SRE | Metrics and alert design, runbook; runs the backfill and rollback commands once while writing it | Runbook |
| Scrum and story lead | Sprint sheet, stories and status every 30 minutes, ideation doc, presentation, demo recording | Stories (Excel), ideation, presentation, demo |

With five people, the navigator also takes SRE.

Git flow on one laptop: one short branch per prompt (`p3-normalise`), commit after each verified step with `feat:`, `fix:`, `test:`, `docs:` prefixes, run `make check`, merge to `main`, push. Artifacts written elsewhere are copied into `docs/` by the driver at 2:00 and 4:00. The code-submission note you mentioned was not in your message: check it now, in case it changes the repo name or the branch to submit.

```text
AI_Manthan_team_31_GridPulse/
├── CLAUDE.md, README.md, Makefile, scripts/make.ps1, pyproject.toml, .env.example
├── .claude/skills/                 # team skills
├── .github/workflows/ci.yml        # lint + unit tests
├── config/                         # pipeline.yaml, quality.yaml, anomalies.yaml
├── src/gridpulse/
│   ├── common/                     # config, paths, time (UTC/IST), units, db, run logging
│   ├── generator/                  # meter_master, readings, scenarios, answer_key
│   ├── ingest/                     # landing → bronze, schema detection
│   ├── quality/                    # rules → quarantine
│   ├── normalise/                  # kWh, dedup, order, consumption, gaps
│   ├── aggregate/                  # hourly, daily, billing, completeness
│   ├── anomalies/                  # spike, tamper, outage
│   ├── publish/                    # gold → PostgreSQL, archive for rollback
│   └── maintenance/                # compaction, retention, rollback, backfill helper
├── dags/gridpulse_daily.py
├── db/init/                        # PostgreSQL schema for gold, ops tables
├── app/                            # Streamlit: Home.py + pages/ (one per dashboard tab)
├── deploy/                         # docker-compose.yml, Dockerfile.airflow
├── tests/unit/, tests/integration/
├── data/                           # git-ignored: landing, lake, answer_key.json
└── docs/                           # all ten artifacts (stubs from P0), adr/, plan-*.md, journal
```

| # | Artifact | Owner | Starts | Lives in |
| --- | --- | --- | --- | --- |
| 1 | Presentation | Scrum lead | 3:15 | Slides, plus a copy in `docs/` |
| 2 | Code base | Driver | 0:00 | Repo, README with one-command start |
| 3 | Test plan | QA | 0:30 | `docs/test-plan.md` |
| 4 | Test results | QA | 2:45 | `docs/test-results.md`, sheet tabs Test cases and Defects |
| 5 | UI designs | UI owner | 0:20 | `docs/ui-design.md` with wireframe and Streamlit screenshots |
| 6 | Stories (Excel) | Scrum lead | 0:10 | GridPulse sprint workbook |
| 7 | Application demo | Scrum lead and driver | 4:00 | Screen recording plus `docs/demo-script.md` with screenshots |
| 8 | Ideation document | Scrum lead | 0:15 | `docs/ideation.md` |
| 9 | LLD document | Navigator | 0:40 | `docs/lld.md`, `docs/adr/`, architecture diagram |
| 10 | Runbook | SRE | 2:15 | `docs/runbook.md` |

## 8. The day's clock

Adjust the start once the organisers confirm it. If a block overruns, the driver cuts scope (full 90-day data, compaction, the Billing tab) before touching the tests or the demo.

&#91;embedded content: build-day clock · 7 blocks, code and artifacts in parallel\]

## 9. Prompt pack

Every prompt casts Claude in the role of the teammate who owns that work, so its answers come with that specialist's priorities and checks. The heading of each prompt shows who runs it, when, and which role Claude plays. One fresh session per prompt, plan mode on, one branch per prompt; after each: check against the answer key, `make.ps1 check`, commit, merge, /claude-journal. "Side session" means a teammate's own laptop, not the repo.

| Prompt | Member who runs it | Claude acts as |
| --- | --- | --- |
| P0 | Driver | Tech lead and data platform architect |
| P1 | Driver with Navigator | Senior data engineer, synthetic data |
| P2 | UI owner (side session) | UI/UX designer for data dashboards |
| P3 | Driver | DevOps engineer |
| P4, P5 | Driver with Navigator | Senior data engineer, ingestion and time-series |
| P6 | Driver with Navigator | Analytics engineer, consumption and billing |
| P7 | Driver with Navigator | Data scientist, revenue protection analytics |
| P8 | Driver | Data platform engineer, orchestration |
| P9 | QA | QA and test automation engineer |
| P10 | SRE | Site reliability engineer |
| P11 | Driver with UI owner | Streamlit front-end developer |
| P12 | Navigator (side session) | Solution architect and technical writer |
| P13 | Scrum lead (side session) | Scrum master |

**P1 · Driver · 0:30 · Claude acts as a senior data engineer (synthetic data)**

```text
Act as a senior data engineer who builds realistic synthetic datasets for testing data platforms.
Context: @CLAUDE.md, @docs/card.md, @docs/plan-data.md.
Task: src/gridpulse/generator: seeded, vectorised (NumPy + orjson) generator for meter master and
cumulative-register readings per plan section 3, with every injected problem in the table and
data/answer_key.json listing each one (meter, time window, expected outcome).
CLI: --meters 5000 --days 14 --start 2026-08-01 --seed 42. Folders by arrival_date.
Plan first. Then run it at --days 2 and show file counts, row counts and answer-key totals.
```

**P2 · UI owner · 0:20 · Claude acts as a UI/UX designer (side session)**

```text
Act as a senior UI/UX designer for operational data dashboards used by utility engineers.
Create one static HTML file: a wireframe of a multi-page Streamlit app "GridPulse · Network
Operations" with five pages (Overview, Completeness, Anomalies, Billing, Pipeline health), a
sidebar with filters for date range, zone and feeder, and the charts and metric definitions below
[paste plan section 6]. Plausible fake numbers, units on every axis, IST on time axes, a
colour-blind-safe palette with red only for alerts, an empty state on one chart. Pages must switch.
After the file, list 5 design decisions with the reason for each (for the UI design artifact).
```

**P3 · Driver · 0:45 · Claude acts as a DevOps engineer**

```text
Act as a DevOps engineer who builds reproducible local data stacks.
/stack-deploy Services: PostgreSQL 16 (databases: gridpulse, airflow), Airflow 2.10.x
(LocalExecutor, webserver + scheduler, our src mounted and installed, data/ volume shared),
and a Streamlit service on port 8501 (placeholder page now; real pages come in P11).
Pin every image tag. Healthchecks and depends_on so `scripts/make.ps1 up` works from a fresh
clone. One-shot init: run db/init SQL and seed meter_master. Show docker compose ps when healthy.
```

**P4 · Driver · 1:00 · Claude acts as a senior data engineer (ingestion and quality)**

```text
Act as a senior data engineer who specialises in messy IoT ingestion and data quality.
Context: @CLAUDE.md, @docs/plan-storage.md, @docs/plan-model-logic.md.
Task: src/gridpulse/ingest and quality as DuckDB SQL called from Python functions that take a
processing date. Landing → bronze (schema detection, raw_json, source_file, ingested_at),
then quality rules → quarantine with rule and reason. Partition overwrite only; rerunning a date
must give identical output. Plan first; list edge cases the plan misses before coding.
```

**P5 · Driver · 1:20 · Claude acts as a senior data engineer (time-series)**

```text
Act as a senior data engineer experienced with smart-meter time series.
Task: src/gridpulse/normalise per plan section 5 steps 1-5 over the 3-day lookback window:
kWh conversion, dedup with dup_conflict, ordering, interval consumption with rollover, gap
grid and spans_gap. Write silver/readings and silver/gaps partitioned by date and zone.
Verify against data/answer_key.json: duplicates, gaps and rollovers counts must match.
Call out any place where UTC vs IST could shift a reading into the wrong day.
```

**P6 · Driver · 1:45 · Claude acts as an analytics engineer (consumption and billing)**

```text
Act as an analytics engineer who builds billing-grade aggregates for a utility.
Task: src/gridpulse/aggregate (hourly, daily meter/feeder/zone, completeness, billing_monthly
with register-difference billing and REVIEW rules) and src/gridpulse/publish (copy touched gold
partitions to PostgreSQL by delete-then-insert per date in one transaction; move the previous
Parquet partition to _archive/run_id=). Add a reconciliation query: silver kWh per day equals
gold daily kWh per zone summed. Show the reconciliation result.
```

**P7 · Driver · 2:05 · Claude acts as a data scientist (revenue protection)**

```text
Act as a data scientist on a utility's revenue-protection team, careful about false positives.
Task: src/gridpulse/anomalies: spike, tamper and outage exactly as in plan section 5, thresholds
from config/anomalies.yaml, deterministic anomaly_id. Run on the generated data and show a table:
answer-key anomalies vs detected (hit, miss, false positive) for each check. Explain every miss.
```

**P8 · Driver · 2:25 · Claude acts as a data platform engineer (orchestration)**

```text
Act as a data platform engineer who runs Airflow in production.
Task: dags/gridpulse_daily.py: ingest → quality → normalise → aggregate → anomalies → publish →
compact → retention → metrics, retries=2 with 1-minute delay, one run per ds, max_active_runs=1.
Backfill: scripts/make.ps1 backfill START END runs airflow dags backfill. Compaction and
retention per plan section 4, logging file counts before/after to pipeline_runs. Rollback:
scripts/make.ps1 rollback DATE restores _archive into gold and republishes.
```

**P9 · QA · from 1:00 · Claude acts as a QA and test automation engineer**

```text
Act as a QA and test automation engineer for data pipelines who hunts boundary cases.
/data-tests Target: <unit conversion | gap detection | dedup and out-of-order | each anomaly>.
Use crafted meter histories with fixed timestamps; test names from plan section 10. Then add:
aggregate reconciliation to raw totals, rerun-same-date idempotency, late file inside and
outside the lookback window. Record results in the Test Cases tab format.
```

**P10 · SRE · 2:15 · Claude acts as a site reliability engineer**

```text
Act as a site reliability engineer for data platforms.
/sre-drill Build phase only (no drill this time). pipeline_runs captures ingest lag, completeness
per zone, duplicate rate and run duration. The metrics task writes ops_alerts when any zone's
completeness is under 90% or drops more than 5 points against its 7-day average, and fails the
task. Draft docs/runbook.md: failed task retry, completeness drop, backfill a date range, roll
back a bad run, disk full. Every command copy-pasteable; mark which ones we have verified.
```

**P11 · Driver + UI owner · 2:45 · Claude acts as a Streamlit front-end developer**

```text
Act as a Streamlit front-end developer who cares about usability and accessibility.
Context: @docs/ui-design.md (wireframe and metric definitions), @docs/plan-ui.md.
Task: app/Home.py plus one page per dashboard tab in app/pages/. Read PostgreSQL via SQLAlchemy
(engine in st.cache_resource, queries in st.cache_data with a 60 s ttl), sidebar filters for date
range, zone and feeder shared across pages, metric definitions as chart help tooltips, units and
IST on axes, empty, loading and error states on every chart. Match the wireframe. Replace the P3
placeholder in Compose. Plan first.
```

**P12 · Navigator · 3:15 · Claude acts as a solution architect and technical writer (side session)**

```text
Act as a solution architect and technical writer preparing hackathon deliverables for judges.
From @docs/lld.md, @docs/adr/, @docs/test-results.md and git log, draft: (1) a 10-slide outline:
problem, architecture, two ADRs, data quality, anomalies with answer-key hit rate, Streamlit
dashboard, SRE metrics and alert, Claude usage, security, performance; (2) docs/demo-script.md
for a 5-minute demo with exact commands and what to point at. Mark anything you could not verify.
```

**P13 · Scrum lead · every 30 min · Claude acts as a Scrum master (side session)**

```text
Act as a Scrum master. Here is the Stories tab [paste] and the latest git log [paste].
Propose a status for each story (To do, In progress, Review, Done, Blocked) with one line of
evidence each, flag stories at risk for the current sprint, and suggest what to cut first.
```

## 10. Tests and SRE

Each card testing item maps to named tests, so a judge's "show me" takes seconds. Unit tests run in CI; integration tests need the stack and run locally.

| Card asks for | Tests |
| --- | --- |
| Unit conversion | `test_wh_divided_by_1000`, `test_v2_kwh_unchanged`, `test_missing_unit_falls_back_to_master` |
| Gap detection | `test_missing_interval_written_to_gaps`, `test_gap_never_filled`, `test_reading_after_gap_spans_two_intervals` |
| Duplicates and out-of-order | `test_exact_duplicate_dropped`, `test_conflicting_duplicate_keeps_latest_and_flags`, `test_out_of_order_readings_sorted_before_delta` |
| Quality rules | `test_unknown_meter_quarantined`, `test_negative_reading_quarantined`, `test_register_decrease_quarantined`, `test_rollover_allowed`, `test_day_under_90pct_flagged` |
| Aggregate reconciliation | `test_gold_daily_equals_silver_sum`, `test_billing_register_diff_matches_interval_sum_without_gaps` |
| Anomalies on crafted data | `test_spike_flags_at_z4`, `test_spike_silent_with_13_baseline_samples`, `test_tamper_flags_at_48h_zero`, `test_tamper_silent_at_47h`, `test_tamper_silent_when_feeder_also_zero`, `test_outage_flags_half_feeder_two_intervals`, `test_outage_silent_single_interval` |
| Idempotency and late data | `test_rerun_same_date_identical_output`, `test_late_file_inside_lookback_included`, `test_late_file_after_lookback_needs_backfill` |

The answer-key hit table from P7 (expected vs detected per check) is the headline of the test results artifact.

SRE metrics, all in `pipeline_runs` and on the Pipeline health tab: ingest lag, completeness per zone, duplicate rate, run duration per task. The alert: completeness under 90% in any zone, or a drop of more than 5 points against the zone's 7-day average; it writes `ops_alerts`, shows red on the dashboard and fails the metrics task in Airflow.

There is no SRE drill this time, but the card still expects a backfill and rollback runbook. The SRE runs each command once while writing it and records the result in the test results:

| Check | How to trigger | What "good" looks like |
| --- | --- | --- |
| Backfill | Delete gold for two dates, then `make.ps1 backfill <start> <end>` | Gold and dashboard restored; numbers equal the pre-delete snapshot |
| Rollback | Set `spike.z_threshold: 0.5`, run a day (anomaly flood), then `make.ps1 rollback <date>` | Previous gold restored from `_archive`; anomaly count back to normal |
| Completeness alert | Generator flag drops 30% of one zone's files for a day | ops\_alerts row written; red on the Pipeline health page |
| Failed task retry | Make PostgreSQL unreachable during publish | Retries visible in Airflow, then success; no partial data |
