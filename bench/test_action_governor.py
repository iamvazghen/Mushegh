"""36.F6 — the autonomy governor: calls, spend and wall-clock ceilings (hermetic, no network).

The gate for the Wave-0 floor that blocks the unpark. What it has to prove is narrow and specific:

  * Each of the three ceilings refuses INDEPENDENTLY — a flood that is cheap must still stop, and an
    expensive single call must stop too.
  * The refusal is deterministic and in code: the model is never consulted about whether to continue.
    The BoomLLM below fails the test loudly if it is ever called past a ceiling.
  * The refusal is AUDITED, with a rule that names which ceiling fired. An autonomous run that was
    cut short is exactly what an incident review goes looking for.
  * The ledger survives a restart. This is the property that matters most and the easiest to get
    wrong: an in-memory counter is reset by the very restart loop it exists to stop, and this brain
    restarts daily by design.
  * An unpriced model is counted, never treated as free (cost.py's rule).

    uv run python bench/test_action_governor.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain import audit                                  # noqa: E402
from mushegh.brain.governor import GOVERNOR, Governor, GovernorRefusal   # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class BoomLLM:
    """Fails loudly if the worker ever reaches the model. Proves the stop is deterministic."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_route: dict = {}

    async def complete(self, *a, **k):
        self.calls += 1
        raise AssertionError("the model must NOT be called once a ceiling is reached")


def _refusal(gov: Governor) -> GovernorRefusal | None:
    try:
        gov.check()
    except GovernorRefusal as e:
        return e
    return None


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        ledger = tmpdir / "governor.json"
        audit_dir = tmpdir / "audit"
        audit_dir.mkdir()
        audit._audit_dir = lambda: audit_dir          # hermetic: no repo/state writes

        print("\n[1] each ceiling refuses independently")
        g = Governor(max_calls=3, max_usd=99.0, max_seconds=9999.0, path=ledger)
        g.reset()
        check("an empty window allows work", _refusal(g) is None)
        g.charge(calls=3)
        r = _refusal(g)
        check("the CALLS ceiling refuses", r is not None and r.ceiling == "calls",
              f"got {r and r.ceiling}")

        g = Governor(max_calls=9999, max_usd=0.05, max_seconds=9999.0, path=ledger)
        g.reset()
        g.charge(calls=1, model="minimax:MiniMax-Text-01", in_tokens=1_000_000, out_tokens=0)
        r = _refusal(g)
        check("the SPEND ceiling refuses while calls are fine", r is not None and r.ceiling == "spend",
              f"got {r and r.ceiling}")

        g = Governor(max_calls=9999, max_usd=99.0, max_seconds=2.0, path=ledger)
        g.reset()
        g.charge(seconds=2.5)
        r = _refusal(g)
        check("the RUNTIME ceiling refuses while calls and spend are fine",
              r is not None and r.ceiling == "runtime", f"got {r and r.ceiling}")

        print("\n[2] an unpriced model is counted, not free")
        g = Governor(max_calls=9999, max_usd=0.01, max_seconds=9999.0, path=ledger)
        g.reset()
        g.charge(calls=1, model="a-model-nobody-has-priced", in_tokens=5_000_000, out_tokens=9_000)
        snap = g.snapshot()
        check("an unpriced call adds no phantom money", snap["usd"] == 0.0, str(snap["usd"]))
        check("but it IS counted as unpriced", snap["unpriced_calls"] == 1, str(snap))
        check("so it cannot silently pass the spend ceiling as a zero", _refusal(g) is None)

        print("\n[3] the refusal is audited, naming the ceiling")
        for f in audit_dir.glob("*.jsonl"):
            f.unlink()
        g = Governor(max_calls=1, max_usd=99.0, max_seconds=9999.0, path=ledger)
        g.reset()
        g.charge(calls=1)
        _refusal(g)
        lines = [json.loads(ln) for f in sorted(audit_dir.glob("*.jsonl"))
                 for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        denies = [ln for ln in lines if ln.get("decision") == "deny"]
        check("the refusal wrote an audit line", bool(denies), f"{len(lines)} lines, none denied")
        if denies:
            rec = denies[-1]
            check("it is recorded as a denial, not a failure",
                  rec["decision"] == "deny" and rec["ok"] is False, json.dumps(rec)[:160])
            check("the rule names which ceiling fired",
                  rec.get("rule_applied", "").startswith("governor:"), rec.get("rule_applied", ""))
            check("and it carries a non-owner actor",
                  bool(rec.get("actor")) and rec["actor"] != "owner", rec.get("actor", ""))

        print("\n[4] the ledger survives a restart - the whole point of a file")
        g = Governor(max_calls=2, max_usd=99.0, max_seconds=9999.0, path=ledger)
        g.reset()
        g.charge(calls=2)
        fresh = Governor(max_calls=2, max_usd=99.0, max_seconds=9999.0, path=ledger)
        r = _refusal(fresh)
        check("a NEW instance over the same file still refuses", r is not None and r.ceiling == "calls",
              "a restart reset the budget — this is the OpenClaw failure mode")

        print("\n[5] an expired window rolls over")
        state = json.loads(ledger.read_text(encoding="utf-8"))
        state["window_started"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        ledger.write_text(json.dumps(state), encoding="utf-8")
        rolled = Governor(max_calls=2, max_usd=99.0, max_seconds=9999.0, window_hours=24.0,
                          path=ledger)
        check("work is allowed again after the window expires", _refusal(rolled) is None)
        check("and the counters actually reset", rolled.snapshot()["calls"] == 0,
              str(rolled.snapshot()))

        print("\n[6] a corrupt ledger fails open to a fresh window, it does not wedge the brain")
        ledger.write_text("{not json at all", encoding="utf-8")
        salvaged = Governor(max_calls=5, max_usd=99.0, max_seconds=9999.0, path=ledger)
        check("a corrupt ledger does not raise", _refusal(salvaged) is None)

        print("\n[7] the worker honours it deterministically - no model call past a ceiling")
        from mushegh.brain import worker as worker_mod

        spent = Governor(max_calls=1, max_usd=99.0, max_seconds=9999.0, path=ledger)
        spent.reset()
        spent.charge(calls=1)
        real, worker_mod.GOVERNOR = worker_mod.GOVERNOR, spent
        try:
            boom = BoomLLM()
            w = worker_mod.TaskWorker(boom, {}, [], max_steps=4, actor="mushegh:test")
            result = asyncio.run(w.run("do some research"))
            check("the worker stopped without calling the model", boom.calls == 0,
                  f"the model was called {boom.calls} time(s)")
            check("it says it ran out of budget rather than inventing an answer",
                  "budget" in (w.stopped_early or "").lower(), w.stopped_early)
            check("and the owner is told, in the result",
                  "budget" in result.lower(), result[:160])
        finally:
            worker_mod.GOVERNOR = real

        print("\n[8] the shared ledger is a real module-level singleton")
        check("GOVERNOR exists and reads its ceilings from settings",
              isinstance(GOVERNOR, Governor) and GOVERNOR.max_calls > 0
              and GOVERNOR.max_usd > 0 and GOVERNOR.max_seconds > 0,
              f"{GOVERNOR.max_calls}/{GOVERNOR.max_usd}/{GOVERNOR.max_seconds}")
        check("its window is a real duration", GOVERNOR.window_hours > 0)
        check("and snapshot() reports the ceilings for a review surface",
              {"max_calls", "max_usd", "max_seconds", "resets_at"} <= set(GOVERNOR.snapshot()),
              str(sorted(GOVERNOR.snapshot()))[:160])

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
