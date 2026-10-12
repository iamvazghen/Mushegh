# S13 — Notification Management

> **One line:** getting a thing to the owner, at most three times a day, without ever claiming
> it was received.
> **Status:** built, not well structured · **Registry:** S13 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M20, M23, M38 · **Decisions:** D-07, D-29, D-18, D-32, D-34

## Purpose

Mushegh can reach the owner four ways: spoken through a listening edge, pushed to a phone,
messaged over Telegram, and rendered on the HUD. This system decides which one, when, and
whether at all. The number that constrains everything is the **interruption budget**: at most
three audio interruptions per day, and **zero** inside a scheduled focus block (D-29). That is
enforced in code, not by good intentions, and one interruption inside a focus block is a bug
rather than a judgement call.

The second correction is about honesty. Delivery is not receipt. `push()` returning `True` means
an HTTP POST was accepted; it says nothing about eyes, and inferring "seen" from a successful
POST is the same overclaim as a status page that shows green because it never asked. Three
states — delivered, seen, acted-on — with exactly one permitted inference between them.

The third is the silent-ok list (D-07): toggling a predefined lighting scene, appending to
daily notes, setting a local timer, read-only queries, and polling transit or weather happen
without asking. Everything else confirms. The list is a whitelist; adding to it is a decision,
not a feature.

If it is absent, Mushegh either nags until he mutes the channel — and then misses the alert that
mattered — or stays silent and fails the one job it has.

## Structure

| Path | Role |
|---|---|
| `src/mushegh/brain/delivery.py` | The ledger: `delivered` / `seen` / `acted-on`, one named inference to "seen", and the re-raise sweep (13.F3) |
| `src/mushegh/brain/proactive.py` | The decision core — budget, quiet hours, relevance threshold, repeat suppression, day rollover — pure, with an injectable clock |
| `src/mushegh/brain/scheduler.py` | One process-wide APScheduler persisted to SQLite; reminders survive a restart |
| `src/mushegh/brain/telegram_bridge.py` | Inbound and outbound Telegram; only the owner's own chat id is answered |
| `src/mushegh/brain/tools/notify.py`, `src/mushegh/brain/tools/phone.py`, `src/mushegh/brain/tools/telegram.py` | The handler belt for push, phone and Telegram |
| `src/mushegh/brain/presence.py` | Answers "is he here", which is the input to channel choice |
| `src/mushegh/edge/offline_queue.py` | Holds an undeliverable item until the edge returns |

The ledger is a JSON file, not a table — `state_dir() / "delivery_ledger.json"`, a few hundred
rows, read once per re-raise sweep. A table would be the better shape at ten times that size;
it is the wrong shape now, and the comment in the module says so.

`src/mushegh/brain/delivery.py` is deliberately the *downstream* half. S14 decides whether to speak; this
records what happened after the message left, which is the part that is normally missing
entirely.

## Goals

1. Never more than three audio interruptions per local day, and exactly zero inside a
   scheduled focus block (M23, D-29).
2. Delivered, seen and acted-on are three distinct states, with one named inference and
   nothing inferred (13.F3).
3. No duplicate delivery — one sender, one path (13.F2).
4. Channel chosen by urgency and context: voice if present, push if away, Telegram if neither
   (13.R1).
5. Non-urgent items accumulate into the next brief rather than interrupting (13.R2).
6. Every escalation has a stop condition, so no alert can loop (13.R3).
7. Actions on the silent-ok list are silent; everything else is confirmed (D-07).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_proactive_windows.py`, `uv run python bench/test_proactive_suppression.py` | ≤3 audio interruptions per day across a simulated week; exactly 0 inside a focus block | registry records 13.F1 done, whose gate is these two scripts; M23 open; not yet measured in this doc |
| 2 | B1 | `uv run python bench/test_delivery_ledger.py` | an unacknowledged urgent item is re-raised exactly once; 0 items marked `seen` without the one permitted inference | registry records 13.F3 done; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_acknowledgements.py` | 0 duplicate deliveries of the same item on the same channel per day | registry records 13.F2 done; run not reproduced here — not yet measured |
| 4 | B1 | new `bench/test_notify_routing.py` (planned, 13.R1 — does not exist yet) | 10/10 items routed by the stated rule; 0 voice attempts with no listening edge | not yet measured |
| 5 | B1 | new `bench/test_notify_routing.py` [batch] (planned — does not exist yet) | 5 non-urgent items produce 0 interruptions and 1 batched entry | not yet measured |
| 6 | B1 | `uv run python bench/test_deadmans_switch.py` (to be extended) | 0 loops; every escalation path terminates in ≤1 re-raise | not yet measured (13.R3 open) |
| 7 | B4 | `src/mushegh/brain/approvals.py` and the handler schema guards | 5 named silent-ok classes, and 0 others; any new silent-ok handler is a charter edit | not yet measured — the open gap is 05.R1, which is `open`, so a spend or a send can still be one voice command away today (see [05-browser-control.md](05-browser-control.md)) |

Quiet hours (D-32) are a separate boundary from the budget: they are edited by the owner, in
a file, by hand. No tool call and no natural-language request changes them, and there is no
test that would let one.

## Failure modes

**The budget is not enforced on one path.** The budget lives in the proactive engine; a
reminder fired by `src/mushegh/brain/scheduler.py` or a Telegram send from a tool can bypass it. The owner sees
four interruptions in an afternoon and starts ignoring all of them. Diagnose: `journalctl -u
openmushegh-brain -n 300 | grep -i "proactive\["`, then `ls ~/.mushegh` for the persisted budget and
suppression state, then the engine's per-kind hold counts.

**Duplicate delivery.** The recorded incident this system was written to stop: the same two
lines — "N past-due tasks", "M important emails" — pushed three to four times each, seven or
eight duplicates a day, because suppression was per-window and reset on every brain restart.
Suppression and the day's budget are now persisted, so a restart does not re-fire them. If it
recurs, the state file is being reset or unreadable: `cat ~/.mushegh/daily_digest_state.json`.

**Overclaiming delivery.** An urgent item is pushed to a phone in a coat pocket, counted as
delivered, and never mentioned again. The ledger is the only defence, and it is a JSON file
that a failed write will not report. Diagnose: `cat ~/.mushegh/delivery_ledger.json` and look at
the `seen` column.

**Escalation loops.** An alert re-raises, is re-raised, is re-raised. The deadman's switch
(13.R3) is open work, so the stop condition today is the ledger sweep's one-re-raise rule.
Owner symptom: he turns the phone off.

**Ambient nudges.** Anything that arrives because it seemed interesting rather than because
he asked is a D-34 violation, and the fastest way to lose the channel is to do it twice.

## Open questions

1. 13.R1 needs per-device capability advertisement from S12.R2. Until the brain knows which
   device is listening, channel choice is a guess dressed as a rule.
2. Is the one-re-raise cap the right stop condition, or should an unacknowledged urgent item
   escalate to Telegram on the second miss?
3. M20 is a single milestone — "Lamp toggle, no latency, over Home Assistant" — and it
   defines no classes. D-07 lists exactly five silent-ok actions, and lighting is one of
   them, which leaves four: appending entries to daily notes, setting local timers,
   read-only file and system queries, and polling transit and weather. Are those four
   genuinely silent-ok, and does each survive D-09's "a confirmation never carries to the
   next action"?
