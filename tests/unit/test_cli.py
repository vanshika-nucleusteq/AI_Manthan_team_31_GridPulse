"""CLI: one subcommand per DAG task; built steps run, the rest print TODO."""

import json

import pytest

from gridpulse import cli
from gridpulse.cli import STEPS, main

DAG_TASKS = [
    "ingest",
    "quality",
    "normalise",
    "aggregate",
    "anomalies",
    "publish",
    "compact",
    "retention",
    "metrics",
]
BUILT = ["ingest", "quality", "normalise", "aggregate", "publish"]


def test_cli_has_one_subcommand_per_dag_task() -> None:
    assert list(STEPS) == DAG_TASKS


@pytest.mark.parametrize("step", [s for s in DAG_TASKS if s not in BUILT])
def test_cli_unbuilt_step_prints_todo_and_exits_zero(
    step: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([step, "--ds", "2026-08-01"]) == 0
    assert capsys.readouterr().out.startswith(f"TODO: {step} for ds=2026-08-01")


@pytest.mark.parametrize("step", BUILT)
def test_cli_built_step_prints_its_counts_as_json(
    step: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "run_step", lambda s, ds: {"step": s, "ds": ds.isoformat(), "rows": 3})
    assert main([step, "--ds", "2026-08-01"]) == 0
    assert json.loads(capsys.readouterr().out) == {"step": step, "ds": "2026-08-01", "rows": 3}


def test_cli_rejects_invalid_ds() -> None:
    with pytest.raises(SystemExit):
        main(["ingest", "--ds", "2026-13-01"])
