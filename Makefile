PY ?= python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: venv lint test check generate up down reset logs run-day backfill rollback

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

generate:
	@echo "TODO: built in P1"

up down reset logs:
	@echo "TODO: built in P3"

run-day backfill rollback:
	@echo "TODO: built in P8"
