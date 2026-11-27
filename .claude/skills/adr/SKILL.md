---
name: adr
description: Use when the team needs to make or record an architecture decision (delivery guarantees, storage, partitioning, state, orchestration, tool choice) or asks for an ADR.
---
# Architecture Decision Record

1. Ask for the decision question if it is not clear.
2. Lay out 2-3 real options. For each: how it works, cost in build time today, failure modes, what it means for testing and operations.
3. Challenge the option the team leans towards: give the strongest argument against it.
4. **Stop. The team decides.** Do not pick for them.
5. Write `docs/adr/NNNN-<kebab-title>.md` (next free number):

```
# NNNN. <Title>
Date: <today>  Status: Accepted  Deciders: <names>
## Context
## Options considered
## Decision
## Consequences (good, bad, follow-ups)
## How we will verify it
```
Keep it under one page.
