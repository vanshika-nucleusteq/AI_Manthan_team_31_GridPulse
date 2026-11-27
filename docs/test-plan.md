# Test plan

Owner: QA. Covers the card's must-haves (MH1 to MH7) and data quality rules. Every test name states the
rule and the expected result (CLAUDE.md). One command runs them all: `make.ps1 test` (unit) or
`make.ps1 check` (lint + unit); CI runs the same on every push and pull request.

## Scope

| Must-have (card) | Covered by |
| --- | --- |
| MH1 Ingestion of both schema versions, raw kept, version recorded | `test_ingest_quality.py` |
| MH2 Normalisation: kWh, dedup, ordering, gaps not filled | `test_normalise.py`, `test_late_and_reconcile.py` |
| MH3 Hourly/daily per meter, feeder, zone; monthly billing | `test_aggregate.py`, integration `test_publish.py` |
| MH4 Spike, tamper, outage | `test_anomalies.py` + answer-key evaluation |
| MH5 Storage layout: partitions, compaction, retention | `test_maintenance.py`, partition tests in normalise/aggregate |
| MH6 Orchestrated daily runs, retry, backfill | `test_maintenance.py` (DAG file, run logging), `test_cli.py`, late-file tests |
| MH7 Dashboard | P11 (UI test cases to be added with the Streamlit pages) |
| Data quality rules | `test_ingest_quality.py`, `test_aggregate.py` (completeness flag) |

Out of scope here: load testing beyond the 21-day dataset, browser UI tests (P11).

## Approach (unit, integration, answer key)

1. **Unit tests on crafted data** (CI): fixed timestamps and fixed meter IDs, built through the real functions
   (ingest, quality, normalise, aggregate, anomalies) in a temporary lake. No random data in assertions.
2. **Integration tests** (local, stack up): `pytest -m integration tests/integration`, PostgreSQL seed and
   publish idempotency.
3. **Answer-key verification** (generated data, seed 42): every injected problem in `data/answer_key.json`
   is checked with `python -m gridpulse.anomalies.evaluate` and `python -m gridpulse.aggregate.reconcile`.

Case types used below: Functional, Boundary (exactly at, just below or above a threshold or window edge),
Should not trigger, Negative / dead-letter (bad input goes to quarantine with a reason, never a crash),
Replay / idempotency (same input twice gives identical output), Reconciliation (counts or kWh match
across layers).

## Test cases by must-have

Generated from the collected test suite (Test Cases tab format; one row per test function).

