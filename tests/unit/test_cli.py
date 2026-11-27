"""CLI stub: one subcommand per DAG task, each a TODO for now."""

import pytest

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


def test_cli_has_one_subcommand_per_dag_task() -> None:
    assert list(STEPS) == DAG_TASKS


@pytest.mark.parametrize("step", DAG_TASKS)
def test_cli_step_prints_todo_and_exits_zero(step: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([step, "--ds", "2026-08-01"]) == 0
    assert capsys.readouterr().out.startswith(f"TODO: {step} for ds=2026-08-01")


def test_cli_rejects_invalid_ds() -> None:
    with pytest.raises(SystemExit):
        main(["ingest", "--ds", "2026-13-01"])
