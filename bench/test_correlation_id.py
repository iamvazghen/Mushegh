"""31.F5 — one correlation id, edge -> brain -> tool -> audit, with no gaps (hermetic, no network).

Jev p=0.93, conf 0.87: *instrument first: guarantee one correlation id propagates edge -> brain ->
tool -> audit with no gaps, THEN observe. Traces you cannot join prove nothing.* This is the Wave-0
floor that every other runtime-evidence claim depends on — 28 of 50 systems are waiting on "runtime
evidence", and evidence you cannot join is not evidence.

Two of the four hops already worked and are regression-checked here: the edge mints the id and puts
it on the `Utterance` (`edge/brain_client.py`), the brain adopts it (`server.py`), and it reaches the
pc agent (`pc_link.py` -> `pc_agent.py`). The two that did NOT work were the records that matter:
the turn trace the HUD reads and the audit line an incident review reads. A trace and an audit line
for the same turn could not be joined at all.

The test that actually matters is [3]: one simulated turn, and every record it produces carries the
same id.

    uv run python bench/test_correlation_id.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain import audit                        # noqa: E402
from mushegh.brain import turn_trace as T              # noqa: E402
from mushegh.shared import errors as _err              # noqa: E402
from mushegh.shared.protocol import Utterance          # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


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

        print("\n[1] hop 1 - the edge mints an id and the protocol carries it")
        tid = _err.new_turn()
        check("new_turn() returns a usable id", bool(tid) and len(tid) >= 8, tid)
        check("current_turn() reports it back", _err.current_turn() == tid)
        utt = Utterance(text="what is the weather", session_id="s1", ts_user_stop_ms=0, turn_id=tid)
        check("Utterance carries turn_id across the edge->brain boundary", utt.turn_id == tid)
        check("and it is optional, so an older edge still connects",
              Utterance(text="hi", session_id="s1", ts_user_stop_ms=0).turn_id == "")

        print("\n[2] hop 2 - the brain adopts the edge's id rather than minting its own")
        adopted = _err.new_turn(utt.turn_id or None)
        check("the brain adopts the id it was given", adopted == tid, f"{adopted} != {tid}")
        minted = _err.new_turn(None)
        check("and mints one when the edge sent none", bool(minted) and minted != tid)

        print("\n[3] hops 3 and 4 - ONE turn, and every record it writes shares the id")
        for f in audit_dir.glob("*.jsonl"):
            f.unlink()
        tid = _err.new_turn()
        with T.turn("what's the weather") as tr:
            tr.set_intent("general")
            T.fired("weather")
            audit.record("weather", {"city": "Yerevan"}, "18C and clear")
            audit.record("set_reminder", {"text": "umbrella"}, "done")
        row = T.last()
        rows = _lines(audit_dir)

        check("the turn row carries a turn_id at all", bool(row) and "turn_id" in (row or {}),
              str(row)[:160])
        check("the turn row's id is the turn's id", bool(row) and row.get("turn_id") == tid,
              f"{row and row.get('turn_id')} != {tid}")
        check("both audit lines were written", len(rows) == 2, str(len(rows)))
        check("every audit line carries the SAME id",
              bool(rows) and all(r.get("turn_id") == tid for r in rows),
              str([r.get("turn_id") for r in rows]))
        check("so trace and audit JOIN on one key - the whole point",
              bool(row) and bool(rows)
              and {row.get("turn_id")} == {r.get("turn_id") for r in rows},
              f"trace={row and row.get('turn_id')} audit={[r.get('turn_id') for r in rows]}")
        check("and the tool that fired is on the joined row",
              bool(row) and "weather" in (row.get("tools_fired") or []), str(row))

        print("\n[4] a dropped hop is visible, not papered over")
        for f in audit_dir.glob("*.jsonl"):
            f.unlink()
        _err.new_turn("")          # no correlated entry point
        _err._turn.set("")         # explicitly clear, as an uncorrelated job would be
        with T.turn("a scheduled job") as tr:
            tr.set_intent("general")
            audit.record("some_job", {}, "ok")
        row = T.last()
        rows = _lines(audit_dir)
        check("an uncorrelated turn records a BLANK id rather than inventing one",
              bool(row) and row.get("turn_id") == "", str(row and row.get("turn_id")))
        check("and so does its audit line, so the gap is countable",
              bool(rows) and rows[0].get("turn_id") == "", str(rows[:1]))

        print("\n[5] an explicit override wins, for a caller that knows better")
        for f in audit_dir.glob("*.jsonl"):
            f.unlink()
        audit.record("x", {}, "ok", turn="deadbeef")
        rows = _lines(audit_dir)
        check("audit.record(turn=...) is honoured", rows and rows[0]["turn_id"] == "deadbeef",
              str(rows[:1]))

        print("\n[6] an unattended run is correlated too - it mints its own")
        for f in audit_dir.glob("*.jsonl"):
            f.unlink()
        from mushegh.brain import worker as worker_mod
        from mushegh.brain.governor import Governor

        class OneToolLLM:
            def __init__(self) -> None:
                self._step = 0
                self.last_route = {"answered_by": "minimax:MiniMax-Text-01"}

            async def complete(self, messages, tools=None, tool_choice=None):
                self._step += 1
                if self._step == 1:
                    call = type("C", (), {
                        "id": "c1",
                        "function": type("F", (), {"name": "web_search",
                                                   "arguments": "{}"})(),
                    })()
                    return type("M", (), {"content": "", "tool_calls": [call]})()
                return type("M", (), {"content": "found it", "tool_calls": None})()

        async def fake_tool(args):
            return "a result"

        loose = Governor(max_calls=9999, max_usd=9999.0, max_seconds=9999.0,
                         path=tmpdir / "gov.json")
        loose.reset()
        real, worker_mod.GOVERNOR = worker_mod.GOVERNOR, loose
        try:
            _err._turn.set("")     # no ambient turn: the worker must create one
            w = worker_mod.TaskWorker(OneToolLLM(), {"web_search": fake_tool}, [],
                                      max_steps=3, actor="mushegh:worker")
            asyncio.run(w.run("look something up"))
            rows = _lines(audit_dir)
            check("the worker minted a correlation id", bool(getattr(w, "turn_id", "")),
                  str(getattr(w, "turn_id", None)))
            check("its audit lines carry it, so the run is reconstructable",
                  bool(rows) and all(r.get("turn_id") == w.turn_id for r in rows),
                  f"want {getattr(w, 'turn_id', None)}, got {[r.get('turn_id') for r in rows]}")

            # ...and the other way round: work spawned BY a turn stays joined to that turn, so
            # "the owner asked X" and "here is the background work it spawned" share one key.
            for f in audit_dir.glob("*.jsonl"):
                f.unlink()
            asked = _err.new_turn()
            w2 = worker_mod.TaskWorker(OneToolLLM(), {"web_search": fake_tool}, [],
                                       max_steps=3, actor="mushegh:worker")
            asyncio.run(w2.run("look something up"))
            rows = _lines(audit_dir)
            check("a run started inside a live turn ADOPTS that turn's id",
                  w2.turn_id == asked, f"{w2.turn_id} != {asked}")
            check("so the request and the work it spawned join on one key",
                  bool(rows) and all(r.get("turn_id") == asked for r in rows),
                  str([r.get("turn_id") for r in rows]))
        finally:
            worker_mod.GOVERNOR = real

        print("\n[7] the two hops that already worked stay wired")
        src = (ROOT / "src/mushegh/edge/brain_client.py").read_text(encoding="utf-8")
        check("the edge still mints a turn id", "new_turn()" in src)
        check("and still sends it", "turn_id=turn_id" in src)
        src = (ROOT / "src/mushegh/brain/server.py").read_text(encoding="utf-8")
        check("the brain still adopts the edge's id", "new_turn(utt.turn_id or None)" in src)
        src = (ROOT / "src/mushegh/brain/pc_link.py").read_text(encoding="utf-8")
        check("the brain still forwards it to the pc agent", '"turn_id"' in src)
        src = (ROOT / "src/mushegh/edge/pc_agent.py").read_text(encoding="utf-8")
        check("and the pc agent still adopts it", 'data.get("turn_id")' in src)

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
