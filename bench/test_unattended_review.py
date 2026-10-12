"""45.F4 — a surface for reviewing everything done unattended (hermetic, no network).

Jev p=0.74, conf 0.65: *the one safety addition that must exist first.* It is the exception to
"build the visible surface after the first real week" — that directive is about the control room;
this is about being able to answer "what did it do while I wasn't watching", which has to be
answerable **before** anything runs unattended.

The gate: every unattended action appears with its **actor**, its **correlation id** and its
**outcome**. Section [4] is the one that matters — a real worker run, and the review surface finds it
without being told it happened.

It also checks the two things that make the surface trustworthy rather than merely present:
  * the owner's OWN actions must not appear (or "unattended" means nothing); and
  * an action with no correlation id is reported as an uncorrelated gap rather than silently merged
    into a neighbouring run, which would invent a history that did not happen.

    uv run python bench/test_unattended_review.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain import audit                      # noqa: E402
from mushegh.brain import review                     # noqa: E402
from mushegh.brain.audit import _owner_day           # noqa: E402
from mushegh.shared import errors as _err            # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class OneToolLLM:
    """One tool call, then a written result."""

    def __init__(self, tool: str = "web_search") -> None:
        self._tool = tool
        self._step = 0
        self.last_route = {"answered_by": "minimax:MiniMax-Text-01"}

    async def complete(self, messages, tools=None, tool_choice=None):
        self._step += 1
        if self._step == 1:
            call = type("C", (), {
                "id": "c1",
                "function": type("F", (), {"name": self._tool, "arguments": "{}"})(),
            })()
            return type("M", (), {"content": "", "tool_calls": [call]})()
        return type("M", (), {"content": "done", "tool_calls": None})()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        audit_dir = tmpdir / "audit"
        audit_dir.mkdir()
        audit._audit_dir = lambda: audit_dir
        review._audit_dir = lambda: audit_dir
        # The daily audit file is named by the OWNER's calendar day, not UTC's — see
        # audit._owner_day, pinned by six assertions in test_audit_integrity.py. This gate used
        # UTC and therefore failed on its own between 00:00 and 02:00 local, asserting the old
        # behaviour rather than the system.
        today = _owner_day(datetime.now(timezone.utc))

        print("\n[1] the owner's own work is not 'unattended'")
        (audit_dir / f"{today}.jsonl").write_text("\n".join(json.dumps(r) for r in [
            {"ts": f"{today}T10:00:00", "turn_id": "own", "tool": "weather", "actor": "owner",
             "decision": "allow", "ok": True, "result": "18C"},
            {"ts": f"{today}T11:00:00", "turn_id": "bg1", "tool": "web_search",
             "actor": "mushegh:backlog", "decision": "allow", "ok": True, "result": "found"},
        ]) + "\n", encoding="utf-8")
        runs = review.unattended_runs()
        ids = {r["turn_id"] for r in runs}
        check("an owner action is excluded", "own" not in ids, str(ids))
        check("an unattended action is included", "bg1" in ids, str(ids))

        print("\n[2] outcome is distinguished from mere success")
        check("allow + ok is 'done'",
              review.outcome_of({"decision": "allow", "ok": True}) == "done")
        check("allow + not ok is 'failed', not 'refused'",
              review.outcome_of({"decision": "allow", "ok": False}) == "failed")
        check("defer is 'awaiting approval', which is neither",
              review.outcome_of({"decision": "defer", "ok": False}) == "awaiting approval")
        check("deny is 'refused'",
              review.outcome_of({"decision": "deny", "ok": False}) == "refused")

        print("\n[3] actions group into the run that produced them")
        (audit_dir / f"{today}.jsonl").write_text("\n".join(json.dumps(r) for r in [
            {"ts": f"{today}T11:00:00", "turn_id": "run1", "tool": "web_search",
             "actor": "mushegh:objectives", "decision": "allow", "ok": True, "result": "a"},
            {"ts": f"{today}T11:00:02", "turn_id": "run1", "tool": "scrape_url",
             "actor": "mushegh:objectives", "decision": "allow", "ok": False, "result": "timeout"},
            {"ts": f"{today}T11:00:04", "turn_id": "run1", "tool": "send_email",
             "actor": "mushegh:objectives", "decision": "defer", "ok": False, "result": "DEFERRED"},
            {"ts": f"{today}T12:00:00", "turn_id": "run2", "tool": "governor",
             "actor": "mushegh:backlog", "decision": "deny", "ok": False,
             "rule_applied": "governor:calls_ceiling", "result": "ceiling"},
            {"ts": f"{today}T13:00:00", "turn_id": "", "tool": "mystery",
             "actor": "unattributed", "decision": "allow", "ok": True, "result": "?"},
        ]) + "\n", encoding="utf-8")
        snap = review.review_snapshot()
        by_id = {r["turn_id"]: r for r in snap["runs"]}
        check("three actions of one run group into one run",
              "run1" in by_id and by_id["run1"]["action_count"] == 3,
              str(by_id.get("run1", {}).get("action_count")))
        check("its outcomes are counted separately",
              by_id.get("run1", {}).get("outcomes") ==
              {"done": 1, "failed": 1, "awaiting approval": 1},
              str(by_id.get("run1", {}).get("outcomes")))
        check("a governor refusal shows as refused",
              by_id.get("run2", {}).get("outcomes") == {"refused": 1},
              str(by_id.get("run2", {}).get("outcomes")))
        check("runs are newest first", [r["turn_id"] for r in snap["runs"]][0] == "",
              str([r["turn_id"] for r in snap["runs"]]))
        check("a blank correlation id is reported as an uncorrelated gap",
              snap["uncorrelated_runs"] == 1, str(snap["uncorrelated_runs"]))
        check("and is NOT merged into a neighbouring run",
              sum(r["action_count"] for r in snap["runs"]) == 5,
              str([(r["turn_id"], r["action_count"]) for r in snap["runs"]]))
        check("runs needing the owner are separated out",
              len(snap["needs_attention"]) == 2,
              str([r["turn_id"] for r in snap["needs_attention"]]))
        check("actors are tallied so a new driver is visible",
              snap["actors"] == {"mushegh:objectives": 3, "mushegh:backlog": 1, "unattributed": 1},
              str(snap["actors"]))

        print("\n[4] THE GATE: a real unattended run appears with actor, id and outcome")
        for f in audit_dir.glob("*.jsonl"):
            f.unlink()
        from mushegh.brain import worker as worker_mod
        from mushegh.brain.governor import Governor

        async def fake_tool(args):
            return "a result"

        loose = Governor(max_calls=9999, max_usd=9999.0, max_seconds=9999.0,
                         path=tmpdir / "gov.json")
        loose.reset()
        real, worker_mod.GOVERNOR = worker_mod.GOVERNOR, loose
        try:
            _err._turn.set("")
            w = worker_mod.TaskWorker(OneToolLLM(), {"web_search": fake_tool}, [],
                                      max_steps=3, actor="mushegh:worker")
            asyncio.run(w.run("research something"))
        finally:
            worker_mod.GOVERNOR = real

        snap = review.review_snapshot()
        found = [r for r in snap["runs"] if r["turn_id"] == w.turn_id]
        check("the run the worker just did is on the surface", bool(found),
              f"looking for {w.turn_id}, got {[r['turn_id'] for r in snap['runs']]}")
        if found:
            run = found[0]
            check("with its ACTOR", run["actors"] == ["mushegh:worker"], str(run["actors"]))
            check("with its CORRELATION ID", run["turn_id"] == w.turn_id and run["correlated"])
            check("with an OUTCOME per action",
                  all(a["outcome"] in ("done", "failed", "awaiting approval", "refused")
                      for a in run["actions"]),
                  str([a["outcome"] for a in run["actions"]]))
            check("and the tool it actually ran",
                  any(a["tool"] == "web_search" for a in run["actions"]),
                  str([a["tool"] for a in run["actions"]]))
            check("each action says which rule permitted it",
                  all(a["rule"] for a in run["actions"]),
                  str([a["rule"] for a in run["actions"]]))

        print("\n[5] the governor's remaining budget rides along")
        check("the snapshot carries the ledger", isinstance(snap.get("governor"), dict))
        check("with the ceilings, so 'how much is left' is answerable",
              {"max_calls", "max_usd", "max_seconds", "resets_at"} <= set(snap["governor"]),
              str(sorted(snap.get("governor", {}))))

        print("\n[6] it is reachable, and fail-quiet")
        srv = (ROOT / "src/mushegh/brain/server.py").read_text(encoding="utf-8")
        check("/review.json is served", '"/review.json"' in srv)
        check("behind the same auth as /hud.json",
              srv.split('"/review.json"')[1].split("return")[0].count("_post_authorized") == 1)
        hud_src = (ROOT / "src/mushegh/brain/hud.py").read_text(encoding="utf-8")
        check("and the HUD carries the headline", '"unattended": _safe(_unattended' in hud_src)

        review._audit_dir = lambda: tmpdir / "does-not-exist"
        check("a missing audit directory yields an empty surface, not a crash",
              review.review_snapshot()["run_count"] == 0)
        bad = tmpdir / "bad"
        bad.mkdir()
        (bad / f"{today}.jsonl").write_text("{not json\n" + json.dumps(
            {"ts": f"{today}T09:00:00", "turn_id": "ok1", "tool": "t",
             "actor": "mushegh:worker", "decision": "allow", "ok": True}) + "\n", encoding="utf-8")
        review._audit_dir = lambda: bad
        check("one unreadable line does not hide the rest of the day",
              review.review_snapshot()["action_count"] == 1,
              str(review.review_snapshot()))

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
