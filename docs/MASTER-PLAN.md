# Afon & OpenAfon — Master Plan (2026-06-24 snapshot)

> [!warning] **Superseded. Do not plan from this file.**
> The 2026-06-24 plan is gone. Planning moved to **[`docs/ROADMAP.md`](ROADMAP.md)** (40
> milestones), intent moved to **[`docs/DECISIONS.md`](DECISIONS.md)** (62 binding decisions,
> 2026-10-03), and the running engineering log remains **`TODO.md`**, which is the canonical
> roadmap. What is actually built and proven is `docs/systems-plan.json`, rendered to
> `docs/SYSTEMS.md`.
>
> This stub is kept only so old citations resolve. It preserves no current instruction.

**Date of the snapshot:** 2026-06-24. **Collapsed:** 2026-10-03.

## What replaced it

| Question | Now answered by |
|---|---|
| What will be built, and what will never be? | [`docs/DECISIONS.md`](DECISIONS.md) |
| What is actually running? | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| What happens next, in what order? | [`docs/ROADMAP.md`](ROADMAP.md) |
| What does each of the fifty systems do? | [`docs/subsystems/`](subsystems/README.md) |
| What counts as proof? | [`docs/EVIDENCE.md`](EVIDENCE.md) |
| What is built and proven, per task? | `docs/systems-plan.json` → [`docs/SYSTEMS.md`](SYSTEMS.md) |
| What happened, in order, with evidence? | `TODO.md` |
| Why was it built that way? | [`docs/SYSTEMS-DETAILS.md`](SYSTEMS-DETAILS.md) (frozen archive) |

## The history this snapshot replaced

The 2026-06-24 file itself replaced an earlier set — ROADMAP, FINISH-AND-OPENAFON-ROADMAP,
AUDIT, PHASE-VERIFICATION, BENCHMARKS, TESTING, TASK-QUEUE-PLAN, EXPANSION-PLAN, a
multi-device plan, and a deleted `next-steps/` set. All of those are gone; their surviving
content is in the registry and the archive named above.

## Why the body was deleted rather than kept

Three reasons, in order of how much they cost:

1. **It was wrong, and the wrongness propagated.** It asserted a `bench/train_wakeword.py`
   that has never existed in this repo, and that single claim reached four other files
   before a directory listing caught it. `bench/test_doc_paths.py` now fails any roadmap
   citing a path that is not in the tree. A 34 KB document containing known-false claims
   is an active hazard, not an archive — the registry already preserves the task history
   this file was trying to summarise.
2. **It predates the fifty-system registry**, so its own sequencing was obsolete before
   this stub was written.
3. **It predates the 2026-08-12 rename** from `jarvis` to `afon`; paths in it are dead.

## Two corrections that outlive the snapshot

- "Local-first" overstates what this is. The accurate description is **self-hosted state
  with cloud inference** (Jev p=0.77).
- Model assessments are **advisory input**, not authority. De-scoping requires the
  owner's explicit sign-off ([`docs/DECISIONS.md`](DECISIONS.md) D-47). This snapshot was
  written before that rule existed, and the S49 fabrication drop — decided by a model
  score — is being re-signed under it.

## Ground rules that still hold

- No task is done until a repeatable benchmark, test, or live-device check backs it. The
  current bar is stricter: a passing hermetic suite **and** seven consecutive days of real
  use ([`docs/EVIDENCE.md`](EVIDENCE.md)).
- The repository is private. Do not commit or push without an explicit ask.
- Secrets, biometrics and vault contents never leave this machine and never enter the
  public repo ([`docs/DECISIONS.md`](DECISIONS.md) D-57).
