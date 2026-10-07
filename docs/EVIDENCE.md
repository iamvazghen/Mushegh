# Evidence — what counts as proving it

Written 2026-10-03. This file defines the word "benchmark" as used in
[`docs/subsystems/`](subsystems/README.md), and the bar for calling a task done.

> A passing hermetic suite proves your code agrees with your mocks. That is necessary
> and insufficient. (D-43)

---

## The definition of done

A task is **done** when both hold:

1. the hermetic suite passes, and
2. the owner has used the capability for **seven consecutive days** without manual
   patching.

Not one or the other. A green suite with no field use is a hypothesis. A week of field
use with a red suite is a mess. Neither is done.

## The benchmark ladder

Every goal in every subsystem doc carries a benchmark from this ladder, or says
plainly that it has none. A goal with no benchmark is allowed — an unnamed one is not.
The fifty documents it governs are in [`docs/subsystems/`](subsystems/README.md).

| Tier | Name | What it is | Strength |
|---|---|---|---|
| **B1** | Hermetic test | A named `bench/` script and a threshold, run by the pre-push suite | Necessary. Proves internal consistency only |
| **B2** | Live drill | A written procedure with a pass condition, performed against the running system | Strong. Proves the real path works |
| **B3** | Production tenure | N consecutive days of real use, no manual patching | Strongest. The D-43 bar |
| **B4** | Invariant | A property that must hold for the system to be safe at all — checked in code, and a violation is a hard failure | Structural. Holds regardless of behaviour |
| **B5** | Measurement | A number from a live run: latency, accuracy, rate, cost | Only as good as its method and its last-recorded date |

### Rules for writing a benchmark

- **Name the command or the drill.** `test_doc_paths.py` means something;
  "works reliably" does not.
- **State the threshold.** `≥90%`, `<300 ms`, `0 leaks`, `exactly 3 max`.
- **Record the last measurement and its date**, or write `not yet measured`. A
  benchmark with no number is a wish wearing a target's clothes.
- **Say what the number is measured over.** Ten prompts is not a percentage; forty is
  not a month.
- **B1 alone is never sufficient** to mark a user-visible capability done.

## What does not count as evidence

- **Mocks.** A subsystem whose tests pass only against in-memory fakes is unproven by
  default. This is why 95 records sit at `unverified-import`.
- **An imported claim.** Copied from an earlier plan, never run here. Import is not
  verification; the 2026-09-20 downgrade (p=0.88) exists precisely because the two were
  being confused.
- **A model evaluation.** A score is input to a decision, not proof of a capability
  (D-47).
- **Code existing.** Code-complete and controlling nothing is *dark*, and dark is not a
  status (D-46).
- **A passing registry check.** `systems_plan.py check` proves the plan is internally
  consistent. It proves nothing about the software.

## The evidence vocabulary in the registry

Recorded per task in `docs/systems-plan.json`; rendered into
[SYSTEMS.md](SYSTEMS.md):

| Kind | Meaning |
|---|---|
| `hermetic-test` | Runs in the pre-push suite; a green run is the record |
| `exempt-test` | A real test deliberately outside the suite (live, benchmark, self-referential) |
| `unregistered-test` | A real `bench/` script the hermetic runner does not carry — weaker than registered, weaker than neither |
| `planned-test` | The gate is declared but the test does not exist yet |
| `manual` | Requires a human drill |

`unverified-import` is not in that list on purpose: it is a claim without a run, and it
is labelled so no one can mistake it for proof.

Two more record kinds exist, and neither is proof of anything:

| Kind | Meaning |
|---|---|
| `owner-decision` | A dated instruction from the owner in [DECISIONS.md](DECISIONS.md). Authority over *what gets built* — never evidence that something works |
| `recorded-note` / `migration-checkpoint` | A statement written by whoever did the work. Auditable, not proof |

## Cancelled and deferred tasks do not owe evidence

A task marked `cancelled` will never be done, so no gate has to pass for it — but the
planner refuses a cancellation that does not carry an `owner-decision` record, because
"cancelled" would otherwise be the cheapest way to make a number look better. A task
marked `deferred` is still owed, so it keeps its gate and its place in the denominator;
it simply stops appearing as the next thing to do.

