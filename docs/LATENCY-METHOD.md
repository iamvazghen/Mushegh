# M13 — the latency measurement method

> **Why this file exists.** M13's acceptance criterion is *"measured over 30 utterances per
> device, method and date recorded"* (D-35, [`../ROADMAP.md`](../ROADMAP.md) M13). As of
> 2026-10-11 neither latency gate in the tree measures that, and the milestone has been open
> partly because **the method itself was never fixed** — so "30 utterances" meant whatever the
> person measuring happened to say, and two runs were not comparable.
>
> What exists today, and what it is not:
>
> | File | What it is | What it is **not** |
> |---|---|---|
> | `bench/test_latency_budget.py` | A live regression guard: one WS round-trip to the brain must answer inside a deliberately generous budget (~1s tailnet). Skips when no brain is reachable. | Not M13. One utterance, one device, one path, and it is a pass/fail tripwire. |
> | `bench/test_latency_guard.py` | A CI guard: config invariants (endpointing, first-token timeout, TTFW target) plus a synthetic TTFW distribution through the same VAQI math. | Not M13. Its own docstring says it plainly: *"There is no mic in CI, so this can't measure a real TTFW."* |

**This document and [`../bench/latency_corpus.json`](../bench/latency_corpus.json) are the
method.** They do not set a budget — D-35 owns that, and this file must never be used to argue
the budget. They fix *what is measured, under what conditions, and how it is summarised*, so
that the number is reproducible and the next person does not have to invent a protocol to
compare against it.

## What is measured

Per `src/mushegh/edge/latency_meter.py`, the marks already in the audio path:

```
turn latency: stt=310ms brain=1180ms tts=190ms total=1680ms
```

| Segment | From → to |
|---|---|
| `stt` | user stopped speaking → STT emitted the final transcript |
| `brain` | final transcript → TTS started (VPS hop + LLM first token + any tool call) |
| `tts` | TTS started → first audible word |
| `total` | the TTFW — **the number D-35 budgets** |

All four marks pass through one late slot in the audio path regardless of direction, so one
processor sees the whole turn. A run that misses the budget **must name the bucket** — a total
with no attribution is a number with no next action.

## The corpus

`bench/latency_corpus.json` holds **30 utterances per device**, in seven classes:

`reflex` · `chat` · `tool` · `compound` · `adversarial` · `long` (and `reflex` repeated per device)

The classes are the point. A single p95 over a corpus that is all `chat` turns is a number
about nothing in particular. `compound` is where the completion pass can cost a second LLM
round trip; `adversarial` is where calibration may add a hedge pass; `long` is where a vault
read runs. **Report p95 per class as well as overall** — the overall p95 tells you the budget is missed, the per-class p95 tells you which turn shape to fix.

## Conditions

Recorded per run, because a latency number without its conditions is not evidence:

- **room** — quiet, no other voice
- **device** — one device, **battery saver off** (it changes CPU clocks; a number across power states is meaningless)
- **brain** — the VPS brain at its normal tailnet location, *not* localhost. A localhost number is a different product.
- **providers** — the STT and TTS actually used, by name
- **machine load** — no other agent, no `graphify`, no docker build, no behavioural suite

That last one is not ceremony. On 2026-10-10 an otherwise-idle laptop produced LLM first-token
latencies of 403 ms, 813 ms, 1625 ms, 2802 ms and 2829 ms within one run, and the behavioural
suite logged 20 apparent "provider failovers" that turned out to be B4's deliberate
`skip_primary` retry. **Latency measured on a loaded machine describes the load, not the code.**

## Statistics

- **p50, p95, mean, n** — D-35 is a ceiling the owner experiences on the worst turn, and M13 says p95 explicitly. A mean hides exactly the tail that makes the product feel slow.
- **median of three passes** per device. One pass is a sample, not a measurement.
- **excluded, and counted separately**: turns with no STT mark (a reflex turn has nothing to wait for — the meter renders them `?`), and **barge-in turns**, which are M12 / D-49's number (<350 ms to halt playback) with their own budget.

## Recording the run

A result is only complete with all four:

1. the **date**,
2. the **conditions** above,
3. the per-class p50/p95 and the overall,
4. the commit SHA and the resolved STT/TTS providers.

The machine-readable location for the numbers is `~/.mushegh/latency_runs/` (declared in
`brain/data_classes.py` as an ordinary, host-local store). **The date is not optional**: a
latency number without one is the exact failure this project has already paid for once, in
`01.F1`, where a measurement disagreement was reported for three separate attempts before anyone
measured it.

## What blocks the run today

Not the method — the **edge is parked**. `~/.mushegh/MAINTENANCE` says:

> *"Parked 2026-08-13 by owner request: nothing in production until the TODO list is done."*

The edge reads that file at startup and exits with the message rather than starting. Measuring
end-to-end latency requires a running voice loop, so this measurement cannot be taken until the
owner unpark the edge — which is tied to the TODO list, and is not an agent's decision to take.

Until then, what is honestly established:

- the **guards** exist and are green (config invariants; a synthetic distribution through the live VAQI math)
- the **live regression guard** exists and skips when no brain is reachable
- the **corpus and protocol are fixed**, so the run is one command and comparable to the next one
- **no end-to-end latency number has been taken.** Goal 7 stays `not yet measured`, and the
  benchmark table in [`subsystems/18-microphone-and-speaker.md`](subsystems/18-microphone-and-speaker.md)
  and [`subsystems/01-brain-core-intelligence.md`](subsystems/01-brain-core-intelligence.md) say so.