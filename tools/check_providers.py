"""Is the model chain actually alive? A diagnostic, not a gate.

**Why this exists.** `test_finetune.py` pins four invariants about the chain's SHAPE: the primary
is the paid MiniMax, there are at least three entries across at least two providers, a free tier
sits between the primary and the gateway, and the vercel entries are a contiguous tail at the end.
All four held on 2026-10-10 while six of the eight entries could not answer a single request. A
shape gate cannot see that, and the suite stayed green.

Measured the same morning, probing each entry individually:

    minimax:MiniMax-Text-01            WORKS
    groq:llama-3.3-70b-versatile       404  — that model id does not exist
    groq:llama-3.1-8b-instant          404  — that model id does not exist
    gemini-3.5-flash                    connection error
    mistral-small-latest               connection error
    groq/compound                      connection error
    vercel:deepseek/deepseek-v3.2      402  — out of credit
    vercel:alibaba/qwen3.5-flash       402  — out of credit

One reachable provider is not a fallback. This checks liveness so that "green suite" and "an
answer actually arrives" stop being different claims.

**Deliberately NOT a registered gate.** It needs the network and the owner's credentials, and a
red suite caused by a billing state is not a defect in the code — it is a fact about the
account. It exits non-zero so it can be wired into a pre-flight check later, but nothing imports
it into `run_all_tests.py`.

Usage:
    uv run python tools/check_providers.py            # report; exit 0 unless fewer than 2 live
    uv run python tools/check_providers.py --min 3    # demand three
    uv run python tools/check_providers.py --all      # probe every entry, not just the chain head
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: What each failure means, so the report says something actionable rather than "failed".
DIAGNOSIS = {
    "402": "OUT OF CREDIT — top up or replace this provider",
    "401": "key rejected — check the credential",
    "403": "blocked or unauthorised — often the upstream refusing this client",
    "404": "that model id does not exist — replace it with a current one",
    "429": "rate limited — free tier exhausted",
}


def _classify(exc: Exception) -> tuple[str, str]:
    text = str(exc)
    for code, meaning in DIAGNOSIS.items():
        if f"Error code: {code}" in text or f" {code} " in text:
            return code, meaning
    name = type(exc).__name__
    if "Connection" in name or "Timeout" in name or "Connect" in text:
        return "net", "unreachable from this host"
    return "-", name


async def _probe(client, model: str) -> tuple[bool, str]:
    try:
        await client.complete(
            [{"role": "user", "content": "Reply with the single word OK."}],
            tools=[],
            only=[model],
        )
        return True, ""
    except Exception as exc:  # noqa: BLE001 - the failure IS the measurement
        return False, _classify(exc)[1]


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min", type=int, default=2,
                    help="how many entries must answer (default 2 — one primary is not a fallback)")
    ap.add_argument("--all", action="store_true",
                    help="probe every entry instead of stopping at the first live one")
    args = ap.parse_args()

    try:
        from afon.config import settings
        from afon.brain.llm import LLMClient
    except Exception as exc:  # noqa: BLE001
        print(f"cannot load the runtime: {type(exc).__name__}: {exc}")
        return 2

    chain = [settings.llm_primary_model]
    chain += [m.strip() for m in (settings.llm_fallback_models or "").split(",") if m.strip()]
    chain = list(dict.fromkeys(chain))

    print(f"Probing {len(chain)} chain entr{'y' if len(chain) == 1 else 'ies'}\n")
    client = LLMClient()
    live: list[str] = []

    for model in chain:
        ok, why = await _probe(client, model)
        if ok:
            live.append(model)
            print(f"  LIVE   {model}")
            if not args.all and len(live) >= args.min:
                for rest in chain[chain.index(model) + 1:]:
                    print(f"  (skipped, not probed)  {rest}")
                break
        else:
            print(f"  DEAD   {model}\n           -> {why}")

    print(f"\n{len(live)} of {len(chain)} entries can answer")
    if not live:
        print("\nNOTHING can answer. Afon cannot complete a turn at all.")
        return 1
    if len(live) < args.min:
        print(f"\nBelow the floor of {args.min}. A primary is not a fallback: with one reachable "
              f"entry there is no failover when it fails, and the measured behavioural score "
              f"becomes a measurement of that one provider rather than of Afon.")
        return 1
    if len(live) > 1 and len(live) < len(chain):
        print("\nThe dead entries are not free. Each one costs a failed round trip on every turn "
              "that falls through to a later provider — which is exactly the latency that gets "
              "misread as the brain being slow. Repair or remove them; do not promote the "
              "gateway above a working primary to hide it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))