## What still owes evidence

The systems the owner believes are broken, named 2026-10-03, and therefore the ones
whose status rests on the weakest records:

- **S26 Multi-Modal Perception** — suspected broken; B1-only evidence.
- **S46 Predictive Analytics** — now removed as a system (D-28); its floor tasks still
  claim green.
- **S34 Health & Wellness** — half-built, no data source, tools only.

Any of these may be "complete for now" in the dashboard and still be unproven. The
dashboard reports what is recorded; this file decides what a record has to contain.

### What the hardware plan owes

Ten gates are owed to hardware-facing rules. **Seven exist and are green; three do not exist
yet** — and for those three, every benchmark for the 28 devices in [HARDWARE.md](HARDWARE.md)
stays `not yet measured`:

| Task | The gate that would prove it | Why it is not optional |
|---|---|---|
| `28.R4` | `test_blast_radius_refusal.py` | **Exists and green** (29/29, 2026-10-03). The one hardware-adjacent rule already enforced in code |
| `28.R5` | `test_lock_readonly.py` | A smart lock is arriving; D-13 must hold on every integration path. **Still missing** |
| `37.R5` | `test_never_store.py` | **Exists and green** (50/50, 2026-10-04). The D-24 set is enforced at the write boundary and the audit trail withholds what the store refused — the two doors, not one |
| `41.R4` | `test_no_unprompted_feed.py` | **Exists and green** (10/10, 2026-10-04). The unprompted news feed is closed and the seam is asserted with a stubbed registry |
| `18.R4` | `test_tts_local_default.py` | **Exists and green** (14/14, 2026-10-04). `tts_provider` now defaults to local Piper; note the live config still pins cloud, so this is code-correct and machine-not-yet |
| `18.R5` | `test_wakeword_offline.py` | **Exists and green** (11/11, 2026-10-04). The wake path is local and the two dead settings are gone — and the gate found that only 1 of the 7 configured phrases actually loads |
| `36.R4` | `test_credential_inventory.py` | ~15 live credentials, one decision row each (D-62). **Still missing** |
| `26.R5` | `test_no_frame_egress.py` | **Exists and green** (53/53, 2026-10-04). The seam cannot carry a frame and `see()` is not on it — which is a claim about code, not about the cameras, none of which exist yet |
| `43.R5` | `test_room_presence.py` | Presence is a laptop poll today; mmWave changes what the claim can be. **Still missing** |
| `01.R6` | `test_jev_tool_arbitration.py` | **Exists and green** (37/37, 2026-10-03). Jev picks the tool group; the 400ms cap and the silent fallback are what make that safe |

## What the scorecard can and cannot tell you (measured 2026-10-03)

`bench/behavioral_suite.py` reads **59.3/100** overall. Read the per-category medians
before believing the total, because the instrument's shape matters more than the number:

| Needs no credential | | Needs a credential or a mount | |
|---|---:|---|---:|
| Safety | 100 | Knowledge | 29 |
| Calibration | 100 | Combination | 40 |
| Latency | 100 | Honesty | 40 |
| Conversation | 96.5 | Time/Utility | 43 |
| Multi-Device | 88 | Proactivity, Autonomy, Fleet, Modes | 46 |
| | | Memory, Web, Tasks, Channels | 46–50 |

Everything internal scores 88–100. Almost everything with a token scores 40–50, and the
outputs cluster rather than spread. **So a large part of this total is unconfigured
integrations, not brain quality** — which is the same reason S20 and S28 are called dark
rather than finished. And `01.E1`'s 51.5 is a median of **two** cases.

Consequence for this file: a benchmark whose score moves when a credential appears is
measuring configuration. Under D-43 the elite bar is the one that cannot be gamed that
way — thirty days of real use, zero panics, zero data corruption, zero unexpected cloud
egress (D-44). See [DECISIONS.md](DECISIONS.md) D-44 for why E1 and E2 need re-specifying
before they can honestly be chased.

## The standing test

For any capability, the honest question is:

> If this broke at 2:00 AM, would I know from `journalctl`, `sqlite3` and `curl` — and
> would the number I look at be a real one?

If the answer is no, the missing thing is a benchmark, and that is the work.
