"""14.R4 — a stated goal can produce an interruption at all.

Three properties, which are the gate:

1. **A deviation from a stated goal emits a signal above the context override (0.85)**, so it is
   capable of interrupting media. Before this source existed, nothing in Mushegh could: every companion
   kind is pinned at 0.62 against a 0.85 bar, and the only source that cleared it needed a *calendar
   event*. `14.F3` ("every signal kind is reachable") passes and does not cover this, because a kind
   that only ever fires while he is idle is reachable.
2. **A goal-aligned session that looks identical by elapsed time does NOT.** Same minutes, same
   deadline, `coding` instead of `media` — silence. This is the property that makes the source safe
   to arm, and the one an elapsed-time heuristic cannot have.
3. **Every judged moment is recorded with its reason whether or not it was voiced.** Silence produces
   no evidence (Jev 0.76), so a held moment must leave a trace or the source is unfalsifiable.

Hermetic: `judge()` is pure, so every case here is a function call — no sqlite, no brain, no clock.
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain import goal_deviation as gd  # noqa: E402
from mushegh.config import settings  # noqa: E402

PASS = FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}".rstrip())


@dataclass
class G:
    """Stands in for world_model.Goal — judge() reads it by attribute, so this is the whole fixture."""

    id: str
    text: str
    deadline: str | None = None


NOW = datetime(2026, 9, 21, 21, 30)
MIN = 25


def day(n: int) -> str:
    return (NOW + timedelta(days=n)).date().isoformat()


def main() -> int:
    override = settings.proactive_context_override_urgency
    quiet = settings.proactive_quiet_override_urgency
    base = settings.proactive_relevance_threshold

    print("\n[1] a deviation from a stated goal can interrupt media (the gap 14.F3 does not cover)")
    tomorrow = [G("ship", "ship the Rently beta", day(1))]
    j = gd.judge(category="media", run_minutes=70, goals=tomorrow, now=NOW, min_minutes=MIN)
    check("a long film against a deadline tomorrow is a deviation", j.deviating, j.reason)
    check(f"...and its urgency clears the context override ({override})",
          j.urgency > override, f"urgency={j.urgency}")
    check("...so it is capable of interrupting media at all", j.urgency > override)
    check(f"...but stays below the quiet-hours override ({quiet}), which it must never cross",
          j.urgency < quiet, f"urgency={j.urgency}")
    check("...and names the rungs that produced the number, not just the number",
          "base" in j.reason and "deadline" in j.reason and "sustained" in j.reason, j.reason)
    check("...and carries the goal it is about", j.goal_id == "ship" and j.days_until == 1,
          f"{j.goal_id} {j.days_until}")

    print("\n[2] a goal-aligned session, identical by elapsed time, does NOT")
    aligned = gd.judge(category="coding", run_minutes=70, goals=tomorrow, now=NOW, min_minutes=MIN)
    check("70 minutes of coding against the same deadline is not a deviation", not aligned.deviating)
    check("...and scores zero, not merely below a threshold", aligned.urgency == 0.0,
          str(aligned.urgency))
    check("...while the elapsed time is identical to the case above", True)
    check("...and it still says WHY, so the moment is auditable",
          "not a discretionary category" in aligned.reason, aligned.reason)
    for cat in ("docs", "comms", "other"):
        r = gd.judge(category=cat, run_minutes=240, goals=tomorrow, now=NOW, min_minutes=MIN)
        check(f"four hours of {cat} is never a deviation", not r.deviating, r.reason)
    check("browsing is NOT discretionary by category alone (the expensive false positive)",
          not gd.judge(category="browsing", run_minutes=240, goals=tomorrow, now=NOW,
                       min_minutes=MIN).deviating)

    print("\n[3] the ladder is deterministic, monotone, and bounded")
    a = gd.judge(category="media", run_minutes=70, goals=[G("g", "g", day(6))], now=NOW,
                 min_minutes=MIN)
    b = gd.judge(category="media", run_minutes=70, goals=[G("g", "g", day(2))], now=NOW,
                 min_minutes=MIN)
    c = gd.judge(category="media", run_minutes=70, goals=[G("g", "g", day(0))], now=NOW,
                 min_minutes=MIN)
    check("a nearer deadline is never less urgent", a.urgency < b.urgency < c.urgency,
          f"{a.urgency} {b.urgency} {c.urgency}")
    short = gd.judge(category="media", run_minutes=30, goals=tomorrow, now=NOW, min_minutes=MIN)
    long_ = gd.judge(category="media", run_minutes=70, goals=tomorrow, now=NOW, min_minutes=MIN)
    check("a longer stretch is never less urgent", short.urgency < long_.urgency,
          f"{short.urgency} {long_.urgency}")
    check("the same inputs give the same answer (no clock, no randomness)",
          gd.judge(category="media", run_minutes=70, goals=tomorrow, now=NOW,
                   min_minutes=MIN) == long_)
    worst = gd.judge(category="media", run_minutes=10_000, goals=[G("g", "g", day(0))], now=NOW,
                     min_minutes=MIN)
    check(f"nothing can push it to or past the quiet override ({quiet})", worst.urgency < quiet,
          str(worst.urgency))
    check("...because the ceiling is declared, not emergent", gd.URGENCY_CEILING < quiet,
          str(gd.URGENCY_CEILING))

    print("\n[4] the cases where saying nothing is correct")
    check("under the minimum stretch, nothing",
          not gd.judge(category="media", run_minutes=MIN - 1, goals=tomorrow, now=NOW,
                       min_minutes=MIN).deviating)
    no_deadline = gd.judge(category="media", run_minutes=240, goals=[G("x", "learn German")],
                           now=NOW, min_minutes=MIN)
    check("a goal with no deadline creates no pressure", not no_deadline.deviating,
          no_deadline.reason)
    far = gd.judge(category="media", run_minutes=240, goals=[G("x", "x", day(30))], now=NOW,
                   min_minutes=MIN)
    check("a deadline outside the window creates no pressure", not far.deviating, far.reason)
    check("...and says so, naming the window", "inside" in far.reason, far.reason)
    past = gd.judge(category="media", run_minutes=240, goals=[G("x", "x", day(-3))], now=NOW,
                    min_minutes=MIN)
    check("an already-passed deadline does not nag forever", not past.deviating, past.reason)
    check("no goals at all, nothing",
          not gd.judge(category="media", run_minutes=240, goals=[], now=NOW,
                       min_minutes=MIN).deviating)
    check("a malformed deadline is ignored, not a crash",
          not gd.judge(category="media", run_minutes=240, goals=[G("x", "x", "not-a-date")],
                       now=NOW, min_minutes=MIN).deviating)
    check("the nearest pressing deadline wins when several press",
          gd.judge(category="media", run_minutes=70,
                   goals=[G("far", "far", day(6)), G("near", "near", day(1))],
                   now=NOW, min_minutes=MIN).goal_id == "near")

    print("\n[5] every judged moment is recorded, voiced or not — silence must leave a trace")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "log.jsonl"
        voiced_j = long_
        held_j = gd.judge(category="media", run_minutes=30, goals=[G("g", "g", day(6))], now=NOW,
                          min_minutes=MIN)
        check("the held case is a real deviation, just not an urgent one", held_j.deviating,
              held_j.reason)
        check(f"...and sits below the context override ({override}), so it would be HELD",
              held_j.urgency < override, str(held_j.urgency))
        gd.record(voiced_j, emitted=True, key="K-voiced", path=p)
        gd.record(held_j, emitted=True, key="K-held", path=p)
        gd.record(aligned, emitted=False, path=p)
        gd.confirm("K-voiced", path=p)          # the engine actually spoke this one
        rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
        judged = [r for r in rows if "deviating" in r]
        check("all three judged moments are on disk, including the non-deviation", len(judged) == 3,
              str(len(judged)))
        check("each row carries its reason", all(r["reason"] for r in judged))
        check("each row carries a timestamp", all(r.get("ts") for r in judged))
        check("each judged row records whether it was handed to the engine",
              all("emitted" in r for r in judged))
        heldback = gd.held(path=p)
        check("held() returns exactly the would-have-said", len(heldback) == 1, str(heldback))
        check("...the deviation the engine never spoke", heldback[0]["key"] == "K-held")
        check("...not the one it did speak", all(r["key"] != "K-voiced" for r in heldback))
        check("...and not the aligned moment, which was never a deviation",
              all(r["deviating"] for r in heldback))
        spoke = gd.voiced(path=p)
        check("voiced() returns the other half", len(spoke) == 1 and spoke[0]["key"] == "K-voiced",
              str(spoke))
        check("a confirmation is what separates them, not a guess made at judgement time",
              heldback[0]["emitted"] is True)

    print("\n[6] it cannot break a tick")
    check("a log that cannot be written is swallowed",
          gd.record(long_, emitted=True, path=Path("/nonexistent-dir-14r4/x/y.jsonl")) is None)
    check("held() on a missing file is empty, not an exception",
          gd.held(path=Path("/nonexistent-dir-14r4/nope.jsonl")) == [])
    check("the source is registered with the engine", _registered())
    check("it is OFF by default — the owner arms it deliberately",
          settings.goal_deviation_enabled is False)
    check("the log is a declared store, so 37.R4 covers it", _declared())
    check(f"the base relevance threshold ({base}) is below the ceiling, so it can be voiced at all",
          base < gd.URGENCY_CEILING)

    print("\n[7] through the REAL engine, with the owner busy — the property that actually matters")
    # The arithmetic above only shows a number above a constant. This drives the engine's own gate
    # with `is_busy` pinned True, which is the exact condition under which every companion source is
    # held, and asserts that this one is not.
    import asyncio

    from mushegh.brain.proactive import ProactiveEngine, Signal

    def engine_for(sig: Signal) -> ProactiveEngine:
        return ProactiveEngine(emit=_emit, sources=[lambda: [sig]], is_busy=lambda: True,
                               clock=lambda: NOW)

    interrupting = Signal(key="gd-1", kind="goal-deviation", urgency=long_.urgency,
                          message=gd._message(long_))
    got = asyncio.run(engine_for(interrupting).maybe_interject())
    check(f"a {long_.urgency} goal deviation is voiced even though the owner is busy",
          got is not None and got.channel != "suppressed", str(got))

    companion = Signal(key="c-1", kind="coaching", urgency=0.62, message="evening review?")
    check("...while a 0.62 companion signal in the same engine is HELD (the trap, demonstrated)",
          asyncio.run(engine_for(companion).maybe_interject()) is None)

    borderline = Signal(key="gd-2", kind="goal-deviation", urgency=held_j.urgency,
                        message=gd._message(held_j))
    check(f"...and a {held_j.urgency} deviation is held too — the bar is the urgency, not the kind",
          asyncio.run(engine_for(borderline).maybe_interject()) is None)

    idle = ProactiveEngine(emit=_emit, sources=[lambda: [borderline]], is_busy=lambda: False,
                           clock=lambda: NOW)
    check("...but the same borderline signal IS voiced when he is not busy",
          asyncio.run(idle.maybe_interject()) is not None)

    print("\n[8] the registered source itself — where the voiced/held decision is actually taken")
    # Found by mutation: sections 1-7 all passed with `goal_deviation_signals()` returning a signal
    # for a HELD moment, because they exercised judge() and record() but never the source the engine
    # calls. The decision lives here, so it is tested here.
    from mushegh.brain import world_model

    class FakeWorld:
        def __init__(self, goals):
            self._g = goals

        def active_goals(self, now=None):
            return self._g

    def run_source(category, run_minutes, goals, log):
        real_activity, real_world, real_enabled, real_log = (
            gd._current_activity, world_model.WORLD, settings.goal_deviation_enabled,
            settings.goal_deviation_log_path)
        gd._current_activity = lambda now: (category, run_minutes)
        world_model.WORLD = FakeWorld(goals)
        settings.goal_deviation_enabled = True
        settings.goal_deviation_log_path = str(log)
        try:
            return asyncio.run(gd.goal_deviation_signals(now=NOW))
        finally:
            gd._current_activity, world_model.WORLD = real_activity, real_world
            settings.goal_deviation_enabled = real_enabled
            settings.goal_deviation_log_path = real_log

    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "src.jsonl"
        sigs = run_source("media", 70, tomorrow, log)
        check("an urgent deviation produces exactly one signal", len(sigs) == 1, str(sigs))
        if sigs:
            check("...of kind goal-deviation", sigs[0].kind == "goal-deviation", sigs[0].kind)
            check("...carrying the interrupting urgency", sigs[0].urgency > override,
                  str(sigs[0].urgency))
            check("...naming the goal in what it would say", "ship the Rently beta" in sigs[0].message,
                  sigs[0].message)
            check("...keyed per goal per day, so it cannot nag twice",
                  sigs[0].key.startswith("goal-deviation-ship-"), sigs[0].key)

        check("...and carries an action, which is how a real voicing gets confirmed",
              bool(sigs) and sigs[0].action is not None)
        check("...so until the engine speaks, it counts as a would-have-said",
              len(gd.held(path=log)) == 1, str(gd.held(path=log)))
        if sigs:
            # The action resolves the log path when it RUNS, not when it was built, so it has to be
            # called with the setting still in place — which is how the live brain calls it too.
            settings.goal_deviation_log_path = str(log)
            try:
                sigs[0].action()                 # what the engine runs when it really interjects
            finally:
                settings.goal_deviation_log_path = None
            check("...and once the engine interjects, it moves to voiced()",
                  gd.held(path=log) == [] and len(gd.voiced(path=log)) == 1,
                  f"held={gd.held(path=log)} voiced={gd.voiced(path=log)}")

        far_log = Path(td) / "held.jsonl"
        held_sigs = run_source("media", 30, [G("g", "g", day(6))], far_log)
        check("a borderline deviation is still EMITTED — the source never second-guesses the engine",
              len(held_sigs) == 1, str(held_sigs))
        check("...and stays a would-have-said for as long as nothing confirms it",
              len(gd.held(path=far_log)) == 1, str(gd.held(path=far_log)))

        aligned_log = Path(td) / "aligned.jsonl"
        check("a goal-aligned session produces no signal",
              run_source("coding", 240, tomorrow, aligned_log) == [])
        check("...and is logged as judged-but-not-a-deviation, not omitted",
              aligned_log.exists() and len(gd.held(path=aligned_log)) == 0
              and aligned_log.read_text(encoding="utf-8").count("\n") == 1)

        off_log = Path(td) / "off.jsonl"
        settings.goal_deviation_log_path = str(off_log)
        try:
            check("disabled, it does nothing and writes nothing",
                  asyncio.run(gd.goal_deviation_signals()) == [] and not off_log.exists())
        finally:
            settings.goal_deviation_log_path = None

    print(f"\n=== {PASS}/{PASS + FAIL} checks passed ===")
    return 1 if FAIL else 0


async def _emit(message: str, urgency: float, listening: bool) -> str:
    return "voice"


def _registered() -> bool:
    from mushegh.brain.proactive import default_signal_sources

    return any(getattr(s, "__name__", "") == "goal_deviation_signals"
               for s in default_signal_sources())


def _declared() -> bool:
    from mushegh.brain import data_classes as dc

    store = dc.classify("goal_deviation_log.jsonl")
    return store is not None and not store.leaves_host


if __name__ == "__main__":
    raise SystemExit(main())
