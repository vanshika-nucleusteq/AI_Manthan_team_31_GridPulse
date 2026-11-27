# GridPulse: smart meter telemetry platform

AI Manthan Wave 2, Track B, team 31. A batch platform that ingests synthetic smart meter telemetry,
normalises it to kWh on a 15-minute UTC grid, produces billing-ready consumption and flags spike,
tamper and outage anomalies. Scope: `docs/card.md`. Design: `docs/gridpulse-plan.md`.
Team rules: `CLAUDE.md`.

## How to run

### Prerequisites
Python 3.12, Docker with Compose. Copy `.env.example` to `.env`.

### Local dev
```
powershell -ExecutionPolicy Bypass -File scripts/make.ps1 venv
powershell -ExecutionPolicy Bypass -File scripts/make.ps1 check
```
(`make venv` and `make check` on Linux and macOS.)

### Full stack
TODO: built in P3 (`make.ps1 up`).
