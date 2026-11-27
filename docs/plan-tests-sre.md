# Plan: tests and SRE

> Source: docs/gridpulse-plan.md §10. Copied verbatim; edit the original first, then re-split.

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
