---
name: mcx-recover
description: "Recover — bounded correction from recorded failure evidence"
aliases: [recover]
---

# mcx recover

Correction is bounded and evidence-carrying. The failure packet is derived from
what is already recorded — nothing is re-diagnosed by guessing, and a retry
never repeats the same request.

## Required Skill Capabilities

- `call_mcp` — `mcx_recover_*`, `mcx_start_recover_dispatch`,
  `mcx_job_status`.
- `ask_user` — when the budget runs out or the packet says a human is needed.
- `maintain_ledger` — keep the retry count per criterion visible.

## Non-skippable gates

- **Do not fix it by hand.** Same reason as Execute: hand edits leave no
  record, and Verify refuses work it has no record of.
- **Do not raise the retry budget.** Two corrections per criterion, and a new
  specification revision resets it. If the budget is spent, that is the signal
  to involve the user.
- **`BLOCKED` and `STALL` are not retryable.** Retrying them burns money and
  changes nothing.

## The loop

1. `mcx_recover_plan` — derives the failure packets. Read them before doing
   anything: they carry the source, a classification, and the error excerpt.
2. `mcx_recover_dispatch` — re-runs the criterion **with the failure evidence
   attached**. On the last attempt in the budget it also tells the worker to
   change approach rather than repeat.
3. Back to the Verify skill. Correction is not completion.
4. `mcx_recover_gate` tells you whether correction is still possible.

`recover dispatch` drives the same coding agent as `execute next` and is just
as long. `mcx_start_recover_dispatch` returns a receipt and
`mcx_job_status` follows it.

## Classifications

| classification | meaning | what you do |
|---|---|---|
| unclassified | an ordinary failure | dispatch a correction |
| `BLOCKED` | something outside the workspace is in the way — missing access, missing dependency | **stop and tell the user what is blocked** |
| `STALL` | the same error three times running | **stop.** A fourth attempt produces the fourth identical error |

A caveat worth stating out loud: a cancelled attempt is recorded as a failure
with a fixed message, so **cancelling the same criterion three times reads as
`STALL`**. If you see a stall the user caused by cancelling, say so instead of
reporting the runtime as stuck.

## When the budget is exhausted

Do not work around it. Show the user:

- which criterion is failing and how many corrections it has had,
- the error excerpt from the last attempt,
- the classification.

Then ask what they want: change the specification (a new Blueprint revision
resets the budget), change the goal (back to Brief), or stop.

## What this Stage does not do

- It does not roll anything back. Failed attempts leave their changes in the
  workspace.
- It does not classify a specification gap. If the real problem is that the
  criteria contradict each other, no amount of correction fixes it — say so and
  go back to Blueprint.
