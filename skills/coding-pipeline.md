# The coding pipeline — which tool gets the work, and why it is not your choice

Vazghen's direction, 2026-10-11. Read this **before** you write a coding brief, because the first
decision is not how to phrase it, it is where it goes.

## The split: one question decides it

**Is this about what the thing looks like, or about what it does?**

| The work | Where it goes |
|---|---|
| Websites, landing pages, UI, UX, layout, design decisions, visual direction | **Open Design MCP** — `read_skill('prompting-open-design')` |
| Everything else that touches code: backend, APIs, data, scripts, tests, git, infra, refactors, bug fixes | **the coding chain** below |

Open Design concerns itself **only** with frontend. A coding CLI will happily rewrite a landing
page and produce something that works and looks wrong — that is the exact failure the split exists
to prevent. `executors.resolve()` refuses a `Domain.FRONTEND` brief rather than letting it fall
through, so if you try it you get a sentence pointing you here, not a diff.

A job with both halves is **two briefs**, not one: the design surface to Open Design, the logic
behind it to the chain. Say so out loud when you split one — Vazghen asked for one thing and is
getting two pieces of work.

## The chain, in his order

1. **Claude Code** (`claude -p`) — the main coding development tool. Everything starts here.
2. **mcode** (MiniMax Code, `mcode exec`) — the **first** fallback.
3. **Mistral Vibe** (`vibe -p`) — the **second** fallback.

`executors.CODING_CHAIN` is that tuple, and three things follow from it that you do not get to
renegotiate:

- **The order is a decision, not a preference.** `pick()` deliberately does not arbitrate on
  coding: a model allowed to prefer the second entry has quietly replaced his choice, and would do
  it invisibly, because an executor choice is not reported to him.
- **Fallback means on failure.** mcode is tried when Claude Code *failed* — a non-zero exit or a
  parser verdict, never "it looked like it struggled". `dispatch_chain()` owns that walk.
- **A deadline does not fall back.** If the first one timed out it may still be writing in that
  worktree; handing the same brief to the next one is how two agents edit one tree.

A coding CLI that is not named in the chain is not a candidate at all. If you add one, add the
name — the drop is logged, loudly, precisely so an added executor cannot vanish in silence.

## What you owe every coding brief

The brief is the whole interface: the executor sees the text and the repo, and never your
environment, the vault, or a credential. So:

- **An acceptance check, always.** A brief with no way to tell "done" is refused before dispatch,
  and that refusal is correct — an un-checkable brief is not a small brief, it is an unverifiable
  one. Name the test, the command, or the observable fact.
- **The repo path.** A coding brief without one is refused.
- **A deadline.** A delegation with no deadline is never late.
- **Architecture before instructions.** `read_skill('architecture-modelling')` — a brief that
  names the wrong seam produces a diff that works and belongs in the wrong file.

## What happens to the result

Nothing, until he says so. The executor produces a **transcript and a diff**; it never lands
anything. A dedicated branch, a green suite, no schema migration and his explicit approval are
what come next, and that path is `code_improve.py` / `executors/landing.py`, not the executor.

Report the pipeline honestly when it mattered: *"Claude Code failed on the import, mcode did it"*
is useful. Reporting a clean run that took two tries is not.

## Per-tool prompting

Each CLI rewards a different brief shape, measured from its own `--help` on this machine:

- `read_skill('prompting-claude-code')`
- `read_skill('prompting-mcode')`
- `read_skill('prompting-mistral-vibe')`
- `read_skill('prompting-open-design')`
- `read_skill('ponytail-and-caveman')` — the discipline that keeps the diff small
- `read_skill('graphify')` — read the structure before you read the source
