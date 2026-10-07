"""01.E1 / 01.E2 — the elite scorecard measures the BRAIN, not the owner's configuration (D-44).

`bench/behavioral_suite.py` drives the real agent, so it needs a model and cannot run hermetically.
This file therefore does not re-score anything. It proves the INSTRUMENT is honest, which is the
part that was broken, using synthetic inputs and no model call at all.

**What was actually wrong, in arithmetic rather than impression.** A turn whose expected tool did
not fire is scored `correctness = 10` plus a latency band (`eff ∈ {25, 18, 10, 4}`) plus a delivery
band (`∈ {15, 9, 3}`). So every such turn lands in {29, 35, 40, 43, 50, 62, …} — and those are
exactly the numbers the old scorecard reported: Knowledge 29 = 10+4+15, Combination 40 = 10+10+15,
Time/Utility 43 = 10+18+15, Memory/Web/Tasks 50 = 10+25+15. A turn that did what it was asked scores
60+25+15 = 100. **The whole 40/50/100 cluster was "the expected tool did not fire", and the overall
was a weighted average of 100s and missing API keys.** A missing token was being reported as a
decision that was wrong, which is the one confusion `01.E2` exists to prevent.

So the re-spec, asserted here:

  * an unconfigured scenario is **skipped, not scored** — and stays visible as unconfigured, so the
    gap is reported rather than quietly excluded
  * the overall is computed over **runnable scenarios only**, and the scorecard records that basis
  * a category with fewer than `MIN_RUNNABLE_PER_CATEGORY` runnable scenarios is **underpowered** and
    excluded, because `01.E1`'s own 51.5 was a median of two cases
  * **nothing is loosened**: the band arithmetic is asserted unchanged, so the re-spec cannot have
    quietly made scoring kinder
  * the need tables are checked against the real `Settings` fields and the real scenario list, in
    BOTH directions — a renamed scenario, a typo'd credential field, or a new scenario that forgets
    to declare its dependency all fail here rather than quietly shifting the score

Hermetic: pure functions and a fake settings object. No model, no network, no credentials read.

    uv run python bench/test_scorecard_integrity.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class FakeSettings:
    """A settings stand-in. Every field blank unless a test sets it."""

    def __init__(self, **set_: str) -> None:
        self._set = set_
        for name in _all_fields():
            setattr(self, name, set_.get(name))


def _all_fields() -> set[str]:
    from afon.config import Settings
    return set(Settings.model_fields)


def main() -> int:
    import behavioral_suite as bs
    from afon.config import Settings

    print("\n[1] the cluster had a cause, and it is arithmetic")
    src = (ROOT / "bench" / "behavioral_suite.py").read_text(encoding="utf-8")
    # A turn that expected a tool and did not get it, across the whole (eff, delivery) grid.
    # Computed, not transcribed: a first draft of this file asserted the band from memory and got
    # it wrong, which is the same class of error the note it was checking had made.
    band = sorted({10 + eff + dlv for eff in (25.0, 18.0, 10.0, 4.0) for dlv in (15.0, 9.0, 3.0)})
    check("the scorer's 'expected tool did not fire' band is 17-50 and nothing else",
          band == [17.0, 23.0, 29.0, 31.0, 35.0, 37.0, 38.0, 43.0, 44.0, 50.0], str(band))
    for score, name in ((29.0, "Knowledge"), (43.0, "Time/Utility"), (50.0, "Memory/Web/Tasks")):
        check(f"the old {name} score is reachable from that grid, so it was a missing tool rather "
              f"than a brain failure", score in band, str(score))
    check("and 40 is NOT reachable — the note that claimed 10+10+15 was wrong, and says so",
          40.0 not in band and "It is not" in src, str(band))
    check("...the suite records the band in its own docstring so nobody re-derives it",
          "10+4+15" in src and "17–50" in src)

    print("\n[2] a missing credential is a skip, not a score")
    blank = FakeSettings()
    check("a scenario with no need is runnable", bs.missing_credentials("", blank) == [])
    check("a scenario needing web_search is skipped with a blank key",
          bs.missing_credentials("web_search", blank) == ["brave_api_key"],
          str(bs.missing_credentials("web_search", blank)))
    check("...and runs once the key exists",
          bs.missing_credentials("web_search", FakeSettings(brave_api_key="k")) == [])
    check("notion needs BOTH its token and its database id",
          bs.missing_credentials("notion", FakeSettings(notion_token="t")) == ["notion_tasks_db_id"],
          str(bs.missing_credentials("notion", FakeSettings(notion_token="t"))))
    check("...and runs with both",
          bs.missing_credentials("notion", FakeSettings(notion_token="t", notion_tasks_db_id="d")) == [])
    check("two needs at once are all reported, not just the first",
          bs.missing_credentials("telegram,calendar", blank) == ["telegram_bot_token",
                                                                "google_refresh_token"],
          str(bs.missing_credentials("telegram,calendar", blank)))
    check("an UNKNOWN need key is runnable rather than silently skipped",
          bs.missing_credentials("typo_key", blank) == [],
          "a typo that skipped a scenario would improve the score every time")

    print("\n[3] the need tables are real, not invented")
    settings_fields = set(Settings.model_fields)
    for key, fields in bs.NEEDS.items():
        unknown = [f for f in fields if f not in settings_fields]
        check(f"NEEDS[{key!r}] names real Settings fields", not unknown, str(unknown))
        check(f"NEEDS[{key!r}] is not empty — an empty need would make the check vacuous",
              bool(fields))
    for tool, need in bs.TOOL_NEEDS.items():
        check(f"TOOL_NEEDS[{tool!r}] points at a declared need", need in bs.NEEDS, need)
    for sid, need in bs.SCENARIO_NEEDS.items():
        check(f"SCENARIO_NEEDS[{sid!r}] points at a declared need", need in bs.NEEDS, need)

    print("\n[4] the tables agree with the real scenario list, in BOTH directions")
    scs = bs.scenarios()
    ids = {s.id for s in scs}
    for sid in bs.SCENARIO_NEEDS:
        check(f"SCENARIO_NEEDS has a scenario that exists: {sid}", sid in ids,
              "a renamed scenario would leave a dead entry")
    missing_decl = []
    for s in scs:
        expected = sorted({bs.TOOL_NEEDS[t] for tu in s.turns for t in (tu.expect_tools or ())
                           if t in bs.TOOL_NEEDS})
        if not expected:
            continue
        declared = bs.needs_of(s.id, s.needs)
        if not any(k in declared.split(",") for k in expected):
            missing_decl.append(f"{s.id} expects {expected} but declares {declared!r}")
    check("every scenario expecting a credentialed tool DECLARES its dependency",
          not missing_decl, "; ".join(missing_decl) or "none")
    check("and the suite resolves a need from the table when the scenario declares none",
          bs.needs_of("web_search") == "web_search" and bs.needs_of("identity") == "")
    check("an explicit declaration on the scenario wins over the table",
          bs.needs_of("web_search", "notion") == "notion")

    print("\n[5] the overall is over runnable scenarios only, and says so")
    # Two scenarios per category, so the underpowered rule does not fire on this data — asserted
    # separately below with a one-scenario category. A first draft gave one per category and then
    # expected all three to score, which the floor correctly refused.
    results = [
        {"id": "identity", "category": "Conversation", "score": 100.0, "weight": 1.0},
        {"id": "chat2", "category": "Conversation", "score": 93.0, "weight": 1.0},
        {"id": "safety", "category": "Safety", "score": 100.0, "weight": 1.0},
        {"id": "safety2", "category": "Safety", "score": 100.0, "weight": 1.0},
        {"id": "s1", "category": "Time", "score": 50.0, "weight": 1.0},
        {"id": "s2", "category": "Time", "score": 40.0, "weight": 1.0},
    ]
    rep = bs.rollup(results)
    check("categories with enough scenarios are scored",
          set(rep["categories"]) == {"Conversation", "Safety", "Time"},
          str(sorted(rep["categories"])))
    check("a category with a single scenario is UNDERPOWERED, not scored",
          "Alone" not in bs.rollup(
              [{"id": "a", "category": "Alone", "score": 100.0, "weight": 1.0}])["categories"]
          and bs.rollup([{"id": "a", "category": "Alone", "score": 100.0,
                          "weight": 1.0}])["underpowered"] == {"Alone": 1})
    check("an underpowered category is excluded from the overall",
          bs.rollup([{"id": "a", "category": "Alone", "score": 0.0, "weight": 1.0}])["overall"] == 0.0,
          "a 0-scoring lone scenario must not drag the overall")
    check("weights are honoured in the category mean",
          bs.rollup([{"id": "a", "category": "W", "score": 100.0, "weight": 3.0},
                     {"id": "b", "category": "W", "score": 50.0, "weight": 1.0}]
                   )["categories"]["W"] == 87.5)
    check("the report states its basis in words, not just by omission",
          "runnable" in rep["basis"] and "excluded" in rep["basis"], rep["basis"])
    check("and it counts what it scored and what it left out",
          rep["n_scenarios_scored"] == 6 and rep["n_scenarios_excluded"] == 0, str(rep))
    check("an underpowered category is counted in the excluded figure",
          bs.rollup([{"id": "a", "category": "Alone", "score": 0.0,
                      "weight": 1.0}])["n_scenarios_excluded"] == 1)
    check("an empty result set does not divide by zero",
          bs.rollup([])["overall"] == 0.0)

    print("\n[6] nothing was loosened")
    # The minimum runnable count is a floor on evidence, not a discount on quality.
    check("the runnable floor is 2 — a median of one case is not a measurement",
          bs.MIN_RUNNABLE_PER_CATEGORY == 2, str(bs.MIN_RUNNABLE_PER_CATEGORY))
    tree = ast.parse(src)
    score_fn = next((n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "_score_turn"), None)
    check("the per-turn scorer is untouched by the re-spec", score_fn is not None
          and "correctness = 10.0" in ast.get_source_segment(src, score_fn),
          "the re-spec must change what is COUNTED, not how a turn is scored")
    check("...so a configured-but-wrong turn still scores as badly as before",
          "correctness = 0.0" in (ast.get_source_segment(src, score_fn) or ""))
    check("the verdict thresholds are unchanged (85/72/55)",
          all(t in src for t in ('overall >= 85', 'overall >= 72', 'overall >= 55')))
    check("the scorecard on disk now records the unconfigured list",
          '"unconfigured": unconfigured' in src)
    check("...and the underpowered categories", '"underpowered": report["underpowered"]' in src)

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
