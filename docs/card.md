## **Track B · Use Case: GridPulse – Smart Meter Telemetry Platform**

**Problem statement.** A power distribution utility collects readings from thousands of smart meters through field gateways. Data arrives late, duplicated and in changing formats, so billing disputes are common and tampering or outages are found only after complaints. Build a platform that ingests meter telemetry, normalises it, produces billing-ready consumption and flags anomalies.

**Data consumers.** Billing analyst, network operations engineer, revenue-protection team.

**Sources (synthetic).** 5,000 meters across 20 feeders and 6 zones, each sending a reading every 15 minutes, about 480,000 events per day, for 3 months of history. Events are JSON messages landed as files or sent to Kafka (team's choice). Schema version 1 has meter ID, timestamp, energy in Wh and status; version 2 adds voltage and firmware version, and some meters report in kWh.

**Must-have scope**

1. Ingestion of both schema versions with raw data preserved and a record of which version each event used.  
2. A normalisation layer that converts units to kWh, removes duplicates, orders events, and marks missing intervals as gaps instead of silently filling them.  
3. A consumption layer: hourly and daily kWh per meter, per feeder and per zone, and a monthly billing-ready table per meter.  
4. Anomaly detection with three checks: spike (z-score against the meter's own history), suspected tamper (zero consumption for 48 hours while neighbours on the same feeder are normal), and outage (many meters on one feeder missing readings at the same time).  
5. A storage layout designed for time-series access: date and zone partitioning, a file compaction approach and a retention rule (raw 30 days, hourly 13 months), with the reason for each choice written in an ADR.  
6. Orchestrated daily runs with retry and a backfill option for a date range.  
7. A Superset dashboard with feeder consumption, anomaly list, data completeness percentage per zone and a pipeline-health tab.

**Data quality rules.** Meter ID exists in the meter master. Energy reading not negative. Cumulative register never decreases unless a rollover is flagged. Completeness per meter per day above 90%, otherwise a quality flag on that day.

**Phase-by-phase expectations**

| Phase | Expected output | How Claude should be used |
| :---- | :---- | :---- |
| Architecture | Architecture diagram, partitioning and retention design, schema-evolution approach, ADR on handling late data | Ask Claude to propose partitioning options and predict query patterns for each, then test the prediction |
| Insight layer (UI) | One dashboard for network operations with defined consumption and completeness metrics | Claude proposes layouts and metric definitions; the team checks them against the answer key |
| Development | Ingestion for two schema versions, normalisation, aggregation, anomaly checks, DAG | Plan-first prompts, CLAUDE.md with unit and time-zone rules, small verified commits |
| Testing | Unit tests for unit conversion and gap detection, aggregate reconciliation to raw totals, duplicate and out-of-order tests, anomaly tests on crafted data | Claude builds crafted meter histories for each anomaly; the team confirms what should and should not flag |
| Deployment | Docker Compose with orchestrator, compute, storage, database and Superset; CI with tests; one-command start | Claude writes Compose and CI; team proves a clean start |
| Support (SRE) | Metrics for ingest lag, completeness, duplicate rate and run duration, an alert on completeness drop, a backfill and rollback runbook | Claude drafts the runbook; the team practises a backfill and a rollback once |

