# S12 — Multi-Device Coordination

> **One line:** one owner, several devices, one answer — and the goal moves between them
> while the transcript does not.
> **Status:** built, not well structured · **Registry:** S12 · 3/3 floor, 0/5 raise, 0/1 elite
> **Milestones:** M34 · **Decisions:** D-03, D-36, D-38, D-39, D-40, D-49

## Purpose

Afon is one person's system, and that person carries several clients: the laptop first, the
phone second, the room hardware third (D-36). The laptop is the primary interface because
that is where the deep work and the development happen. **Smart glasses stay parked for the
voice path**: D-36 holds them until sub-second latency is solved, and owning the hardware does
not change that condition — the worst case is still ~700 ms against a <350 ms budget (D-49).
So the Mentra Live glasses are planned as a **POV capture device feeding the local detector**,
which is what they are good at, and not as a wake-and-talk endpoint. If the latency work lands
later they join the voice path with no re-integration.

Three rules make the shape. Transport is the tailnet; no inbound ports are ever opened, and
the absence of a perimeter to defend is the entire security argument (D-03). Away from home
means a phone client over the tailnet, **not** a server-side stand-in pretending to have a
body (D-39) — a VPS cannot hear the room, and pretending otherwise produces a voice that
claims to notice things it cannot. **The Pixel with Termux matches that rule exactly**: away
from home it is a phone client over the tailnet running background presence beacons, with
nothing on the VPS standing in for a body, and 12.R5 is the row that has to make it so. And
what migrates between devices is the goal and the working context, never the raw transcript,
which becomes visual clutter at every screen size (D-40, M34).

**The three room satellites are fixed endpoints of that migration, not new memories.** Three
HA Voice Preview Edition satellites — office, living room, hallway, placed by D-38 before
anything is unboxed — each forward audio to the local pipeline. Walking from the desk to the
hallway is a change of endpoint, not a change of session: the goal and the working context
arrive, the raw transcript stays where it was recorded. That is D-40 applied to always-
listening hardware, and it is the same answer 12.E1 asks for at a smaller scale.

