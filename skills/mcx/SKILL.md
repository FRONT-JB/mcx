---
name: mcx
description: "Use Mission Control when a prompt says `mcx`, `mcx brief`, `mcx blueprint`, `mcx execute`, `mcx verify`, or `mcx recover`; coordinate a coding mission through Brief, Blueprint, Execute, Verify, and Recover."
---

# mcx

> **mcx — coordinates AI coding missions. Executed is not verified.**
>
> Mission Control is not an AI. It does not generate or review code.
> It coordinates missions.

This skill owns **the order**. Each Stage skill owns what happens inside one
Stage. Mission Control owns the verdicts — you never overrule one.

## Required Skill Capabilities

- `ask_user` — put human-judgment questions to the user through the runtime's
  question surface. Mission Control never asks; it only exposes.
- `call_mcp` — call `mcx_*` tools.
- `run_shell` — fall back to the `mcx` CLI, and write the decision trail.
- `inspect_code` — answer repo-local factual questions from the files instead
  of asking the user.
- `maintain_ledger` — keep the current mission id, Stage, and open blockers
  visible in the conversation.

## Usage

```
mcx <what you want built>
```

**Trigger keywords:** "start a mission", "mcx", "mission control"

## Tools and the CLI are the same thing

Every tool maps to a CLI command by name — `mcx_brief_ask` is `mcx brief ask`,
`mcx_verify_gate` is `mcx verify gate`. Both go through the same dispatch, so
mission state, the command ledger, and Stage routing are identical either way.

Prefer the `mcx_*` tools. If they are not registered, run the CLI with the same
arguments; nothing about the mission changes.

**`mission` is required on every call.** Mission Control does not remember a
"current mission" for you — the CLI keeps a convenience pointer, the MCP server
does not. Carry the id yourself and keep it visible.

## Exit codes — `HOLD` is not a failure

| exit | meaning | what you do |
|---|---|---|
| 0 | success, or Gate `CLEAR` | continue |
| 2 | the command ran fine, the **verdict** is negative (`HOLD`, QA not PASS) | read the reasons, act on them, **do not retry** |
| 1 | error, contract violation, blocked entry | fix the cause |

Over MCP the same split arrives as `is_error=false` with
`result_type: "hold"`. **Retrying a `HOLD` changes nothing** — a Gate is a
judgment about state, not a flaky call. Change the state or ask the user.

## The order

```
brief      start → ask/answer loop → assess → audit → approve → gate
blueprint  generate → qa loop → approve → gate
execute    next (repeat) → gate
verify     mechanical → semantic → gate    →  MISSION COMPLETE
                                    ↓ HOLD
recover    plan → dispatch → gate → back to verify
```

Rules that hold across the whole run:

1. **Never skip a Gate.** A Gate `CLEAR` is the only legitimate way out of a
   Stage. If a Gate says `HOLD`, the next step is in its `blocking_reasons`.
2. **Never approve on the user's behalf.** `brief approve` and
   `blueprint approve` record a human decision. Ask, then record what they
   said.
3. **Never write the code yourself.** You have editing tools; this workflow
   does not use them. `execute next` dispatches the work so that it is
   recorded, and Verify refuses work it has no record of.
4. **Report `MISSION COMPLETE` only when `verify gate` says it.** No other
   command can declare success, and neither can you.

## Running it

1. Start with the Brief skill. Do not draft a specification first — the whole
   point is that ambiguity is removed before anything is written down.
2. At each Stage boundary run that Stage's `gate` and read the outcome.
   `CLEAR` moves on; `HOLD` gives you the work.
3. Run `mcx_status` whenever the user asks where things stand, or whenever you
   have lost the thread. It shows the Stage, blockers in their **original
   wording**, and the call count. It never advances anything.
4. When `verify gate` returns `HOLD`, go to the Recover skill. When it returns
   `CLEAR — MISSION COMPLETE`, tell the user and stop.

## Long commands

`execute next`, `recover dispatch`, and `verify semantic` drive real work and
can run for many minutes. Each has a `mcx_start_*` twin that returns a receipt
immediately:

```
mcx_start_execute_next  →  { "job": "<mission>#<n>", "state": "running" }
mcx_job_status          →  running / completed / hold / failed / cancel_requested
mcx_cancel_job          →  asks the running process to stop
```

Use the twin when you want to stay responsive to the user, and poll
`mcx_job_status`. Use the plain tool when you are willing to wait.

## What Mission Control will not do for you

- It will not ask the user anything. Blocking questions come back as data; you
  relay them.
- It will not adopt a revision. Candidates are proposals until the user picks
  one.
- It will not tell you the mission is done. Only `verify gate` does that.
