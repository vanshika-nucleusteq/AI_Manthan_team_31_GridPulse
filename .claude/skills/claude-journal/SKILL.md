---
name: claude-journal
description: Use after any meaningful Claude session (architecture, build, test, deploy, SRE) or when someone says "log this", "journal" or "add a journal entry".
---
# Claude usage journal entry

Append one entry to `docs/claude-journal.md` (create it with a title if missing). Ask the user for anything you cannot see. Target 5-8 entries for the whole day, spread across phases.

```
## <n>. <phase> — <one-line task>   (<time>, <person>)
**Prompt (summary):** the ask, with context given, constraints and what was excluded
**Technique:** plan mode / CLAUDE.md rule / skill used / trimmed logs / examples given
**What Claude produced:** 1-2 lines
**How we verified:** test run, count check, manual read, query result
**Correction:** what was wrong or missing, and how we fixed it (write "none" only if truly none)
**Outcome / commit:** <hash or file>
```
At least one entry in the day must show a real correction of Claude's output. Be honest: a correction is evidence of judgement, and judges look for it.
