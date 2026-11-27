---
name: step
description: Use when someone types "/step P<n>" (P1-P13) to run one prompt from the team prompt pack in docs/prompts/ end to end under the CLAUDE.md Autonomy rules.
---
# Run one prompt-pack step

Argument: a prompt id such as `P4`. If it is missing or `docs/prompts/<id>.md` does not exist, list the files in `docs/prompts/` and ask which one.

1. Read `docs/prompts/<id>.md`. The first line names who runs it, when, and the role Claude plays: take on that role for the whole step. The fenced block is the task, word for word.
2. Read `CLAUDE.md` and every file the prompt @-mentions (e.g. `@docs/plan-data.md`). If the prompt invokes a skill (e.g. `/stack-deploy`, `/data-tests`, `/sre-drill`), load that skill too. If it says `[paste ...]`, ask for the pasted input before planning.
3. Present one numbered plan: files to create or change, commands to run, how you will verify (tests, answer-key checks), the branch name (`p<n>-<short-name>`) and the planned commits. List any ambiguity in the card or plan as a question with your suggested answer. Then wait for "go".
4. After "go", follow the CLAUDE.md **Autonomy rules** to the end of the step without asking again:
   - create the branch, implement in small verified commits (feat/fix/test/docs/chore);
   - run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make.ps1 check` and fix failures yourself, up to 3 attempts;
   - merge to `main`, push to `origin main`, add a /claude-journal entry (with any correction made);
   - stop and ask only for the reasons listed in the Autonomy rules.
5. Finish with the 5-line summary from the Autonomy rules.

Side-session prompts (P2, P12, P13) produce artifacts rather than code: skip the branch and merge unless they write files into this repo.
