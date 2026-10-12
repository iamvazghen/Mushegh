# S18 — Microphone & Speaker Management

> **One line:** the audio path, which is the product — every other subsystem is downstream of a
> voice that arrives cleanly and answers inside the budget.
> **Status:** complete for now · **Registry:** S18 · 4/5 floor, 0/8 raise, 0/1 elite
> **Milestones:** M12, M13, M14, M15, M16, M39 · **Decisions:** D-17, D-19, D-35, D-49, D-56,
> D-16, D-55, D-67

## Purpose

If the microphone hears badly, no amount of model quality downstream matters. This is the
system that decides when Mushegh is listening, what he heard, where the sound goes, and how
quickly he stops talking when the owner talks over him. It is where the numbers live, and the
numbers are not good yet.

**Barge-in worst case is ~700 ms against a <350 ms budget** (D-49, M12). That is a defect
with a number, not a preference, and it is the single most felt thing about the voice path.
**End-to-end is <300 ms on the laptop and <500 ms on the phone** (D-35, M13), measured over 30
utterances per device with the method and date recorded — which has not been done.

Three rules shape the rest. On a poor microphone the gate **rejects marginal audio and offers
push-to-talk** rather than guessing through noise (D-56, M14): a missed word is cheap, a
fabricated one is not. **Local TTS is the default** — Piper or Kokoro — with cloud opt-in,
because at 3 AM latency and privacy dominate cost and personality, every time (D-17, M16).
And there is **one wake phrase** (D-19), sacred to on-device keyword spotting, because
multiple phrases multiply false-positive wakeups on constrained hardware.

The handover gap sits here too: there is no reproducible edge audio tuning guide, and that
blocks anyone but the owner from reaching a working voice loop (D-55, M39).

**Three HA Voice Preview Edition satellites are coming — office, living room, hallway** — one
per non-private room, each a mic and a speaker that forwards audio to the local edge pipeline
([../HARDWARE.md](../HARDWARE.md) H5). The placement rule is D-38 made physical: no bedroom,
no bathroom, decided before anything is unboxed. This is where D-19 stops being an
abstraction. Seven wake phrases on one laptop the owner wakes with a button press is a
harmless convenience; **seven phrases on three always-listening satellites multiplies false
wakes threefold**, and a 3 AM false wake in three rooms is the exact failure the charter
exists to prevent. **D-67 proposes one answering phrase on the satellites** — a name rather
than a command, leaving "time to work" and "six-one-nine" on the laptop where a misfire costs
nothing. It is proposed, not in force: the choice is the owner's nod, and no satellite exists
to measure against yet.

## Structure

| Path | Role |
|---|---|
| `src/mushegh/edge/wake_word.py` | openWakeWord, local, nothing forwarded until a wake word is heard; a listening window opens and closes on silence |
| `src/mushegh/edge/audio_gate.py` | `HalfDuplexGate` — drops mic audio while Mushegh is speaking, plus a tail cooldown. The stopgap that replaced barge-in on open speakers |
| `src/mushegh/edge/aec.py` | The echo-cancellation seam for open speakers; the only filters that actually cancel are proprietary, licence-gated SDKs |
| `src/mushegh/edge/vad_bargein.py` | Silero VAD plus `BargeInProcessor`; "user started speaking while Mushegh is talking" becomes a real interruption |
| `src/mushegh/edge/stt.py` | STT selection — Deepgram by default (streaming, ~300ms endpointing) with local Whisper as the fallback. **The unresolved conflict, not a settled choice:** Deepgram cannot transcribe Ukrainian, which the owner speaks, and does so *silently* — plausible Russian comes back and Mushegh answers confidently in the wrong language. Local Whisper hears all six but measured at 3.00s mean on this CPU (1.39x real time, 1.7x over budget). D-78 and 18.R7 |
| `src/mushegh/edge/stt_routing.py` | 18.R7 — which ear transcribes this turn, as pure logic: a language the fast ear cannot hear moves the **next** turn to the local one, learned from the transcript. Not in the live frame path yet (`18.R8`); the predictive version was measured at 1089ms/turn and rejected |
| `src/mushegh/edge/tts.py` | TTS selection — Piper, Kokoro, ElevenLabs, switched by one setting |
| `src/mushegh/edge/audio_devices.py` | Output device discovery and selection, including the A2DP/HFP distinction on AirPods |
| `src/mushegh/edge/switch_audio.py` | The voice command "switch to my headphones", saved as a preference the watchdog picks up |
| `src/mushegh/edge/audio_watchdog.py` | Liveness: a probe timestamps every input frame and trips on a stale stream after a Bluetooth topology change |
| `src/mushegh/edge/device_profile.py` | Classifies the endpoint and decides whether barge-in is safe |
| `src/mushegh/edge/latency_meter.py` | `TTFWMeter` — attributes a turn to stt / brain / tts so a lag is fixed with data rather than by ear |
| `src/mushegh/edge/voice_health.py` | Cloud-first with automatic local failover, on a startup probe and a runtime error counter |
| `src/mushegh/edge/listening_pulse.py`, `src/mushegh/edge/audio_gate.py`, `src/mushegh/edge/stt.py`, `src/mushegh/edge/tts_leadin.py` | Audible proof of life and the lead-in so the owner knows the mic is open |
| `src/mushegh/edge/_supervisor.py` | `run_supervised` relaunches the edge on any return |

