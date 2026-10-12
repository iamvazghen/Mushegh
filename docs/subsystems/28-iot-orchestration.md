# S28 — Environmental / IoT Orchestration

> **One line:** Mushegh reads and actuates the house's own sensors, lights, climate and air through a local Home Assistant Green — and today controls nothing at all, because no token is installed.
> **Status:** built and **dark** — complete code, no token, controls nothing; the hardware that would make it real is ordered but not installed · **Registry:** S28 · 2/5 floor, 0/5 raise, 0/1 elite
> **Milestones:** M20 · **Decisions:** D-07, D-13, D-14, D-62, D-63, D-64, D-65, D-68

## Purpose

Mushegh actuates the house: a predefined lighting scene, the desk lamp, a climate
setpoint, a named multi-device state. It reads an entity's real state and reports
what it observed, not what it commanded. It confirms before anything with a security
edge, and it **refuses** the two domains D-13 puts outside the blast radius entirely —
`lock` and `garage_door`. A typed confirm is not physical presence, so for those two a
confirmation is not a slower path to the same outcome; there is no path at all. The
refusal lives inside `ha_call`, before a request is built, rather than in the policy layer
above it, so a refactor of the confirm gate cannot quietly reopen it. Registry task
`28.R4` is **in-progress**: `bench/test_blast_radius_refusal.py` is green at 29/29, and
D-43's seven-day bar is still outstanding.

This system is **dark**. The code is complete, the schemas are registered, the
read-back verification is written and gated — and there is no Home Assistant token on
the host, so every call takes the "not configured" path. Under D-46 dark work is not
progress and must not be counted as any. The unblock is a single credential, which is
exactly why it is the cheapest available win in the roadmap (M20, four hours) and
exactly why it needs a live drill before anyone calls it wired.

The credential budget is four tokens in total (D-62) and Home Assistant is one of them.
There is no room for a second smart-home integration and no cloud vendor in the loop.

**The hardware plan names the box.** [HARDWARE.md](../HARDWARE.md) §5 (H2) puts a
**Home Assistant Green** in the hallway as the local automation controller: it holds the
state, the entity registry, and the one token the house needs. Mushegh talks to it over the
tailnet with the single HA token — credential 1 of the four (D-62) — and that credential is
the one the docs have been calling `28.F1` and that has still never been installed. Installing
it is what makes S28 stop being dark, and it also settles the old question of whether an
instance exists to install a token into: it does, and it is named.

**One coordinator, not two.** Green ships a built-in Zigbee radio. The HA Connect ZBT-1 has
a better one and adds Thread, and running both against one mesh is the classic way to end up
with devices that appear and disappear depending on which coordinator claimed them last.
**D-64** picks the ZBT-1 and leaves Green's radio unused — one radio, one owner of the mesh.
The Aqara U200 is Matter-over-Thread, so Thread has to exist, and a border router sitting
beside the controller is simpler to reason about at 2 AM than a built-in radio is to discover
late.

**Reads first, actuators after.** D-63 gates every device on three questions, in order: is it
local, which room, read or actuate. The H2 order follows that. **Read-only first:** Aqara door
and window contacts ×5, then Heiman/Aqara smoke+CO ×2, then Aqara water leak ×3. Every one
is a read whose failure mode costs nothing, and each one makes the next integration easier to
test. The smoke/CO pair is the only hardware in this house permitted to interrupt the owner
outside the D-29 budget, because D-18 makes life safety the one exception.

**The water shut-off valve stays physical.** Mushegh reports *"the basin under the kitchen sink
is wet"*; the owner turns the valve. A Shelly plug on the washing machine may cut *that
appliance* — D-68 confines the plugs to appliance circuits — and it may not touch the
plumbing.

**The Aqara U200 front-door lock is the sharpest edge in the inventory.** Mushegh **reads** its
state and may say "the front door is unlocked". It **never actuates** it: not with a
confirmation, not with a code, not inside a scheduled routine, and not on any path — Matter,
Thread, Zigbee, or through Home Assistant. That is D-13 applied to local hardware instead of
a cloud one (D-65), the same rule `28.R4` now enforces against Home Assistant, and `28.R5`
tracks the lock itself against a planned gate.

