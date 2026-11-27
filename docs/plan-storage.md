# Plan: storage layout

> Source: docs/gridpulse-plan.md §4. Copied verbatim; edit the original first, then re-split.

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

