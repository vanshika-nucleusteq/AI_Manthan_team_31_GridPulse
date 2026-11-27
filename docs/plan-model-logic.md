# Plan: data model and logic

> Source: docs/gridpulse-plan.md §5. Copied verbatim, except the P0 team decisions marked **P0 decision** below (the original is unchanged).

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
| `consumption_daily_meter` | meter\_id, local\_date | kwh, intervals\_present, completeness\_pct, quality\_flag = NOT (completeness\_pct > 90) (**P0 decision**) |
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


### P0 decisions (team answers to the gap review)

- **P6 requirement: hourly feeder and zone tables.** Must-have 3 asks for hourly kWh per meter, per feeder and per zone; the table above only had it per meter. P6 adds:

| Table | Key | Main columns |
| --- | --- | --- |
| `consumption_hourly_feeder` | feeder\_id, hour\_start (IST) | kwh, meters\_reporting, completeness\_pct |
| `consumption_hourly_zone` | zone\_id, hour\_start (IST) | kwh, meters\_reporting, completeness\_pct |

- **Completeness flag.** The card says "above 90%, otherwise a quality flag", so `quality_flag = NOT (completeness_pct > 90)` (threshold `completeness_flag_pct` in `config/quality.yaml`), for meter-days and for feeder and zone aggregates. Exactly 90% (86.4 of 96 intervals) cannot occur for a full meter-day, but the rule is written this way so it is correct at the boundary.
