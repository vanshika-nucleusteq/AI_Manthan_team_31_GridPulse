"""Answer-key evaluation: expected vs detected anomalies per check (hit, miss, false positive).

Run: python -m gridpulse.anomalies.evaluate   (uses GRIDPULSE_DATA_DIR, default data/)
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from typing import Any

import orjson

from gridpulse.common.lake import Lake, lake_from_config
from gridpulse.ingest.bronze import connect

CHECKS = ("spike", "tamper", "outage")


def _ts(value: Any) -> datetime:
    return (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )


def _overlaps(a: dict, b: dict) -> bool:
    return _ts(a["window_start"]) < _ts(b["window_end"]) and _ts(b["window_start"]) < _ts(
        a["window_end"]
    )


def _entity(event: dict) -> str:
    return event.get("meter_id") or event["feeder_id"]


def detected_events(lake: Lake, first: date, last: date) -> list[dict]:
    files = lake.files("gold", "anomalies", first, last)
    if not files:
        return []
    rel = connect().sql(f"SELECT * FROM read_parquet({files!r}, hive_partitioning = false)")
    return [dict(zip(rel.columns, row, strict=True)) for row in rel.fetchall()]


def evaluate(lake: Lake | None = None) -> dict[str, Any]:
    lake = lake or lake_from_config()
    key = orjson.loads((lake.data_dir / lake.paths["answer_key"]).read_bytes())
    gen = key["generator"]
    first = date.fromisoformat(gen["start"])
    last = first + timedelta(days=int(gen["days"]) - 1)
    detected = detected_events(lake, first, last)
    report: dict[str, Any] = {"period": f"{first} to {last}", "checks": {}}
    for check in CHECKS:
        expected = [s for s in key["scenarios"] if s["type"] == check]
        found = [d for d in detected if d["type"] == check]
        matched: set[int] = set()
        rows = []
        for exp in expected:
            hits = [
                i for i, d in enumerate(found) if _entity(d) == _entity(exp) and _overlaps(d, exp)
            ]
            matched.update(hits)
            should_flag = exp["expected"].startswith("flag")
            if should_flag:
                outcome = "hit" if hits else "miss"
            else:
                outcome = "flagged although expected silent" if hits else "correct silent"
            rows.append(
                {
                    "entity": _entity(exp),
                    "window_start": exp["window_start"],
                    "expected": exp["expected"],
                    "outcome": outcome,
                }
            )
        false_pos = [found[i] for i in range(len(found)) if i not in matched]
        report["checks"][check] = {
            "expected_flag": sum(r["expected"].startswith("flag") for r in rows),
            "hits": sum(r["outcome"] == "hit" for r in rows),
            "misses": sum(r["outcome"] == "miss" for r in rows),
            "correct_silent": sum(r["outcome"] == "correct silent" for r in rows),
            "flagged_expected_silent": sum(r["outcome"].startswith("flagged") for r in rows),
            "false_positives": len(false_pos),
            "detail": rows,
            "false_positive_sample": [
                {
                    "entity": _entity(f),
                    "window_start": str(f["window_start"]),
                    "score": float(f["score"]),
                }
                for f in sorted(false_pos, key=lambda f: -float(f["score"]))[:10]
            ],
        }
    return report


def main() -> int:
    report = evaluate()
    print(f"Answer-key evaluation, {report['period']}")
    cols = [
        "expected_flag",
        "hits",
        "misses",
        "correct_silent",
        "flagged_expected_silent",
        "false_positives",
    ]
    print(f"{'check':<8} | " + " | ".join(f"{c:>23}" for c in cols))
    for check, r in report["checks"].items():
        print(f"{check:<8} | " + " | ".join(f"{r[c]:>23}" for c in cols))
    for check, r in report["checks"].items():
        for row in r["detail"]:
            if row["outcome"] not in ("hit", "correct silent"):
                print(
                    f"  {check} {row['outcome']}: {row['entity']} {row['window_start']} "
                    f"({row['expected']})"
                )
        for fp in r["false_positive_sample"]:
            print(
                f"  {check} false positive: {fp['entity']} {fp['window_start']} score {fp['score']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
