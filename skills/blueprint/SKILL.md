---
name: mcx-blueprint
description: "Blueprint — turn an approved Brief into an approved, immutable specification"
aliases: [blueprint]
---

# mcx blueprint

Produce a specification whose acceptance criteria are measurable, then get a
human to approve it. Once approved, a revision never changes — a change is a
new revision and a new approval.

## Required Skill Capabilities

- `ask_user` — the User Adoption Gate. Nothing is adopted without it.
- `call_mcp` — `mcx_blueprint_*` tools.
- `run_shell` — the decision trail.
- `maintain_ledger` — keep the QA score, the iteration number, and every
  rejected candidate visible across turns.

## Non-skippable gates

- **No candidate is accepted by default.** Every revision that enters the
  specification was picked by the user, one question at a time.
- **Never approve to get past a low score.** If QA will not pass, that is
  information; take it to the user.
- **Constraints and non-goals are carried verbatim.** The generator is required
  to copy them word for word, and the scope check rejects edits. If QA suggests
  changing one, that suggestion cannot be applied here — say so, and take it
  back to the Brief if it matters.

## The loop

1. `mcx_blueprint_generate` — runs once and establishes the specification.
2. `mcx_blueprint_qa` — returns `iteration`, `revision`, the assessment, and an
   `action`.
3. Branch on `action`:
   - **`done`** → go to Approval.
   - **`continue`** → run the adoption cycle below, then QA again.
   - **`escalate`** → stop. The problem is at specification level and another
     round will not fix it. Show the assessment and offer going back to Brief.
   - **`exhausted`** → the iteration cap is reached. **Do not run another
     round.** Show the *best* attempt — not the last one — with its score, and
     ask the user: accept it below threshold, or go back to Brief.

Tell the user the iteration number from round 3 onward. Show deltas, not the
whole assessment every time.

## Adoption cycle (the REVISE branch)

**Diverge, then structure, then let the user choose, then apply.**

**1 — Collect.** Gather candidate revisions from what you actually have:
- QA findings — structural gaps and contradictions in the specification.
- The Brief — read it back and look for what the specification lost: a
  constraint that got softened, something the user rejected creeping back in,
  nuance the user spent several rounds on that got flattened.

Do not resolve disagreements between the two here. Carry both forward.

**2 — Structure.** Tag each candidate:
- **Convergent** — proposed by more than one source. Strongest signal.
- **Conflicting** — mutually exclusive proposals. **The user decides these,
  not you.**
- **Singleton** — one source only. Keep, mark weaker.

**3 — User Adoption Gate.** Ask with `ask_user`, **single-choice questions
only**, in this order:

1. **Conflicts first**, one question per conflict group, with exactly one
   option per resolution plus "leave unchanged". Asking these first is what
   stops two contradictory revisions from both landing.
2. Convergent candidates as one batch question: apply all / review one by one /
   skip.
3. Singletons as one batch question, same shape.

Every batch question carries a skip option. **Skipping is not accepting a
below-threshold specification** — that is a separate, explicit choice at the
loop boundary.

**4 — Apply.** `mcx_blueprint_revise` takes `draft_file`, not free text: write
the complete revised specification as JSON and pass its path.

```json
{
  "goal": "...",
  "constraints": ["..."],
  "non_goals": ["..."],
  "acceptance_criteria": [
    {
      "description": "...",
      "verify_command": "pytest -q",
      "expected_artifacts": ["src/thing.py"],
      "output_assertion": "..."
    }
  ]
}
```

Start from the current specification and change only what the user accepted —
it is a whole document, so anything you leave out is deleted. `constraints` and
`non_goals` must be carried **word for word**; the scope check rejects the
draft otherwise, which is the check doing its job, not an obstacle to work
around.

Keep every rejected candidate in your ledger so the next round does not
re-propose it.

## Decision trail

After each round, append to `~/.mcx/decisions/<mission_id>.md` (create the
directory if needed):

```markdown
## Iteration N — score X.XX

- [A] [QA + Brief] sharpen criterion 3 — **accepted**
- [B] [Brief] re-add the "single user only" constraint — **accepted**
- [C] [QA] add a retry criterion — rejected

### Changed
- criteria[2]: "easy to use" → "first-time user finishes in under 3 clicks"
```

This is where "who accepted what" lives. Mission Control records the approval,
not the person — the trail is what makes the decision auditable. If the file
cannot be written, put the same block in your reply instead of dropping it.

## Approval and handoff

1. Show the user the complete specification. Not a summary.
2. Ask for approval in their own words.
3. `mcx_blueprint_approve` with their statement. If QA never passed and the
   user chose to accept anyway, add `accept_below_threshold` — approving a
   below-threshold specification without it is refused, and that refusal is
   there so the acceptance is recorded as a decision rather than slipping
   through.
4. `mcx_blueprint_gate`. `CLEAR` → hand off to the Execute skill.

Approval binds to the scored current revision. Revising after approval makes it
stale, and the Gate will say so.
