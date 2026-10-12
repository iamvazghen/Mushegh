"""36.F7 — every action and audit record carries a non-empty, TRUTHFUL actor (hermetic, no network).

Jev p=1.00, conf 0.99 — the most confident actionable directive of the 999: *make the actor an
explicit field on every action and audit record now, even though there is only ever one value.
Retrofitting an identity concept later is the expensive part; carrying it is nearly free.*

The field already half-existed. `audit.record` has taken an ``actor`` since 2026-08-09 (iFixAi B03),
defaulting to ``owner`` on the reasoning that Mushegh is single-principal. That default is right for the
owner's own dispatch path and was a **false record** everywhere else, because:

  * the autonomous worker called the tool registry DIRECTLY, so unattended actions reached no audit
    log at all — `agent.py` records the owner's tool calls in its dispatch loop, and nothing recorded
    Mushegh's own; and
  * anything that did arrive unlabelled was written down as the owner's doing.

So this gate checks three separate things, and the middle one is the regression that matters: an
unattended action must never be attributable to the owner.

    uv run python bench/test_actor_field.py
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain import audit                            # noqa: E402
from mushegh.brain.governor import Governor                # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class ToolThenStopLLM:
    """One tool call, then a written result — the shortest complete worker run."""

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
        return type("M", (), {"content": "Here is what I found.", "tool_calls": None})()


def _lines(audit_dir: Path) -> list[dict]:
    out = []
    for f in sorted(audit_dir.glob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    return out


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        audit_dir = tmpdir / "audit"
        audit_dir.mkdir()
        audit._audit_dir = lambda: audit_dir

        print("\n[1] no audit line can be written without an actor")
        audit.record("some_tool", {"a": 1}, "ok")
        audit.record("explicit", {}, "ok", actor="mushegh:test")
        audit.record("blank", {}, "ok", actor="")
        audit.record("whitespace", {}, "ok", actor="   ")
        rows = _lines(audit_dir)
        check("every line has a non-empty actor",
              all(str(r.get("actor", "")).strip() for r in rows),
              str([r.get("actor") for r in rows]))
        by_tool = {r["tool"]: r["actor"] for r in rows}
        check("an unspecified actor is the owner, on the owner's own path",
              by_tool.get("some_tool") == "owner", str(by_tool))
        check("an explicit actor is kept verbatim", by_tool.get("explicit") == "mushegh:test")
        check("a BLANK actor becomes 'unattributed', never an empty field",
              by_tool.get("blank") == "unattributed", str(by_tool.get("blank")))
        check("and so does a whitespace-only one",
              by_tool.get("whitespace") == "unattributed", str(by_tool.get("whitespace")))

        print("\n[2] the regression that matters: unattended work is NOT the owner's")
        for f in audit_dir.glob("*.jsonl"):
            f.unlink()
        from mushegh.brain import worker as worker_mod

        loose = Governor(max_calls=9999, max_usd=9999.0, max_seconds=9999.0,
                         path=tmpdir / "gov.json")
        loose.reset()
        real, worker_mod.GOVERNOR = worker_mod.GOVERNOR, loose
        try:
            async def fake_tool(args):
                return "a result"

            w = worker_mod.TaskWorker(ToolThenStopLLM(), {"web_search": fake_tool},
                                      [], max_steps=3, actor="mushegh:worker")
            asyncio.run(w.run("look something up"))
            rows = _lines(audit_dir)
            check("the worker's tool call IS audited now", bool(rows),
                  "unattended actions reached no audit log at all before this")
            check("it is attributed to the worker, not the owner",
                  all(r["actor"] != "owner" for r in rows),
                  str([r.get("actor") for r in rows]))
            check("and the actor names the driver",
                  any(r["actor"] == "mushegh:worker" for r in rows),
                  str([r.get("actor") for r in rows]))
            if rows:
                check("the line records what ran and that it was permitted",
                      rows[-1]["tool"] == "web_search" and rows[-1]["decision"] == "allow",
                      json.dumps(rows[-1])[:160])

            print("\n[3] a deferred outward step is audited too, as a deferral")
            for f in audit_dir.glob("*.jsonl"):
                f.unlink()
            w2 = worker_mod.TaskWorker(ToolThenStopLLM(tool="send_email"),
                                       {"send_email": fake_tool}, [], max_steps=3,
                                       actor="mushegh:backlog")
            asyncio.run(w2.run("email someone"))
            rows = _lines(audit_dir)
            defers = [r for r in rows if r.get("decision") == "defer"]
            check("the deferral is recorded", bool(defers),
                  f"{len(rows)} lines, none deferred: {[r.get('decision') for r in rows]}")
            if defers:
                check("as a deferral rather than a success or a failure",
                      defers[-1]["ok"] is False and defers[-1]["decision"] == "defer")
                check("attributed to the driver that attempted it",
                      defers[-1]["actor"] == "mushegh:backlog", defers[-1]["actor"])
                check("and the rule says nobody was there to confirm",
                      "confirm" in defers[-1].get("rule_applied", ""),
                      defers[-1].get("rule_applied", ""))
        finally:
            worker_mod.GOVERNOR = real

        print("\n[4] each autonomous driver names itself at its call site")
        # A blanket "mushegh:worker" would answer "not the owner" but not "which unattended driver",
        # and the four have very different risk profiles.
        expected = {
            "src/mushegh/brain/backlog.py": "mushegh:backlog",
            "src/mushegh/brain/objectives.py": "mushegh:objectives",
            "src/mushegh/brain/code_improve.py": "mushegh:code_improve",
            "src/mushegh/brain/agent.py": "mushegh:copilot",
        }
        for rel, actor in expected.items():
            src = (ROOT / rel).read_text(encoding="utf-8")
            check(f"{rel.rsplit('/', 1)[-1]} passes actor={actor}", f'actor="{actor}"' in src)

        print("\n[5] the worker never falls back to an owner attribution")
        src = (ROOT / "src/mushegh/brain/worker.py").read_text(encoding="utf-8")
        check("TaskWorker declares an actor parameter", "actor: str = \"mushegh:worker\"" in src)
        check("its default is not the owner", not re.search(r'actor:\s*str\s*=\s*"owner"', src))
        blank = worker_mod.TaskWorker(ToolThenStopLLM(), {}, [], actor="")
        check("a blank actor still resolves to a non-owner value",
              blank._actor and blank._actor != "owner", blank._actor)

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
