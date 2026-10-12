# Principles — how decisions get made here

Derived from [DECISIONS.md](DECISIONS.md). This file is the short version: the
judgement calls that are not tied to one subsystem. Read it before proposing
architecture, and before adding anything.

---

## 1. The 2:00 AM rule

> If it fails at 2:00 AM, can I debug it in 90 seconds with `journalctl`, `sqlite3`
> and `curl`?

This is the single filter applied to every architectural proposal. It is why the
system is SQLite over Postgres, a WebSocket over a message fabric, a process over a
cluster, and a script over a workflow engine.

**The test:** name the three commands you would run, in order, at 2 AM. If the answer
involves a dashboard, a CLI for a framework nobody remembers installing, or a log
search across twelve services, the proposal fails here and does not get a benchmark.

Enterprise plumbing scales headcount. This system has one operator.

## 2. The typed boundary

The model may emit arbitrary text. Only a Pydantic-validated payload reaches the OS.

Consequences that are not negotiable:

- A handler that takes a raw string where a schema belongs is a defect, not a shortcut.
- Adding a handler is adding a place this can fail. Read `src/mushegh/brain/tools/base.py`
  and `src/mushegh/brain/tools/__init__.py` before writing one.
- A tool's schema is the contract. Changing it changes the public surface, which the
  self-edit rule forbids (D-08).

## 3. The owner is the only authority

- **De-scoping** requires the owner's deliberate sign-off. Model evaluations are
  advisory input (D-47).
- **Quiet hours** are changed by editing a file, by the owner, by hand. No tool call
  changes them (D-32).
- **Overriding a refusal** is a physical act — a CLI flag or a hardware key. Not a
  request in conversation (D-14).
- **Conflicts between values** resolve as Safety > Privacy > Honesty > Helpfulness,
  and that order is testable (D-10).

The system is one person's. It optimises for that person's judgement, not for an
audience, a stakeholder, or a market.

## 4. Prove it, then run it

A green hermetic suite proves the code agrees with the mocks. That is necessary and
insufficient.

The bar for "done" is a passing suite **and** seven consecutive days of real use with
no manual patching (D-43). A subsystem whose tests pass only against in-memory mocks is
treated as unproven by default — which is why 95 records sit at `unverified-import`
rather than claiming to be verified.

## 5. Count what controls something

Code that controls no live device, file, or credential is dark. Dark work is not
progress, and the dashboard is built to make that impossible to hide.

Dark systems get one of three fates, in order: **wire it**, **complete it**, or
**delete it**. Building an artificial bridge to make dark code look used is worse than
the deletion. 8–10 hours a week is the whole budget (D-46).

## 6. Subtract before you add

The tool belt is 153 schemas and 155 handlers, heading for 90–100 (D-06). 50 subsystems
is already too many, and a new one needs an independent daemon or a distinct security
boundary to justify existing (D-42).

The default answer to a new capability is a handler in an existing system. The default
answer to an unused handler is deletion.

## 7. Quiet by default

- Three audio interruptions per day, maximum. Zero during a focus block (D-29).
- Unprompted speech only for life-safety and hard count-downs (D-18).
- Never bring the owner something unasked because it seemed interesting (D-34).
- Never suggest. Answer and act (D-27).
- Ambiguity resolves to the *conservative* branch, always. A missed word is cheap
  (D-56); a fabricated one is not.

## 8. Honest storage

- The vault is the human source of truth; SQLite is the runtime cache; markdown wins
  every disagreement (D-22).
- Some things are never stored, not retained-for-a-period but never stored at all
  (D-24).
- Superseded memories are tombstoned, never silently wiped (D-25).
- Everything must stay legible to `sqlite3` and a text editor in 2036 (D-54).

## 9. Boring formats, sharp edges

Boring storage and transport: markdown, SQLite, WebSocket, a tailnet, a process under
systemd. Sharp judgement where it earns its keep: the speaker threshold, the
interruption budget, the destructive-write blast radius, the refusal policy.

Complexity is a cost with a maintenance bill. It has to buy something the owner will
actually feel.

## 10. The standing line

A bad Mushegh is noticed within a week: it speaks when uninvited, misreads intent, and
leaves half-baked state that has to be undone from a terminal.

Everything in these docs exists to make that impossible, and to make sure that when
something does go wrong, the answer is 90 seconds of `journalctl` away rather than a
night of archaeology.
