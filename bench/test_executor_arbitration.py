"""M45 — Jev picks the executor, and cannot widen what code offered (D-73, D-76, D-81).

Three coding CLIs are installed and all three are permitted to receive the same brief, so
something has to choose. The thing that makes a paid model safe on that path is not the quality of
its pick — it is that **the ballot is built by code and a silent failure keeps the deterministic
answer**. This gate holds those two, plus the one nobody thinks to test:

  * **Jev can never name an executor that is not installed**, because `candidates()` filtered by
    `shutil.which` before the question was asked. The ballot is the boundary.
  * **An outage, a timeout or a disabled service costs nothing and says nothing.** The budget is
    400 ms; the correct behaviour past it is to carry on exactly as before (D-73). And the owner
    never hears that an arbitration happened at all — he asked for the work, not for a routing
    report (D-34).
  * **A near-tie is not an opinion.** `Arbitration.arbitrated` is gated on the entropy zone
    (D-76), so a flat distribution reads as "no winner" and the deterministic order stands. A coin
    flip dressed as a decision is worse than an arbitrary rule, because it is believable.

And the question itself: the wording is declared in `judgment.ROUTE_INSTRUCTIONS`, not passed in by
the caller. A caller that could write its own instructions could widen what the model is being
asked to decide without touching the judgment module — which is the review surface.

Hermetic: a fake transport stands in for the Jev service, and the executor table is substituted.
No network, no process, no cost.

    uv run python bench/test_executor_arbitration.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  <- {detail}" if detail else ""))


def _answer(choice: str, probs: dict[str, float]) -> dict:
    return {"model": "jev-test",
            "answers": {"route": {"choice": choice, "probabilities": probs, "confidence": 0.9}}}


async def main() -> int:  # noqa: PLR0915
    import afon.brain.executors as X
    from afon.brain.executors import Brief, BriefRefused, Domain, ExecutorSpec, Tier
    from afon.brain.judgment import ROUTE_INSTRUCTIONS, JudgmentService

    src = (Path(__file__).resolve().parents[1]
           / "src/afon/brain/executors/__init__.py").read_text(encoding="utf-8")
    pick_src = src.split("async def pick(")[1].split("\ndef ")[0]
    repo = str(Path(__file__).resolve().parents[1])

    print("[0] the question is declared in the judgment module, not written by the caller")
    check("there is a wording for the executor question",
          "executor" in ROUTE_INSTRUCTIONS and ROUTE_INSTRUCTIONS["executor"].strip())
    check("the set of purposes is closed and small",
          sorted(ROUTE_INSTRUCTIONS) == ["executor", "tools"], str(sorted(ROUTE_INSTRUCTIONS)))
    text = ROUTE_INSTRUCTIONS["executor"].lower()
    check("it says the options are already installed and already permitted",
          "installed" in text and "permitted" in text,
          "so the model is choosing, not granting")
    check("it puts authorization out of scope explicitly",
          "out of scope" in text and ("authorization" in text or "permission" in text))
    check("it never asks the model whether the work should happen",
          "should" not in text and "safe" not in text and "allow" not in text, text)
    check("pick() names the purpose rather than passing wording",
          'route_purpose="executor"' in pick_src and "instructions" not in pick_src)

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        original = X.SPECS

        # Three installed coding executors, and one that is not installed. `sys.executable` always
        # exists; the fourth binary never does, so `available()` is being measured, not asserted.
        def spec(name: str, argv0: str) -> ExecutorSpec:
            return ExecutorSpec(name=name, domains=(Domain.CODING,), tiers=(Tier.CORPORATE,),
                                argv=(argv0, "exec", "{task}"))

        three = (spec("alpha", sys.executable), spec("beta", sys.executable),
                 spec("gamma", sys.executable), spec("ghost", "afon-no-such-binary-xyz"))
        X.SPECS = three
        brief = Brief(domain=Domain.CODING, task="fix the off-by-one in the paging helper",
                      acceptance="the paging test passes", tier=Tier.CORPORATE, repo=repo)

        try:
            print("\n[1] the ballot is built by code, and an uninstalled executor is not on it")
            names = [s.name for s in X.candidates(brief)]
            check("only installed executors are candidates", names == ["alpha", "beta", "gamma"],
                  str(names))
            check("the uninstalled one is excluded", "ghost" not in names)

            seen: list[dict] = []

            async def transport(payload, _k, _e, _t):
                seen.append(payload)
                return 200, _answer("group_2", {"group_1": 0.04, "group_2": 0.92,
                                                "group_3": 0.04})

            svc = JudgmentService(key="k", transport=transport, log_path=root / "a.jsonl")
            got, arb = await X.pick(brief, service=svc)
            check("Jev's pick is the one used", got.name == "beta", got.name)
            check("the arbitration is reported to the caller, not spoken",
                  arb is not None and arb.arbitrated and arb.winner == "beta", repr(arb))
            check("exactly one call was made", len(seen) == 1, str(len(seen)))
            if seen:
                crit = seen[0]["questions"]["route"]["criteria"]
                check("the options are exactly the installed executors",
                      sorted(crit.values()) == ["alpha", "beta", "gamma"], json.dumps(crit))
                check("THE UNINSTALLED EXECUTOR IS NOT EVEN ON THE BALLOT",
                      "ghost" not in json.dumps(seen[0]),
                      "Jev cannot name what it was never offered")
                check("the question is the brief's task",
                      seen[0]["state"]["question"] == brief.task)
                check("only the route question is asked",
                      sorted(seen[0]["questions"]) == ["route"],
                      "no urgency or tone — this is not a turn")
                check("the executor wording was sent, not the tool wording",
                      seen[0]["questions"]["route"]["instructions"]
                      == ROUTE_INSTRUCTIONS["executor"])
                blob = json.dumps(seen[0]).lower()
                leaked = [w for w in ("api_key", "token", "secret", "vault", "biometric",
                                      "password", "\\\\users\\\\") if w in blob]
                check("no credential or path rode along outbound", not leaked, str(leaked))

            print("\n[2] a near-tie is not an opinion (D-76)")

            async def flat(_p, _k, _e, _t):
                return 200, _answer("group_1", {"group_1": 0.36, "group_2": 0.34,
                                                "group_3": 0.30})

            svc = JudgmentService(key="k", transport=flat, log_path=root / "flat.jsonl")
            got, arb = await X.pick(brief, service=svc)
            check("a flat distribution leaves the deterministic order standing",
                  got.name == "alpha", got.name)
            check("...and is reported as not arbitrated rather than as a winner",
                  arb is not None and not arb.arbitrated, repr(arb))

            print("\n[3] silence keeps every candidate (D-73)")

            async def slow(_p, _k, _e, _t):
                await asyncio.sleep(2.0)
                return 200, _answer("group_3", {"group_3": 0.99})

            svc = JudgmentService(key="k", transport=slow, log_path=root / "slow.jsonl")
            t0 = time.perf_counter()
            got, arb = await X.pick(brief, service=svc)
            elapsed = (time.perf_counter() - t0) * 1000
            check("a timeout returns inside the budget", elapsed < 1200, f"{elapsed:.0f}ms")
            check("...and keeps the deterministic choice", got.name == "alpha", got.name)
            check("...and a late answer is discarded, not applied",
                  arb is None or not arb.arbitrated, repr(arb))

            async def boom(_p, _k, _e, _t):
                raise RuntimeError("jev is down")

            svc = JudgmentService(key="k", transport=boom, log_path=root / "boom.jsonl")
            got, _ = await X.pick(brief, service=svc)
            check("an outage keeps the deterministic choice", got.name == "alpha", got.name)

            class Exploding:
                async def arbitrate(self, *_a, **_kw):
                    raise RuntimeError("the service itself blew up")

            got, arb = await X.pick(brief, service=Exploding())
            check("even a broken service object degrades rather than raising",
                  got.name == "alpha" and arb is None, got.name)

            svc = JudgmentService(key="", transport=boom, log_path=root / "nokey.jsonl")
            got, _ = await X.pick(brief, service=svc)
            check("no API key configured is a normal outcome, not an error", got.name == "alpha")

            svc = JudgmentService(key="k", enabled=False, transport=boom,
                                  log_path=root / "off.jsonl")
            got, _ = await X.pick(brief, service=svc)
            check("a disabled service is a normal outcome too", got.name == "alpha")

            print("\n[4] a verdict outside the ballot is a protocol fault, not a route")

            async def off_ballot(_p, _k, _e, _t):
                return 200, {"model": "jev-test", "answers": {"route": {
                    "choice": "group_9", "probabilities": {"group_9": 0.99}, "confidence": 0.9}}}

            svc = JudgmentService(key="k", transport=off_ballot, log_path=root / "off2.jsonl")
            got, _ = await X.pick(brief, service=svc)
            check("an unmappable choice cannot select anything", got.name == "alpha", got.name)
            check("resolve() is still the authority that refuses it",
                  _raises(lambda: X.resolve(brief, chosen="ghost"), BriefRefused),
                  "pick() is the policy; resolve() is the rule")
            check("...and refuses a name that was never a spec at all",
                  _raises(lambda: X.resolve(brief, chosen="rubo"), BriefRefused))

            print("\n[5] arbitration costs nothing when there is nothing to decide")
            calls = {"n": 0}

            class Counting:
                async def arbitrate(self, *_a, **_kw):
                    calls["n"] += 1
                    return None

            X.SPECS = (spec("only", sys.executable),)
            got, arb = await X.pick(brief, service=Counting())
            check("a single candidate is returned with no call",
                  got.name == "only" and arb is None and calls["n"] == 0, str(calls))

            X.SPECS = (spec("ghost", "afon-no-such-binary-xyz"),)
            check("no installed candidate is REFUSED, not arbitrated",
                  await _refuses(X, brief, Counting()))
            check("...and still no call was made", calls["n"] == 0, str(calls))
        finally:
            X.SPECS = original

    print("\n[6] the owner never hears that an arbitration happened (D-34)")
    for word in ("sir", "speak", "say(", "notify", "announce", "tts"):
        check(f"pick() never {word!r}s", word not in pick_src.lower())
    check("a protocol fault is logged, not spoken", "logger.warning" in pick_src)
    check("...and an outage is quieter still than that", "logger.debug" in pick_src)
    check("pick() starts no process", "create_subprocess" not in pick_src)
    check("the entropy gate is not re-implemented here",
          "normalized_entropy(" not in pick_src and "entropy_zone(" not in pick_src
          and "arbitrated" in pick_src,
          "Arbitration.arbitrated already carries D-76's zone; a second threshold here would be "
          "a second place for the bar to drift")
    check("no confidence threshold is invented alongside it",
          "probability" not in pick_src and "0." not in pick_src.replace("D-7", ""),
          "a magic number here would silently override the declared zones")

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


def _raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


async def _refuses(X, brief, service) -> bool:
    from afon.brain.executors import BriefRefused

    try:
        await X.pick(brief, service=service)
    except BriefRefused:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
