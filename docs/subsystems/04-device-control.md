# S04 — Device Control

> **One line:** Mushegh acting on the machine the owner is sitting at — twelve typed operations, verified after the fact, and a kill switch that actually kills.
> **Status:** complete for now; no wall hardware installed · **Registry:** S04 · 4/4 floor, 2/4 raise, 0/1 elite
> **Milestones:** M36 · **Decisions:** D-13, D-41, D-63, D-68

## Purpose

Device control is the place where a wrong turn is visible in the physical world. The
contract is deliberately narrow: twelve operations over the PC link, each with a typed
result, each checked after it fires. Mushegh opens the app, and then confirms the app is
open (04.R1). It sets the volume, and then confirms the volume. A write that returns
without an exception has been *accepted*; whether it landed is a question only a
verification answers — the same distinction S06 applies to documents.

Destructive operations refuse or confirm (04.F2), and the outer boundary is D-13: no
door lock, no main breaker, no recursive filesystem purge, and no external dispatch
without the owner physically present. A dead PC link is reported as unreachable within
one turn and never as success (04.F4) — a device that did not answer is a fact, not a
failure to hide.

The kill switch is the other half of the purpose. D-41: `systemctl stop openmushegh-edge`
over SSH or the tailnet. In-flight tasks take SIGTERM, escalate to SIGKILL after 3 s,
and uncommitted edits remain in a Git stash — never lost, and never committed by the
kill path. A system that can act on a machine must be stoppable in one command, and
stopping it must not cost the owner work in progress.

Physical hardware now sits alongside both halves. The hardware plan puts Shelly
dimmer/relay modules **behind existing wall switches**, and the constraint that matters is
not the automation — it is that **a wall switch must still work by hand**. Programming
lighting control is the goal; a house where the light can only come on by voice is a worse
house, and a module that breaks its own manual override has failed regardless of what the
automation reports. A guest, a visitor and a 2 AM panic are all cases the voice path does
not cover, and none of them know the house has an automation. The remote kill (D-41) and
the edge executor are the software half of the same promise: a stopped automation has to
leave a working light switch rather than a dead wall.

If this is absent, Mushegh can talk but not act, and the owner is back to typing.

## Structure

The brain owns the decision; the machine that owns the hardware runs the agent.

```
utterance ──> brain/tools/  pc_agent handler set (twelve ops)
                  │  PC_LINK
                  v
   laptop:  src/mushegh/edge/pc_agent.py      the executor, typed results
            src/mushegh/edge/device_profile.py what this machine is
            src/mushegh/edge/switch_audio.py   output device routing
            src/mushegh/edge/remote_brain.py
                  │
                  v
   brain:  src/mushegh/brain/pc_link.py       the link; link-down is a state
            src/mushegh/brain/health.py        reachability
   safety: src/mushegh/brain/approvals.py, argcheck.py, audit.py  (D-13, D-41)
```

| Concern | Where |
|---|---|
| The twelve operations, routing | `src/mushegh/edge/pc_agent.py` + `test_pc_agent_routing.py` |
| Verify-after-act (04.R1) | `src/mushegh/brain/pc_link.py`; `test_pc_verify.py` |
| Destructive refusal (04.F2) | `argcheck.py`, `approvals.py`; `test_pc_agent_refuse.py` |
| Sleep / suspend and post-resume (04.F3) | `test_pc_suspend.py` |
| Link-down within one turn (04.F4) | `pc_link.py`; `test_pc_verify.py` extended |
| Remote kill (D-41, M36) | `systemctl stop openmushegh-edge`; `scripts/restart_edge.ps1` to bring it back |
| Service registration on the laptop | `scripts/install_edge_service.ps1` |
| Wall lighting behind existing switches | S28, not S04 — the module only has to keep the hand switch working |
| Appliance circuits (Shelly Plug Gen3 ×4) | S28 (D-68) — appliance circuits only, never the core circuit |

**Process ownership:** the executor is edge. The brain decides and verifies; the
laptop-side agent executes. This split is why "the brain lives on the VPS" does not stop
device control from being visible on the owner's screen.

**What it stores:** the device roster, last-known link state, and per-operation
verification results. The audit trail of what was done and confirmed lives in
`audit.py`.

## Goals

1. **The owner can run any of twelve device operations by voice**, typed result.
2. **No device action is reported as done until it has been verified** (04.R1).
3. **A dead PC is reported unreachable within one turn**, never as success (04.F4).
4. **Destructive operations refuse or confirm** (04.F2); the four D-13 categories refuse
   outright with the owner physically present.
5. **Sleep and suspend are handled**, and post-resume behaviour is defined (04.F3).
6. **The remote kill works**: SIGTERM, SIGKILL at 3 s, uncommitted work in a stash,
   nothing lost and nothing committed by the kill path (D-41).
