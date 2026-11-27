# UI design

Dashboard **GridPulse · Network Operations**: a multi-page Streamlit app (port 8501), one page per tab, with
sidebar filters for date range, zone and feeder shared across pages. Design source: `docs/plan-ui.md` (plan §6).
The card names Superset for must-have 7; the team uses Streamlit (see `docs/lld.md`).

## Users and questions

| User | Main question | Page they start on |
| --- | --- | --- |
| Network operations engineer | Is the network normal today? Where is data missing? | Overview, Completeness |
| Revenue-protection team | Which meters look tampered or spiky? | Anomalies |
| Billing analyst | Which bills are safe to send? | Billing |
| Platform team / SRE | Can we trust today's numbers? | Pipeline health |

## Wireframe

- File: [`docs/ui/wireframe.html`](ui/wireframe.html), one self-contained HTML file (no external files or fonts), opens offline in any browser. Pages switch from the sidebar or by URL hash: `#overview`, `#completeness`, `#anomalies`, `#billing`, `#pipeline`.
- Online copy (private claude.ai artifact; share it from its Share menu): https://claude.ai/artifact/UyrPMinNjsyfJy1pXyAGE1
- All numbers are **fake** and seeded so screenshots are repeatable. They are shaped like the generator output (5,000 meters, 20 feeders, 6 zones, F07 outage, 3 tamper, 10 spikes) but are not read from `data/`.
- Story told by the fake data: on 14 Aug, Z2 drops to 88.9% completeness (late gateway files on F06/F07, a pipeline problem) and F07 has a 10:00–12:00 IST outage (a field problem), so the alert states are visible.
- Screenshots (headless Edge, 1400 × 1150): [overview](ui/screens/overview.png) · [completeness](ui/screens/completeness.png) · [anomalies](ui/screens/anomalies.png) · [billing](ui/screens/billing.png) · [pipeline health](ui/screens/pipeline.png).
- Empty state: pick **Zone = Z3** (or any zone but Z2) on the Anomalies page; the outage timeline shows "No outages on 14 Aug in this scope" with the reason.

## Pages

| Page | Charts | Answers |
| --- | --- | --- |
| Overview | KPI tiles: yesterday's kWh (with change vs the day before), meters reporting %, open anomalies, zones ≤ 90% complete; feeder consumption bar for the selected day; daily kWh line per zone, last 30 days | "Is the network normal today?" |
| Completeness | Zone × day heatmap of completeness % (cell value printed, flagged cells outlined and marked "!"); table of meter-days flagged, with a likely cause column | "Where is data missing, and is it a field or a pipeline problem?" |
| Anomalies | Anomaly list (type, meter or feeder, zone, window in IST, score); anomalies per day stacked by type; outage events on a feeder timeline for the selected day | "What should revenue protection and network ops look at first?" |
| Billing | Bill counts (all, READY, REVIEW); monthly billing table with billed kWh (register), sum of intervals, difference %, days flagged, READY/REVIEW pill; REVIEW count by reason | "Which bills are safe to send?" |
| Pipeline health | Fired ops alerts (top, red rows); run duration per task; quarantine rows by rule; ingest lag per run; duplicate rate per run | "Can we trust today's numbers?" |

## Metric definitions

Shown as the "i" help tooltip on every chart and KPI.

| Metric | Definition | Source |
| --- | --- | --- |
| Consumption (kWh) | Sum of interval consumption for the period; readings spanning a gap count in the interval they arrive | `consumption_daily_*` |
| Completeness % | Intervals received ÷ intervals expected (96 per meter per day) × 100; flagged unless > 90 | `consumption_daily_*` |
| Meters reporting % | Meters with at least one reading that day ÷ active meters in master | `consumption_daily_zone` |
| Open anomalies | Anomalies in the selected window, by type | `anomalies` |
| Duplicate rate | Duplicates dropped ÷ readings received, per run | `pipeline_runs` |
| Ingest lag | Run start time − latest `ingested_at` in bronze for that run | `pipeline_runs` |
| Run duration | End − start of each task in the latest run | `pipeline_runs` |

Billed kWh (Billing page) = register at month end − register at month start, rollover-adjusted (`billing_monthly`).

## Design decisions

