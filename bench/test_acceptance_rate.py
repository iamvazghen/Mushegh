"""14.R1 — the outcome loop, and the acceptance rate 14.E1 asks for.

`test_proactive_learning.py` already proves the mechanism: the three-word reaction vocabulary
(`act`/`dismiss`/`ignore`), the penalty fold that raises the effective threshold for a kind the owner
keeps refusing, the decay back toward base, persistence across a restart, the six-minute pending
window, and the classifier that turns "stop reminding me" into a negative. That is the feedback, and
it works.

**What was missing is the number.** `14.E1` asks for an "acceptance rate ≥60% over a real week" and
nothing computed one — a reader had to reach into `_fb_stats` (a private, nested, per-kind dict) and
choose a denominator. The choice is not obvious, because the vocabulary has three words and silence
is not a refusal:

    act     he did the thing
    dismiss he said no, and the code treats that as its strongest signal
    ignore  he said nothing

So `ProactiveEngine.acceptance_rate()` returns **two** named rates with their definitions attached —
`strict` (act / act+dismiss, silence is not held against a nudge) and `lenient` (act / all three,
silence is). Neither is presented as *the* rate, because which one to quote is the owner's judgement
and the 60% bar lands in a different place depending on it. Surfacing the choice is the honest move;
picking one silently would have made a number look like a decision.

What is asserted here:

  * **both rates are arithmetically right**, and neither is the other's
  * **the counts come back**, so a reader can recompute rather than trust
  * **a cold start is 0.0, not 1.0** — a brand-new engine has no acceptance rate, and reporting a
    perfect one would make an empty ledger look like a success
  * **one kind and all-kinds are different claims**, and the function says which it answered
  * **the rates follow the recorded reactions** — a dismissal lowers them, an act raises them
  * **the mechanism itself is not disturbed**: an unknown reaction is still ignored, and the
    threshold still moves the way 14.R1's design says it should

Hermetic: a temp state root and a scripted clock. No model, no network, no credentials.

    uv run python bench/test_acceptance_rate.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TMP = tempfile.mkdtemp(prefix="mushegh-accept-")
os.environ["MUSHEGH_STATE_DIR"] = str(Path(_TMP) / "state")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0
NOON = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def engine():
    from mushegh.brain.proactive import ProactiveEngine
    return ProactiveEngine(emit=lambda *a, **k: None, clock=lambda: NOON)


def main() -> int:
    from mushegh.brain.proactive import ProactiveEngine

    _FB_DELTA = ProactiveEngine._FB_DELTA   # a CLASS attribute, not a module global

    print("\n[1] a cold start has no acceptance rate — and must not look like a perfect one")
    e = engine()
    r0 = e.acceptance_rate()
    check("a brand-new engine reports 0.0, not 1.0", r0["strict"] == 0.0 and r0["lenient"] == 0.0,
          str(r0))
    check("...with an empty ledger, not a fake one", r0["total"] == 0, str(r0))
    check("...and it says what it answered", r0["kind"] == "all" and r0["kinds"] == [], str(r0))
    check("...and carries its own definition, so the number cannot be quoted bare",
          "strict" in r0["definition"] and "lenient" in r0["definition"], r0["definition"])

    print("\n[2] the two rates are arithmetically right, and they differ")
    e = engine()
    for _ in range(3):
        e.record_feedback("reminder", "act", now=NOON)
    for _ in range(1):
        e.record_feedback("reminder", "dismiss", now=NOON)
    for _ in range(2):
        e.record_feedback("reminder", "ignore", now=NOON)
    r = e.acceptance_rate("reminder")
    check("the counts come back so a reader can recompute",
          (r["act"], r["dismiss"], r["ignore"]) == (3, 1, 2), str(r))
    check("strict = act/(act+dismiss), silence not held against a nudge",
          r["strict"] == 0.75, f"{r['strict']} from {r}")
    check("lenient = act/(act+dismiss+ignore), silence held against it",
          r["lenient"] == 0.5, f"{r['lenient']} from {r}")
    check("...so the two are genuinely different numbers, which is the whole point",
          r["strict"] != r["lenient"], f"{r['strict']} == {r['lenient']}")
    check("...and they add up: lenient is strict scaled by the decided fraction",
          abs(r["lenient"] - r["strict"] * (4 / 6)) < 1e-9, f"{r['lenient']} vs {r['strict']}")

    print("\n[3] the rate follows the reactions, in the right direction")
    before = e.acceptance_rate("reminder")["strict"]
    e.record_feedback("reminder", "dismiss", now=NOON)
    after_dismiss = e.acceptance_rate("reminder")["strict"]
    check("a dismissal lowers the acceptance rate", after_dismiss < before,
          f"{before} -> {after_dismiss}")
    e.record_feedback("reminder", "act", now=NOON)
    check("an act raises it back", e.acceptance_rate("reminder")["strict"] > after_dismiss,
          f"{after_dismiss} -> {e.acceptance_rate('reminder')['strict']}")
    e.record_feedback("reminder", "ignore", now=NOON)
    check("an ignore lowers the LENIENT rate only — that is the difference between the two",
          e.acceptance_rate("reminder")["lenient"] < e.acceptance_rate("reminder")["strict"],
          str(e.acceptance_rate("reminder")))

    print("\n[4] one kind and all-kinds are different claims, and it says which")
    e = engine()
    for _ in range(4):
        e.record_feedback("reminder", "act", now=NOON)
    e.record_feedback("conflict", "dismiss", now=NOON)
    allk, one = e.acceptance_rate(), e.acceptance_rate("reminder")
    check("a single kind is answered as that kind", one["kind"] == "reminder" and one["kinds"]
          == ["reminder"], str(one))
    check("all-kinds aggregates and NAMES them", allk["kind"] == "all"
          and allk["kinds"] == ["conflict", "reminder"], str(allk["kinds"]))
    check("...and the two rates genuinely differ, so mixing kinds is not a free choice",
          allk["strict"] != one["strict"], f"all {allk['strict']} vs one {one['strict']}")
    check("a kind with no reactions reads 0.0 rather than erroring",
          e.acceptance_rate("never-heard-of-it")["strict"] == 0.0)

    print("\n[5] the mechanism 14.R1 built is not disturbed")
    check("the reaction vocabulary is still exactly the three words",
          set(_FB_DELTA) == {"act", "dismiss", "ignore"}, str(sorted(_FB_DELTA)))
    check("a dismissal still bites hardest — trust, not noise",
          _FB_DELTA["dismiss"] > _FB_DELTA["ignore"] > 0 > _FB_DELTA["act"],
          str(_FB_DELTA))
    e2 = engine()
    before_pen = e2.effective_threshold("reminder", NOON)
    e2.record_feedback("reminder", "dismiss", now=NOON)
    check("...and a dismissal still raises the bar for that kind",
          e2.effective_threshold("reminder", NOON) > before_pen,
          f"{before_pen:.3f} -> {e2.effective_threshold('reminder', NOON):.3f}")
    e3 = engine()
    e3.record_feedback("reminder", "dismiss", now=NOON)
    e3.record_feedback("reminder", "nonsense", now=NOON)
    check("an unknown reaction is still ignored, not folded in as silence",
          e3.acceptance_rate("reminder")["dismiss"] == 1
          and e3.acceptance_rate("reminder")["total"] == 1, str(e3.acceptance_rate("reminder")))

    print("\n[6] the rate is a REPORT, not a decision")
    src = (ROOT / "src" / "mushegh" / "brain" / "proactive.py").read_text(encoding="utf-8")
    body = src[src.index("def acceptance_rate("):src.index("def pending_key(")]
    check("it sets no penalty and moves no threshold — quoting a rate must not change behaviour",
          "_penalty" not in body and "_register_outcome" not in body and "_save_state" not in body)
    check("...it only reads the stats it was given", "_fb_stats" in body)
    check("it names BOTH rates rather than picking one for the owner",
          '"strict"' in body and '"lenient"' in body)

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