| ID | Must-have / area | Test | Checks (rule, then expected result) | Type | Cases | File |
| --- | --- | --- | --- | --- | --- | --- |
| TC-001 | MH3 consumption + billing | `test_gold_daily_equals_silver_sum` | Gold daily equals silver sum | Reconciliation | 1 | `test_aggregate.py` |
| TC-002 | MH3 consumption + billing | `test_day_under_90pct_flagged` | Day under 90% flagged | Boundary | 1 | `test_aggregate.py` |
| TC-003 | MH3 consumption + billing | `test_silent_meter_counts_as_zero_completeness` | Silent meter counts as zero completeness | Functional | 1 | `test_aggregate.py` |
| TC-004 | MH3 consumption + billing | `test_hourly_bucket_uses_ist_hour` | Hourly bucket uses IST hour | Functional | 1 | `test_aggregate.py` |
| TC-005 | MH3 consumption + billing | `test_billing_month_uses_ist_boundary` | Billing month uses IST boundary | Boundary | 1 | `test_aggregate.py` |
| TC-006 | MH3 consumption + billing | `test_billing_register_diff_matches_interval_sum_without_gaps` | Billing register diff matches interval sum without gaps | Reconciliation | 1 | `test_aggregate.py` |
| TC-007 | MH3 consumption + billing | `test_billing_with_gap_still_matches_and_flagged_day_sets_review` | Billing with gap still matches and flagged day sets review | Reconciliation | 1 | `test_aggregate.py` |
| TC-008 | MH3 consumption + billing | `test_rollover_in_month_billed_correctly` | Rollover in month billed correctly | Functional | 1 | `test_aggregate.py` |
| TC-009 | MH3 consumption + billing | `test_replaced_gold_partition_moved_to_archive` | Replaced gold partition moved to archive | Functional | 1 | `test_aggregate.py` |
| TC-010 | MH3 consumption + billing | `test_rerun_same_date_identical_output` | Rerun same date identical output | Replay / idempotency | 1 | `test_aggregate.py` |
| TC-011 | MH3 consumption + billing | `test_publish_deletes_partition_then_copies_explicit_columns` | Publish deletes partition then copies explicit columns | Functional | 1 | `test_aggregate.py` |
| TC-012 | MH4 anomaly checks | `test_spike_flags_at_z4` | Spike flags at z = 4 | Boundary | 1 | `test_anomalies.py` |
| TC-013 | MH4 anomaly checks | `test_spike_silent_just_under_z4` | Spike silent just under z = 4 | Boundary | 1 | `test_anomalies.py` |
| TC-014 | MH4 anomaly checks | `test_spike_silent_with_13_baseline_samples` | Spike silent with 13 baseline samples | Boundary | 1 | `test_anomalies.py` |
| TC-015 | MH4 anomaly checks | `test_spike_skips_gap_hours` | Spike skips gap hours | Should not trigger | 1 | `test_anomalies.py` |
| TC-016 | MH4 anomaly checks | `test_tamper_flags_at_48h_zero` | Tamper flags at 48h zero | Boundary | 1 | `test_anomalies.py` |
| TC-017 | MH4 anomaly checks | `test_tamper_silent_at_47h` | Tamper silent at 47h | Boundary | 1 | `test_anomalies.py` |
| TC-018 | MH4 anomaly checks | `test_tamper_silent_when_feeder_also_zero` | Tamper silent when feeder also zero | Should not trigger | 1 | `test_anomalies.py` |
| TC-019 | MH4 anomaly checks | `test_tamper_silent_when_meter_incomplete` | Tamper silent when meter incomplete | Should not trigger | 1 | `test_anomalies.py` |
| TC-020 | MH4 anomaly checks | `test_outage_flags_half_feeder_two_intervals` | Outage flags half feeder two intervals | Functional | 1 | `test_anomalies.py` |
| TC-021 | MH4 anomaly checks | `test_outage_silent_single_interval` | Outage silent single interval | Boundary | 1 | `test_anomalies.py` |
| TC-022 | MH4 anomaly checks | `test_outage_silent_below_half_feeder` | Outage silent below half feeder | Boundary | 1 | `test_anomalies.py` |
| TC-023 | MH4 anomaly checks | `test_consecutive_outage_intervals_merge` | Consecutive outage intervals merge | Functional | 1 | `test_anomalies.py` |
| TC-024 | MH4 anomaly checks | `test_anomaly_id_deterministic` | Anomaly id deterministic | Functional | 1 | `test_anomalies.py` |
| TC-025 | MH4 anomaly checks | `test_outage_ignores_quarantined_gaps` | Outage ignores quarantined gaps | Should not trigger | 1 | `test_anomalies.py` |
| TC-026 | MH4 anomaly checks | `test_rerun_same_date_identical_output` | Rerun same date identical output | Replay / idempotency | 1 | `test_anomalies.py` |
| TC-027 | MH6 DAG task CLI | `test_cli_has_one_subcommand_per_dag_task` | Cli has one subcommand per dag task | Functional | 1 | `test_cli.py` |
| TC-028 | MH6 DAG task CLI | `test_cli_unbuilt_step_prints_todo_and_exits_zero` | Cli unbuilt step prints todo and exits zero | Functional | 1 | `test_cli.py` |
| TC-029 | MH6 DAG task CLI | `test_cli_built_step_prints_its_counts_as_json` | Cli built step prints its counts as json | Functional | 8 | `test_cli.py` |
| TC-030 | MH6 DAG task CLI | `test_cli_rejects_invalid_ds` | Cli rejects invalid ds | Negative / dead-letter | 1 | `test_cli.py` |
| TC-031 | Test data (generator) | `test_same_seed_gives_identical_files_and_answer_key` | Same seed gives identical files and answer key | Replay / idempotency | 1 | `test_generator.py` |
| TC-032 | Test data (generator) | `test_existing_output_is_kept_unless_overwrite` | Existing output is kept unless overwrite | Negative / dead-letter | 1 | `test_generator.py` |
| TC-033 | Test data (generator) | `test_meter_master_splits_meters_evenly_and_zones_have_3_or_4_feeders` | Meter master splits meters evenly and zones have 3 or 4 feeders | Functional | 1 | `test_generator.py` |
| TC-034 | Test data (generator) | `test_kwh_reporting_meters_are_v2_meters` | Kwh reporting meters are v2 meters | Functional | 1 | `test_generator.py` |
| TC-035 | Test data (generator) | `test_v1_has_energy_wh_and_v2_has_energy_unit_voltage_firmware` | V1 has energy wh and v2 has energy unit voltage firmware | Functional | 1 | `test_generator.py` |
| TC-036 | Test data (generator) | `test_answer_key_counts_match_written_rows` | Answer key counts match written rows | Reconciliation | 1 | `test_generator.py` |
| TC-037 | Test data (generator) | `test_unknown_meter_ids_are_outside_master` | Unknown meter ids are outside master | Negative / dead-letter | 1 | `test_generator.py` |
| TC-038 | Test data (generator) | `test_register_never_decreases_except_injected_and_rollover` | Register never decreases except injected and rollover | Negative / dead-letter | 1 | `test_generator.py` |
| TC-039 | Test data (generator) | `test_late_files_land_in_later_arrival_date_folder` | Late files land in later arrival date folder | Functional | 1 | `test_generator.py` |
| TC-040 | Test data (generator) | `test_scenario_meter_sets_do_not_overlap` | Scenario meter sets do not overlap | Should not trigger | 1 | `test_generator.py` |
| TC-041 | Test data (generator) | `test_spike_on_short_history_is_expected_silent` | Spike on short history is expected silent | Should not trigger | 1 | `test_generator.py` |
| TC-042 | Test data (generator) | `test_tamper_skipped_when_window_shorter_than_60_hours` | Tamper skipped when window shorter than 60 hours | Functional | 1 | `test_generator.py` |
| TC-043 | MH1 ingestion + data quality rules | `test_v1_v2_detected_and_version_recorded` | V1 v2 detected and version recorded | Functional | 1 | `test_ingest_quality.py` |
| TC-044 | MH1 ingestion + data quality rules | `test_explicit_schema_version_wins` | Explicit schema version wins | Functional | 1 | `test_ingest_quality.py` |
| TC-045 | MH1 ingestion + data quality rules | `test_missing_unit_falls_back_to_master` | Missing unit falls back to master | Functional | 1 | `test_ingest_quality.py` |
| TC-046 | MH1 ingestion + data quality rules | `test_unknown_meter_quarantined` | Unknown meter quarantined | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-047 | MH1 ingestion + data quality rules | `test_unknown_meter_without_unit_is_unknown_meter_not_bad_unit` | Unknown meter without unit is unknown meter not bad unit | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-048 | MH1 ingestion + data quality rules | `test_unknown_unit_quarantined_as_bad_unit` | Unknown unit quarantined as bad unit | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-049 | MH1 ingestion + data quality rules | `test_negative_reading_quarantined` | Negative reading quarantined | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-050 | MH1 ingestion + data quality rules | `test_status_error_quarantined_as_meter_error` | Status error quarantined as meter error | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-051 | MH1 ingestion + data quality rules | `test_register_decrease_quarantined` | Register decrease quarantined | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-052 | MH1 ingestion + data quality rules | `test_rollover_allowed` | Rollover allowed | Should not trigger | 1 | `test_ingest_quality.py` |
| TC-053 | MH1 ingestion + data quality rules | `test_conflicting_duplicate_not_flagged_as_decrease` | Conflicting duplicate not flagged as decrease | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-054 | MH1 ingestion + data quality rules | `test_previous_reading_comes_from_context_day` | Previous reading comes from context day | Boundary | 1 | `test_ingest_quality.py` |
| TC-055 | MH1 ingestion + data quality rules | `test_malformed_line_quarantined_without_crash` | Malformed line quarantined without crash | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-056 | MH1 ingestion + data quality rules | `test_corrupt_file_quarantined` | Corrupt file quarantined | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-057 | MH1 ingestion + data quality rules | `test_off_grid_timestamp_quarantined_within_tolerance_kept` | Off grid timestamp quarantined within tolerance kept | Boundary | 1 | `test_ingest_quality.py` |
| TC-058 | MH1 ingestion + data quality rules | `test_naive_timestamp_quarantined` | Naive timestamp quarantined | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-059 | MH1 ingestion + data quality rules | `test_offset_timestamp_converted_to_utc` | Offset timestamp converted to UTC | Functional | 1 | `test_ingest_quality.py` |
| TC-060 | MH1 ingestion + data quality rules | `test_ingested_at_comes_from_arrival_stamp` | Ingested at comes from arrival stamp | Functional | 1 | `test_ingest_quality.py` |
| TC-061 | MH1 ingestion + data quality rules | `test_rerun_same_date_identical_output` | Rerun same date identical output | Replay / idempotency | 1 | `test_ingest_quality.py` |
| TC-062 | MH1 ingestion + data quality rules | `test_late_file_after_lookback_found_by_backfill` | Late file after lookback found by backfill | Boundary | 1 | `test_ingest_quality.py` |
| TC-063 | MH1 ingestion + data quality rules | `test_missing_landing_folder_fails_instead_of_emptying_bronze` | Missing landing folder fails instead of emptying bronze | Negative / dead-letter | 1 | `test_ingest_quality.py` |
| TC-064 | Platform (database init) | `test_init_db_runs_sql_files_in_name_order` | Init db runs sql files in name order | Functional | 1 | `test_init_db.py` |
| TC-065 | Platform (database init) | `test_seed_skipped_when_master_csv_missing` | Seed skipped when master csv missing | Functional | 1 | `test_init_db.py` |
| TC-066 | Platform (database init) | `test_meter_master_upsert_is_keyed_on_meter_id` | Meter master upsert is keyed on meter id | Functional | 1 | `test_init_db.py` |
| TC-067 | Platform (database init) | `test_sqlalchemy_url_uses_psycopg3_driver` | Sqlalchemy url uses psycopg3 driver | Functional | 1 | `test_init_db.py` |
| TC-068 | MH2/MH6 late data, reconciliation, replay | `test_late_file_inside_lookback_included` | Late file inside lookback included | Boundary | 1 | `test_late_and_reconcile.py` |
| TC-069 | MH2/MH6 late data, reconciliation, replay | `test_late_file_after_lookback_needs_backfill` | Late file after lookback needs backfill | Boundary | 1 | `test_late_and_reconcile.py` |
| TC-070 | MH2/MH6 late data, reconciliation, replay | `test_records_in_equal_kept_plus_quarantined_plus_duplicates` | Records in equal kept plus quarantined plus duplicates | Reconciliation | 1 | `test_late_and_reconcile.py` |
| TC-071 | MH2/MH6 late data, reconciliation, replay | `test_gold_daily_equals_raw_register_difference` | Gold daily equals raw register difference | Reconciliation | 1 | `test_late_and_reconcile.py` |
| TC-072 | MH2/MH6 late data, reconciliation, replay | `test_ts_60s_off_grid_kept_61s_quarantined` | Ts 60s off grid kept 61s quarantined | Boundary | 1 | `test_late_and_reconcile.py` |
| TC-073 | MH2/MH6 late data, reconciliation, replay | `test_rerun_same_date_identical_output_end_to_end` | Rerun same date identical output end to end | Replay / idempotency | 1 | `test_late_and_reconcile.py` |
| TC-074 | MH5/MH6 storage ops + orchestration | `test_compaction_merges_files_into_one_sorted_file` | Compaction merges files into one sorted file | Functional | 1 | `test_maintenance.py` |
| TC-075 | MH5/MH6 storage ops + orchestration | `test_compaction_leaves_single_file_partition_alone` | Compaction leaves single file partition alone | Should not trigger | 1 | `test_maintenance.py` |
| TC-076 | MH5/MH6 storage ops + orchestration | `test_retention_deletes_only_partitions_past_their_rule` | Retention deletes only partitions past their rule | Should not trigger | 1 | `test_maintenance.py` |
| TC-077 | MH5/MH6 storage ops + orchestration | `test_months_back_handles_year_boundary` | Months back handles year boundary | Boundary | 1 | `test_maintenance.py` |
| TC-078 | MH5/MH6 storage ops + orchestration | `test_rollback_restores_archived_gold_and_keeps_undo` | Rollback restores archived gold and keeps undo | Functional | 1 | `test_maintenance.py` |
| TC-079 | MH5/MH6 storage ops + orchestration | `test_rollback_without_archive_is_an_error` | Rollback without archive is an error | Negative / dead-letter | 1 | `test_maintenance.py` |
| TC-080 | MH5/MH6 storage ops + orchestration | `test_pipeline_runs_counts_per_task` | Pipeline runs counts per task | Functional | 1 | `test_maintenance.py` |
| TC-081 | MH5/MH6 storage ops + orchestration | `test_failed_step_is_recorded_then_reraised` | Failed step is recorded then reraised | Negative / dead-letter | 1 | `test_maintenance.py` |
| TC-082 | MH5/MH6 storage ops + orchestration | `test_dag_imports_nothing_from_gridpulse_and_runs_every_cli_step_in_order` | Dag imports nothing from gridpulse and runs every cli step in order | Functional | 1 | `test_maintenance.py` |
| TC-083 | MH2 normalisation | `test_wh_divided_by_1000` | Wh divided by 1000 | Functional | 1 | `test_normalise.py` |
| TC-084 | MH2 normalisation | `test_v2_kwh_unchanged` | V2 kWh unchanged | Should not trigger | 1 | `test_normalise.py` |
| TC-085 | MH2 normalisation | `test_missing_interval_written_to_gaps` | Missing interval written to gaps | Functional | 1 | `test_normalise.py` |
| TC-086 | MH2 normalisation | `test_gap_never_filled` | Gap never filled | Should not trigger | 1 | `test_normalise.py` |
| TC-087 | MH2 normalisation | `test_reading_after_gap_spans_two_intervals` | Reading after gap spans two intervals | Functional | 1 | `test_normalise.py` |
| TC-088 | MH2 normalisation | `test_exact_duplicate_dropped` | Exact duplicate dropped | Functional | 1 | `test_normalise.py` |
| TC-089 | MH2 normalisation | `test_conflicting_duplicate_keeps_latest_and_flags` | Conflicting duplicate keeps latest and flags | Functional | 1 | `test_normalise.py` |
| TC-090 | MH2 normalisation | `test_out_of_order_readings_sorted_before_delta` | Out of order readings sorted before delta | Functional | 1 | `test_normalise.py` |
| TC-091 | MH2 normalisation | `test_rollover_consumption_uses_register_max` | Rollover consumption uses register max | Functional | 1 | `test_normalise.py` |
| TC-092 | MH2 normalisation | `test_rollover_status_without_wrap_uses_plain_delta` | Rollover status without wrap uses plain delta | Should not trigger | 1 | `test_normalise.py` |
| TC-093 | MH2 normalisation | `test_quarantined_interval_is_a_gap_with_cause` | Quarantined interval is a gap with cause | Functional | 1 | `test_normalise.py` |
| TC-094 | MH2 normalisation | `test_interval_at_1830_utc_belongs_to_next_ist_day` | Interval at 1830 UTC belongs to next IST day | Boundary | 1 | `test_normalise.py` |
| TC-095 | MH2 normalisation | `test_reading_snapped_across_ist_midnight_lands_next_day` | Reading snapped across IST midnight lands next day | Boundary | 1 | `test_normalise.py` |
| TC-096 | MH2 normalisation | `test_first_window_reading_uses_context_day` | First window reading uses context day | Boundary | 1 | `test_normalise.py` |
| TC-097 | MH2 normalisation | `test_rerun_same_date_identical_output` | Rerun same date identical output | Replay / idempotency | 1 | `test_normalise.py` |
| TC-098 | MH2 normalisation | `test_failed_swap_restores_previous_partition` | Failed swap restores previous partition | Negative / dead-letter | 1 | `test_normalise.py` |
| TC-099 | Platform (package) | `test_package_imports_and_exposes_version` | Package imports and exposes version | Functional | 1 | `test_smoke.py` |
| TC-100 | MH3/MH7 publish (integration) | `test_publish_twice_leaves_same_rows_as_gold_parquet` | Publish twice leaves same rows as gold parquet | Replay / idempotency | 1 | `test_publish.py` |
| TC-101 | Platform (stack, integration) | `test_meter_master_seeded_with_5000_rows_and_reseed_is_idempotent` | Meter master seeded with 5000 rows and reseed is idempotent | Replay / idempotency | 1 | `test_stack.py` |

