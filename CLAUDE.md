# CLAUDE.md — AI Manthan, Wave 2, Track B (team NN)

## Project
<!-- Fill at kick-off, 3-5 lines: the problem in our words, data consumers, must-have scope list. -->
Problem:
Consumers:
Must-haves (numbered, from the card):

## Stack (open-source only)
Kafka · Spark Structured Streaming (or plain Python consumer) · PostgreSQL · Airflow/dbt if batch · Superset · Docker Compose · GitHub Actions

## Hard rules
- Synthetic data only. Never generate real or realistic personal or card data; use tokens and fake IDs.
- No secrets in the repo. Config via `.env` (git-ignored) and `.env.example` with dummy values.
- Plan first: for any task bigger than one file, propose a numbered plan and wait for approval.
- One task per session. Small changes; one commit per change; prefixes feat, fix, test, docs, ci, chore.
- Every must-have gets a test. Test names state the rule and the result, e.g. `test_velocity_rule_fires_on_sixth_txn_in_minute`.
- Writes to the database are idempotent upserts keyed on a natural key. Replaying input must not duplicate rows.
- Bad records never crash the pipeline: they go to a dead-letter destination with a reason.
- Thresholds and rule settings live in config (YAML or a table), never hard-coded.
- If unsure about a requirement, ask; do not invent scope.

## Repo layout
src/ (producer, processor, sinks) · tests/ · deploy/ (compose, CI, Superset) · docs/ (adr/, runbook.md, rca.md, lld.md, ideation.md, test-plan.md, claude-journal.md)

## Message / data schema
<!-- Paste the event schema here at kick-off: field, type, allowed values, key. Claude must follow it exactly. -->

## Commands
- Start everything: `make up` (or `docker compose -f deploy/docker-compose.yml up -d`)
- Tests: `make test` (pytest)
- Lint: `make lint` (ruff + black --check)

## Style
Python: Black + Ruff, snake_case, type hints. SQL: snake_case, explicit column lists. No commented-out code.

## Skills in this repo
/kickoff-card · /adr · /claude-journal · /data-tests · /stack-deploy · /sre-drill
