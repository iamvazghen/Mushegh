# S23 — 24/7 Reachability

> **One line:** Reachable from any of the owner's devices at 3 AM, over a tailnet, with no inbound port opened anywhere — and parked on purpose when he does not want it.
> **Status:** complete for now — **currently parked by design** · **Registry:** S23 · 4/4 floor, 2/4 raise, 0/1 elite
> **Milestones:** M37 · **Decisions:** D-03, D-01

## Purpose

The brain runs on an always-on host so a message sent at 22:00 reaches something. The
phone can reach it with the laptop off. Nothing about it is exposed to the internet: one
bearer token, one WebSocket, carried by a WireGuard tailnet, and **no inbound ports are
opened, ever** (D-03). The security argument is the absence of a perimeter to defend, not
the strength of one.

Reachability is only half of it. The system must also *stop* when the owner wants it to,
and stopping must survive a tired operator, a scheduled task with a repetition trigger, and
a machine that reboots. Parking is one command — write `~/.afon/MAINTENANCE` — and
`src/afon/shared/maintenance.py` exists because a parked deployment once did not stay
parked: on 2026-08-13 the laptop's `AfonEdge` / `AfonPcAgent` scheduled tasks carried a
five-minute repetition trigger and `Disable-ScheduledTask` needed elevation, so a working
session was interrupted by an assistant that had been told to stop. Unparking is therefore
a checklist, `scripts/unpark_check.py`, verifying each floor before the thing starts.

If this system is absent the owner has two bad options and no good one: an assistant that
only exists at the desk, or one reachable from the open internet.

## Structure

| Side | Path | Role |
|---|---|---|
| VPS | `deploy/vps/afon-brain.service` | The brain under systemd, `Restart=always`, linger; the unit is rewritten per account by `install-brain.sh` |
| VPS | `deploy/vps/afon-ticker.service`, `afon_ticker.py` | Recurring reminders, owned outside the brain process so a brain restart does not lose them |
| VPS | `src/afon/brain/server.py` | Dispatch, and the `GET /healthz` endpoint that answers a probe |
| VPS | `src/afon/brain/telegram_bridge.py` | Bot API long-poll — the reason a message works with the laptop off |
| VPS | `src/afon/brain/webhooks.py` | HMAC-verified inbound POSTs from outside, for push rather than polling |
| Both | `src/afon/shared/maintenance.py` | The park marker, honoured by launchers, system units and scheduled tasks |
| Both | `scripts/unpark_check.py`, `bench/test_unpark_gate.py` | Unparking verifies each Wave-0 floor first |
| Edge | `src/afon/edge/brain_client.py` | Survives a brain restart instead of holding a dead socket |
| Edge | `src/afon/edge/offline_queue.py` | Keeps promises across an outage: capture, transcribe locally, answer on return (23.R4) |
| Edge | `src/afon/edge/degraded_answers.py` | With no LLM reachable, still answers time, reminders and status (23.R2) |
| Edge | `src/afon/edge/reflexes.py` | Turns needing no external answer get no brain round-trip |
| Edge | `src/afon/edge/remote_brain.py` | One brain and one memory across laptop, phone and panel |
| Edge | `src/afon/edge/edge_lite.py` | The Termux phone edge: mic → brain → TTS, no wake word, no barge-in |
| Outside | `deploy/uptime_watch.py` | Liveness from a host that is not the VPS |

Transport is one bearer token over the tailnet. The edge holds no inbound listener; the
laptop's `src/afon/edge/pc_agent.py` dials *out* to the brain's control socket, so a
laptop on hostile wifi still exposes nothing. The system stores no state of its own beyond
the maintenance marker and the watcher's: held messages live in the error spool, queued
utterances in the edge's offline queue.

## Goals

1. Reachable from any of the owner's devices, with zero inbound ports exposed. Threshold:
   **0** listening ports reachable from the internet — an invariant, checked by inspecting
   the host, not by a test in this tree.
2. Parking holds everywhere: launcher, system unit, scheduled task. Threshold: **0**
   autostarts while `~/.afon/MAINTENANCE` exists.
3. Unparking verifies each floor before the thing starts. Threshold: **100%** of floors
   checked; unpark refuses while any Wave-0 floor is unmet.
4. A message sent while the brain is down is held and answered on return. Threshold: **0**
   dropped messages across an outage.
5. With no LLM reachable, time, reminders and status still answer. Threshold: **100%** of
   that set answerable from the edge.
