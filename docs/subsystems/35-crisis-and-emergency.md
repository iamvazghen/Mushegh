# S35 — Crisis & Emergency Response

> **One line:** A deterministic emergency path that runs ahead of the model and entirely locally — where the escalation ladder is SMS/push to a list the owner has not written down yet, and there are no outbound voice calls.
> **Status:** half-built — system-level crisis protocols exist, *owner*-level does not; the life-safety hardware that would feed it is ordered, and the list it reports into is still unwritten · **Registry:** S35 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M07 · **Decisions:** D-11, D-13, D-18, D-32, D-63

## Purpose

The one path that must not depend on anything that fails during an emergency. A person
saying "call an ambulance" gets a deterministic classification, a locally-resolved
contact list, and an escalating notification — before the language model is consulted,
and without requiring a provider, a token, or a synced vault (D-11, and the module's
own stated reason: the network is a thing that fails during emergencies).

What was there before was system-level: `ragnarok` and `phoenix` recover *Mushegh*.
Nothing recovered the owner. That gap is the system, and it is still half-built because
the list does not exist. `emergency.md` is **not on disk**; `emergency.configured()`
returns False and `ladder()` falls back to a single `push` step with an empty target.
`35.R1`'s current text — "notify → **call** → contact a third party" — is the wrong
ladder under D-11 and is scheduled to be rewritten to notify → **SMS/push to a fixed
list** → third party.

Two hard properties. Safety-critical steps are deterministic and **must not route
through a language model**: the classifier is a conservative keyword classifier with a
manual trigger (`35.F1`, done, 0 false positives on 50 ordinary prompts), and the
contacts are a plain file read. And unprompted speech is permitted here and almost
nowhere else — physical safety is one of the two carve-outs in D-18.

**The hardware makes this system real, which makes the missing list urgent.** Two smoke+CO
detectors and three water-leak sensors arrive with a Home Assistant to report them. They
are the only hardware in the house permitted to interrupt the owner outside the D-29 budget,
because D-18 makes life safety the one exception, and D-32 lets only life-safety alerts
pierce quiet hours. So the order of this work is not free: **installing life-safety sensors
before the emergency list is written down inverts it.** A detector that fires into a ladder
with an empty target and no stop conditions is a worse system than no detector, because it
manufactures the appearance of a working emergency path while reaching nobody. `35.R1` is
blocked on the owner decision recorded below, and the honest sequence is the list, then the
hardware, then the drill. The leak sensors are read-only and the shut-off valve stays a
physical act: Mushegh reports *"the basin under the kitchen sink is wet"*, and the owner turns
the valve (D-13, D-63).

If this is absent: an alarm reaches nobody, and the one system that exists purely for
the worst ten minutes of the owner's life is the one with no owner-decided content.

## Structure

`src/mushegh/brain/emergency.py`, 365 lines, and the whole system.

- `classify(text)` — the deterministic classifier: `MEDICAL`, `FIRE`, `INTRUDER`,
  `ACCIDENT`, `UNKNOWN`, with `DEFAULT` for the fallback. `MANUAL` holds the exact
  trigger phrases — `mushegh emergency`, `emergency protocol`, and two more — so a manual
  trigger exists for someone who cannot be classified (35.F1, done).
- `ladder(category)` — reads `emergency.md` from disk **every time**, never cached,
  because a stale ladder held in a process up for three weeks is exactly the failure
  this exists to prevent. It falls back to the `default:` line, then to a bare `push`.
  `_path()` honours `settings.emergency_contacts_path`, else `emergency.md` at the repo
  root. The file is gitignored and the format is one line per category: action targets
  in the order to try them. `ACTIONS` today is `push, call, signal, telegram, email`;
  under D-11 the outbound voice `call` does not belong in a ladder Mushegh climbs on its
  own, and the third party is a person, not a channel.
- `raise_alarm(alarm, text)` — walks the ladder with `STEP_TIMEOUT_S = 2.5` per step, so
  one unreachable contact cannot stall the next. `python -m mushegh.brain.emergency` runs
  the module selfcheck.
- `35.F2` (a contact list with a defined action per category, stored locally) is
  recorded `done` — the *code* reads a list. The list itself does not exist, which is
  the whole of the remaining gap.
- `src/mushegh/brain/protocols.py` and the `ragnarok` / `phoenix` drills
  (`bench/test_protocol_drills.py`) cover the Mushegh-level side. `src/mushegh/shared/errors.py`
  and the dead-man's switch (`bench/test_deadmans_switch.py`) are where `35.R2` silence
  detection would attach.

**What the hardware adds.** A smoke/CO detector or a leak sensor reports to Home Assistant
Green, and the brain reads it over the same single local endpoint every other house signal
uses — one hop, one token, no new daemon, no new inbound port. A sensor transition enters
`raise_alarm()` as a trigger, and it is the one place an unprompted signal is correct: D-18's
life-safety carve-out and D-32's quiet-hours rule both name exactly this. The classifier and
the ladder still run before the model, so a detector event gets no more of a say than the
spoken "call an ambulance" it replaces.

Ownership: the brain process. No LLM, no network dependency, no new daemon.

## Goals

1. A conservative emergency classifier with a manual trigger, deterministic and ahead of
   the model, with a 0 false-positive rate on ordinary speech (35.F1).
2. A locally-resolved contact list with a defined action per category, read from disk at
   the moment of use (35.F2).
3. The escalation ladder is notify → **SMS/push to a fixed list** → third party, each
   step with a stop condition, and **no open-ended outbound voice calls** (D-11,
   rewritten `35.R1`).
4. A missed check-in after an at-risk signal triggers the same ladder (`35.R2`).
5. A post-incident record written automatically, without the owner having to remember
   to write one (`35.R3`).
