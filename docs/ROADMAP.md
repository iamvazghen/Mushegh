# Roadmap — 40 milestones, 8–10 hours a week

Written 2026-10-03, from the owner interview. This replaces task-granularity planning
(D-45): 403 micro-tasks became administrative overhead for one maintainer, so the
planning surface is now **~40 milestones**, each with a benchmark and a rough cost.

**The registry keeps the history.** `docs/systems-plan.json` and
[SYSTEMS.md](SYSTEMS.md) remain the record of what was built and proven, at task
granularity. This file is what to work on next, at milestone granularity.

**Hardware has its own sequencing authority.** [HARDWARE.md](HARDWARE.md) owns the order
in which 28 devices get touched, because the order is a property of the house, not of the
software. Where the two overlap, this table names the milestone; where the hardware
contradicts the charter, HARDWARE.md §9 names the conflict rather than resolving it in
silence.

**Capacity is the arbiter.** 8–10 hours a week (D-46). Dark systems first, speculative
elite work last, and deletion before construction. Total ≈ 156 hours of build work —
roughly 16–19 weeks at capacity, before M40 which is elapsed time, not effort.

---

## The north star

The acceptance scenario, from the owner's own description of a good Tuesday. Every
milestone exists to make this unremarkable:

> 07:30 — a silent summary on the phone: weather, sleep, three priorities.
> 08:30 — a spoken phrase triggers focus mode; lighting adjusts, notifications mute.
> 09:00–12:30 — deep work; quick spoken thoughts and tasks route into the daily note
> **without interrupting**.
> 13:00 — a brief spoken check-in on the afternoon.
> 14:00–17:30 — development; Mushegh runs tests and local scripts on request.
> 18:00 — a concise markdown wrap-up log; equipment powered down.
> Evening — zero unprompted interruptions unless something is genuinely unsafe.

The two hardest constraints in that paragraph are *without interrupting* and *without
prompting*. Everything below is one or the other.

---

## Phase 0 — Subtract (M01–M08) · ~30 h

**The cheapest progress available is deletion.** Every milestone here removes work
rather than adding it, and the first five are decisions the owner has already made.

| ID | Milestone | Systems | Done when | h |
|---|---|---|---|---|
| M01 | Re-sign the S49 drop; resolve the three open floor tasks that contradict it | S49 | Registry shows a decision record and no open fabrication tasks (D-47, D-48) | 1 |
| M02 | Cancel the Postgres migration and delete the scaffolding | S30 | `postgres_client.py`, `postgres_vectors.py`, `store_migration.py` gone; no `postgres` import remains under `src/mushegh/`; 30.F1/R5–R9 cancelled (D-02) | 3 |
| M03 | Delete the recommendation engine | S15 | No handler proposes unprompted content; a test asserts it stays deleted (D-27) | 2 |
| M04 | Delete the graph relation layer | S24, S30 | Edge indexing gone; 607 inferred edges dropped; recall latency holds or improves; markdown still wins every disagreement (D-26, D-22) | 6 |
| M05 | Remove ML forecasting | S46 | `forecast.py` deleted or honestly renamed; no time-series model in `src/mushegh/` (D-28) | 2 |
| M06 | Cancel inventory; narrow finance to market alerts | S47, S40 | No transaction ingest path exists anywhere; a watched-symbol alert still works (D-12) | 2 |
| M07 | Settle every dark system: wire, complete, or delete | S20, S28, S34, S35, S49, S50 | Each of the six ends in one of the three fates, on the record (D-46) | 10 |
| M08 | Make this file the planning surface | all | The registry is history, not the to-do list; ~40 milestones are the plan (D-45) | 4 |

**M07 needs one owner decision per system, not engineering.** Three are still open and
are listed in [REGISTRY-RECONCILIATION.md](REGISTRY-RECONCILIATION.md) §F.

---

## Phase 1 — Voice, the part that must be excellent (M09–M18) · ~34 h

English flawless, German clean (D-16). This is the product; everything else is
plumbing. Each of these has a number attached, because "feels responsive" is not a
measurement.

