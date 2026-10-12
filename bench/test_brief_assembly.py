"""M46 — a brief is assembled by code from a record, and an unverifiable one is refused.

The owner called this layer "professional prompting". What makes it professional is not the
wording — it is that the constraints come from a table a reviewer reads once, instead of from
whichever turn happened to write the prompt. So this gate holds three things:

  1. **An un-checkable brief never reaches a process.** `Brief` already refuses an empty
     acceptance check; the failure that gets past that is an acceptance check which *restates the
     task*. It reads like diligence and verifies nothing, so a run that "met" it was measured
     against its own instructions.
  2. **Every brief carries its domain's constraints, and no caller can drop them.** The caller
     does not write them, cannot pass them in, and cannot opt out — the text is assembled from
     `CONSTRAINTS`, which is code.
  3. **The owner's tier split is read out of the executor table, not restated here.** "Coding goes
     to the corporate CLIs; personal work runs on free models" is already in `SPECS`, and a second
     copy of it would be a second thing to keep true.

Plus the two constraints that exist because a later check cannot undo the failure: an executor
told to commit has already committed, and an OpenClaw agent told to send has already sent.

Hermetic: pure assembly. Nothing is dispatched, no process starts, no network.

    uv run python bench/test_brief_assembly.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


def _raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


@dataclass
class FakeTask:
    """Stands in for `tasks.Task` with only the fields `from_task` reads."""

    title: str
    kind: str = "coding"
    description: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def main() -> int:  # noqa: PLR0915
    import mushegh.brain.executors.briefing as B
    from mushegh.brain.executors import SPECS, BriefRefused, Domain, Tier

    repo = str(Path(__file__).resolve().parents[1])
    src = (Path(__file__).resolve().parents[1]
           / "src/mushegh/brain/executors/briefing.py").read_text(encoding="utf-8")

    print("[1] the constraint set is code, and covers every delegated domain")
    delegated = {d for s in SPECS for d in s.domains}
    check("every domain that has an executor has a constraint set",
          delegated <= set(B.CONSTRAINTS), str(sorted(d.value for d in
                                                      delegated - set(B.CONSTRAINTS))))
    check("no constraint set exists for a domain with no executor",
          set(B.CONSTRAINTS) <= delegated,
          "a constraint set for nothing is speculative")
    check("reading is declared as not-delegated, with the reason (D-86)",
          Domain.READING in B.NOT_DELEGATED and "library" in B.NOT_DELEGATED[Domain.READING])
    check("asking for reading's constraints refuses rather than returning nothing",
          _raises(lambda: B.constraints_for(Domain.READING), BriefRefused))
    for d in sorted(delegated, key=lambda x: x.value):
        got = B.constraints_for(d)
        check(f"{d.value}: the common lines come first and the domain's follow",
              got[:len(B.COMMON_CONSTRAINTS)] == B.COMMON_CONSTRAINTS
              and len(got) > len(B.COMMON_CONSTRAINTS))

    print("\n[2] the tier is derived from the executor table, not restated")
    check("coding is corporate", B.tier_for(Domain.CODING) is Tier.CORPORATE)
    check("daily life is personal", B.tier_for(Domain.DAILY) is Tier.PERSONAL)
    check("business is corporate", B.tier_for(Domain.BUSINESS) is Tier.CORPORATE)
    check("finance defaults to the free pool when its executor serves both",
          B.tier_for(Domain.FINANCE) is Tier.PERSONAL,
          "the cheaper default is the one that fails safe")
    check("a domain with no executor refuses rather than defaulting",
          _raises(lambda: B.tier_for(Domain.READING), BriefRefused))
    check("the split is not hardcoded a second time in this module",
          "Domain.CODING: Tier" not in src and "SPECS" in src,
          "it is read back out of the table")

    print("\n[3] an un-checkable brief is refused before anything is dispatched")
    check("no task is refused",
          _raises(lambda: B.assemble(domain=Domain.DAILY, task="  ",
                                     acceptance="an appointment exists"), BriefRefused))
    check("no acceptance check is refused, and the message asks the right question",
          _refuses_saying(B, Domain.DAILY, "book the dentist", "", "would tell you this was done"))
    check("AN ACCEPTANCE CHECK THAT RESTATES THE TASK IS REFUSED",
          _raises(lambda: B.assemble(domain=Domain.DAILY, task="Book the dentist",
                                     acceptance="book the dentist!"), BriefRefused),
          "it reads like diligence and verifies nothing")
    check("...including with different punctuation and case",
          _raises(lambda: B.assemble(domain=Domain.DAILY, task="Fix the paging bug.",
                                     acceptance="  fix THE paging bug  "), BriefRefused))
    check("a genuinely different check is accepted",
          B.assemble(domain=Domain.DAILY, task="Book the dentist",
                     acceptance="a confirmed appointment appears in the calendar").acceptance
          .startswith("a confirmed"))
    check("a coding brief with no repo is refused here, not at dispatch",
          _raises(lambda: B.assemble(domain=Domain.CODING, task="fix the paging bug",
                                     acceptance="the paging test passes"), BriefRefused),
          "by dispatch the owner has already been told his work was delegated")
    check("a non-coding brief carrying a repo is refused",
          _raises(lambda: B.assemble(domain=Domain.DAILY, task="book the dentist",
                                     acceptance="an appointment exists", repo=repo),
                  BriefRefused))

    print("\n[4] the assembled text carries the work, the constraints and the check")
    brief = B.assemble(domain=Domain.CODING, task="Fix the off-by-one in the paging helper",
                       acceptance="bench/test_paging.py passes", repo=repo)
    body = brief.task
    check("the task is the first thing said", body.startswith("Fix the off-by-one"))
    check("EVERY declared constraint is present",
          all(c in body for c in B.constraints_for(Domain.CODING)),
          str([c[:40] for c in B.constraints_for(Domain.CODING) if c not in body]))
    check("the acceptance check is the LAST line",
          body.strip().splitlines()[-1] == "Done when: bench/test_paging.py passes",
          "it is what the executor is measured on, so it is what it reads last")
    check("the acceptance field is the check itself, not the whole prompt",
          brief.acceptance == "bench/test_paging.py passes")
    check("the tier was filled in without the caller saying so", brief.tier is Tier.CORPORATE)
    check("the repo is carried through", brief.repo == repo)
    check("the brief is dispatchable as built",
          brief.acceptance.strip() and brief.repo and brief.timeout_s >= 5)

    print("\n[5] the constraints that a later check cannot undo")
    coding = " ".join(B.constraints_for(Domain.CODING)).lower()
    check("a coding executor is told not to commit, push or open a PR",
          "do not commit" in coding and "push" in coding and "pull request" in coding,
          "landing.py enforces it; saying it saves a wasted paid run")
    check("...and not to add a schema migration (D-08 condition 3)",
          "schema migration" in coding,
          "a diff that does is refused before the owner sees it, so the run is wasted")
    check("...and to run the suite and report red honestly",
          "test suite" in coding and "red" in coding)
    for d in (Domain.DAILY, Domain.BUSINESS):
        text = " ".join(B.constraints_for(d)).lower()
        check(f"{d.value}: nothing is sent outward without the owner seeing it",
              "send nothing" in text,
              "an agent that already sent an email has done something no check undoes")
    finance = " ".join(B.constraints_for(Domain.FINANCE)).lower()
    check("finance: no money moves, no order is placed (40.F2, D-83)",
          "move no money" in finance and "no order" in finance)
    check("finance: every figure carries an as-of time and says what it omits",
          "as-of" in finance and "leaves out" in finance)
    check("finance: an unfetchable price is reported, never invented",
          "invented quote" in finance)
    common = " ".join(B.COMMON_CONSTRAINTS).lower()
    check("every executor is told it has no stdin and must not ask",
          "non-interactively" in common and "do not ask" in common,
          "a process waiting on input reads as a hang, not as a missing detail")
    check("every executor is told to say what it could not verify", "could not verify" in common)
    check("every executor is told it has no credentials", "credentials" in common)

    print("\n[6] a brief comes from the task record, not from a fresh sentence")
    rec = FakeTask(title="Fix the off-by-one in the paging helper", kind="coding",
                   meta={"acceptance": "bench/test_paging.py passes"})
    got = B.from_task(rec, repo=repo)
    check("the title becomes the work", got.task.startswith("Fix the off-by-one"))
    check("meta['acceptance'] becomes the check",
          got.acceptance == "bench/test_paging.py passes")
    check("the kind picks the domain", got.domain is Domain.CODING)
    check("A TASK WITH NO RECORDED ACCEPTANCE CHECK IS REFUSED, NOT GIVEN A GENERATED ONE",
          _raises(lambda: B.from_task(FakeTask(title="Fix the paging bug"), repo=repo),
                  BriefRefused),
          "a generated check would be Mushegh marking his own homework")
    check("...and the refusal says what to do about it",
          _refuses_saying(B, None, None, None, "add one to the task",
                          lambda: B.from_task(FakeTask(title="Fix the paging bug"), repo=repo)))
    check("a description that merely echoes the title is not an acceptance check",
          _raises(lambda: B.from_task(FakeTask(title="Fix the paging bug",
                                               description="fix the paging bug."), repo=repo),
                  BriefRefused))
    check("a description that genuinely differs is used",
          B.from_task(FakeTask(title="Fix the paging bug",
                               description="the paging test passes on a page of one"),
                      repo=repo).acceptance.startswith("the paging test passes"))
    check("a non-coding record does not need a repo",
          B.from_task(FakeTask(title="Book the dentist", kind="fleet",
                               meta={"acceptance": "a confirmed appointment exists"}))
          .domain is Domain.DAILY)

    print("\n[7] what this module must not become")
    import inspect

    check("it starts no process", "subprocess" not in src)
    check("it calls no model",
          "from mushegh.brain.llm" not in src and "from mushegh.brain.judgment" not in src
          and "import llm" not in src,
          "assembly is deterministic - a model writing the constraints could soften them")
    params = set(inspect.signature(B.assemble).parameters)
    check("assemble() takes no constraints argument",
          not {p for p in params if "constraint" in p or "prompt" in p or "system" in p},
          f"a caller that could pass them could drop them: {sorted(params)}")
    check("...nor a tier, which is derived",
          "tier" not in params, f"{sorted(params)}")
    check("render() takes no constraints argument either",
          not {p for p in inspect.signature(B.render).parameters if "constraint" in p})
    check("CONSTRAINTS is a module-level table of plain strings",
          all(isinstance(v, tuple) and all(isinstance(x, str) and x for x in v)
              for v in B.CONSTRAINTS.values()),
          "not callables, not formats - nothing that can be computed per call")
    check("no template engine and no per-executor prompt variants",
          "jinja" not in src.lower() and "ExecutorSpec" not in src,
          "the constraint that differs by executor rather than by domain has not appeared yet")

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


def _refuses_saying(B, domain, task, acceptance, phrase, call=None) -> bool:
    """A refusal is only useful if it says what to change, so assert on the message too."""
    from mushegh.brain.executors import BriefRefused

    try:
        if call is not None:
            call()
        else:
            B.assemble(domain=domain, task=task, acceptance=acceptance)
    except BriefRefused as e:
        return phrase in str(e)
    except Exception:  # noqa: BLE001
        return False
    return False


if __name__ == "__main__":
    raise SystemExit(main())
