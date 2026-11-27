# Plan: sources, schemas and the generator

> Source: docs/gridpulse-plan.md §3. Copied verbatim; edit the original first, then re-split.

## 3. Sources, schemas and the generator

The readings are cumulative register values (the card's "register never decreases" rule implies it), so interval consumption is the difference between consecutive readings for a meter.

| Field | v1 | v2 | Notes |
| --- | --- | --- | --- |
| meter\_id | ✓ | ✓ | `MTR-00001` to `MTR-05000`; must exist in meter master |
| ts | ✓ | ✓ | ISO-8601 UTC, should sit on a 15-minute boundary |
| energy\_wh | ✓ | – | Cumulative register in Wh |
| energy + unit | – | ✓ | Cumulative register; unit `Wh` or `kWh` (assumption, see below) |
| status | ✓ | ✓ | `OK`, `ROLLOVER` (register wrapped), `ERROR` |
| voltage | – | ✓ | Volts, nullable |
| firmware\_version | – | ✓ | For example `2.4.1` |

Schema detection: an explicit `schema_version` field wins; otherwise the presence of `voltage` or `firmware_version` means v2. Every bronze row keeps `schema_version`, `source_file` and `ingested_at`, which is must-have 1.

Assumption to confirm with the mentor: the card says some v2 meters report in kWh but names no unit field. We generate a `unit` field; if it is missing, we fall back to `reporting_unit` in the meter master.

Meter master (`meter_master`, seeded): meter\_id, feeder\_id (`F01`–`F20`, 250 meters each), zone\_id (`Z1`–`Z6`, 3 or 4 feeders each), meter\_type (residential or commercial), reporting\_unit, register\_max\_kwh, install\_date.

The generator (`make generate`) writes JSONL.gz files to `data/landing/arrival_date=YYYY-MM-DD/feeder=Fxx/<file>.jsonl.gz` (folders are by arrival date, so a late file holds readings from an earlier day, exactly like a slow gateway) and, alongside, `data/answer_key.json` listing every injected problem. That file is how the team proves each anomaly and quality check, as the card asks.

| Injected on purpose | Rate or count | Proves |
| --- | --- | --- |
| Schema v2 rollout | 40% of meters switch from day 45 | Must-have 1 |
| kWh-reporting meters | 15% of v2 meters | Unit conversion |
| Duplicate readings | 2% (exact) plus 0.2% (same key, different value) | Dedup and conflict flag |
| Late files | 3% of files land 1–2 days late | ADR 0001 lookback |
| Missing intervals | 1% random, plus one meter missing half a day | Gap marking and completeness flag |
| Spikes | 10 meters, one hour at 6–10× normal | Spike check |
| Tamper | 3 meters reading zero for 60 hours, feeder normal | Tamper check |
| Feeder outage | F07, 2 hours, 80% of meters silent | Outage check |
| Unknown meter IDs | 0.1% | Meter master rule |
| Negative or decreasing register | 20 readings each | Quality rules |
| Rollovers | 5 meters wrap with status ROLLOVER | Allowed decrease |

Scale: the card's full size is 5,000 meters × 96 readings × 90 days, about 43 million readings. Develop on `--days 14` (6.7 million), then run the full 90 days once in the background for the performance story. Generation must be vectorised (NumPy, orjson) and seeded, so every run produces the same answer key.

