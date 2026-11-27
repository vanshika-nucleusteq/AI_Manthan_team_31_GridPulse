"""Smoke test: the package and every subpackage import."""

import importlib

import gridpulse

SUBPACKAGES = [
    "common",
    "generator",
    "ingest",
    "quality",
    "normalise",
    "aggregate",
    "anomalies",
    "publish",
    "maintenance",
]


def test_package_imports_and_exposes_version() -> None:
    assert gridpulse.__version__ == "0.1.0"
    for name in SUBPACKAGES:
        assert importlib.import_module(f"gridpulse.{name}") is not None
