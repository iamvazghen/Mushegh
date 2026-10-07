# S02 — LLM Integration

> **One line:** The only module that knows a model vendor exists, and the chain that keeps Afon talking when one stops answering.
> **Status:** complete for now · **Registry:** S02 · 3/3 floor, 3/3 raise, 0/1 elite
> **Milestones:** M16 · **Decisions:** D-17, D-35

## Purpose

Every call Afon makes to a model goes through `src/afon/brain/llm.py`. It holds the
provider list, the ordered chain, the cooldown state, the cost accounting, and the
distinction between a transient failure worth retrying and a permanent one worth
stopping. The blueprint proposed a LiteLLM proxy router; that was declined because a
router is a second failure domain with its own config file, and a 90-second shell
diagnosis beats a distributed trace (D-01). A fallback chain inside one module is
inspectable with `journalctl` and `sqlite3`; a router is not.

D-17 is the reason this system is local-first. Local TTS and local inference win at
3 AM, every time — latency and privacy dominate cost and personality. The cloud path is
an opt-in for when quality is worth the egress, not a default that fails open.

The second refusal here is the one that matters most. When the primary and the first
fallback both fail, the failure must be **audible in the voice path**, not silent. A
muted Afon is indistinguishable from an Afon that is merely thinking, and the owner's
first response to silence is to speak again, louder, into a room where nothing is
listening. 02.E1 is that drill and it is still open.

If this is absent, Afon cannot think. The degradation paths in the edge
(`src/afon/edge/degraded_answers.py`, `src/afon/edge/offline_queue.py`) can answer time
and reminders from the edge, and that is the whole of what survives.

## Structure

One module owns the vendor knowledge, inside the brain process.

```
turn request ──> llm.py
                  ├─ settings.llm_chain: [primary, fallback…]
                  ├─ _FAILOVER = (RateLimitError, APITimeoutError, APIError) → next entry
                  ├─ _PERMANENT_ERR_CUES → bench, do not flap back (vendor error body, not HTTP status)
                  ├─ first-token stall → failover fast, not on request timeout
                  ├─ ChainExhausted / CHAIN_EXHAUSTED = "all LLM models failed"
                  ├─ vision chain: VISION_CHAIN_EXHAUSTED
                  └─ METRICS: tokens, money, per-tier and per-intent-class cost
```

| Concern | Where |
|---|---|
| Chain, failover, cooldowns | `src/afon/brain/llm.py` |
| Tool-tier vs thinking-tier routing (02.F2) | `src/afon/brain/llm.py` |
| Per-tier cost accounting (02.R1) | `cost.py`, `metrics.py`, surfaced in the HUD |
| Streaming correctness under failover (02.R3) | `llm.py`; the chain may switch mid-answer, so a duplicated or truncated sentence is the defect to watch |
| Prompt-cache discipline (02.R2) | `context.py` builds a byte-identical stable prefix; `bench/test_prompt_prefix_stable.py` |
| Wire markers for a dead chain | `llm.py`; `bench/test_llm_chain_exhausted.py` asserts the harness and the module still agree |
| Degradation when nothing answers | `src/afon/edge/degraded_answers.py`, `src/afon/edge/offline_queue.py`, `src/afon/edge/reflexes.py` |
| Local speech (D-17) | `src/afon/edge/tts.py`, `src/afon/edge/stt.py` |

**Process ownership:** brain. The edge never calls a vendor; it streams to the brain and
receives text.

**What it stores:** provider health, cooldowns, token and money counters. Nothing about
what was said is kept here — that is `metrics.py` and the session store.

## Goals

1. **A rate-limit, a timeout, or a first-token stall fails over to the next chain entry
   without the owner noticing a gap.**
2. **A permanent failure (dead credit, invalid key) is benched** rather than retried,
   so the chain does not flap onto a dead key every turn.
3. **A full outage of primary plus first fallback is audible in the voice path** — the
   owner is told within the same turn, in words, not by silence.