**The NFC tags close the 2 AM question.** Ten tags arrive with the plan, and one of them is
the answer to the question this document used to leave open. A tag on the wall by the door is
a physical act in the literal sense — touch required, unforgeable by voice — so the tag, not
a confirmation, is the presence proof. That is D-14 satisfied by a 12-cent object (D-65). One
tag becomes the door tag; the other nine are room triggers and a night-mode tag.

If this is absent: the north-star Tuesday loses its 08:30. A spoken phrase that sets
focus mode has no physical half, and the first item on the silent-ok list (D-07) —
toggling a predefined lighting scene — cannot be exercised at all. Everything else
Mushegh does is a voice answering a voice.

## Structure

`src/mushegh/brain/tools/smarthome.py` is the whole surface, 161 lines. Two schemas,
registered into the tool belt like any other handler (D-04):

- `ha_state(entity)` — read one entity. Silent-ok: it is a read (D-07).
- `ha_call(domain, service, entity)` — actuate.

`_configured()` is False without `MUSHEGH_HA_URL` and `MUSHEGH_HA_TOKEN`; the handlers
return a spoken note naming what is missing rather than raising. `_read_back()` re-reads
the entity after the call and compares it against `_EXPECTED`, which is what makes
"the state I observed" checkable at all (28.F2, done).

`SENSITIVE_DOMAINS` in the same module is the security-edge list. `BLAST_RADIUS_DOMAINS`
in the same module is the smaller list that refuses outright: `lock` and `garage_door`.
`CONFIRM_TIER` in `src/mushegh/brain/proactive.py` lists `ha_call`, and its domain-aware
check mirrors the sensitive list: `light`, `scene`, `climate` and `switch` flow silently;
`alarm_control_panel`, `cover` and `climate` confirm; `lock` and `garage_door` are
refused inside `ha_call` before the URL is even built. Both layers agree those two are
sensitive — the gate still flags them — but only the refusal is load-bearing.

Data flow: utterance -> `src/mushegh/brain/agent.py` -> `ha_call` schema ->
domain-aware confirm gate -> REST POST to the HA instance over the LAN or the tailnet
-> `_read_back()` -> observed state -> one spoken line.

**What the house adds, and in what order.** None of it is installed; every row is the
ordered plan from [HARDWARE.md](../HARDWARE.md) §5, and the order is the argument.

| Device | What Mushegh may do | Confirmation |
|---|---|---|
| Aqara contact sensors ×5 | read; gate heating, the brief, and "is anyone home" | n/a (a read) |
| Heiman/Aqara smoke+CO ×2 | read and raise; may pierce quiet hours (D-18) | n/a |
| Aqara water leak ×3 | read and report; the valve is the owner's | n/a |
| Shelly Dimmer/Relay ×4, behind wall switches | turn lights on and off, run scenes | **none** (D-07) — the manual wall switch must still work |
| Shelly Plug Gen3 ×4 | switch an appliance; cut an appliance on a safety signal | none for the silent-ok set; confirm otherwise (D-68) |
| Aqara TRV / Tado valves | set a target temperature in an occupied room | none |
| Aqara roller blinds ×2 | open, close, tilt — as pre-set scenes | none |
| Levoit Core 300 on a plug | on when PM2.5 or TVOC crosses a threshold, off when it clears | **none** — safety-adjacent |
| **Aqara U200 front-door lock** | **read state only** | n/a — never actuated (D-13, D-65, `28.R5`) |
| NFC tags ×10 | the owner's physical act (D-14, D-65) | the touch *is* the proof |

The plugs stop at the appliance: never the main breaker, never the network, never anything
UPS-backed, because a plug that can make the house dark is a plug that can make the brain
unreachable (D-68).