**Endpoints, not implementations.** Three HA Voice Preview Edition satellites — office, living
room, hallway (H5) — forward audio to this pipeline rather than hosting one. Each is an
endpoint `src/mushegh/edge/device_profile.py` already knows how to classify, and they are what
D-38 and D-67 are about. There is no satellite row in the table above, and that absence is
the honest state: the hardware is a plan, and the wake-set question behind it is open.

All of it runs in the **edge** process, on the machine the owner is sitting at. The brain
never touches audio.

Two places where the code and the charter are not yet the same thing, stated plainly:
`src/mushegh/edge/wake_word.py` ships and advertises a **multi**-wake-word set against D-19's single phrase,
and `src/mushegh/edge/tts.py` names `elevenlabs` as the default while `src/mushegh/edge/voice_health.py` states that cloud is
the primary route — which inverts D-17. Both are M15 and M16 work, not accidents.

Two further registry tasks were added on 2026-10-03 because the environment contradicts two
more decisions, and both are `open` with a `planned-test` gate and no measurement behind
them. **18.R4** (`new test_tts_local_default.py`): D-17 makes local TTS the default with the
cloud path an explicit opt-in, and the code is the other way round — `tts_provider` *defaults*
to `elevenlabs` in `src/mushegh/config.py` with `MUSHEGH_ELEVENLABS_API_KEY` configured, and
`src/mushegh/edge/tts.py` names cloud as the default with Piper and Kokoro reached only as the
fallback that fires when a cloud provider cannot be constructed. That is a real mismatch, not
a soft one. **18.R5** (`new test_wakeword_offline.py`): the wake phrase is detected by
openWakeWord and is already local, so what is missing is the *assertion* — a wake must still
fire with all network egress blocked. The same task removes the two settings that imply
otherwise: `MUSHEGH_WAKE_WORD_ENGINE` and `MUSHEGH_PORCUPINE_ACCESS_KEY` are still listed in
`.env.example` but have been read by nothing since 2026-08-01.

## Goals

1. Barge-in halts playback within 350 ms, from a measured worst case of ~700 ms (D-49, M12).
2. End-to-end latency: laptop <300 ms, phone <500 ms, measured over 30 utterances per device
   (D-35, M13).
3. A poor microphone is rejected, not guessed through, and push-to-talk always works
   (D-56, M14).
4. Local TTS is the default and there is no outbound audio at 3 AM (D-17, M16).
5. One wake phrase, and a noise-floor sweep admits no false wake (D-19).
6. English ≥95% and German ≥90% intent accuracy; the other four languages are no longer
   claimed (D-16, M15).
