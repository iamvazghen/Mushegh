"""44.R4 / O2.6 — escalate on low confidence, not only on classification (hermetic, no network).

Registry gate: *a low-confidence non-destructive action prompts rather than proceeding.*

Jev p=0.64, conf 0.55: *when the model is unsure it asks rather than proceeds, independent of
whether the action is classified destructive.* The confirm tier answers "how bad is this action";
this answers "does it know what it was asked", and those are different questions. `create_task` is
frictionless **by design** — capture-by-voice is the whole point — so it is exactly the kind of call
classification lets through and confidence should not.

Section [4] is the gate: a real pass through `MusheghAgent._execute_calls` with a tool that is NOT in
the confirm tier, and the call is held.

The two things that stop it becoming noise are checked as hard as the escalation itself: it must
never fire on a read, and it must never hold a call the owner has already affirmed.

    uv run python bench/test_confirm_low_confidence.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault(
    "MUSHEGH_GOVERNOR_LEDGER", str(Path(tempfile.gettempdir()) / "mushegh-test-governor.json")
)

from mushegh.brain import agent as agent_mod                              # noqa: E402
from mushegh.brain import audit                                           # noqa: E402
# The daily audit file is named by the OWNER's calendar day, not UTC's — see audit._owner_day,
# pinned by six assertions in test_audit_integrity.py. This gate derived the name from UTC and
# so failed on its own between 00:00 and 02:00 local, asserting the old behaviour.
from mushegh.brain.audit import _owner_day                                # noqa: E402
from mushegh.brain.proactive import CONFIRM_TIER, is_write, low_confidence  # noqa: E402
from mushegh.shared import errors as _err                                 # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    print("\n[1] it only asks about calls that CHANGE something")
    check("a write is a write", is_write("create_task") and is_write("update_task"))
    check("a read is not", not is_write("weather") and not is_write("recall"))
    check("a write without a verb prefix is still a write", is_write("remember") and is_write("ha_call"))
    check("hedging about a READ is not worth a question",
          low_confidence("weather", said="I think you meant Yerevan") == "",
          "asking 'are you sure?' before a weather lookup is how a gate gets switched off")

    print("\n[2] the two signals, neither of which needs a model")
    check("the model hedged in the same breath",
          "i think" in low_confidence("create_task", said="I think you meant the Tuesday one"))
    check("or the call is a repair of one the schema already rejected",
          "schema" in low_confidence("create_task", repaired=True))
    check("a repair does not need any words at all",
          low_confidence("create_task", said="", repaired=True) != "")
    check("a confident write is not held",
          low_confidence("create_task", said="Creating that now.") == "")
    check("no words and no repair means nothing to escalate",
          low_confidence("create_task", said="") == "")
    check("the reason is speakable, not a score",
          isinstance(low_confidence("create_task", repaired=True), str))

    print("\n[3] this is genuinely the gap classification leaves")
    check("create_task is deliberately NOT in the confirm tier",
          "create_task" not in CONFIRM_TIER,
          "if it were gated, 44.R4 would be doing nothing new")
    check("...and it is a write, so uncertainty about it matters", is_write("create_task"))

    with tempfile.TemporaryDirectory() as tmp:
        audit_dir = Path(tmp) / "audit"
        audit_dir.mkdir()
        audit._audit_dir = lambda: audit_dir
        today = _owner_day(datetime.now(timezone.utc))

        ran: list[str] = []

        async def handler(args):
            ran.append("create_task")
            return "created"

        def run(said: str, *, granted: bool = False, enabled: bool = True,
                tool: str = "create_task") -> list[dict]:
            for f in audit_dir.glob("*.jsonl"):
                f.unlink()
            ran.clear()
            agent_mod.settings.escalate_on_low_confidence = enabled
            agent_mod.settings.face_second_factor = False
            a = agent_mod.MusheghAgent()
            a._registry = {tool: handler}
            a._confirm_granted = granted
            _err._turn.set("t-lowconf")
            asyncio.run(a._execute_calls(
                [], [{"id": "c1", "name": tool, "arguments": json.dumps({"title": "x"})}],
                assistant_content=said,
            ))
            p = audit_dir / f"{today}.jsonl"
            return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] \
                if p.exists() else []

        print("\n[4] THE GATE: an unsure, non-destructive call is held, not run")
        lines = run("I think you meant the Tuesday one — creating it.")
        check("the handler never ran", ran == [], f"it ran anyway: {ran}")
        check("exactly one audit line", len(lines) == 1, str(len(lines)))
        if lines:
            ln = lines[0]
            check("decision is defer — it is asking, not refusing",
                  ln.get("decision") == "defer", str(ln.get("decision")))
            check("the rule names low confidence, not the confirm tier",
                  ln.get("rule_applied") == "low_confidence:model_was_unsure",
                  str(ln.get("rule_applied")))
            check("it carries the correlation id", ln.get("turn_id") == "t-lowconf")
            check("and says what it was unsure about, in words",
                  "unsure" in str(ln.get("result", "")).lower() or "i think" in str(ln.get("result", "")))

        print("\n[5] and it does not become noise")
        lines = run("Creating that now.")
        check("a confident write just runs", ran == ["create_task"], str(ran))
        check("and is audited as allowed",
              lines and lines[0].get("decision") == "allow", str(lines and lines[0].get("decision")))

        lines = run("I think you meant the Tuesday one.", granted=True)
        check("an already-affirmed call is not held a second time",
              ran == ["create_task"],
              "a yes answers the uncertainty as well as the permission")

        lines = run("I think you meant the Tuesday one.", enabled=False)
        check("the off switch really is off", ran == ["create_task"], str(ran))
        agent_mod.settings.escalate_on_low_confidence = True

        print("\n[6] the hold reads correctly on the review surface")
        from mushegh.brain.review import outcome_of

        check("a low-confidence hold reads as awaiting the owner, not as a failure",
              outcome_of({"decision": "defer", "ok": False}) == "awaiting approval")

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
