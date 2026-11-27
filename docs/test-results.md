# Test results

Run on 2026-11-27 (IST), branch `p9-qa`, Windows 11 / Python 3.12, DuckDB 2.0.1.

## Summary

| Area | Result |
| --- | --- |
| Unit tests (`make.ps1 test`) | **106 passed, 0 failed** in 90 s (101 test functions) |
| Integration tests (stack up) | 2 passed (meter master seed + reseed; publish twice = same rows) |
| Answer-key anomalies (21 days) | spike 10/10, tamper 3/3, outage 1/1; **580 spike false positives** (DEF-08, open) |
| Reconciliation silver to gold (21 days) | 21 days, difference 0.000000 on every day |
| PostgreSQL vs Parquet row counts | 9 of 9 tables equal |
| Lint (ruff, black --check) | clean |

## Answer-key hit table (expected vs detected)

| Data | Check | Expected flag | Hits | Misses | Correctly silent | False positives |
| --- | --- | --- | --- | --- | --- | --- |
| 21 days (`data/`) | spike | 10 | 10 | 0 | 0 | 580 |
| | tamper | 3 | 3 | 0 | 0 | 0 |
| | outage | 1 | 1 | 0 | 0 | 0 |
| 14 days (P7 run) | spike | 0 | 0 | 0 | 10 (13-day baseline) | 0 |
| | tamper | 3 | 3 | 0 | 0 | 0 |
| | outage | 1 | 1 | 0 | 0 | 0 |

Earlier pipeline stages against the 14-day answer key (P4, P5, P6): bronze rows = rows written (6,804,128);
quarantine UNKNOWN_METER 6,651, NEGATIVE_READING 20, REGISTER_DECREASED 20 (exact cells); exact duplicates
dropped 133,023 and conflicts flagged 13,302 (exact cells); gaps 68,888; 5 rollovers on the exact cells;
49 REVIEW bills = the half-day meter + the 48 F07 meters predicted from the answer key.

Spike false-positive analysis (21 days): median excess 0.04 kWh, mostly 02:00 to 04:00 IST, baseline sd
about 0.009 kWh. Adding `kWh >= 2 x baseline mean` keeps 10/10 hits with 0 false positives (proposed).

## Unit test run

| File | Tests (cases) |
| --- | --- |
| `test_ingest_quality.py` | 21 |
| `test_normalise.py` | 16 |
| `test_anomalies.py` | 15 |
| `test_generator.py` | 12 |
| `test_aggregate.py` | 11 |
| `test_cli.py` | 11 (incl. parametrised) |
| `test_maintenance.py` | 9 |
| `test_late_and_reconcile.py` | 6 |
| `test_init_db.py` | 4 |
| `test_smoke.py` | 1 |
| **Total** | **106 passed** |

## Reconciliation results

`python -m gridpulse.aggregate.reconcile --from 2026-08-01 --to 2026-08-21` (kWh per IST day):

```
     local_date |      silver_kwh |   gold_zone_kwh |  gold_meter_kwh | gold_hourly_kwh |    max_abs_diff
     2026-08-01 |    38293.819000 |    38293.819000 |    38293.819000 |    38293.819000 |        0.000000
     2026-08-02 |    38439.717000 |    38439.717000 |    38439.717000 |    38439.717000 |        0.000000
     2026-08-03 |    38429.317000 |    38429.317000 |    38429.317000 |    38429.317000 |        0.000000
     2026-08-04 |    38434.178000 |    38434.178000 |    38434.178000 |    38434.178000 |        0.000000
     2026-08-05 |    38421.002000 |    38421.002000 |    38421.002000 |    38421.002000 |        0.000000
     2026-08-06 |    38471.454000 |    38471.454000 |    38471.454000 |    38471.454000 |        0.000000
     2026-08-07 |    38417.969000 |    38417.969000 |    38417.969000 |    38417.969000 |        0.000000
     2026-08-08 |    38428.581000 |    38428.581000 |    38428.581000 |    38428.581000 |        0.000000
     2026-08-09 |    38453.060000 |    38453.060000 |    38453.060000 |    38453.060000 |        0.000000
     2026-08-10 |    38441.513000 |    38441.513000 |    38441.513000 |    38441.513000 |        0.000000
     2026-08-11 |    38423.849000 |    38423.849000 |    38423.849000 |    38423.849000 |        0.000000
     2026-08-12 |    38408.825000 |    38408.825000 |    38408.825000 |    38408.825000 |        0.000000
     2026-08-13 |    38430.215000 |    38430.215000 |    38430.215000 |    38430.215000 |        0.000000
     2026-08-14 |    38412.984000 |    38412.984000 |    38412.984000 |    38412.984000 |        0.000000
     2026-08-15 |    38431.806000 |    38431.806000 |    38431.806000 |    38431.806000 |        0.000000
     2026-08-16 |    38429.263000 |    38429.263000 |    38429.263000 |    38429.263000 |        0.000000
     2026-08-17 |    38433.093000 |    38433.093000 |    38433.093000 |    38433.093000 |        0.000000
     2026-08-18 |    38446.133000 |    38446.133000 |    38446.133000 |    38446.133000 |        0.000000
     2026-08-19 |    38403.362000 |    38403.362000 |    38403.362000 |    38403.362000 |        0.000000
     2026-08-20 |    38431.835000 |    38431.835000 |    38431.835000 |    38431.835000 |        0.000000
     2026-08-21 |    38468.855000 |    38468.855000 |    38468.855000 |    38468.855000 |        0.000000
21 days, 0 with a difference: PASS
```

