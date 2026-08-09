---
name: mcx-verify
description: "Verify — decide on evidence whether the mission is actually done"
aliases: [verify]
---

# mcx verify

Two layers. Mechanical runs the approved verification command and keeps what it
produced. Semantic judges each acceptance criterion against that evidence. Only
this Stage's Gate can say `MISSION COMPLETE`.

## Required Skill Capabilities

- `call_mcp` — `mcx_verify_*`, `mcx_start_verify_semantic`, `mcx_job_status`.
- `ask_user` — when a verdict is uncertain and needs a human.
- `maintain_ledger` — keep per-criterion verdicts visible.

## Non-skippable gates

- **An agent's claim of success is not evidence.** Nothing said in an execution
  attempt counts here. Only what the verification command produced does.
- **Do not declare completion.** Report what `mcx_verify_gate` returned, in its
  words. `MISSION COMPLETE` is a Gate output, not a summary you write.
- **Uncertainty is not failure.** A verdict that is unsure blocks the Gate and
  waits for a human. Take it to the user rather than re-running until it
  resolves itself.

## The order

1. `mcx_verify_mechanical` — runs the approved `verify_command` as a real
   process and stores the output. Re-running invalidates the semantic verdicts
   on purpose: they were judged against the old evidence.
2. `mcx_verify_semantic` — one verdict per criterion, on top of that evidence.
   Long; use `mcx_start_verify_semantic` and poll if you want to stay
   responsive.
3. `mcx_verify_gate`.

## Reading the Gate

`CLEAR — MISSION COMPLETE` requires all of: mechanical passed, every criterion
has a verdict on the current evidence, none satisfied-but-uncertain, and no
suspicion that a criterion was gamed rather than met.

`HOLD` gives the reason:

| reason | what it means | where to go |
|---|---|---|
| mechanical failed | the verification command did not pass | Recover |
| criterion not satisfied | a criterion was judged unmet | Recover |
| verdicts stale | evidence was re-run after judging | run semantic again |
| uncertain verdict | the judge was not confident | **ask the user**, do not re-run |
| reward hacking suspected | the criterion looks satisfied by gaming it | **ask the user** — this is the finding that most needs a human |

The last two are escalations, not errors. Show the reasoning and let the user
decide.

## What this Stage does not check

Say this plainly when it matters, rather than implying the Gate covers more
than it does:

- Side effects of the verification command **outside the workspace** are not
  blocked.
- Constraint violations and non-goal work have **no deterministic check** —
  they are in the judge's input but there is no field for the verdict.
- The workspace revision is not tracked, so "verified against exactly this
  state" is not enforced.

If the user is relying on any of these, tell them it is not covered.
