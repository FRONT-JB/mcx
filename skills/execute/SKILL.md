---
name: mcx-execute
description: "Use for `mcx execute` or a request to continue Mission Control execution; run the approved specification one acceptance criterion at a time."
---

# mcx execute

Work is dispatched one acceptance criterion at a time, under the approved
specification, and every attempt is recorded. **Executed is not verified** —
finishing this Stage means the work exists, not that it is correct.

## Required Skill Capabilities

- `call_mcp` — `mcx_execute_*`, `mcx_start_execute_next`, `mcx_job_status`,
  `mcx_cancel_job`.
- `ask_user` — only when something needs a human decision; this Stage is
  otherwise unattended.
- `maintain_ledger` — keep which criteria are done and which are open visible.

## Non-skippable gates

- **Do not write the code yourself.** You have editing tools. Using them here
  produces work with no record, and Verify refuses work it has no record of —
  the mission would stall with the files already changed.
- **Do not retry a `HOLD`.** Execute's Gate reports a state, and the state does
  not change because you asked twice.
- **Do not decide the work is good.** That is Verify's job, on evidence.

## The loop

1. `mcx_execute_next` — dispatches the next unexecuted criterion, waits for it,
   records the attempt.
2. Repeat until it reports there is nothing left.
3. `mcx_execute_gate`. `CLEAR — Clear for Verify` → hand off to the Verify
   skill.

Criteria run in declaration order and a failure stops the run. That is
deliberate: a later criterion usually assumes the earlier one landed.

## Long runs

`execute next` drives a real coding agent and can take many minutes — the
silence timeout alone is 900 seconds. To stay responsive:

```
mcx_start_execute_next  →  { "job": "<mission>#<n>", "state": "running" }
```

Poll `mcx_job_status` with that job id. States are `running`, `completed`,
`hold`, `failed`, and `cancel_requested`.

If the user wants to stop, `mcx_cancel_job`. The running process is actually
terminated, and the attempt closes as a failure — **there is no separate
"cancelled" state yet**, so tell the user that a cancelled criterion looks like
a failed one in the record. Cancelling the same criterion three times will make
Recover read it as a stall.

Do not poll in a tight loop. Check, report progress to the user, and come back.

## When the Gate says HOLD

| reason | what it means |
|---|---|
| attempt still open | a dispatch never recorded a result — a crash or a kill. There is no cleanup path for this yet; report it |
| criterion unexecuted | a criterion in the current revision was never dispatched |
| criterion failed | an attempt failed. This is Recover's input, not something to retry here |

For a failure, go to the Recover skill. Do not re-dispatch the same criterion
from here — Recover exists so that the retry carries the failure evidence
instead of repeating the same request.
