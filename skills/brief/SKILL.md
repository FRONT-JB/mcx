---
name: mcx-brief
description: "Use for `mcx brief \"work to do\"` or a request to start or continue a Mission Control Brief; remove ambiguity from a coding intent until it can be specified."
---

# mcx brief

Turn *"build me X"* into something precise enough that a specification can be
written without guessing. One question at a time, and the user's answers are
the only source of decisions.

## Required Skill Capabilities

- `ask_user` — every question in this Stage goes to the human.
- `call_mcp` — `mcx_brief_*` tools.
- `inspect_code` — answer repo-local factual questions from the files.
- `run_shell` — CLI fallback and the decision trail.
- `maintain_ledger` — keep the ambiguity score, round count, and open items
  visible between turns.

## Non-skippable gates

- **Never answer a decision question yourself.** `--authority decision` means a
  human decided it.
- **Facts from the repository are observations, not decisions.** Read the files
  and submit them with `--authority observation`.
- **`brief gate` returning `CLEAR` is not the end of the Stage** — it is
  permission to hand off. `brief audit` must have run and be satisfied first.
- **The user approves in their own words.** `brief approve <statement>` records
  a human statement; do not invent one.

## The loop

1. `mcx_brief_start` with the user's intent. Keep the returned `mission_id`
   visible from here on.
2. `mcx_brief_ask` → one question comes back.
3. **Decide who should answer it:**
   - The answer is in the repository (test runner, language version, existing
     conventions) → read the files yourself and submit
     `mcx_brief_answer --authority observation` with what you found. Say where
     you found it.
   - The answer is a decision, a preference, or a trade-off → put it to the
     user with `ask_user`, then submit their answer with
     `--authority decision`.
   - **When unsure, ask the user.** A wrong observation becomes a requirement
     nobody agreed to.
4. `mcx_brief_assess` to see the clarity picture. Repeat from step 2 until it
   reports the closing conditions are met.

Anything the user states that is not an answer to the open question —
a constraint, a non-goal, something out of scope — goes in with
`mcx_brief_candidate`. Unresolved candidates block the Gate on purpose;
resolve them with `mcx_brief_resolve` once the user has said which way.

## Closure audit

`mcx_brief_audit` runs three independent lanes and returns
`blocking_questions`.

**Relay them verbatim.** Do not summarize, merge, or soften them — the wording
is the finding. Ask them one at a time with `ask_user`, and submit each answer
with `mcx_brief_answer --question "<the blocking question>"` so it is recorded
against the question it belongs to.

Re-run the audit after answering. It is normal for it to take several rounds.

## Approval and handoff

1. Show the user what the Brief now says — goals, constraints, non-goals, open
   items. Not a summary of the conversation: the recorded content.
2. Ask whether it is right. If not, keep going; you are not finished.
3. `mcx_brief_approve "<what the user said>"`.
4. `mcx_brief_gate`. `CLEAR` → hand off to the Blueprint skill.
   `HOLD` → the reasons say what is missing; go do that.

Approval is bound to the current revision. If an answer arrives after approval,
the approval goes stale and must be taken again — that is intended, not a bug.

## When the Gate says HOLD

Read `blocking_reasons` and act on them literally. Common ones:

| reason | what it means |
|---|---|
| clarity below threshold | keep asking; the intent is still vague |
| current revision not approved | the user has not approved this version |
| unresolved material item | a candidate is still `needs_confirmation` or `conflicting` |
| closure audit not satisfied | `mcx_brief_audit` has open blocking questions |

Retrying the Gate will not change any of them.