6. System-level crisis protocols stay drill-tested, because a drill that has not been run
   is a protocol that does not work (35.F3).
7. A smoke/CO or water-leak transition raises the same deterministic ladder a spoken
   trigger does, with no confirmation step and nothing routed through the model (D-18,
   D-32) — and the leak is reported, never acted on: the valve is the owner's (D-13).

## Benchmarks

1. **B1** — `bench/test_emergency_path.py`. Threshold: 0 false positives across 50
   ordinary prompts, and a manual trigger fires on every one of its exact phrases.
   Registry records 35.F1 `done` as of 2026-10-03; no field measurement. This is a
   B1-only benchmark and D-43 says that is not sufficient for a user-visible capability.
2. **B1** — `bench/test_emergency_path.py [contacts resolved offline]`. Threshold:
   `ladder()` returns the owner's steps with no network, no token and no vault read.
   Registry records 35.F2 `done`. Note the ladder file is absent, so the resolved steps
   in production today are the bare `push` fallback. Last measurement:
   `not yet measured`.
3. **B1 planned** — `bench/test_emergency_path.py [ladder]`, the rewritten `35.R1`.
   Threshold: 0 outbound voice-call actions reachable from the ladder, and every step
   carries a stop condition. Last measurement: `not yet measured` — the assertion is
   not written and the ladder text still says "call".
4. **B1 planned** — `bench/test_deadmans_switch.py` extended (the `35.R2` gate).
   Threshold: a missed check-in after an at-risk signal raises the ladder within the
   declared window. Last measurement: `not yet measured`.
5. **B1** — `bench/test_protocol_drills.py` (35.F3, done) and
   `bench/test_protocol_reports.py` extended (the `35.R3` gate). Thresholds: `ragnarok`
   and `phoenix` complete without manual repair, and a post-incident record exists after
   every raised alarm with 0 manual steps required. Registry record 2026-10-03 for the
   first; last measurement `not yet measured` for the second.
6. **B2 live drill** — `35.E1`, and this is the benchmark that matters more than any of
   the above: two rehearsed drills, one voice-triggered and one silence-triggered, run
   end to end with a real contact. Threshold: 2 of 2 completed, every intended contact
   reached, 0 steps requiring improvisation. Last measurement: `not yet measured` —
   and it cannot be run until the list exists.
7. **B1 planned** — new `bench/test_detector_ladder.py`; planned and not written.
   Threshold: a simulated smoke, CO and leak transition each reach the ladder with 0
   confirmation steps and 0 model calls, quiet hours suppress an ordinary alert and not a
   life-safety one, and a leak raises without any plumbing actuation. Last measurement:
   `not yet measured` — no detector is installed.

## Failure modes

**An alarm fires and nobody is contacted.** The defining failure. The ladder file is the
first thing to check, and it is absent today:

    python -c "from mushegh.brain.emergency import configured; print('ladder configured:', configured())"
    python -c "from mushegh.brain.emergency import ladder; print(ladder())"
    journalctl -u openmushegh-brain -n 200 | grep -iE "emergency|ladder|raise_alarm"

`configured(): False` with a `push` step and no target means the system is working
exactly as written and the content is missing.

**A false positive mutes the system.** One alarm that interrupts at 03:00 with a push to
a real person is expensive; the classifier is deliberately conservative because of it.
`bench/test_emergency_path.py` is the regression, and the journal shows every
`raise_alarm` with its text.

**A contact is unreachable and the ladder stalls.** `STEP_TIMEOUT_S = 2.5` bounds each
step. If the whole ladder appears to have done nothing, the journal says whether it
walked the steps or parsed none.

**An outbound voice call happens, or the model is asked to decide.** It must not do
either (D-11). If `ACTIONS` is ever extended with a channel that dials a person, that is
a decision made in code rather than in DECISIONS.md, and
`bench/test_emergency_path.py [ladder]` is the test that should have stopped it. The
classifier and the ladder both run before the model; a diagnosis or judgement call
appearing in that path means the deterministic property is gone and the system has
become less reliable, not more.

**A detector fires into a ladder with no stop conditions.** The failure mode the arriving
hardware introduces. Two smoke/CO detectors and three leak sensors give this system a real
trigger for the first time, and the ladder that trigger climbs is still the bare `push`
fallback with an empty target: the owner would get a notification with nowhere for it to
escalate to, at the exact moment having one mattered. Check `configured()` and `ladder()`
first, using the two commands above. Until both are right the honest state is that the
sensors are ordered and not installed, and `35.R1` is blocked on the list.

## Open questions

1. **Who is on the list, in what order, and what is each stop condition?** The owner
   said this would be encoded once, by hand. It has not been written down, and it is a
   decision rather than engineering — which is why M07 lists S35 as needing an owner
   decision and not a milestone. The arriving smoke/CO and water-leak sensors make it
   urgent rather than optional: **installing life-safety sensors before this list exists
   inverts the order**, and `35.R1` is blocked until the owner writes it. The ladder it has
   to satisfy is notify → SMS/push to a fixed list → third party, with no outbound voice
   calls (D-11), and smoke/CO is the one signal permitted to pierce quiet hours (D-18,
   D-32).
2. What ends the ladder? A stop condition per step is required by the rewritten
   `35.R1`, and "the owner says it is over" is a different mechanism from "the push was
   delivered". Those have very different failure modes and only one is checkable.
3. Is silence detection (`35.R2`) in scope for a system whose list does not exist? It
   multiplies the blast radius of a false trigger — a missed check-in is a claim about
   the owner's safety, made without evidence. That may deserve the same standard as
   D-13's categories rather than a proactive signal.
