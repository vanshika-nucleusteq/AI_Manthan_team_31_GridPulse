---
name: sre-drill
description: Use for observability and incidents: metrics, alerts, Superset health dashboards, runbooks, the SRE drill, triage of a fault, root cause analysis and the RCA write-up.
---
# SRE: observe, drill, learn

## Before the drill (build phase)
- Metrics for a data pipeline: consumer lag, processing latency, throughput (in/out per minute), dead-letter rate, freshness (now minus max event time in the store), volume per minute.
- One alert with a threshold and where it fires (log line, table, Superset alert or Prometheus rule).
- `docs/runbook.md`: per symptom → how to see it → likely causes → exact commands to check → fix → how to confirm recovery. Include replay/backfill (offset reset) steps. Every command must be run once by a human.

## During the drill
1. **Detect** from our own metric or alert. Note the time.
2. **Triage**: user gives trimmed evidence (relevant log lines + metric values), never the whole log. List hypotheses ranked by likelihood with a check for each. The team chooses which to test.
3. **Fix** the cause, not the symptom. Add a regression test and, if missing, an alert.
4. Confirm recovery against the same metric.

## RCA (`docs/rca.md`)
```
# RCA: <title>
Timeline (detected, triaged, fixed, verified, with times)
Impact (what data/consumers, how long)
Root cause (5 whys, short)
Detection: how we found it, how fast; what would have found it faster
Fix and verification
Prevention: test added, alert added, runbook updated
```