If it is absent, the owner re-explains the same context at the desk every morning, or the
phone is the only Afon that exists while the laptop is on.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/afon/edge/device_profile.py` | edge | Classifies the resolved output endpoint (Bluetooth/AirPods/headset → private, Realtek/internal → shared) and decides barge-in from it. Remote clients declare a hint |
| `src/afon/edge/edge_lite.py` | edge | Android/Termux client: push-to-talk → STT → the same brain WebSocket, registered as `device_id="android"` so existing phone routing applies |
| `src/afon/edge/brain_bridge.py`, `src/afon/edge/brain_client.py` | edge | The WebSocket client; `src/afon/edge/remote_brain.py` is the alternate brain address |
| `src/afon/brain/server.py`, `src/afon/brain/protocols.py` | brain | Dispatch, and the shared message definitions both sides compile against |
| `src/afon/brain/presence.py` | brain | Foreground window and idle samples, polled via `pc_agent`; the roster of rooms and the derived context |
| `src/afon/brain/coordination.py` | brain | One row per unit of delegated work: claimed before it is worked, only the holder writes the result |
| `src/afon/brain/hud.py`, `clients/hud-spatial/src/App.tsx` | brain + client | Read-mostly JSON snapshot; optional, and the system is complete without it |

The laptop edge is a full Pipecat pipeline — wake word, VAD, barge-in, speaker ID, local
Whisper, Piper. None of that ports to a phone, and `src/afon/edge/edge_lite.py` is the honest minimum rather
than a degraded copy. The wall panel is a third profile, not a third implementation.

The endpoint list is now concrete ([../HARDWARE.md](../HARDWARE.md) H5): the laptop, three
HA Voice Preview Edition satellites in the office, living room and hallway, the Pixel with
Termux as the phone client, and the Mentra Live glasses attached as a POV camera feeding the
local detector rather than as a voice client (D-36, D-49). None of the four is a fifth
implementation — the satellites and the glasses are endpoints the existing pipeline already
classifies, and none of the four exists in code today, so nothing here is a new daemon
(D-42).

What is **not** here yet: per-device capability advertisement (12.R2). Today the brain knows a
device connected and roughly what class it is; it does not know which device has a camera, a
mic or a speaker. That gap is why channel routing (13.R1) is still open.

## Goals

1. One answering device when two edges hear the same wake word (12.F3) — arbitration, not a
   chorus.
2. A reconnect does not lose the brain link or the session (12.F2).
3. The session follows the owner between devices (12.R1, M34) — the goal and the working
   context, not the transcript (D-40).
4. The brain knows which device has which capability (12.R2).
5. A device degrades to text-only or push-only and still works (12.R3).
6. The transport is the tailnet, and no inbound port exists to attack (D-03).
7. Away from home, the body is the phone — the VPS never impersonates one (D-39).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_device_handoff.py` [double-wake] | exactly 1 of 2 edges answers; 0 double-speech events | registry records 12.F3 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_edge_reconnect.py` | 0 lost links across the reconnect sequence; session survives | registry records 12.F2 done; run not reproduced here — not yet measured |
| 3 | B2 | M34 drill: start a task on the phone, finish it at the desk | the active goal and working context are present at the desk; the raw transcript is absent | not yet measured (12.R1 open; its registry entry names S07.F1, which is `done`) |
| 4 | B1 | new `bench/test_device_capabilities.py` (planned, 12.R2 — does not exist yet) | the brain's device record lists mic, speaker and camera per device; 0 unadvertised capabilities | not yet measured |
| 5 | B1 | `uv run python bench/test_edge_lite.py` (to be extended) | text-only and push-only paths each complete one turn unaided | not yet measured (12.R3 open) |
| 6 | B4 | `ss -ltnp` on the brain host, plus a connection attempt from a non-tailnet host | 0 non-loopback inbound listeners for the edge; 0 successful external connections | not yet measured — structural claim, unverified: no inbound port is opened by construction, but no run and no date records it |
| 7 | B4 | grep the brain for a device-emulating code path | 0 handlers that synthesise a device presence the owner is not at | structural; the phone client is the only away-mode |

Also relevant and already written: `uv run python bench/test_phase6_multidevice.py` and
`uv run python bench/test_session_identity.py` [cross-device]. Both are B1; the cross-device
case is the one 12.R1 needs.

## Failure modes

**Two edges answer.** The owner says the wake phrase in a room with a laptop and a panel, and
hears Afon twice, in two voices, with different content. The arbitration in 12.F3 is the
answer; until per-device capability advertisement lands, the tiebreak is a property of the
client, not of the situation. Diagnose: `journalctl -u openafon-edge -n 200 | grep -i
wake`, then the device ids on those lines.

**The link drops mid-turn.** The edge reconnects (12.F2 records this as fixed) but the
half-finished turn is lost, and the owner restates it. If the reconnect is the cause rather
than the symptom, look at the transport, not at session identity.

**Context does not follow.** The owner starts something on the phone and the desk does not
know. This is 12.R1, which is open; its registry entry names S07.F1 as a dependency and
07.F1 is `done`, so it is a known-open state rather than a
regression. The tempting wrong fix — shipping the transcript so the desk can catch up — is
forbidden by D-40.

**Away from home and the phone path is broken.** There is no fallback body by design (D-39).
Diagnose: `journalctl -u openafon-brain -n 200 | grep -i telegram`, then `curl` the brain's
status endpoint from the phone's network.

## Open questions

1. 12.R1's registry entry names S07.F1, and 07.F1 is `done`; the task itself is still open.
   Is cross-device session identity a change to how sessions are keyed, or a second store
   that mirrors the goal?
2. The wall panel is a third device profile or a second `edge_lite`? D-42 requires an
   independent daemon or a distinct security boundary for a new system, and a panel is
   probably neither.
3. Capability advertisement: pushed once at connect, or polled from `src/afon/brain/presence.py` on the same
   cycle as the activity snapshot?