Ownership: the brain process. No new daemon, no new store, no new table, no inbound
port. `docs/home-assistant.md` holds the token setup, the confirmation policy and the
live acceptance procedure. Open tasks: `28.F1` (the token), `28.R1` named scenes,
`28.R2` presence-driven rules, `28.R3` offline-entity reporting, `28.R4` blast-radius
refusal (in-progress), `28.R5` the U200 read-only on every integration path,
`28.F4` the ordered install-then-scenes sequence, `28.F5` dry-run plus an
interlock on every physical action, `28.E1` a week of scenes with no surprises.

## Goals

1. Actuate one real entity on a spoken command, with the answer checked against a
   read-back rather than against the command.
2. Flow lighting scenes silently, confirm security edges (D-07), and refuse the blast
   radius outright with no confirmation path at all (D-13) — `lock` and `garage_door`,
   which is what the code now does (`28.R4`). The middle tier D-13 does not name —
   `alarm_control_panel`, `cover`, `climate`, `water_heater` — keeps confirming, because
   a wall where a speed bump was wanted is its own failure.
3. Degrade to a spoken "not configured yet" note when the token is absent, with no
   exception and no stack trace.
4. Report observed state, never the command sent (28.F2).
5. Report a dead entity as dead rather than reporting success (28.R3, open).
6. Reads land before actuators: the contact, smoke/CO and water-leak sensors are
   trustworthy before anything in the house is switched.
7. The listed actuators flow silently inside the D-07 whitelist — lights and scenes, an
   appliance on a plug, a purifier on an air reading — and the wall switch behind every
   dimmer still works by hand.
8. The U200 lock is read-only on **every** integration path — Matter, Thread, Zigbee,
   Home Assistant, macro, skill — with no confirmation flag that unlocks one (`28.R5`).

## Benchmarks

1. **B2 live drill** — install the token, speak 50 lamp toggles, measure end to end.
   Threshold: p95 < 500 ms and 50/50 spoken answers matching the post-call read-back.
   Last measurement: `not yet measured`. The procedure is written up in
   `docs/home-assistant.md`; the token is not installed, so it has not been run.
2. **B1** — `bench/test_smarthome_verify.py`, `bench/test_phase11_integrations.py`,
   `bench/test_confirm_tier_documented.py`, `bench/test_blast_radius_refusal.py`.
   Threshold: 0 sensitive domains ungated, and 0 blast-radius domains reachable even when
   confirmed. Last measurement: the first three green as of 2026-10-03;
   `test_blast_radius_refusal.py` green 29/29 the same day — four attempted bypass
   arguments change nothing, the middle tier still confirms, and `ha_state` still reads a
   lock, because information is not actuation. The registry records 28.F2/F3 `done`
   against these gates with no field measurement, and records `28.R4` as **in-progress**
   rather than done: D-43's seven-day bar is outstanding and the token is not installed,
   so no live drill has run.
3. **B1** — unconfigured host: both `ha_state` and `ha_call` return the spoken note
   with `MUSHEGH_HA_TOKEN` unset. Threshold: 0 exceptions, 0 tracebacks in the journal.
   Last measurement: `not yet measured`.
4. **B2 drill** — change one light out of band in the HA UI, then ask Mushegh for its
   state. Threshold: the spoken answer matches the observed state in 10/10 trials.
   Last measurement: `not yet measured`.
5. **B1 planned** — `bench/test_smarthome_verify.py [offline]`, extended to an
   unreachable entity. Threshold: 0 cases where an offline entity is reported as a
   success. Last measurement: `not yet measured` — the assertion is not written and
   `28.R3` is open.
6. **B1 planned** — new `bench/test_lock_readonly.py`, the `28.R5` gate; the file does not
   exist yet. Threshold: reading the U200 lock entity succeeds, and 0 lock or unlock service
   calls reach the mesh from any path — HA, Matter, Thread, Zigbee, macro, skill — with or
   without a confirmation flag. Last measurement: `not yet measured`.