7. **A named target resolves to the right machine** with more than one online (04.R2).
8. **The wall switch still works by hand** with the automation stopped, dead or
   uninstalled. Lighting control is the goal; a light that only comes on by voice is a
   worse house than one with no automation.

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | Twelve operations | B1 | `bench/test_pc_agent_routing.py` | 12/12 route, 12/12 typed results | not yet measured |
| 2 | Verify-after-act | B1 | `bench/test_pc_verify.py` [04.R1] (35) | 0 actions reported without a post-action read | 35 per the registry gate text; evidence kind `unverified-import` for the surrounding floor — **not yet measured** as a dated run. 04.F4 is the one task in S04 carrying a `recorded-note` (2026-09-12) |
| 3 | Link-down honesty | B1 | `bench/test_pc_verify.py` extended with a link-down case | 0 false successes; 1 turn to report unreachable | not yet measured |
| 4 | Destructive refusal | B4 | `bench/test_pc_agent_refuse.py`; D-13 categories | 0 D-13 categories executable | not yet measured |
| 5 | Suspend handling | B1 | `bench/test_pc_suspend.py` | defined behaviour across sleep, hibernate and resume | not yet measured |
| 6 | **Remote kill (D-41, M36)** | B2 | Kill the edge mid-edit over SSH/tailnet; then inspect the stash | SIGTERM observed; SIGKILL at exactly 3 s; uncommitted work present in `git stash list`; 0 commits from the kill path | not yet measured — the drill is written (M36) but not performed |
| 7 | Named targets | B1 | `bench/test_device_handoff.py` extended | 0 wrong-machine resolutions with >1 device online | not yet measured — 04.R2 open |
| 8 | Wall lighting, hand override | B4 | Manual drill: stop Home Assistant, then throw a dimmer's wall switch by hand | the light comes on with the automation down; 0 rooms where voice is the only path | not yet measured — no module is installed |
| 9 | Relay power loss | B4 | Cut power to one relay module, restore it, then use the switch by hand | the restored state is stated to the owner rather than left to be discovered; 0 silently inert switches | not yet measured — no module is installed |

Goal 6 is the one that would be felt in an emergency, and it is the only benchmark here
that is a drill rather than a test, because a unit test cannot prove that a process
being SIGKILLed leaves a stash behind. Goal 7 is unbuilt: 04.R2 is open and the gate is
an extension of `test_device_handoff.py`, so with one machine online the ambiguity has
never been exercised.
## Failure modes

**A false success.** The worst failure here, and the reason verify-after-act exists.
Mushegh says the app is open and nothing is on screen. The owner discovers it when the
thing they asked for has not happened, minutes later, having trusted the answer. 04.F4
is the same class from the other side: an unreachable machine reported as success.
Reproduce with `bench/test_pc_verify.py`; in the field, check `journalctl` on the laptop
for the link state, then the reachability record the brain holds.

**The link dies mid-turn.** The brain has already promised an action. The fix is to
report unreachable, not to retry silently, because a silent retry is indistinguishable
from a slow machine.

**Suspend loses the turn.** The laptop sleeps between request and execution and the
action lands on wake, minutes later, unasked. `test_pc_suspend.py` covers the
behaviour; in the field the symptom is an action the owner did not remember asking for.

**The kill loses work.** SIGTERM is taken, SIGKILL follows at 3 s, and something in
flight was uncommitted. This is what D-41's stash clause exists to prevent, and it is
the failure that would cost the owner actual work rather than a convenience. Diagnose
with `git stash list` and `git status` on the laptop.

**The wrong machine answers.** With more than one device online, a named target can
resolve to the VPS or the wrong laptop. Nothing detects it because each machine reports
success. 04.R2 is open precisely because this has never been tested.

**The switch goes dead with the relay.** A dimmer or relay module behind a wall switch is
powered from its own circuit, and cutting that power — a tripped breaker, a rewire, a
UPS event — leaves the switch behind it inert until the relay is re-energised. The symptom
is a wall switch that does nothing and looks broken, and the owner finds it by touching it
rather than by reading a report. This is a state to be **told about**, not worked around:
an automation that cannot say "that switch will not work until the relay is back" has
failed the same promise as one that reports a false success, and the wall switch not
working is the half of this system no test can fake.

## Open questions

1. D-41 names the kill as `systemctl stop openmushegh-edge`, but
   `scripts/install_edge_service.ps1` registers a Windows Scheduled Task named
   `MusheghEdge`. Are these the same unit under two names, or does the kill path only
   exist for the Linux side and need a Windows equivalent before M36 can pass?
2. 04.R2 (named targets with more than one machine online) has no measurement and no
   device-handoff coverage beyond the existing extension point. Does the roster need a
   second real device before this can be closed honestly?
3. M36's drill has never been run, so the 3-second SIGKILL-to-SIGKILL interval is
   specified and unverified. Is the interval configurable, or is 3 s a constant in the
   supervisor?
