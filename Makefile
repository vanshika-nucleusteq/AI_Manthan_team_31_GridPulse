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

run-day backfill rollback:
	@echo "TODO: built in P8"
