# GridPulse prompt pack

Prompts P1-P13 from `docs/gridpulse-plan.md` section 9, one file each, copied word for word.
The first line of each file says who runs it, when, and which role Claude plays.

Every prompt casts Claude in the role of the teammate who owns that work, so its answers come with that specialist's priorities and checks. The heading of each prompt shows who runs it, when, and which role Claude plays. One fresh session per prompt, plan mode on, one branch per prompt; after each: check against the answer key, `make.ps1 check`, commit, merge, /claude-journal. "Side session" means a teammate's own laptop, not the repo.

Run one in this repo with `/step P4` (skill `.claude/skills/step/`): Claude reads the prompt and its
@-mentioned files, presents one plan, waits for "go", then follows the CLAUDE.md Autonomy rules.

| Prompt | Member who runs it | Claude acts as |
| --- | --- | --- |
| P0 | Driver | Tech lead and data platform architect |
| P1 | Driver with Navigator | Senior data engineer, synthetic data |
| P2 | UI owner (side session) | UI/UX designer for data dashboards |
| P3 | Driver | DevOps engineer |
| P4, P5 | Driver with Navigator | Senior data engineer, ingestion and time-series |
| P6 | Driver with Navigator | Analytics engineer, consumption and billing |
| P7 | Driver with Navigator | Data scientist, revenue protection analytics |
| P8 | Driver | Data platform engineer, orchestration |
| P9 | QA | QA and test automation engineer |
| P10 | SRE | Site reliability engineer |
| P11 | Driver with UI owner | Streamlit front-end developer |
| P12 | Navigator (side session) | Solution architect and technical writer |
| P13 | Scrum lead (side session) | Scrum master |

## Files

- [P1.md](P1.md): Driver · 0:30 · Claude acts as a senior data engineer (synthetic data)
- [P2.md](P2.md): UI owner · 0:20 · Claude acts as a UI/UX designer (side session)
- [P3.md](P3.md): Driver · 0:45 · Claude acts as a DevOps engineer
- [P4.md](P4.md): Driver · 1:00 · Claude acts as a senior data engineer (ingestion and quality)
- [P5.md](P5.md): Driver · 1:20 · Claude acts as a senior data engineer (time-series)
- [P6.md](P6.md): Driver · 1:45 · Claude acts as an analytics engineer (consumption and billing)
- [P7.md](P7.md): Driver · 2:05 · Claude acts as a data scientist (revenue protection)
- [P8.md](P8.md): Driver · 2:25 · Claude acts as a data platform engineer (orchestration)
- [P9.md](P9.md): QA · from 1:00 · Claude acts as a QA and test automation engineer
- [P10.md](P10.md): SRE · 2:15 · Claude acts as a site reliability engineer
- [P11.md](P11.md): Driver + UI owner · 2:45 · Claude acts as a Streamlit front-end developer
- [P12.md](P12.md): Navigator · 3:15 · Claude acts as a solution architect and technical writer (side session)
- [P13.md](P13.md): Scrum lead · every 30 min · Claude acts as a Scrum master (side session)

## Reusing this pack in another squad

Copy `docs/prompts/`, `.claude/skills/step/` and the CLAUDE.md "Autonomy rules" section, then edit the
prompts' @-mentions and section numbers to match your own plan.
