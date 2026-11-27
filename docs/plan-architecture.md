# Plan: architecture and key decisions

> Source: docs/gridpulse-plan.md §1-2. Copied verbatim; edit the original first, then re-split.

## 1. Architecture

A batch medallion pipeline on one laptop, started by `make.ps1 up`: four containers (PostgreSQL, Airflow webserver and scheduler, Streamlit) plus a one-shot init. Every task reads and overwrites whole date partitions, which is what makes reruns, late data and backfill safe.

&#91;embedded content: GridPulse architecture · 6 components, 8 DAG tasks\]

> The diagram is an image: see the original build-plan doc (PDF export, page 4; not kept in the repo). Text version until `docs/lld.md` redraws it in Mermaid:
> - Components: generator (stands in for field gateways; writes `data/landing/` and `data/answer_key.json`), Parquet data lake (`data/lake/`: raw, bronze, quarantine, silver, gold, `_archive`), DuckDB compute inside Python tasks, Airflow 2.10 (webserver and scheduler, LocalExecutor), PostgreSQL 16 (gold copies and Airflow metadata), Streamlit dashboard (port 8501).
> - DAG `gridpulse_daily` (from P8): ingest → quality → normalise → aggregate → anomalies → publish → compact → retention → metrics.

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