| ID | Milestone | Systems | Done when | h |
|---|---|---|---|---|
| M09 | Re-enrol the voice profile on good audio | S08 | B5: ≥ the recorded threshold cosine similarity on 20 held-out utterances; enrolment passes the SNR floor. **This is the gate for S08–S11** | 3 |
| M10 | Enrol on ArcFace; retire the legacy LBP reference | S09 | B2: enrol and match 10/10 at desk lighting, with backlight and partial profile cases recorded | 2 |
| M11 | Raise the speaker threshold; ship the three-way verdict | S10 | B1: 0 false-owner matches in 100 impostor trials; "unsure" routes to a soft path, never to a refusal or a grant (D-15) | 4 |
| M12 | Cut barge-in to under 350 ms | S18 | B5: p95 from `latency_meter.py` under 350 ms, down from the measured ~700 ms worst case (D-49) | 6 |
| M13 | End-to-end latency: laptop <300 ms, phone <500 ms | S18, S01 | B5: measured over 30 utterances per device, method and date recorded (D-35) | 5 |
| M14 | Reject marginal audio; offer push-to-talk; run the wake word on-device | S18 | B1: a noise-floor sweep admits no false wake; the PTT path always works (D-56); the wake fires with all egress blocked and no cloud key (`18.R5`, D-19) | 4 |
| M15 | Reduce the language matrix to English and German | S01, S18 | B1: matrix reduced; EN ≥95% intent accuracy, DE ≥90%, the other four no longer claimed (D-16) | 4 |
| M16 | Local TTS by default, cloud as opt-in | S18, S02 | B1: default config local; no outbound audio at 3 AM; cloud path degrades cleanly (`18.R4`, D-17) | 3 |
| M17 | Kill trailing; flat and corrective on error | S25, S01 | B1: no trailing offer in 50 replies; error style asserted by test (D-20) | 2 |
| M18 | Make uncertainty audible | S01, S45 | B1: an uncertain answer carries a hedge; S45 reports confidence where it varies (D-52) | 2 |

**M09 is the blocker.** The voice profile is measurably weak and face enrolment has
never run on the current backend, so everything downstream of speaker ID is being
measured against a weak reference. It is also the dullest task here — acoustic
enrolment needs physical quiet, calibration and edge debugging, which is exactly why it
has been avoided.

---

## Phase 2 — The silent-ok loop (M19–M25) · ~33 h

The smallest thing that proves the whole thing works: speak at the desk, get an
accurately parsed task with its deadline in the daily note, and toggle the desk lamp
without latency. Everything in this phase is on the whitelist (D-07) — no confirmation
is required, and none is asked for.

| ID | Milestone | Systems | Done when | h |
|---|---|---|---|---|
| M19 | Speak → task + deadline → daily note | S07, S30, S33 | B2: 20 spoken tasks produce 20 correct note entries, 0 lost, 0 duplicated (the north-star loop) | 6 |
| M20 | Lamp toggle, no latency, over Home Assistant | S28, S13 | B2: token installed; 50 toggles at p95 <500 ms; the connection is verified live, not mocked (D-07) | 4 |
| M21 | Structured task capture with real deadlines | S33, S16 | B1: a spoken deadline lands as a date; dependencies surface as "waiting on" | 5 |
| M22 | Calendar two-way sync with conflict highlighting | S21 | B2: CalDAV token installed; an over-constrained day preserves pinned events and names the conflict | 6 |
| M23 | Reminder delivery inside the interruption budget; no unprompted feed | S13, S14, S41 | B1: never more than 3 audio interruptions a day; exactly 0 inside a focus block; a refusal is logged as a negative sample (D-29, D-31); no proactive signal reaches delivery without a prior request (`41.R4`, D-34) | 4 |
| M24 | Workday wrap-up log; morning brief on trigger | S17, S30 | B2: fires on first interaction, renders silently, speaks only when asked; 18:00 produces a concise markdown log (D-33) | 4 |
| M25 | Goals, and stall detection without nagging | S33 | B1: a stalled objective raises one counted signal, not a reminder stream | 4 |

---

## Phase 3 — Trust and proof (M26–M33) · ~33 h

This is what makes the promise in [DECISIONS.md](DECISIONS.md) keepable: nothing
important slips through the cracks, and private data never leaves hardware the owner
controls. Each milestone closes a specific way that promise can be broken.

| ID | Milestone | Systems | Done when | h |
|---|---|---|---|---|
| M26 | The value-precedence test suite | S44 | B1: one test per value conflict; Safety > Privacy > Honesty > Helpfulness is proven, not asserted in a prompt (D-10) | 4 |
| M27 | Blast radius enforced in code | S36, S03, S37, S28 | B1: door locks, breakers, recursive deletes and external dispatch all refuse — one test each; a `lock` or `garage_door` request has **no confirmation path at all** (`28.R4`, D-13, hermetically green 2026-10-03 — the seven-day bar is still owed), while alarm, cover and climate stay confirm-gated | 5 |
| M28 | One confirmation per sensitive mutation | S36, S29 | B1: an approval never carries to the next action (D-09) | 4 |
| M29 | Retention: 30-day expiry and the never-store list enforced | S30, S37 | B2: a live rotation deletes ephemeral telemetry, turns and scratchpads; curated notes survive; each never-store class is **refused at the write boundary** (`37.R5`, D-21, D-24) | 5 |
| M30 | Tombstones instead of silent wipes; a verifiable audit trail | S30, S45 | B1: a superseded memory is absent from recall and present in the audit log (D-25); the audit file carries an integrity check a reader can run without the framework, or "tamper-evident" is struck everywhere (`45.R10`) | 4 |
| M31 | Seven-day tenure on the core loop | S07, S30, S28 | B3: seven consecutive days of real use, zero manual patches — the D-43 bar | 5 |
| M32 | Backup, verify, and restore what matters | S50, S30 | B2: a restore drill on a scratch copy; the vault and database come back legible to `sqlite3` (D-54) | 4 |
| M33 | Private-repo hygiene gate and a credential inventory | all | B1: the pre-commit/pre-push path refuses secrets, vault contents, hostnames and biometric templates (D-57); every credential in the environment maps to a system, a decision and whether it is configured (`36.R4`, D-62) | 4 |

