# Modelling architecture — deciding where a change belongs before writing it

A brief that names the wrong seam produces a diff that works and lives in the wrong file. That is
worse than a failed brief, because it passes its tests and nobody notices for a month. So before
you write a coding brief, spend a few hundred tokens deciding **where** the change goes.

This repo's own history is the argument. Three examples, all real:

- An external coding executor's diff was going to land in `code_improve.py` — the module where
  Mushegh edits his own source with his own tools. It has no isolation: it branches the owner's
  checkout and lets the worker write into it. A coding CLI edits files in its working directory
  and hands back no patch, so the proposal would have been in his tree before the first condition
  had been tested. The right home was a module that gives each brief its own `git worktree`.
- The fleet transport was a WebSocket operator connection for months, with a circuit breaker to
  make the doomed handshake cheap. The breaker was a well-built workaround for a path that should
  not have existed; A2A was the right seam and the breaker's whole subject disappeared with it.
- A library arrived with an SDK and was nearly routed through the executor contract, which bounds
  an **agent** — something that acts on its own judgement. A library is a tool. Routing it through
  the contract would have bought none of its protections and cost all of its ceremony.

## The four questions, in order

**1. What *kind* of thing is this?** The single highest-value distinction, and the one most often
got wrong:

| It is… | Then it is… |
|---|---|
| something that acts on its own judgement | an **agent** — it needs a brief, an acceptance check, a deadline, and a bound |
| something you call and it returns | a **library/tool** — it needs an argument and a return type |
| a published protocol the other side already speaks | a **channel** — use it; do not invent a transport |
| a surface a person looks at | a **design** problem — Open Design, not a coding CLI |

Getting this wrong is how a library ends up with a timeout and a worktree, and how an agent ends
up with no deadline.

**2. Which direction does the data move?** This is the question that decides blast radius. A file
the owner types himself is data he already had; an ingested feed is his history arriving unasked.
The same code reading versus writing are different decisions, and only one of them needs a gate.

**3. What is the smallest thing that can hold this?** Work the ponytail ladder
(`read_skill('ponytail-and-caveman')`). A new module is the *last* option, not the first. Ask, in
order: does it need to exist; does an existing module already own this responsibility; is it a row
in a table rather than a new file.

The best shape in this codebase is the one the executor contract uses: **a table of data plus one
runner.** Adding an executor is a row and a parser, not a module. If your change would be the
fourth near-copy of something, the real change is to turn the three into a table.

**4. What breaks if I am wrong?** Ask the graph, do not guess:

```
graphify affected "<the module you plan to change>" --depth 2
graphify god-nodes --top 10
```

A change to a hub needs a smaller scope and a sharper acceptance check than a change to a leaf.
`read_skill('graphify')`.

## Recording the seam in the brief

The brief should state the seam as a constraint, not leave it to be discovered:

> The fix belongs in `scripts/sync_fleet_roster.py` or nowhere — the roster is **generated** from
> the vault, so editing `src/mushegh/brain/fleet18.json` directly would be overwritten by the next
> sync and would make the packaged copy disagree with the authority.

Notice what that does: it names the file, says why, and names the failure mode of the obvious
wrong answer. An agent given that cannot helpfully do the wrong thing.

## Two invariants this codebase holds, worth copying into any new seam

- **One authority per fact.** When two files can state the same thing, one is the authority and
  the other is generated, with the regeneration command written down and a drift check that
  *reports* a disagreement rather than letting the copy win quietly. "Could not check" and
  "checked and matched" are different states, and only one of them justifies trust.
- **An allowlist, built from nothing.** A denylist is correct until somebody adds a secret to the
  environment, and then it is silently wrong. The same reasoning applies to candidate lists, tool
  surfaces and permitted commands: start empty, add what is needed, and the rule stays true next
  year.

## And the thing that is not architecture

A success message is a claim about control flow. **Verification is a claim about artefacts**, and
only the second one is evidence. This project has produced the same failure three times in two
days — a backup that reported success against a repository it had never read, a timer reading
`active` with no next run, and a sync that logged `sync OK (12 subtrees)` having moved nothing. No
architecture prevents that. Checking the artefact does.
