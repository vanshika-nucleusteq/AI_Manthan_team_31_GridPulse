PY ?= python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: venv lint test check generate up down reset logs seed run-day backfill rollback

COMPOSE := docker compose --env-file .env -f deploy/docker-compose.yml

venv:
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e ".[dev]"

lint:
	$(BIN)/python -m ruff check .
	$(BIN)/python -m black --check .

test:
	$(BIN)/python -m pytest -q

check: lint test

# make generate ARGS="--days 14 --overwrite"
generate:
	$(BIN)/python -m gridpulse.generator $(ARGS)

up:
	python3 scripts/init_env.py
	$(COMPOSE) up -d --build --wait
	$(COMPOSE) ps

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down --volumes --remove-orphans

# make logs ARGS=airflow-scheduler
logs:
	$(COMPOSE) logs --tail 200 $(ARGS)

seed:
	python3 scripts/init_env.py
	$(COMPOSE) run --rm gridpulse-init

# make run-day DS=2026-08-14 | make backfill START=2026-08-01 END=2026-08-14 | make rollback DS=2026-08-14 [RUN_ID=...]
run-day:
	$(COMPOSE) exec -T airflow-scheduler airflow dags backfill gridpulse_daily -s $(DS) -e $(DS) --reset-dagruns -y

backfill:
	$(COMPOSE) exec -T airflow-scheduler airflow dags backfill gridpulse_daily -s $(START) -e $(END) --reset-dagruns -y

rollback:
	$(COMPOSE) exec -T airflow-scheduler /opt/gridpulse-venv/bin/python -m gridpulse.maintenance.rollback --date $(DS) $(if $(RUN_ID),--run-id $(RUN_ID),)