4. **Provider health is learned, not just configured** (02.F3): two failures in five
   minutes moves a provider back in the chain.
5. **Local TTS is the default and no outbound audio leaves the host at 3 AM** (D-17);
   the cloud path is opt-in and degrades cleanly.
6. **Failover mid-stream never duplicates or truncates a sentence** (02.R3).
7. **Cost is attributed per intent class and per tier**, so the owner can see which
   turns are expensive (02.R1).

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | Failover on stall | B1 | `bench/test_brain_llm.py`, `bench/test_resilience.py` | 0 owner-visible gaps; failover before request timeout | not yet measured |
| 2 | Permanent failure benched | B1 | `bench/test_resilience.py` — permanent-cue plants | 0 re-entries into a benched provider inside the cooldown | not yet measured |
| 3 | **Outage is audible (D-17)** | B1 + B2 | `bench/test_resilience.py` chaos case **plus one live drill** (02.E1) | 1 spoken or rendered statement within the same turn; 0 silent turns | not yet measured — the live drill has not been performed |
| 4 | Learned provider health | B1 | `bench/test_provider_cooldown.py` (28) — twelve plants | every plant correctly demoted or restored | 28/28 per the registry gate text; evidence kind `unverified-import` — **not yet measured** as a dated run |
| 5 | Local TTS default (D-17) | B1 | `bench/test_model_tiers.py` (M16) | default config local; 0 outbound audio requests at 3 AM | not yet measured |
| 6 | Streaming under failover | B1 | `bench/test_streaming.py` [02.R3] (22) | 0 duplicated, 0 truncated sentences | not yet measured |
| 7 | Cost per intent class | B1 | `bench/test_metrics.py` [02.R1] (78) | every intent class carries its own token and money row | not yet measured |

Goals 3 and 4 are the load-bearing ones. Goal 3 is the only goal in this system whose
failure is felt rather than logged: a silent outage looks like a system that stopped
listening, and D-17 exists because at 3 AM the local path is the one that has to be
there. Its benchmark is deliberately the hardest in the file — a chaos test proves the
code can be broken on purpose, and only the live drill proves the owner's experience.

## Failure modes

**The chain flaps.** A dead-credit key is treated as a transient 429, benched for the
short cooldown, returns seconds later, and fails every turn in between. The symptom is
constant latency on every request with no error the owner can name. Diagnose:
`journalctl -u openafon` for the failover messages and provider names; then the
provider-health view the HUD reads, to see whether one provider is being retried while
the chain's other entries are fine. The distinction is in the error *body*, not the
HTTP status, and a 404 from a wrong base URL is not a dead key.

**Failover mid-sentence.** The chain switches while an answer is streaming and the owner
hears the same clause twice, or half a clause. Reproduce with
`bench/test_streaming.py` [02.R3].

**The outage is silent.** The worst failure here, and the one 02.E1 exists to close. The
turn produces no text, the edge has nothing to speak, and the owner concludes the
microphone is dead. The constant `CHAIN_EXHAUSTED = "all LLM models failed"` is what the
edge and the test harness key on; if the edge stops honouring it, the marker is
decorative. Diagnose by calling the brain directly over the tailnet and reading the
marker, then checking whether the edge rendered it.

**Cost appears with no attribution.** Tokens are billed but the per-intent-class split is
empty, so the expensive behaviour cannot be named. `bench/test_metrics.py` is the alarm.

## Open questions

1. 02.E1 needs a live drill that takes down the primary and the first fallback
   simultaneously. There is no written procedure for it yet, and the benchmark is not
   "safe" to claim until one exists.
2. Is the failover ordering fixed at configuration time, or should a learned
   cooldown (02.F3) also be allowed to reorder the chain? The two interact and only one
   of them is currently specified.
3. D-17 makes local TTS the default, but no measurement records the latency difference
   between the local and cloud paths on real sentences. Without it, "quality is worth
   the egress" has no price attached.