7. **B1 planned** — new `bench/test_ha_devices.py`, the installed-hardware gate; planned
   and not written. Threshold: each of the 5 contacts, 2 smoke/CO and 3 water-leak sensors
   reports, and 0 of the plugs is reachable on a non-appliance circuit. Last measurement:
   `not yet measured` — none of the hardware exists yet.
8. **B4 drill** — the manual wall switch. Kill Home Assistant, then walk to a dimmer and
   throw the switch by hand. Threshold: the light comes on with HA down; 0 rooms where the
   light only comes on by voice. Last measurement: `not yet measured` — no module is
   installed.

## Failure modes

**No token installed — the current state.** Every `ha_*` call returns "not
configured yet" and nothing in the house moves. The owner hears a correct, useless
answer and may not connect it to the missing credential. Three commands:

    journalctl -u openmushegh-brain -n 200 | grep -i "home.assistant"
    test -n "$MUSHEGH_HA_TOKEN" && echo token-set || echo token-missing
    curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $MUSHEGH_HA_TOKEN" "$MUSHEGH_HA_URL/api/"

A 200 from the third line alongside "not configured" in the first means the token is
missing from the brain process's environment, not absent from the disk.

**Home Assistant unreachable with a token present.** The call raises inside
`safe_call` and returns a short speakable error; nothing changes and the owner is told
nothing happened. Same `curl`, then `journalctl -u home-assistant --since "10 min"`.

**A scene fires and the room is wrong.** `_read_back` returns the real state, so the
spoken answer will contradict the command. That contradiction is the signal. There is
no compensating rollback in `ha_call` — `28.F5` is open.

**A door lock is called.** It refuses — `ha_call` returns the spoken boundary and never
builds a request, and no `confirmed` / `confirm` / `force` argument changes that. Before
`28.R4` this path confirmed, which was a D-13 breach: a confirmed lock call is a missing
refusal, not a tuning problem. What remains unproven is the live path — the token is not
installed, so the refusal has only ever been exercised against a stubbed HTTP layer.

**Two coordinators claim one mesh.** If Green's radio and the ZBT-1 are both left talking to
the same devices, entities appear and disappear depending on which one answered last, and
the symptom reads as a flaky device rather than a duplicated coordinator. D-64 resolves it
by construction — the ZBT-1 owns the mesh and Green's radio stays unused — and the check is
one glance at the HA radio panel: exactly one coordinator, with the Thread stack on it.

**A plug is wired to the wrong circuit.** The failure this document cannot detect from the
brain's side: a Shelly plug on something that matters, so a "silent" automation cuts the
network or a UPS-backed circuit and the house goes dark with the brain unreachable. D-68
bounds the plugs to appliances, and the audit is visual, at install time, by the owner.

**A relay module loses power and the switch dies with it.** Cutting power to a dimmer or
relay behind a wall switch leaves that switch inert until the relay is re-energised. It is
recorded here and in [S04](04-device-control.md) because it is a physical state the owner
learns by touching a dead switch, not by reading a report — see that document's failure
modes.

## Open questions

1. Which entities are actually in scope? The plan names ten read-only sensors and the
   actuator set above, but the HA entity list is the real boundary of this system and
   nobody has written the whole one down. D-37 caps ambient sensing at two rooms, and the
   hallway's third sensor is the transition room rather than a presence room.
2. Should `28.R2` presence-driven automation exist at all? It ties physical actuation
   to inferred state, and D-61 requires that state to stay on the host. An inference
   error would then move lights, not merely a label. The mmWave sensors make the input
   real, which is precisely what makes that error worth worrying about.
3. **Answered — the 2 AM question.** "How does the owner open a locked door by voice at
   2 AM without a confirmation standing in for presence?" now has an answer: the NFC tag
   on the wall by the door. Under D-65 the tag *is* the presence proof, so this stops
   being a design question. What is left is a preference worth writing down — whether the
   owner wants the tag alone for the door, or the tag plus a spoken confirmation for
   non-lock house actions after 2 AM. That is a routing preference, not a safety one.