7. A dead mic or speaker after a device change recovers without a manual restart (18.F1).
8. Three satellites behave as one voice client: one answering phrase per satellite, one room
   answering at a time, and no false wake admitted by an overnight sweep in any of the three
   (D-19, D-67, D-38). No satellite exists, so nothing here is measurable yet.

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B5 | p95 barge-in from `src/mushegh/edge/latency_meter.py` | <350 ms | **~700 ms worst case**, owner-reported 2026-10-03 (D-49). p95 not yet measured |
| 2 | B5 | `uv run python bench/voice_live_bench.py`, read the stt/brain/tts split | laptop <300 ms, phone <500 ms, over 30 utterances each, method and date recorded | not yet measured |
| 3 | B1 | `uv run python bench/voice_offline_check.py`, plus a noise-floor sweep | 0 false wakes admitted by the sweep; the push-to-talk path succeeds in every case | not yet measured (M14 open) |
| 4 | B1 | `uv run python bench/test_local_voice.py` | default config is local; 0 outbound audio requests at 03:00; the cloud path degrades cleanly | not yet measured (M16 open) |
| 5 | B1 | `uv run python bench/test_wakeword.py`, `uv run python bench/verify_wakeword.py` | exactly one configured wake phrase; 0 false wakes on a recorded noise sweep | registry records 18.F3 as done for the barge-in path; the single-phrase requirement is not yet measured |
| 6 | B1 | intent matrix after the language cut | EN ≥95%, DE ≥90%; FR/RU/AM/UK removed from the claimed matrix (D-16) | not yet measured (M15 open) |
| 7 | B1 | `uv run python bench/test_audio_watchdog.py` | a stale stream is detected and the pipeline rebuilt; 0 manual restarts after a Bluetooth topology change | registry records 18.F1 done; run not reproduced here — not yet measured |
| 8 | B1 | an overnight noise sweep per satellite with network egress blocked — **planned drill; no satellite exists to run it on** | 0 false wakes per satellite overnight; 1 answering phrase configured per satellite (D-19, D-67) | not yet measured |

Routing and output: `uv run python bench/test_audio_route.py` and `uv run python
bench/test_audio_output_switch.py` (18.F2), `uv run python bench/test_aec.py` (18.F4, the
echo path's two causes both fixed), `uv run python bench/test_voice_io.py` (where 18.R1's
input-level normalisation lands), and `uv run python bench/test_phase1_vad_bargein.py`.
Readiness: `uv run python bench/edge_readiness.py` and `uv run python
bench/list_audio_devices.py`.

## Failure modes

**Open speakers, no echo cancellation.** The mic re-hears Mushegh's TTS, VAD flags his own
speech, and the half-duplex gate mutes the mic while he talks — so barge-in is simply forced
off. `src/mushegh/edge/aec.py` is a seam, and the only real cancellers are proprietary SDKs, so this is a
licence decision, not a coding one. The owner sees Mushegh unable to be interrupted on the desk
speakers and interruptible on headphones. Diagnose: the endpoint classification in
`src/mushegh/edge/device_profile.py` in `journalctl -u openmushegh-edge`, then `uv run python
bench/test_audio_output_switch.py`.

**Bluetooth goes stale.** The streams open once at startup; AirPods connecting or Bluetooth
sleeping leaves them dead without an error — the mic stops delivering or the speaker write
fails with `Errno -9988`. This was the recurring "I say the wake word and nothing comes"
bug, and the watchdog is the fix. Diagnose: `journalctl -u openmushegh-edge | grep -i watchdog`,
then `uv run python bench/test_audio_watchdog.py`.

**Telephone-grade audio.** Selecting the AirPods hands-free endpoint forces the mic into HFP
at 8/16 kHz, and the wake word and gate both suffer. The owner hears a phone-quality voice
with no explanation. Diagnose: `uv run python bench/list_audio_devices.py` and check which
profile is active.

**Cloud dies.** The 3 AM case: the STT or TTS provider fails and the loop either fails or
starts guessing. `src/mushegh/edge/voice_health.py` fails over to Whisper and Piper on a startup probe and a
runtime error counter — but it currently treats cloud as primary, which D-17 inverts.
Diagnose: the probe result in the edge log, then `uv run python
bench/test_local_voice.py`.

**Barge-in that does not barge.** The 700 ms defect. The owner talks over Mushegh and keeps
hearing him, which reads as being ignored rather than as a latency bug. Diagnose: the
stt/brain/tts split from `src/mushegh/edge/latency_meter.py` — if the brain bucket is large, this is not an
audio problem at all.

## Open questions

1. Echo cancellation on open speakers requires a proprietary, licence-gated SDK. Is a licence
   acceptable for a system whose whole argument is local sovereignty, or does barge-in stay
   off on open speakers permanently?
2. 18.R1 (input level normalisation across devices) is what makes a single gate threshold
   mean the same thing on two machines. Does it land before or after M12?
3. **D-67 needs the owner's nod**: which one answering phrase the three satellites take, and
   whether the laptop keeps the other six as button-press shortcuts. Cutting seven phrases to
   one may also change the false-wake rate on the hardware it has to run on, and 18.R4 (the
   default TTS path asserted local) and 18.R5 (the wake asserted with network egress blocked)
   both want the written config decision before a test can assert it. Which lands first?
