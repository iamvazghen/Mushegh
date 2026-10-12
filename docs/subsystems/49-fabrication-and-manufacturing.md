# S49 — Fabrication & Manufacturing Control

> **One line:** a decision record — physical vanity scope belonging in a standalone slicer/CAD
> utility, not in an ambient assistant; dropped 2026-09-20 and re-signed by the owner
> 2026-10-03.
> **Status:** **dropped 2026-09-20, re-signed by the owner 2026-10-03** (D-47, D-48) — physical vanity scope belonging in a standalone slicer/CAD utility; the decision record is this document · **Registry:** S49 · 0/0 floor, 0/0 raise, 0/0 elite (all three tasks `cancelled`)
> **Milestones:** M01, M07 · **Decisions:** D-47, D-48, D-63, D-70, D-42, D-46

> This document exists so the system is not re-added by accident, and so the governance lesson
> is not lost with it. It is not a roadmap.

## Purpose

S49 was going to control a 3D printer: a decision record naming the first machine and its
control surface, a machine-control tool at the highest confirm grade, and a dry-run or
simulation path before any live command.

**It is out.** Physical vanity scope belongs in a standalone slicer/CAD utility, not in an
assistant that listens all day (D-48). A slicer wants a mesh, a printer profile and a
nozzle-temperature table; an ambient assistant has none of those and would have to guess at
all three, and a guess that heats a nozzle or moves an axis is not a style disagreement.

**The governance part is the part worth keeping.** S49 was dropped on 2026-09-20 on the
strength of a model score (p=0.75). D-47 then said, in the same charter, that AI evaluations
are **advisory input and de-scoping requires the owner's deliberate sign-off**. The owner
re-signed the drop on 2026-10-03. A model that can cancel work unilaterally will eventually
cancel the wrong work, and the fix is procedural: the score is evidence, the owner is the
authority.

**The named trigger for revisiting:** the owner owns a printer, and wants a slicer it can
call. Until both are true, this stays closed.

**The first half is now met, and D-70 recommends keeping the drop.** The owner owns a Prusa
CORE One, a fire-suppression ball, a filament dryer and a maintenance kit — the trigger's
first half, in full. The second half is not met, and the hardware itself supplies the reason:
nothing in the inventory suggests the owner wants a slicer Mushegh can call. A printer in a
workshop is a tool for making brackets. A printer Mushegh can drive is a safety surface with a
heated bed and moving axes, in a house where D-13 already refuses door locks. The charter's
instinct was right and the new hardware confirms it. **D-70 is a recommendation awaiting the
owner's sign-off under D-47, not a decision in force** — and that is the same governance
point this document already exists to make.

**What the printer needs regardless of S49:** fire suppression for unattended prints, dry
filament storage so hygroscopic filament does not wreck dimensional accuracy, and **no print
running overnight while the house is empty**. That last one is the 2 AM question with a new
subject — an unattended machine, unsupervised by the UPS, in a house nobody is in.

## Structure

There is nothing to point at, which is the cleanest possible removal — verified, not assumed:

    grep -rniE "gcode|slicer|octoprint|klipper|filament|printer" src/mushegh/    # 0 matches, 2026-10-03

| Registry row | What it was | State |
|---|---|---|
| `49.F1` | a decision record naming the first machine, its control surface and its safety envelope; the gate was the decision note existing in the vault and being cited here | `cancelled` with an `owner-decision` record (D-47, D-48) |
| `49.F2` | a machine-control tool entering the confirm tier at the highest grade, physical-presence only; the gate was `bench/test_confirm_tier_documented.py` [physical-presence grade] | `cancelled` — the gate exists for S36 and does not need this row |
| `49.F3` | a dry-run or simulation path before any live command; the gate was a **planned** `test_fabrication_dryrun.py` | `cancelled` — the file was never written and never should be |

Two registry leftovers are worth noting, both cheap: the system still carries `dark: true`
in `docs/systems-plan.json` although it has no code and no live tasks, and M07 still lists
S49 among the six dark systems to settle. M01's acceptance line — a decision record and no
open fabrication tasks — is now satisfied by this document and the 2026-10-03 cancellations.

