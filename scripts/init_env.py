"""Create .env from .env.example if missing, replacing change-me secrets with fresh random keys."""

from __future__ import annotations

import base64
import os
import secrets
import sys
from pathlib import Path

GENERATED = {
    "AIRFLOW__CORE__FERNET_KEY": lambda: base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "AIRFLOW__WEBSERVER__SECRET_KEY": lambda: secrets.token_urlsafe(32),
}


def render(example: str) -> str:
    lines = []
    for line in example.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in GENERATED and value == "change-me":
            line = f"{key}={GENERATED[key]()}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main(root: Path) -> int:
    target = root / ".env"
    if target.exists():
        print(".env exists; leaving it unchanged")
        return 0
    target.write_text(render((root / ".env.example").read_text(encoding="utf-8")), encoding="utf-8")
    print("created .env from .env.example with generated Airflow keys")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))
