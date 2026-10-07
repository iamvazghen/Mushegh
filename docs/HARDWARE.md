# Hardware — the integration plan

**Status:** written 2026-10-03 from the owner's device inventory, against the charter in
[DECISIONS.md](DECISIONS.md). This is the **sequencing authority for hardware**. It does not
replace [ROADMAP.md](ROADMAP.md) — it says which box gets touched in which order, and which
milestone each touch belongs to.

**Nothing here is integrated yet.** Every device below is a plan, a credential, or a cable.
Where a device would contradict a charter decision, the contradiction is named in
[§9](#9-where-this-hardware-contradicts-the-charter) rather than smoothed over — that table
is the most useful part of this document.

---

## 1. The rule that governs every line

Hardware does not get to be integrated because it exists. A device joins the system only if
it survives three questions, in this order:

1. **Is it local?** No vendor cloud in the path, no telemetry it doesn't ask for. A device
   that can only be operated through a vendor's servers is not integrated; it is owned.
2. **Which room, and is that room allowed to have a microphone?** D-38 puts bedrooms and
   bathrooms permanently off-limits to ambient hardware. This is a *placement* constraint
   and it is decided before anything is unboxed.
3. **Read, or actuate?** Reads are cheap and reversible. Actuation is where D-13 lives. A
   device that both reads and acts is split in this plan: Afon keeps the read, and the
   physical act stays with the owner (D-14).

## 2. Topology — where each box lives

```
                     ┌──────── the always-on core (UPS-backed) ────────┐
  modem ─ router ─ switch ─┬─ VPS ............... Afon brain, SQLite, vault
                           ├─ Proxmox (Mini-PC) Frigate + Coral, Whisper, Piper
                           └─ NAS (RAID 1) ..... video retention, snapshots
                     └───────────────────────────────────────────────┘
                                   │ tailnet
        ┌──────────────────────────┼───────────────────────────┐
        │                          │                           │
   laptop (Windows)          Pixel + Termux            HA Green + ZBT-1
   primary edge, Hello       mobile edge, beacons      automation + Thread
```

Three rule-holding facts about this picture:

- **The UPS covers the core only.** Modem, router, switch, Mac Mini, Proxmox, NAS. A UPS
  that also fed the house would fail on the wrong side of the 2 AM question.
- **Nothing in the house holds a credential.** The HA token lives on the VPS, the Zigbee
  keys live on HA Green, the camera credentials live on Proxmox. A sensor that needs a cloud
  account to report is not on this diagram.
- **The house never talks to the brain directly.** It reports to HA Green or to the Mini-PC;
  the brain reads one local endpoint. Two hops, both local, is the ceiling before a
  house-to-brain path starts growing its own auth story.

## 3. The allocation table

Every device, its room, the subsystem it lands in, and the phase that touches it. **Phase
numbers are H-phases in [§7](#7-the-order-and-why-that-order).**

| Device | Place | Subsystem | Rule | Phase |
|---|---|---|---|---|
| Modem, router, switch | core | S23 | no inbound ports, ever | H1 |
| APC Back-UPS Pro 1500VA | core | S22, S31 | the one device allowed to cut power | H1 |
| NAS, 2×4 TB RAID 1 | core | S50 | Frigate retention, vault snapshots | H1 |
| Proxmox Mini-PC | core | S26, S18 | Frigate + Coral + Whisper + Piper | H1 |
| VPS | core | S01–S50 | the brain; SQLite, never Postgres (D-02) | H1 |
| Windows laptop | owner | S12, S18, S36 | primary edge + Hello as the D-14 physical act | H1 |
| Home Assistant Green | hallway | S28 | local automation brain | H2 |
| HA Connect ZBT-1 | hallway | S28 | **one** coordinator — see §9.1 | H2 |
| Shelly Plug Gen3 ×4 | by appliance | S28 | appliance circuits only, never the core | H2 |
| Shelly Dimmer/Relay ×4 | behind switches | S28, S04 | manual wall switch must still work | H3 |
| Aqara contact sensors ×5 | doors, windows | S43, S27 | read-only, no mic | H2 |
| Aqara smoke/CO ×2 | kitchen, hallway | S35 | life safety — D-18 may pierce quiet hours | H2 |
| Aqara water leak ×3 | sink, bath, washer | S35, S28 | valve cut-off is the owner's, not Afon's | H2 |
| AirGradient ONE | living room | S27, S33 | read-only, local REST | H3 |
| Aqara FP2 mmWave ×3 | office, living, hallway | S43, S27 | presence in **two** rooms (D-37) | H3 |
| Aqara TRV / Tado valves | occupied rooms | S28 | heating, not presence | H4 |
| Aqara roller blinds ×2 | living, office | S28 | light and temperature | H4 |
| Levoit Core 300 | living room | S28 | on a Shelly plug; air-quality automation | H4 |
| Aqara U200 smart lock | front door | S28 | **read-only to Afon** — D-13 | H4 |
| NFC tags ×10 | on walls, by the door | S28, S10 | the D-14 physical act | H4 |
| Valetudo vacuum | stored, dock | S42 | never scheduled during a focus block | H4 |
| HA Voice Preview ×3 | office, living, hallway | S18, S12 | one mic per non-private room | H5 |
| Garmin Instinct 3 | worn | S34 | FIT export, no vendor cloud | H5 |
| Mentra Live glasses | worn | S26, S12 | camera feed, **not** a voice client (D-36) | H5 |
| Pixel + Termux | carried | S12, S43 | presence beacons, phone client | H5 |
| Reolink PoE ×3 + doorbell | entry, garden, outbuilding | S26 | local RTSP only; no vendor cloud | H6 |
| Google Coral USB | Proxmox | S26 | Frigate's detector | H6 |
| Prusa CORE One | workshop | S49 | D-48's revisit trigger is now met | H7 |
| Fire suppression ball, filament dryer, print kit | workshop | S49 | unattended-printing safety | H7 |
| Brother HL-L2350DW | office | S06 | local print; secrets never queue | H7 |

## 4. The core — H1

Nothing smart happens until the core is honest about what it is running.

**What to do, in order:**

1. **Confirm the UPS is carrying only the core**, and that nothing house-side is on it. A
   UPS that also fed the Shelly plugs would report a clean shutdown while the lights die
   during a cut. The UPS is the one device in this house permitted to cut power, and it does
   that on its own battery logic, never on Afon's instruction (D-13).
2. **Expose one UPS status signal to the brain** — on battery, on line, estimated runtime —
   as a read. Not an actuator. S31 records it as a vital; S22 records the recovery drill.
3. **Mount the NAS, and prove the backup round-trip before anything is written to it.** A
   RAID 1 mirror is not a backup: it protects against one disk failing and nothing else.
   The gate is a restore onto scratch, which is M32.
4. **Decide the Proxmox resource split.** Frigate with the Coral is not a background
   curiosity — it is a continuous detector competing with Whisper and Piper for the same
   cores. Reserve cores for the voice path *first*, and let Frigate take what is left. This
   is the difference between the <300 ms laptop budget (D-35) being a number and being a
   hope.
5. **Wire the laptop's Hello as the D-14 override.** A sensitive management action —
   deploying, changing a credential, overriding a refusal — should require the laptop's
   local biometric, not a spoken "yes". The charter already requires a physical act (D-14);
   this is the cheapest thing on the list that satisfies it.

**Gate for H1:** `journalctl` shows the brain, the UPS and the NAS as three separate
vitals; a restore drill has been run once; the Proxmox core reservation is written down.

## 5. The house — H2 to H4

### H2 — Home Assistant Green, the coordinator, and the sensors that only read

**Home Assistant Green is the automation brain.** It holds state, the entity registry, and
the one token the house needs. Afon talks to it over the tailnet with the single HA token
(D-62, credential 1 of the inventory) — the credential the docs have been calling
`28.F1` and that has never been installed. S28 stops being dark here.

**One coordinator, not two.** Home Assistant Green has its own Zigbee radio. The ZBT-1 has
a better one and adds Thread. Running both against the same mesh is the classic way to end
up with devices that appear and disappear depending on which coordinator claimed them last.
**Pick the ZBT-1** — one USB coordinator, Zigbee plus Thread, one place to look — and leave
Green's radio unused. The U200 is Matter-over-Thread, so Thread has to exist, and a border
router running beside the controller is simpler to reason about at 2 AM than a built-in
radio is to discover late.

**Then, read-only sensors first, in this order:**

1. **Contact sensors ×5** — doors and windows. Cheapest, no power, no network of their own,
   and they pay for themselves immediately: they gate heating, they gate the brief, and
   they are the "is anyone home" signal that no camera should have to provide.
2. **Smoke and CO ×2** — the only devices in this house permitted to interrupt the owner
   outside the D-29 budget, because D-18 makes life safety the one exception. They go
   straight to S35, and S35 is half-built with no emergency list, so **this is the moment
   to write the list down** (see §8).
3. **Water leak ×3** — read and report. The shut-off valve is a physical act, and D-13
   keeps it that way: Afon says "the basin under the kitchen sink is wet", and the owner
   turns the valve. A `Shelly Plug` on the washing machine may cut *that appliance*; it may
   not touch the plumbing.

**Why read-only first:** every one of these is a sensor with no failure mode that costs
anything, and each one makes the next integration easier to test. Actuators come after the
reads are trustworthy.

### H3 — Presence, air, and the sensors that change how Afon speaks

**The Aqara FP2 mmWave sensors are the most valuable thing on this list**, and here is why:
presence in this codebase does not currently exist. `src/afon/brain/presence.py` is a
**laptop activity poller** — it asks the edge what app is in the foreground and how long you
have been idle. It knows "you are in VS Code", and it knows nothing about which room you are
in. Room presence is the thing that makes [S43](subsystems/43-presence-and-continuity.md)
real rather than a title, and it is what lets Afon stop talking to an empty room.

**Three sensors, two rooms, per D-37.** Office and living room cover the practical value.
The third goes in the **hallway**, not a bedroom — a bedroom is air-gapped under D-38, and a
mmWave sensor is ambient hardware. The interesting thing about a hallway is that it is the
one room that is *about* transitions, so a person moving toward the front door is visible
before they reach it. That is the cheap half of S43's "session follows the owner".

**AirGradient ONE** is a local REST read: CO₂, TVOCs, particulates. It is a read, it never
leaves the house, and it is the input the purifier automates on in H4.

### H4 — Actuators, in ascending order of consequence

| Device | What Afon may do | Confirmation | Why |
|---|---|---|---|
| Shelly Dimmer/Relay ×4 | turn lights on and off, scenes | **none** (D-07) | his own lamp; a voice home must not nag |
| Shelly Plug Gen3 ×4 | switch an appliance; cut an appliance on a safety signal | none for the listed silent-ok set; confirm for anything else | appliance circuits only |
| Aqara TRV / Tado valves | set a target temperature | none | heating, gated on contact + presence |
| Roller blinds ×2 | open, close, tilt | none, if pre-set scenes exist | a scene is the unit; raw degree control is a future question |
| Levoit Core 300 | on when PM2.5 or TVOC crosses a threshold, off when it clears | **none** | safety-adjacent and in the silent-ok list |
| Valetudo vacuum | start a room routine | **none**, but it is never *scheduled* | it moves while you are home |
| **Aqara U200 smart lock** | **read state only** | n/a | **D-13** |

**The smart lock is the sharpest edge in this document, and it is exactly where D-13 and
the new hardware meet.** A Matter-over-Thread lock on the front door is the single device
whose wrongful actuation changes the physical security of the house. So:

- Afon **reads** lock state and may say "the front door is unlocked". That is a read, and it
  is useful.
- Afon **never actuates** the lock. Not with a confirmation, not with a code, not with a
  scheduled routine. This is the same rule `28.R4` just enforced against Home Assistant, and
  it applies identically to a lock that is local instead of cloud.

**The NFC tags are how the owner keeps a voice path without breaking that.** A tag on the
wall by the door is a physical act in the literal sense — touch required, no voice command
can fake it. That is D-14's "typed command-line flag or an authenticated hardware key",
satisfied by a 12-cent tag. It also answers the open question left in
[S28](subsystems/28-iot-orchestration.md): *"how does the owner open a locked door by voice
at 2 AM without a confirm standing in for presence?"* — with a tag, the tag **is** the
presence proof. One of the ten tags becomes the door tag; the other nine are room triggers
and a night-mode tag.

**The vacuum is the only device here that moves through the house while nobody is watching
it.** Valetudo keeps it cloud-free, which is why it is on the list at all. The rule that
makes it safe is scheduling, not confirmation: it runs when the house is empty, never inside
a focus block, and never at night (D-32 quiet hours). An autonomous device that interrupts a
meeting is a worse failure than one that misses a room.

## 6. Voice, edge, and health — H5

**Three HA Voice Preview satellites, three non-private rooms.** Each is a mic and a speaker
that forwards audio to the local pipeline. The placement rule is D-38 made physical: office,
living room, hallway. **None in a bedroom, none in a bathroom** — not as a later
reconsideration, not as a firmware flag. If a fourth satellite is ever wanted, the question
to ask first is which room, and the answer has to survive the bedroom rule.

**This is where D-19 stops being an abstraction.** The wake phrase today is **seven** phrases
(`afon`, `alfred`, `robbin`, `assist`, `time to work`, `wake up`, `six-one-nine`) in
`src/afon/config.py`, detected locally by openWakeWord — good, that part is D-19 compliant
and stays. But D-19 also says *one* wake phrase, because "multiple wake phrases multiply
false-positive wakeups on constrained edge hardware". One always-listening mic multiplied by
seven phrases is already a lot; **three satellites make it three times worse**, and a
false wake at 3 AM in three rooms is the exact failure the charter was written to prevent.

So H5 carries a real decision, and it is the owner's: **one phrase on the satellites, and
the phrase that answers to a name rather than a command.** "Time to work" and "six-one-nine"
are shortcuts for a single-user laptop, where a misfire costs nothing because the owner
pressed the button. On an always-listening satellite it costs a wake-up. That is a change to
`AFON_WAKE_WORDS`, one line, and it should be a conscious one.

**The glasses are a camera, not a voice client.** D-36 parks smart glasses for voice until
sub-second latency is solved, and the hardware does not change that condition — the
measured worst case is still ~700 ms against a <350 ms budget (D-49). So the Mentra glasses
are integrated as a **POV capture device feeding the local detector**, which is what they
are actually good at, and *not* as a wake-and-talk endpoint. If the latency work lands later,
the glasses join the voice path then, with no re-integration.

**The Pixel with Termux** matches D-39 exactly: away from home, a phone client over the
tailnet, background presence beacons, no VPS-side stand-in pretending to be a body.

**The Garmin answers an open question, and unblocks real work.** One of the three owner
decisions that were blocking deletions was *"is there a wearable in the house at all?"* — and
there is. FIT export, no vendor cloud, no proprietary API, which is exactly the shape D-57
wants. `34.R4` was deferred on the grounds that no data source existed; a data source now
exists, so **`34.R4` is un-deferred** and S34 stops being half-built-for-a-reason-that-is-no-
longer-true. The export lands in the vault as a raw file, and the derived numbers are
curated facts — which is D-21's split between what expires and what is kept.

## 7. Perception — H6, and the one that needs a decision first

Cameras are the item on this list that changes the character of the system, so they are last
and they are gated on a decision rather than on a purchase.

**The good news is the hardware does the right thing by default.** Frigate plus the Coral
detector is entirely local, which is what D-61 requires of derived state. The bad news is
that `src/afon/config.py`'s **vision model chain is cloud-only** — MiniMax, Gemini and Groq,
all remote. So the moment a frame goes to a vision model, the local property is gone.

**Therefore the rule for H6, and it is not negotiable by convenience:**

> Detections stay local. **Video frames never leave the house.** No frame is sent to a
> vision model, to a logger, or to a crash report.

**The codebase already contains both patterns, which is why this is a rule and not a hope.**
`src/afon/brain/tools/camera.py` holds two tools doing opposite things:

- **`look_around`** grabs a webcam frame and hands it to a vision model through
  `LLMClient.see` — the frame leaves the machine.
- **`visual_presence`** grabs a frame and counts faces **locally** with an OpenCV haar
  cascade. Its own docstring says it: "no cloud, and the image never leaves the machine
  (only a yes/no + count)".

That is the correct design, already written, in the same file. So D-66 is not asking for
something new — it is asking for the second behaviour to be the *only* one on the detector's
path, and the first to stay exactly where it is: an explicit owner-initiated question about
something he is looking at. The practical consequence is that `look_around` must never
become the channel through which a Frigate event is explained, because the moment it is,
"local detection" is a claim about where the metadata was formed, not about where the pixels
went. `26.R5` tracks it.

`visual_presence` is worth naming separately, for a reason that has nothing to do with
cameras in the house: it is a **local face counter on the laptop webcam** — a second
presence source that predates the mmWave sensors, and an ambient camera in a room whether or
not anyone intended one. It is legitimate (it is the owner's own machine, counting his own
seat) and it should stay, but S43 needs to know it exists when it decides which presence
source is authoritative.

**Two more things the cameras force into the open:**

- **RTSP is local only if the camera is configured that way.** Reolink cameras ship with
  cloud enabled. The gate is a camera configured for RTSP with the vendor account
  disconnected, proven by pulling a stream with the WAN cable out — a "local" stream that
  still authenticates against a vendor is not local.
- **The doorbell's two-way audio is a microphone at the front door.** Under D-38 and D-51 it
  needs the same placement answer as a room satellite. The owner should know that answering
  the doorbell is the one interaction where a guest's voice is captured.

**Three cameras is also the number that makes the guest question real.** D-51 keeps the user
model to one person; three indoor cameras plus presence sensors plus a doorbell is the
hardware version of that question. The plan's answer is the same as the charter's: cameras
in the entry, the garden and the outbuilding; **rooms where a guest would be recorded are
covered by presence, not by video.** If the owner ever disagrees, the honest move is to
change D-51 in writing, not to quietly widen the camera list.

## 8. Fabrication and printing — H7, and a decision the owner now has to make

**S49's revisit trigger has been met.** D-48 recorded the trigger for reconsidering dropped
fabrication scope: *"owning a printer, and wanting a slicer it can call."* The owner now
owns a Prusa CORE One, a fire-suppression ball, a filament dryer and a maintenance kit.
That is the trigger, half of it at least.

**So S49 needs an owner decision, and by D-47 it cannot be made by anyone else.** My
recommendation is to **keep it dropped**, for a reason the hardware itself supplies: the
second half of the trigger is *"wanting a slicer it can call"*, and nothing in this inventory
suggests the owner wants that. A printer in a workshop is a tool for making brackets. A
printer Afon can drive is a safety surface with a heated bed and moving axes, in a house
where D-13 already refuses door locks. The charter's instinct was right, and the new
hardware confirms it rather than overturning it.

**What the printer does need, regardless of S49:** a fire-suppression ball over the hot end
for unattended prints, a dry box so hygroscopic filament does not wreck dimensional
accuracy, and — because the printer is unattended-capable — a rule that **a print never runs
while the house is empty overnight.** An unattended machine that is also unsupervised by the
UPS is a 2 AM question with a new subject.

**The laser printer** is S06's physical surface. One constraint, and it is a real one: the
owner's stated use includes *"1Password paper emergency sheets"*, which means **secrets on
paper**. The print action itself is local and fine. The rule is that a print job's content
must never enter the agent's context, the tool log, or the audit trail — the job is
"print the emergency sheet", never the sheet's contents. That is D-57 with paper instead of
git.

## 9. Where this hardware contradicts the charter

The table that matters. Every row is a real conflict, not a hypothetical one.

| # | Conflict | Resolution | Status |
|---|---|---|---|
| 1 | **Two Zigbee radios** — Green has one, the ZBT-1 has a better one | Use the ZBT-1 only; leave Green's radio unused. One coordinator owns the mesh | **open — needs your nod** |
| 2 | **3 mmWave sensors vs D-37's two rooms** | Office + living for presence, hallway for transitions. No bedroom, ever (D-38) | resolved in this plan |
| 3 | **3 mic satellites vs D-38's air-gapped rooms** | Office, living, hallway. A bedroom satellite is a D-38 violation, not a config choice | resolved in this plan |
| 4 | **7 wake phrases vs D-19's one phrase**, now ×3 satellites | Cut to one answering phrase on the satellites. Multiplies false wakes 3× | **open — needs your nod** |
| 5 | **A Matter smart lock vs D-13's door-lock refusal** | Afon reads lock state, never actuates. The same rule `28.R4` now enforces against HA | resolved — enforced in code today for HA |
| 6 | **Shelly "hard-cutoff relays" vs D-13's main breakers** | Appliance circuits only. Never the core circuit, never anything UPS-backed | **open — needs your nod on which circuits** |
| 7 | **3 cameras + doorbell vs D-51's one-person model** | Entry, garden, outbuilding. Rooms a guest would be in get presence, not video | **open — needs your nod** |
| 8 | **Cloud vision chain vs D-61's local-only state** | Coral/Frigate detect locally; frames never leave the house. The `see()` path must not become the detector's channel | **open — needs your nod** |
| 9 | **Glasses in the inventory vs D-36 parking them** | Integrated as POV camera only. The voice path waits on the latency work (D-49) | resolved in this plan |
| 10 | **Garmin answers the wearable question** | `34.R4` un-deferred; S34 is no longer half-built for a missing reason | **applied** |
| 11 | **A printer meets S49's revisit trigger** | Keep S49 dropped. The trigger's second half — *wanting a slicer it can call* — is not met | **open — needs your sign-off (D-47)** |
| 12 | **Printing 1Password sheets vs D-57** | The job is "print the sheet"; the contents never enter context, tools or audit | resolved in this plan |
| 13 | **Frigate + Whisper + Piper on one Mini-PC** | Reserve voice cores first, let the detector take the remainder. Otherwise the D-35 latency budget is a hope | **open — needs a core split decision** |
| 14 | **The vacuum moves while the house is occupied** | Never scheduled in a focus block or at night. D-29's budget applies to the noise, not just the speech | resolved in this plan |

## 10. The order, and why that order

Each phase is a prerequisite for the next, not a preference.

| Phase | What it delivers | Why it cannot be earlier |
|---|---|---|
| **H1** Core | UPS, NAS restore drill, Proxmox core split, laptop Hello as the D-14 act | Every later phase writes to storage or depends on a latency budget that the core split sets |
| **H2** HA + reads | Green live, ZBT-1 chosen, HA token installed — **S28 stops being dark** — plus contacts, smoke/CO, water | Actuators need a trustworthy read layer; the smoke/CO work forces the S35 emergency list to be written |
| **H3** Presence + air | FP2 ×3, AirGradient, room presence that is not a laptop poll | Presence gates the heating and lighting in H4 |
| **H4** Actuators | Dimmers, plugs, TRVs, blinds, purifier, NFC tags, lock read-only, vacuum scheduling | Each one is silent-ok automation built on H2's reads and H3's presence |
| **H5** Voice + health | 3 satellites, glasses as camera, Pixel beacons, Garmin FIT | Satellites multiply false wakes, so they wait until the wake set is decided |
| **H6** Perception | Coral, 3 cameras, doorbell, Frigate retention | Gated on a privacy decision, not on hardware arriving |
| **H7** Fabrication | Printer safety, local printing, the S49 sign-off | The cheapest work in the plan, and deliberately last because it is the most optional |

**H1 and H2 are the whole plan's critical path.** H2 alone unblocks the cheapest real win in
the roadmap — M20, the desk lamp — and it converts the two systems the charter calls dark
(S28) and half-built (S35) into ones that do something.

## 11. What this plan does not do

- **It does not open a single inbound port.** Every integration above is outbound from the
  core or reachable over the tailnet. If a device needs an inbound path, it does not get
  one; it gets a relay.
- **It does not add a fifth system.** A new subsystem needs an independent daemon or a
  distinct security boundary (D-42). Hardware integration lands in the systems that already
  own the job — S28 for the house, S26 for perception, S43 for presence — and only Frigate
  is arguably a separate daemon, which is a future decision, not this one.
- **It does not schedule the vacuum, cut power, or unlock a door.** Those are the three
  things in this document with a physical consequence, and all three stay with the owner.