---

## Phase 4 — Continuity, reach, and handover (M34–M40) · ~26 h + elapsed

| ID | Milestone | Systems | Done when | h |
|---|---|---|---|---|
| M34 | Session continuity: goal and working context migrate | S12, S43, S07 | B2: a task started on the phone is finished at the desk; the transcript does not migrate (D-40) | 5 |
| M35 | Presence in two rooms, no more | S43, S27 | B2: office and living room only; bedroom and bathroom are air-gapped at the sensor layer (D-37, D-38) | 3 |
| M36 | Recovery: config rollback and the remote kill | S22, S04 | B2: kill the edge mid-edit — SIGTERM, SIGKILL at 3 s, uncommitted work in a stash, nothing lost (D-41) | 5 |
| M37 | Liveness from outside the host | S23 | B2: `uptime_watch.py` proves up-ness independently; "up" is not self-reported | 2 |
| M38 | Focus-mode suppression, local-only | S27, S13 | B1: derived state never leaves the host; the audit log shows no broadcast of it (D-61) | 3 |
| M39 | The handover package | S22, S18, all | B2: a clean machine reaches a working voice loop from the setup script alone, plus an edge audio tuning guide. **This is the milestone that makes OpenMushegh adoptable by anyone but the owner** (D-55) | 8 |
| M40 | v1.0 | all | B3: 30 consecutive days with voice capture, task/calendar sync, Home Assistant actuation and vault memory running — **zero panics** (D-53) | elapsed |

**M39 is the one that changes who this is for.** Until it exists, OpenMushegh is a
personal system that happens to be open source — which the owner is fine with, and has
said so (D-57). M39 is what makes the "open-source framework" claim honest.

---

## The order, and the hardware underneath it

Phases here are software-shaped; [HARDWARE.md](HARDWARE.md) §7 is hardware-shaped. They
line up like this, and the hardware phase is a **prerequisite** where the table says so:

| Hardware phase | What it unblocks here | Blocking? |
|---|---|---|
| **H1** core — UPS, NAS, Proxmox core split, laptop Hello as the D-14 act | M32 (restore drill), M36 (recovery), M39 (handover) | **Yes** — the core split sets the latency budget everything else assumes |
| **H2** HA Green + the ZBT-1 + read-only sensors | **M20** (the desk lamp — the cheapest win in the plan, and it un-darkens S28), M23 (reminders, with smoke/CO as the one piercing signal) | **Yes** — no actuator work before the read layer is trustworthy |
| **H3** mmWave presence + AirGradient | M35 (two rooms), M38 (focus suppression) | **Yes** — heating and lighting automations are gated on presence |
| **H4** actuators, NFC tags, lock read-only | M21, M22, M27 (`28.R5`) | No — reads are already trusted by then |
| **H5** satellites, glasses-as-camera, Garmin | M12–M18 (voice), M18 (`18.R4`, `18.R5`) | No, but D-67 must be decided first |
| **H6** Coral, cameras, doorbell | nothing yet | Gated on the privacy decision, not on hardware |
| **H7** printer, fabrication safety | M39 (handover) | No — and deliberately last, because it is the most optional |

**H1 and H2 are the critical path.** H2 alone converts two of the charter's weakest
statuses — S28 dark, S35 half-built with no emergency list — into systems that do something.

---

## Rules of the road

1. **Phase 0 before Phase 1.** Deletion is cheaper than construction and the deletions
   are already decided.
2. **Never start a milestone whose previous dependency is dark.**
3. **A milestone with no benchmark is not ready to be worked.** Add the benchmark first
   ([EVIDENCE.md](EVIDENCE.md)).
4. **If a milestone takes twice its estimate, stop and ask whether it should exist** —
   it is usually a signal that a decision (D-42) was skipped.
5. **M40 needs no engineering.** It needs the system left alone for a month, which is
   the hardest thing on this list.
