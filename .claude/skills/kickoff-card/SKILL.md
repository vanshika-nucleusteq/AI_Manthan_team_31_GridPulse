---
name: kickoff-card
description: Use at the start of the hackathon when the use case card is revealed, or when the team asks to restate the problem, find gaps, slice scope or draft the ideation document.
---
# Kick-off: from card to plan

Input: the use case card text (pasted or a file path).

Do these in order and stop after each for the team's answer. Do not write code.

1. **Restate** the problem in 3 sentences: who hurts, what is slow or wrong today, what "done" looks like.
2. **Gaps and risks**: list ambiguities, missing numbers and risky parts as a table (item · why it matters · options). The team decides every answer; record decisions.
3. **Slice**: split must-haves from stretch. Propose the thinnest end-to-end slice that touches every layer (source → process → store → dashboard) and can run by hour 2.
4. **Big decisions**: name the two decisions that most deserve an ADR (e.g. delivery guarantee, state/watermark, batch vs stream). Hand them to /adr.
5. **Owners**: map each must-have to an owner role and a checkpoint on the clock.
6. Write `docs/ideation.md`: problem, consumers, options considered, chosen approach and why, out of scope.

Remind the team to log this session with /claude-journal.