1. **Each page opens with the question it answers, and summary comes before detail.** Reason: four different users share one app; the question under the title tells each of them in one glance whether they are on the right page, and KPI tiles and alerts sit above the charts that explain them.
2. **Red (vermillion) is used only for alert states; everything else uses the Okabe-Ito colour-blind-safe palette.** Reason: the plan requires a colour-blind-safe palette with red only for alerts, so red keeps one meaning: the zones-≤-90% KPI, flagged heatmap cells, REVIEW bills, fired ops alerts and outages. State is also shown by text ("!", "Alert:", READY/REVIEW pills, line labels at the right edge), never by colour alone.
3. **Units in every axis title and IST on every time axis; daily views name the selected day.** Reason: storage is UTC but every business boundary is IST, and mixing them is the most likely way a reading lands on the wrong day; stating "(IST)" and "(kWh)" on the chart removes the guesswork for screenshots and the demo.
4. **Completeness is a heatmap with the value printed in each cell, plus a "likely cause" column on flagged meter-days.** Reason: the page must tell a field problem (one meter) from a pipeline problem (a whole feeder or zone, late files); the heatmap shows the pattern across zones and days, and the cause column says what to do next.
5. **Explanatory empty states instead of blank charts, and filters that live in the sidebar on every page.** Reason: "no anomalies" is a valid, useful answer and must not look like a broken chart; shared filters mean a user who scopes to a zone stays in that scope when moving between pages, which matches Streamlit's sidebar and session state.

## Streamlit dashboard (P11)

Built from the team's GridPulse design template (Next.js + Tailwind + shadcn reference, rebuilt in Streamlit 1.45
and Plotly): dark theme by default with a light/dark toggle, lime primary, Space Grotesk + JetBrains Mono,
16 px rounded panels, sidebar with five views, header with breadcrumb, day picker, data-freshness pill and
theme toggle. Kept to what the card's must-haves need: operator internals (DAG stepper, backfill form,
storage-layout table) were removed after review to keep the dashboard focused. The layout and components follow the template; **every number comes from the
GridPulse backend**, not from the template's mock data.

Run: `make.ps1 up` then http://localhost:8501 (container), or locally
`streamlit run app/app.py` with `GRIDPULSE_DB_URL` set. Deep links: `?view=anomalies&theme=light&day=2026-08-11`.
Code: `app/app.py` (shell), `app/gridpulse_ui/` (`theme.py`, `data.py`, `components.py`, `views.py`).

| View | Panels (top to bottom) |
| --- | --- |
| Overview | Hero, KPI strip, Feeder consumption + Completeness by zone, Anomaly feed (latest 5) |
| Consumption | Feeder consumption, Network daily consumption, Billing-ready consumption per meter |
| Anomalies | Anomaly summary (3 checks), Anomaly feed (all since go-live), Load heatmap |
| Data quality | Completeness by zone + Data quality rules + Schema evolution, Load heatmap |
| Pipeline health (MH7) | KPI strip (readings, completeness, duplicate rate, quarantined rows), Pipeline run time + Ingest lag, Quarantined rows by rule |

Where each panel's data comes from:

| Panel | Source |
| --- | --- |
| Hero, daily consumption, KPI readings and completeness | `consumption_daily_zone` |
| Feeder consumption (zone pills) | `consumption_hourly_zone`, selected IST day vs previous day |
| Completeness by zone | `consumption_daily_zone` (flag unless completeness > 90%) |
| Anomaly feed and summary | `anomalies` (spike, tamper, outage; thresholds shown from `config/anomalies.yaml`) |
| Load heatmap | `consumption_hourly_feeder`; a cell is a hatched gap when < 50% of expected readings arrived |
| Data quality rules, quarantined rows KPI | `data_quality_daily`, `consumption_daily_meter` |
| Billing table | `billing_monthly` (REVIEW first, then largest READY) |
| Pipeline run time, duplicate rate KPI, data-freshness pill | `pipeline_runs` (written by every CLI step) |
| Schema evolution, ingest lag | bronze Parquet for the selected arrival day (read-only lake mount) |

Deviations from the template, on purpose: zones Z1 to Z6 and feeders F01 to F20 (our data), a day picker
instead of a fixed date (the demo data is 1 to 21 Aug 2026), "Readings received" and "Quarantined rows" KPIs
instead of mock "events" and "ingest lag p95" (ingest lag is its own panel), anomaly status is "open" (no
case workflow yet), no notification bell (it had no function), and no DAG, backfill or storage-layout panels
(backfill and rollback stay command-line operations: `make.ps1 backfill`, `make.ps1 rollback`).

## Streamlit screenshots

Headless Edge, 1440 px wide: [overview (dark)](ui/screens/streamlit-overview-dark.png) · [overview (light)](ui/screens/streamlit-overview-light.png) · [consumption](ui/screens/streamlit-consumption-dark.png) · [anomalies](ui/screens/streamlit-anomalies-dark.png) · [data quality](ui/screens/streamlit-quality-dark.png) · [pipeline health](ui/screens/streamlit-pipeline-dark.png).