Also proven by tests: records in = kept + quarantined + duplicates (8 = 4 + 2 + 2); gold daily kWh = raw
register difference (28.7 kWh); billing register difference = sum of intervals for every bill.

## Backfill and rollback drill results

| Check | How | Result |
| --- | --- | --- |
| Daily run via Airflow | `make.ps1 run-day 2026-08-14` | 9/9 tasks succeeded, run time 74 s, one `pipeline_runs` row per task |
| Rollback | `make.ps1 rollback 2026-08-14` | 9 gold partitions restored from `_archive`, replaced version kept as `rolled_back__<run>`, republished in 11 s |
| Backfill of a late file | `test_late_file_after_lookback_needs_backfill` | daily run leaves the gap; backfill fills it |
| Full backfill (21 days) | generate + ingest + quality + normalise + aggregate in the background | about 16 minutes end to end; reconciliation PASS |

The SRE runs the remaining runbook drills (completeness alert, failed-task retry) in P10.

## Defects

Found during the build; each has a fix commit and a test or check that would catch it again.

| ID | Found in | Steps | Expected | Actual | Severity | Status |
| --- | --- | --- | --- | --- | --- | --- |
| DEF-01 | P4 | Unknown meter row without `unit` | UNKNOWN_METER | Planned rule order gave BAD_UNIT | Medium | Fixed before code (rule order), test `test_unknown_meter_without_unit_is_unknown_meter_not_bad_unit` |
| DEF-02 | P4 | File 2 days late for the 23:00 IST hour, then backfill | Backfill finds it | Quality read bronze only up to ds | High | Fixed, test `test_late_file_after_lookback_found_by_backfill` |
| DEF-03 | P5 | Reading at 18:29:40 UTC | Bucketed in next IST day | Quality bucketed by raw ts | Medium | Fixed (snapped interval), test `test_reading_snapped_across_ist_midnight_lands_next_day` |
| DEF-04 | P5 | Backfill under a Windows file lock | Partition replaced or kept | Partition briefly missing | High | Fixed (retry + restore), test `test_failed_swap_restores_previous_partition` |
| DEF-05 | P6 | Publish gold to PostgreSQL | Rows copied | `sum(count)` came out as float; INTEGER columns rejected it | Medium | Fixed (BIGINT casts); transaction rolled back cleanly |
| DEF-06 | P6 | Publish billing | DATE month | Hive folder name `month=2026-08` replaced the column | Medium | Fixed (`hive_partitioning = false`) |
| DEF-07 | P7 | 60 h tamper run | One tamper event | IST hour keys ended in .5 and rounded half-to-even; run split in two | High | Fixed (`floor`), tests `test_tamper_flags_at_48h_zero` |
| DEF-08 | P7 | Spike check on 21 days | Few or no false positives | 580 false positives at night (tiny baseline sd) | Medium | **Open**: guard `kWh >= 2 x mean` proposed (0 FPs, 10/10 hits), team decision |
| DEF-09 | P7 | Window before go-live | No events | Every feeder looked like an outage | Medium | Fixed (`go_live_date` clamp) |
| DEF-10 | P8 | DAG appears unpaused; scheduler runs ds = today (no data) | Run stops | Retention deleted August landing/bronze; empty silver/gold written | Critical | Fixed (ingest fails on missing landing, DAG unscheduled + paused), test `test_missing_landing_folder_fails_instead_of_emptying_bronze`; data recovered |
| DEF-11 | P8 | Airflow schedule in IST | ds = IST day | `ds` formatted from UTC gives the previous day | High | Fixed before release (DAG in UTC) |
