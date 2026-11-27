---
name: data-tests
description: Use when writing tests for a data pipeline, stream processor, rule engine or data quality checks: rule tests, boundary values, idempotency/replay, late or out-of-order events, malformed data, reconciliation.
---
# Data pipeline tests

For the rule, check or component named by the user:

1. Read the rule's config and code first. Restate the rule precisely (threshold, window, key, inclusive or exclusive).
2. Produce a table of cases before any code: case · input sequence · expected output · why. Include:
   - should trigger, should NOT trigger
   - boundary values: exactly at the threshold, one below, one above; window edges
   - out-of-order and late events (inside and beyond the watermark)
   - duplicates of the same event ID
   - malformed or invalid records → dead-letter with the right reason
3. Wait for the team to add or change cases. Then write pytest tests with crafted, deterministic events (fixed timestamps, fixed IDs). No random data in assertions.
4. Always include, once per pipeline:
   - **Replay test**: same input twice → identical output rows (count and content).
   - **Reconciliation**: records in = records out + dead-lettered + filtered, by count.
5. Test names state rule and result. One command runs them all.
6. Log the run and any defects in the shared defect log (ID, steps, expected, actual, severity, status).