## Boundary cases

| Rule | Exactly at | Just inside | Just outside | Tests |
| --- | --- | --- | --- | --- |
| Spike z-score >= 4 | z = 4.001 flags | | z = 3.99 silent | `test_spike_flags_at_z4`, `test_spike_silent_just_under_z4` |
| Spike baseline >= 14 samples | 14 samples flags | | 13 samples silent | `test_spike_silent_with_13_baseline_samples` |
| Tamper >= 48 zero hours | 48 h flags | | 47 h silent | `test_tamper_flags_at_48h_zero`, `test_tamper_silent_at_47h` |
| Tamper completeness >= 90% | | 100% flags | 89.58% silent | `test_tamper_silent_when_meter_incomplete` |
| Outage >= 50% of feeder, >= 2 intervals | 5/10 for 2 intervals flags | | 4/10 silent; 1 interval silent | `test_outage_flags_half_feeder_two_intervals`, `test_outage_silent_below_half_feeder`, `test_outage_silent_single_interval` |
| Completeness flag = NOT (pct > 90) | (90.0% impossible at 96 intervals) | 87/96 = 90.6% not flagged | 86/96 = 89.6% flagged | `test_day_under_90pct_flagged` |
| Timestamp tolerance 60 s | 60 s kept | 45 s kept | 61 s and 120 s quarantined | `test_ts_60s_off_grid_kept_61s_quarantined`, `test_off_grid_timestamp_quarantined_within_tolerance_kept` |
| Lookback 3 days (D-2..D) | file at D+2 included | | file at D+3 needs backfill | `test_late_file_inside_lookback_included`, `test_late_file_after_lookback_needs_backfill` |
| IST day boundary | 18:30 UTC is the next IST day | 18:29:40 UTC snaps forward | | `test_interval_at_1830_utc_belongs_to_next_ist_day`, `test_reading_snapped_across_ist_midnight_lands_next_day` |
| IST month boundary | 31 Jul 18:30 UTC is August | | | `test_billing_month_uses_ist_boundary` |

## Environments and data

- Unit: Python 3.12 venv, DuckDB in-process, temporary folders; no network, no Docker.
- Integration: `make.ps1 up` stack (PostgreSQL 16, Airflow 2.10, Streamlit).
- Generated data: `data/` = 21-day dataset (5,000 meters, seed 42) with `answer_key.json`.

## Entry and exit criteria

- Entry: the step's code merged on its branch; `make.ps1 check` runs.
- Exit: all unit tests pass; every must-have has at least one test; answer-key checks show no misses;
  reconciliation difference is 0 for every day; every defect found is logged with a status in
  `docs/test-results.md`.