6. Liveness is measured from outside the VPS, so "up" is not self-reported. Threshold:
   **1** external probe on a fixed interval, alerting exactly once per transition (23.R1).
7. Every interruption in thirty days is explained by a record. Threshold: **≥99.5%** uptime
   with a record for each gap (23.E1).

## Benchmarks

- **G1** · B4 · invariant, no test: `ss -tulpn` on the VPS. Threshold: **0** listeners on a
  public interface, tailnet the only route in. A new inbound port is a D-03 violation
  regardless of what any test says. Last: **not yet measured** as a recorded check.
- **G2** · B1 · `bench/test_maintenance_lock.py`. Threshold 0 autostarts while parked. Last:
  **not yet measured**. 23.F3 is `done`; the only status evidence is `unverified-import`.
- **G3** · B1 · `bench/test_unpark_gate.py`. Threshold: unpark refuses while a Wave-0 floor
  is unmet. Last: **not yet measured**.
- **G4** · B1 · `bench/test_error_spool.py` for the held-message path, plus a B2 drill
  across a real restart. Threshold 0 dropped messages. Last: **not yet measured**.
- **G5** · B1 · `bench/test_resilience.py` [degraded] for the no-LLM path, with
  `src/afon/edge/degraded_answers.py` as the implementation. Threshold: time, reminders and
  status all answer. Last: **not yet measured**. 23.R2 is `done`.
- **G6** · B1 · `bench/test_uptime_watch.py` for the edge-triggered alerting: exactly one
  alert on the way down, exactly one on the way back, never a repeat per tick. Threshold 1
  alert per transition. Last: **not yet measured**.
- **G7** · B2 · M37's own gate: `deploy/uptime_watch.py` running from a second host against
  a live brain, alerting on a real outage. Threshold: **1** external probe on a fixed
  interval, **1** alert per transition. The mechanism exists; whether it runs anywhere is
  not recorded. 23.R1 is open. Last: **not yet measured**.
- **23.E1** · B3 · thirty days at ≥99.5% with every interruption explained by a record.
  Threshold: **≥99.5%**, **1** record per gap. Last: **not yet measured**.

## Failure modes

- **The VPS is down and nothing notices.** The single-VPS SPOF. The brain cannot report its
  own death, which is why the watcher lives elsewhere — and if it is not running anywhere,
  the outage is discovered by the owner. Diagnose from outside: run
  `python deploy/uptime_watch.py --once`, or read its state file; inside,
  `systemctl status afon-brain` and `journalctl -u afon-brain -n 200 --no-pager`.
  A second host can run `python deploy/uptime_watch.py --once` against the same
  `healthz` URL and get the same answer.
- **A parked deployment starts anyway.** The 2026-08-13 incident: a repetition trigger on
  a scheduled task, and a disable that needed elevation. The owner is mid-session and the
  assistant speaks. Diagnose: `type %USERPROFILE%\.afon\MAINTENANCE`, then
  `journalctl -u afon-brain -n 100` for the start.
- **The tailnet is up and the brain is not.** The edge sees a live WebSocket and no
  answers, which reads as silence rather than as an error. Diagnose:
  `journalctl -u afon-brain | grep -i websocket` and the edge's own log.
- **The long-poll loses its offset.** Telegram messages stop arriving with no error; the
  bridge looks healthy. Diagnose: `journalctl -u afon-brain | grep -i telegram`, and the
  error spool contents.
- **The watcher spams.** An alert per tick is worse than no watcher, because the owner mutes
  it and then trusts nothing. `bench/test_uptime_watch.py` exists for exactly this, and is why
  the state machine is edge-triggered.
- **Unparking is a keystroke.** `rm ~/.afon/MAINTENANCE` forgets every reason it was parked.
  `scripts/unpark_check.py` exists to refuse that.

## Open questions

1. 23.R1 asks for outside-in liveness and `deploy/uptime_watch.py` is the mechanism. Where
   does it actually run — the laptop, a Pi, another VPS — and who is paged if all three are
   asleep?
2. `deploy/vps/live-check.sh` runs a weekly live integration drill and speaks the failure.
   Is that S23's uptime evidence or S20's? It is currently neither system's recorded
   measurement.
3. The ticker owns recurring reminders outside the brain process. If the ticker is down and
   the brain is up, which one is the authority, and does the owner ever see the difference?