The hardware that triggered this review (H7) is a Prusa CORE One with a fire-suppression
ball, a filament dryer and a maintenance kit, in the workshop. Read under D-63 — local,
placed, read-or-actuate — the printer is local and its placement is a workshop, and it fails
the third question for every use Mushegh would have: it is the most consequential actuator in
the house, and D-13's refusal of it is not a configuration setting. Nothing in that inventory
is a repo path, and nothing in it changes the grep above.

## Goals — anti-goals

1. No machine-control handler, no G-code path, and no printer, nozzle or filament vocabulary
   anywhere under `src/mushegh/`.
2. No "print this for me" routing, and no registry entry that reads as an open fabrication
   task.
3. The drop stands on the owner's signature, not on a model score (D-47).
4. If the trigger is ever met, it returns as a **tool** in an existing domain with the
   physical-presence grade attached (D-13, D-14) — not as a fifty-first system (D-42).

## Benchmarks

These are deletion gates. Each one **fails** if the system reappears.

| Anti-goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `grep -rniE "gcode\|slicer\|octoprint\|klipper\|filament" src/mushegh/` | 0 matches | **0 matches**, checked 2026-10-03 |
| 2 | B1 | `python scripts/systems_plan.py check` | 3 tasks read `cancelled`, 0 read `open`, and every cancellation carries an `owner-decision` record | last run 2026-10-03 as part of the reconciliation |
| 3 | B4 | `docs/DECISIONS.md`, the D-48 row | the drop is recorded as re-signed by the owner with a date, and the reason is the owner\'s own, not a score | holds today: D-48 exists and D-47 states the rule |
| 4 | B4 | the trigger | **half met** — the owner owns a printer; wanting a slicer it can call is not established, so the second half is not | no measurement needed; the condition is a fact about the house. D-70 recommends staying dropped, pending the owner's sign-off (D-47) |

There is no accuracy benchmark here, and there should not be: a benchmark that can only be
run against hardware the system was cancelled for would be a commitment wearing a target's
clothes.

## Failure modes

**Re-added as a feature, from the friendly direction.** The likely trigger is the owner
mentioning a printer in passing — and that trigger is no longer hypothetical, because the
printer is on the shelf. Someone concludes that a 3D-printing integration is a small,
charming addition to an assistant that already reaches the network:

    grep -rniE "gcode|slicer|octoprint|klipper|filament" src/mushegh/
    python -c "import json;d=json.load(open('docs/systems-plan.json',encoding='utf-8'));print([(t['id'],t['state']) for s in d['systems'] if s['id']=='S49' for t in s['tasks']])"
    python scripts/systems_plan.py check

**A model cancels it a second time, and that one sticks.** The D-47 failure, and the reason
the re-signature exists at all. The tell is a status change with an `owner-decision` record
that cites a score rather than a decision:

    python -c "import json;d=json.load(open('docs/systems-plan.json',encoding='utf-8'));print([s['status'] for s in d['systems'] if s['id']=='S49'])"
    grep -n "D-48\|D-47" docs/DECISIONS.md

**The `dark: true` flag outlives the code.** S49 is still listed among the six dark systems
M07 has to settle, and `docs/SYSTEMS.md` still carries it in its dark table — though that
file's systems table already records the re-signed drop, so the two tables disagree. A
system with no code and no live tasks should leave the dark list rather than sit on it:

    python -c "import json;d=json.load(open('docs/systems-plan.json',encoding='utf-8'));print([(s['id'],s.get('dark')) for s in d['systems'] if s['id'] in {'S49','S50'}])"
    grep -n "S49" docs/ROADMAP.md docs/SYSTEMS.md | head

**The planned dry-run test is written anyway.** `49.F3` named `test_fabrication_dryrun.py` as
a planned gate. A planned gate with a cancelled row is a green row waiting to happen:

    ls bench/test_fabrication_dryrun.py

## Open questions

1. Should the `dark: true` flag be cleared now, and S49 dropped from M07's list of six? The
   code is gone, the tasks are cancelled, and the milestone is spending an owner decision on
   a system that no longer exists.
2. If the trigger is ever met, does the machine control live in a separate repository beside
   the slicer — which is what D-48's reasoning implies — or as a gated tool in this brain?
   The two have very different security boundaries and D-42 decides it, not taste.
3. Is the 2026-09-20 model score (p=0.75) recorded anywhere durable? The decision is sound
   without it, but "a model proposed this and the owner signed it" is a governance pattern
   worth having written down the first time it happens again.
