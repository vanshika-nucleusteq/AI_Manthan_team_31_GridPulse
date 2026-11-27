"""Read landing files verbatim: one row per line with file, line number, raw JSON, arrival."""

from __future__ import annotations

import gzip
import re
import zlib
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa

ARRIVAL_STAMP = re.compile(r"_a(\d{8}T\d{4})Z\.jsonl\.gz$")
SCHEMA = pa.schema(
    [
        ("source_file", pa.string()),
        ("line_no", pa.int32()),
        ("raw_json", pa.string()),
        ("ingested_at", pa.timestamp("us", tz="UTC")),
        ("file_rule", pa.string()),
        ("file_reason", pa.string()),
    ]
)


def arrival_time(file_name: str) -> datetime | None:
    """Arrival stamp from the gateway file name; it is ingested_at, so reruns are identical."""
    match = ARRIVAL_STAMP.search(file_name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M").replace(tzinfo=UTC)


def read_landing(landing: Path, arrival_date: date) -> pa.Table:
    folder = landing / f"arrival_date={arrival_date.isoformat()}"
    cols: dict[str, list] = {name: [] for name in SCHEMA.names}

    def add(src: str, line_no: int, raw: str | None, at: datetime | None, rule=None, why=None):
        cols["source_file"].append(src)
        cols["line_no"].append(line_no)
        cols["raw_json"].append(raw)
        cols["ingested_at"].append(at)
        cols["file_rule"].append(rule)
        cols["file_reason"].append(why)

    if not folder.exists():
        # A missing folder means nothing ever arrived for this date or raw data has expired.
        # Failing here stops the run before an empty bronze, silver or gold replaces good data
        # (incident 2026-11-27: a scheduled run for a date with no data reached retention).
        raise FileNotFoundError(f"no landing folder {folder}; refusing to rebuild bronze for it")
    files = sorted(folder.rglob("*.jsonl.gz"))
    for path in files:
        src = path.relative_to(landing).as_posix()
        at = arrival_time(path.name)
        try:
            lines = gzip.decompress(path.read_bytes()).split(b"\n")
        except (OSError, EOFError, zlib.error) as exc:
            add(src, 0, None, at, "CORRUPT_FILE", f"cannot read gzip file: {exc}")
            continue
        rule, why = (None, None) if at else ("MALFORMED_RECORD", "file name has no arrival stamp")
        for line_no, line in enumerate(lines, start=1):
            if line.strip():
                add(src, line_no, line.decode("utf-8", errors="replace"), at, rule, why)
    return pa.table(cols, schema=SCHEMA)
