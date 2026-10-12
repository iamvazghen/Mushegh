"""M13 runner: measure the brain term of end-to-end latency over the fixed corpus.

The protocol is [`docs/LATENCY-METHOD.md`](../LATENCY-METHOD.md) and the corpus is
`bench/latency_corpus.json` — 30 utterances per device across seven turn classes, fixed on
2026-07-11 so two runs are comparable. This is the runner that was missing, and the gate
`bench/test_latency_method.py` only proves the protocol exists.

**What is measured, precisely, and what is not.** End-to-end latency is speech-stop → first
audible word, and it has three segments: `stt` (Deepgram endpointing + final transcript), `brain`
(transcript → TTS started) and `tts` (TTS started → first audible). This runner drives the real
turn path and measures the **`brain` segment end to end** — utterance submitted → reply returned —
which is the segment that carries the VPS hop, the LLM first token, arbitration and any tool call.

It does **not** measure `stt` or `tts`: there is no human at the microphone, so nothing stops
speaking, and TTS time-to-first-audio belongs to the provider's own stream. So the number this
produces is a **lower bound on the full turn**, and is reported as such rather than presented as
the M13 figure. The remaining two segments need a person, and saying so is the honest result.

    MUSHEGH_JEV_MODEL=... uv run python bench/latency_corpus_runner.py --device laptop
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CORPUS = ROOT / "bench" / "latency_corpus.json"

#: Above this, the host is doing something else and the number describes that instead. Chosen from
#: the 2026-07-11 observation rather than guessed: the same utterance spanned 3,552–32,573 ms
#: across runs on a host averaging well past this.
QUIET_CPU_PERCENT = 25.0


def _cpu_percent(interval: float = 0.5) -> float:
    """Host CPU utilisation, measured rather than assumed."""
    try:
        import psutil

        psutil.cpu_percent(interval=interval)
        return float(psutil.cpu_percent(interval=0))
    except Exception:  # noqa: BLE001 — an unmeasurable load is reported as unknown, not as zero
        return -1.0


def load(device: str) -> tuple[list[dict], int]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    batch = next((b for b in data["batches"] if b["device"] == device), None)
    if batch is None:
        raise SystemExit(f"no corpus batch for {device!r}")
    return batch["utterances"], int(batch["budget_ms"])


async def measure(utterances: list[dict], passes: int) -> dict:
    from mushegh.brain.agent import MusheghAgent

    agent = MusheghAgent()
    agent._self_improve = False
    samples: list[float] = []
    per_class: dict[str, list[float]] = defaultdict(list)
    errors: list[str] = []

    for p in range(passes):
        for item in utterances:
            text = item["say"]
            t0 = time.perf_counter()
            try:
                await agent.respond(text)
            except Exception as exc:  # noqa: BLE001 — a failed turn is a sample, not a crash
                errors.append(f"{type(exc).__name__}: {exc}"[:80])
                continue
            ms = (time.perf_counter() - t0) * 1000
            samples.append(ms)
            per_class[item.get("class", "?")].append(ms)
            print(f"    pass {p + 1}  {item.get('class', '?'):12} {ms:7.0f} ms  {text[:44]}")
            await asyncio.sleep(0.2)

    s = sorted(samples)
    return {
        "n": len(s),
        "errors": len(errors),
        "p50": round(statistics.median(s)) if s else None,
        "p95": round(s[int(len(s) * 0.95)]) if s else None,
        "mean": round(statistics.mean(s)) if s else None,
        "min": round(s[0]) if s else None,
        "max": round(s[-1]) if s else None,
        "per_class": {k: {"n": len(v), "p50": round(statistics.median(v))}
                      for k, v in sorted(per_class.items())},
        "error_detail": errors[:5],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="laptop", choices=("laptop", "phone"))
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    utterances, budget = load(args.device)
    print(f"M13 latency corpus — device={args.device}  utterances={len(utterances)}  "
          f"passes={args.passes}  budget={budget} ms")
    print("NOTE: this measures the BRAIN segment only (utterance -> reply). The stt and tts")
    print("segments need a person at the microphone, so this is a LOWER BOUND on the turn.\n")

    # The machine's load is part of the measurement, not a detail beside it. On 2026-07-11 a corpus
    # run was taken while this host also ran a second agent, the Docker supabase stack, OneDrive and
    # Chrome, and the SAME utterance then measured 32,573 ms in one run and 3,552 ms in another on
    # identical code — a 9x spread that had nothing to do with Mushegh. `LATENCY-METHOD.md` already
    # says a latency number measured on a loaded machine describes the load; this makes the runner
    # obey its own protocol instead of trusting the operator to remember it.
    before_load = _cpu_percent()
    result = asyncio.run(measure(utterances, args.passes))
    after_load = _cpu_percent()
    peak_load = max(before_load, after_load)

    result.update({"device": args.device, "passes": args.passes, "budget_ms": budget,
                   "measures": "brain segment only (lower bound)",
                   "measured_at": time.strftime("%Y-%m-%d %H:%M"),
                   "cpu_percent_before": before_load,
                   "cpu_percent_after": after_load})

    contaminated = peak_load > QUIET_CPU_PERCENT
    result["load_contaminated"] = contaminated
    result["provisional"] = contaminated
    if contaminated:
        result["provisional_reason"] = (
            f"host CPU peaked at {peak_load:.0f}% during the run, above the {QUIET_CPU_PERCENT}% "
            f"this runner treats as quiet. The number describes the load, not the code."
        )

    print("\n=== result ===")
    print(f"  n={result['n']}  errors={result['errors']}")
    print(f"  p50 {result['p50']} ms | p95 {result['p95']} ms | mean {result['mean']} ms | "
          f"max {result['max']} ms")
    print(f"  budget {budget} ms -> p95 {'WITHIN' if (result['p95'] or 0) <= budget else 'OVER'} "
          "(brain segment; full turn is larger)")
    print(f"  host CPU: {before_load:.0f}% before -> {after_load:.0f}% after "
          f"(quiet is <= {QUIET_CPU_PERCENT}%)")
    if contaminated:
        print(f"\n  *** PROVISIONAL — {result['provisional_reason']}")
        print("  Do NOT quote this as a capability. Re-run on a quiet machine.")
    else:
        print("\n  measured on a quiet machine — this one is quotable.")
    print("  per class:")
    for cls, row in result["per_class"].items():
        print(f"    {cls:14} n={row['n']:>2} p50={row['p50']} ms")

    out = Path(args.out or f"logs/latency-{args.device}-{time.strftime('%Y%m%d-%H%M')}.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())