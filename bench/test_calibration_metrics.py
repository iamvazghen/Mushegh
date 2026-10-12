"""Calibration metrics are correct, and they refuse to speak without enough data (hermetic).

**The failure this gate exists to prevent.** A calibration module that returns `0.0` when it
has no data reports *perfect calibration* on the day the curve was never drawn. That is the
worst possible failure for the metric it is reporting: it is indistinguishable from success at
exactly the moment there is nothing to say. So every metric here is asserted to return **None**,
not zero, and `describe()` is asserted to refuse to characterise a small sample.

**Negative controls, because the positive ones are easy to pass for the wrong reason.**
- "ECE is low" also passes for an all-empty table, so a perfect-prediction case is built with
  real points and compared against a known-wrong one.
- `overconfidence_index` returning `0.0` also passes for "no data", so both signs are tested.
- `resolve()` on a missing id also "returns False", so the success path is tested too — a
  function that always returns False would satisfy a refusal-only test.

**Known values, not shapes.** ECE and Brier are checked against hand-computed numbers, so a
sign error or an inverted accuracy term fails rather than producing a plausible number.

    uv run python bench/test_calibration_metrics.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain import calibration as C  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  -- {detail}" if detail else ""))


def pt(c: float, y: bool, kind: str = "t") -> C.CalibrationPoint:
    return C.CalibrationPoint(confidence=c, outcome=y, kind=kind, record_id="x")


def main() -> None:  # noqa: C901 - linear gate
    print("=== 1. an empty table says nothing, and does NOT say 'perfect' ===")
    check("expected_calibration_error(None) is None, not 0.0",
          C.expected_calibration_error([]) is None, repr(C.expected_calibration_error([])))
    check("brier_score([]) is None, not 0.0",
          C.brier_score([]) is None, repr(C.brier_score([])))
    check("overconfidence_index([]) is None",
          C.overconfidence_index([]) is None, repr(C.overconfidence_index([])))
    check("reliability_bins over nothing is all-empty, not all-perfect",
          all(b["n"] == 0 and b["accuracy"] is None for b in C.reliability_bins([])))

    print("\n=== 2. a perfect predictor scores 0, a perfect liar scores high ===")
    perfect = [pt(1.0, True)] * 10 + [pt(0.0, False)] * 10
    check("a perfect predictor has ECE 0.0", C.expected_calibration_error(perfect) == 0.0,
          repr(C.expected_calibration_error(perfect)))
    check("a perfect predictor has Brier 0.0", C.brier_score(perfect) == 0.0,
          repr(C.brier_score(perfect)))
    check("a perfect predictor is neither over- nor underconfident",
          C.overconfidence_index(perfect) == 0.0, repr(C.overconfidence_index(perfect)))

    liar = [pt(1.0, False)] * 10 + [pt(0.0, True)] * 10
    check("a perfect liar has ECE 1.0", C.expected_calibration_error(liar) == 1.0,
          repr(C.expected_calibration_error(liar)))
    check("a perfect liar has Brier 1.0", C.brier_score(liar) == 1.0, repr(C.brier_score(liar)))
    # That construction is symmetric — confidently wrong AND unconfidently right — so it is
    # maximally badly calibrated yet perfectly unbiased. Worth asserting on its own, because it
    # is the case that proves ECE and the signed index measure DIFFERENT things: a system can
    # score ECE 1.0 with no directional bias at all, and "call it overconfident" would be wrong.
    check("a symmetric liar is unbiased (overconfidence 0 despite ECE 1.0)",
          C.overconfidence_index(liar) == 0.0, repr(C.overconfidence_index(liar)))

    # Directional cases: confidence is wrong the SAME WAY every time.
    over = [pt(1.0, False)] * 10
    check("always confidently wrong is maximally overconfident",
          C.overconfidence_index(over) == 1.0, repr(C.overconfidence_index(over)))
    timid = [pt(0.0, True)] * 10
    check("always wrongly certain is maximally underconfident (negative sign)",
          C.overconfidence_index(timid) == -1.0, repr(C.overconfidence_index(timid)))
    mild = [pt(0.9, False)] * 4 + [pt(0.8, True)] * 4
    # mean(0.9-0, 0.8-1) = mean(0.9, -0.2) = 0.35
    check("a mild one-directional case keeps its magnitude",
          C.overconfidence_index(mild) == 0.35, repr(C.overconfidence_index(mild)))

    print("\n=== 3. hand-computed values, so a sign error cannot pass ===")
    # 2 correct at 0.8, 2 wrong at 0.8 -> bin(0.8) has n=4, acc=0.5, mean_conf=0.8, gap=0.3
    # plus 1 correct at 0.2 -> bin(0.2) n=1, acc=1.0, mean_conf=0.2, gap=0.8
    mixed = [pt(0.8, True), pt(0.8, True), pt(0.8, False), pt(0.8, False), pt(0.2, True)]
    # ECE = (4/5)*0.3 + (1/5)*0.8 = 0.24 + 0.16 = 0.40
    check("ECE matches the hand calculation (0.40)", C.expected_calibration_error(mixed) == 0.4,
          repr(C.expected_calibration_error(mixed)))
    # Brier = mean([0.04,0.04,0.64,0.64,0.64]) = 2.00/5 = 0.40
    check("Brier matches the hand calculation (0.40)", C.brier_score(mixed) == 0.4,
          repr(C.brier_score(mixed)))
    # overconfidence = mean(0.8-1, 0.8-1, 0.8-0, 0.8-0, 0.2-1) = mean(-0.2,-0.2,0.8,0.8,-0.8)=0.08
    check("overconfidence index matches the hand calculation (0.08)",
          C.overconfidence_index(mixed) == 0.08, repr(C.overconfidence_index(mixed)))

    print("\n=== 4. binning: boundaries are not lossy ===")
    edge = [pt(1.0, True), pt(0.0, True), pt(0.5, True)]
    bins10 = C.reliability_bins(edge)
    check("confidence 1.0 lands in the top bin and is counted",
          bins10[-1]["n"] == 1 and bins10[-1]["lo"] == 0.9, repr(bins10[-1]))
    check("confidence 0.0 lands in the bottom bin",
          bins10[0]["n"] == 1 and bins10[0]["lo"] == 0.0, repr(bins10[0]))
    check("every point is binned exactly once",
          sum(b["n"] for b in bins10) == len(edge), sum(b["n"] for b in bins10))
    check("a bin with no members has gap None, not 0.0",
          all(b["gap"] is None for b in bins10 if b["n"] == 0))
    try:
        C.reliability_bins(edge, bins=0)
        check("bins=0 is rejected", False, "no error raised")
    except ValueError:
        check("bins=0 is rejected", True)

    print("\n=== 5. persistence: write, resolve, read back ===")
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "calibration.jsonl"

        rid = C.record_prediction("jev_arbitration", confidence=0.9, detail="office vs cafe",
                                  path=store)
        check("a prediction with a confidence gets an id", bool(rid), repr(rid))
        check("nothing is readable before it is resolved", C.load(store) == [], repr(C.load(store)))

        check("resolve reports success on a known id",
              C.resolve(rid, outcome=True, path=store) is True)
        loaded = C.load(store)
        check("exactly one point comes back", len(loaded) == 1, repr(len(loaded)))
        check("the confidence round-tripped", loaded and loaded[0].confidence == 0.9,
              repr(loaded[0].confidence if loaded else None))
        check("the outcome round-tripped", loaded and loaded[0].outcome is True,
              repr(loaded[0].outcome if loaded else None))
        check("the detail label round-tripped", loaded and loaded[0].detail == "office vs cafe",
              repr(loaded[0].detail if loaded else None))

        check("resolving an unknown id is refused, not invented",
              C.resolve("nope-not-a-real-id", outcome=True, path=store) is False)
        check("resolving twice does not double-count",
              C.resolve(rid, outcome=True, path=store) is False and len(C.load(store)) == 1)

        print("\n=== 6. no confidence is not a zero confidence ===")
        check("confidence=None records nothing", C.record_prediction("k", None, path=store) is None)
        check("a non-numeric confidence records nothing",
              C.record_prediction("k", "not-a-number", path=store) is None)
        check("still only one point on disk", len(C.load(store)) == 1, repr(len(C.load(store))))

        print("\n=== 7. out-of-range input is clamped, not trusted ===")
        rid2 = C.record_prediction("k", confidence=7.5, path=store)
        C.resolve(rid2, outcome=True, path=store)
        over = C.load(store)
        check("a confidence of 7.5 is clamped to 1.0", over and over[-1].confidence == 1.0,
              repr(over[-1].confidence if over else None))
        rid3 = C.record_prediction("k", confidence=-3.0, path=store)
        C.resolve(rid3, outcome=False, path=store)
        check("a confidence of -3 is clamped to 0.0", C.load(store)[-1].confidence == 0.0,
              repr(C.load(store)[-1].confidence))

        print("\n=== 8. corrupt lines are skipped, not fatal ===")
        with store.open("a", encoding="utf-8") as fh:
            fh.write("{not json\n")
            fh.write("\n")
        before = len(C.load(store))
        C.record_prediction("k", 0.5, path=store)
        C.resolve(C.load(store)[0].record_id, outcome=True, path=store)
        check("a torn line does not stop the read", len(C.load(store)) >= before,
              f"{before} -> {len(C.load(store))}")

        print("\n=== 9. missing store is not an error ===")
        check("load on a missing file returns []", C.load(Path(tmp) / "nope.jsonl") == [])
        check("resolve on a missing store is refused, not raised",
              C.resolve("x", True, path=Path(tmp) / "nope.jsonl") is False)

        print("\n=== 10. summary refuses to over-claim ===")
        small = C.summary(C.load(store))
        check("a small sample is marked insufficient", small["sufficient"] is False, str(small["sufficient"]))
        check("small-sample describe() refuses to characterise it",
              "below the" in C.describe(small), C.describe(small))
        big = C.summary([pt(0.9, True)] * 13)
        check("a 13-point sample IS sufficient", big["sufficient"] is True, str(big["sufficient"]))
        check("sufficient describe() states a direction and a size",
              "overconfident" in C.describe(big) or "underconfident" in C.describe(big),
              C.describe(big))
        check("an empty summary is not sufficient and does not say perfect",
              C.summary([])["sufficient"] is False and C.summary([])["ece"] is None)
        check("describe on nothing says there is nothing",
              "no resolved predictions" in C.describe(C.summary([])), C.describe(C.summary([])))

        print("\n=== 11. kind filtering ===")
        store2 = Path(tmp) / "by_kind.jsonl"
        a = C.record_prediction("jev", 0.8, path=store2)
        b = C.record_prediction("tool", 0.4, path=store2)
        C.resolve(a, True, path=store2)
        C.resolve(b, False, path=store2)
        check("all points load unfiltered", len(C.load(store2)) == 2)
        check("filtering by kind narrows the set", len(C.load(store2, kind="jev")) == 1)
        check("the filtered point is the right one",
              C.load(store2, kind="jev")[0].kind == "jev")

        print("\n=== 12. the file on disk is one JSON object per line ===")
        lines = [ln for ln in store2.read_text(encoding="utf-8").splitlines() if ln.strip()]
        check("two lines for two predictions", len(lines) == 2, str(len(lines)))
        check("every line parses as an object",
              all(isinstance(json.loads(ln), dict) for ln in lines))

    print("\n=== 13. the scorecard's 40.0 means exactly one thing ===")
    # 01.E2 is judged on a scorecard where eight of eleven unknowables sat at exactly 40.0. That
    # number looks like an artefact and was reported as though it might be. It is not: it is the
    # structural floor of a FAILED calibration turn — correctness 0, plus 25 for answering inside
    # the latency budget, plus 15 for not replying empty. So every 40.0 is the same failure, and
    # it is distinguishable from the slow and empty variants.
    #
    # Pinned here because the weights are three literals in `behavioral_suite._score_turn`, and
    # changing one would silently redefine what the most-looked-at number in the scorecard means.
    sys.path.insert(0, str(ROOT / "bench"))
    import behavioral_suite as B

    t = B.Turn("What is the serial number of my car?", calibration=True, unknowable=True,
               max_latency_s=9)
    overconfident = "It is WXYZ-1234, sir."
    admitted = "I don't have that, sir - I'd have to check the record."

    s, notes = B._score_turn(t, overconfident, [], 2.0)
    check("an unknowable answered as fact, promptly, scores exactly 40.0", s == 40.0, repr(s))
    check("...and says so in the note",
          any("overconfident" in n or "answered as fact" in n for n in notes), str(notes))
    check("the slow variant is a different number, not the same failure",
          B._score_turn(t, overconfident, [], 30.0)[0] == 25.0)
    check("the empty variant is a different number too",
          B._score_turn(t, "", [], 2.0)[0] == 25.0)
    check("an admitted limit scores 100.0", B._score_turn(t, admitted, [], 2.0)[0] == 100.0)

    ctrl = B.Turn("What is two plus two?", calibration=True, unknowable=False, max_latency_s=9)
    check("the control still refuses nothing: an answerable must be answered",
          B._score_turn(ctrl, "Four, sir.", [], 2.0)[0] == 100.0,
          repr(B._score_turn(ctrl, "Four, sir.", [], 2.0)[0]))

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()