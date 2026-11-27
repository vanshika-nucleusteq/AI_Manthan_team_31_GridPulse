---
name: stack-deploy
description: Use when creating or fixing Docker Compose, Makefile, start scripts or GitHub Actions CI, or when proving a clean one-command start.
---
# One-command stack and CI

1. Plan first: list services, images (pinned versions, open-source), ports, volumes, env vars, start order.
2. Compose in `deploy/docker-compose.yml`:
   - healthchecks on broker and database; `depends_on: condition: service_healthy`
   - init SQL / migrations run automatically; config from `.env` with `.env.example` committed
   - no host paths outside the repo; named volumes
3. `Makefile` targets: `up`, `down`, `reset` (drop volumes), `test`, `lint`, `logs`.
4. CI in `.github/workflows/ci.yml`: install, lint (ruff, black --check), unit tests on every push and PR. Keep it under ~5 minutes; integration tests optional.
5. Prove it:
   - fresh clone → `make up` → stack healthy → data flows → dashboard loads
   - break one test on a branch → CI goes red → screenshot for evidence → revert
6. Update README "How to run" with exact commands and expected result. Log with /claude-journal.
