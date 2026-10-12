# S07 — Session & Context Management

> **One line:** One conversation has one identity, a working context that trims on purpose, and a goal that follows the owner between devices.
> **Status:** built, not well structured · **Registry:** S07 · 3/3 floor, 3/3 raise, 0/1 elite
> **Milestones:** M19, M31, M34 · **Decisions:** D-23, D-40

## Purpose

A session is the unit the owner experiences: one conversation, started somewhere,
continued somewhere else, closed by voice. Its identity is explicit — one session id per
conversation, carried across edge clients (07.F1) — because a system that cannot name
the conversation cannot summarise it, trim it, resume it, or attribute a task to it.

Trim is lossy **on purpose**. What is dropped from the working context is summarised into
the session record rather than discarded (07.F2), because a context window that silently
forgets is a context window that lies. Reference resolution — "it", "that", "the second
one" — is tested rather than assumed (07.F3, 20/20 with 0 wrong bindings), because a
wrong binding is not a degraded answer, it is a confidently wrong one.

D-23 is the rule that makes correction feel immediate: a correction takes effect at once
in the live context, then is reconciled into permanent memory at the next scheduled
checkpoint. Never "it will be right next time" — a system that needs a checkpoint to
obey the owner has already lost the argument about who is in charge.

D-40 governs the edge of the system: the active goal and immediate working context
migrate across devices; raw transcript history does not. It produces visual clutter
across screen sizes, and a transcript carried to a phone is clutter on a phone.

If this is absent, the owner is treated as a new person on every device, and every
long conversation ends in a re-explanation.

## Structure

Brain owns session state; edges own the transport and the window.

```
laptop / phone / panel
   src/mushegh/edge/assistant.py ──┐
   src/mushegh/edge/brain_bridge.py│
   src/mushegh/edge/brain_client.py┘
                    │
                    │ WS, one session id carried across (07.F1)
                    v
   brain: src/mushegh/brain/server.py
              │
              ├── context.py          build_system_prompt() — the working context
              ├── references.py       "it" / "that" / "the second one" (07.F3)
              ├── memory.py           what survives the trim, six layers
              ├── objectives.py       the goal a turn serves (attribution)
              ├── turn_trace.py       per-turn record
              └── dbconn.py ──> SQLite: sessions, summaries, working context
```

| Concern | Where |
|---|---|
| Session identity across clients (07.F1, 07.R1) | `src/mushegh/brain/server.py`, `dbconn.py`; `test_session_identity.py` |
| Prompt assembly, the working context | `src/mushegh/brain/context.py` |
| Lossy trim with gist retained (07.F2) | `context.py`, `memory.py` |
| Reference resolution (07.F3) | `src/mushegh/brain/references.py`; `test_reference_resolution.py` |
| Topic segmentation (07.R2) | `test_reference_resolution.py` [07.R2] |
| Interruption and resumption, "carry on" (07.R3) | `bench/test_streaming.py` [07.R3] |
| Correction now, reconcile later (D-23) | `context.py` for the immediate half, the checkpoint job for the durable half |
| Goal and context migration (D-40, M34) | S12 owns the wire; this system owns what is worth carrying |

**Process ownership:** brain. The edge holds a window and a session id, not a history.
**What it stores:** session id, per-turn records, close-time summaries retrievable by
date and topic (07.R1), and the working context. Readable with `sqlite3`.

## Goals

1. **A conversation has one identity that survives moving between clients** — started on
   the phone, continued at the desk, closed by voice, as one session (07.E1).
2. **A correction takes effect in the live turn and is reconciled at the next
   checkpoint** — never deferred to a later conversation (D-23).
3. **Trimming the working context never loses the gist** of what was dropped (07.F2).
4. **Every reference resolves to the right referent**, with 0 wrong bindings across the
   labelled set (07.F3).
5. **Long sessions are segmented by topic** so recall does not drag in unrelated turns
   (07.R2).
6. **An interrupted turn can be resumed by "carry on"** (07.R3).
7. **The goal and the immediate working context migrate across devices; the transcript
   does not** (D-40, M34).

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | Session identity across devices | B1 + B2 | `bench/test_phase6_multidevice.py` + one live run (07.E1) | 1 session id across three clients; 0 second sessions created | `test_session_identity.py` records 33/33; the multi-device half is not yet measured — the live run has not been performed |
| 2 | Correction immediacy (D-23) | B4 | Invariant: a correction changes the live context in the same turn; durable write happens at the next checkpoint | 0 corrections that take effect only next time | not yet measured |
| 3 | Lossy trim keeps the gist | B1 | `bench/test_session_identity.py` [trim retains gist] | 0 dropped turns absent from the session record | not yet measured |
| 4 | Reference resolution | B1 | `bench/test_reference_resolution.py` | 20/20 resolved, **0 wrong bindings** | 20/20 with 0 wrong bindings per the registry gate text. The gate is two-sided and this is the one S07 number the registry states explicitly; the surrounding evidence is still `unverified-import` |
| 5 | Topic segmentation | B1 | `bench/test_reference_resolution.py` [07.R2] (22) | 0 unrelated turns retrieved into a topic | 22 per the registry gate text, `unverified-import` — **not yet measured** as a dated run |
| 6 | Resume after interruption | B1 | `bench/test_streaming.py` [07.R3] (65) | "carry on" resumes without re-asking context | not yet measured |
| 7 | Goal migrates, transcript does not (D-40) | B2 | Drill: start a task on the phone, finish it at the desk (M34) | goal and working context present on the second device; **0 transcript turns** present | not yet measured — M34 open |

Goal 7 is the one where a wrong result is invisible: if the transcript migrates too,
nothing breaks and the phone is simply unusable. It is a drill, not a test, because the
thing being checked is the owner's screen.

## Failure modes

**A session splits across devices.** The owner continues on the phone and gets a blank
context, so they re-explain a conversation the brain already has. The symptom is a
repetition the owner does not understand. Diagnose: compare session ids in the SQLite
sessions table, then the `journalctl` entries for both clients at the handover point.

**Trim drops something load-bearing.** The context is smaller and the answer is subtly
wrong, with no error anywhere. 07.F2 exists because a context window that silently
forgets is worse than one that is merely long.

**A reference binds to the wrong thing.** "the second one" resolves to the wrong item
and the owner acts on it. 07.F3's gate is two-sided on purpose — a resolution rate
alone would pass a system that resolves confidently and wrongly.

**A correction waits for the checkpoint.** The owner corrects the system and the next
answer is still wrong. This is the D-23 failure and it reads as being ignored, which is
the fastest way to lose the owner's trust in the whole system.

**Everything migrates.** The transcript follows the goal to the phone and the window
becomes unusable. D-40 forbids it; the symptom is the owner abandoning voice on the
phone.

## Open questions

1. 07.E1 needs a live run across three clients and the registry records only the
   hermetic half. Which three clients is the drill defined over — laptop, phone, wall
   panel (D-36)?
2. D-23 splits a correction into an immediate in-session effect and a durable reconcile
   at the next checkpoint. No record says what happens if the process dies between the
   two, so the correction can be lost in the gap. Which layer owns that?
3. The registry shows 0/1 elite for S07 and 3/3 on both floor and raise. What is the
   elite gate, given D-44 says the elite tier is mis-specified?
