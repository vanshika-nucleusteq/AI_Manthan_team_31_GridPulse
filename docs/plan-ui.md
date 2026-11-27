# Plan: UI design

> Source: docs/gridpulse-plan.md §6. Copied verbatim; edit the original first, then re-split.

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

