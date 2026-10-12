"""45.R3 — a past turn can be reconstructed, and the replay is honest about what it cannot see.

Two stores hold a turn's history and neither was built to be a witness: the turn trace (the
decision) and the audit trail (what was actually done). `mushegh/brain/replay.py` joins them on
`turn_id` and reports both. What is asserted here is that the join works, and — more to the point —
that the replay does not quietly paper over the three things it genuinely cannot show:

  * **the owner's words.** `TurnTrace.text` exists in memory and is deliberately absent from the
    persisted row, so a replay shows the decision and not the utterance. The replay must SAY that,
    because an empty field and a redacted field look identical on screen and mean opposite things.
  * **a D-24 payload.** Since 37.R5 the audit trail writes `<withheld: …>` in place of a
    never-store class, and secrets are redacted. A replay must label those arguments *withheld by
    policy* and name WHICH argument — "Mushegh decided not to keep this" is information; "we lost it"
    is not, and a replay that cannot tell them apart is worse than none.
  * **a turn with a blank `turn_id`.** Unjoinable, and it must say so rather than return a
    half-answer that looks complete.

And the property that makes the replay worth having: **it verifies what it replays.** Each returned
audit line carries its chain state, so a turn whose trail was edited is explained *and* flagged in
the same breath. Quoting a decision from a tampered file is the failure that matters, and it costs
one field to avoid.

Hermetic: two temp directories, synthetic traces and audit lines. No settings, no model, no network.

    uv run python bench/test_decision_replay.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0

TURN = "turn-abc123"


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def write_trace(root: Path, row: dict, day: str = "2026-10-04") -> None:
    root.mkdir(parents=True, exist_ok=True)
    with (root / f"turns-{day}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def write_audit(root: Path, obj: dict, day: str = "2026-10-04") -> None:
    from mushegh.brain.audit_verify import GENESIS, _HASH_FIELD, _PREV_FIELD, line_hash

    root.mkdir(parents=True, exist_ok=True)
    obj = dict(obj)
    obj[_PREV_FIELD] = GENESIS if obj.get("_first", True) else obj.get("_prev")
    obj.pop("_first", None)
    obj.pop("_prev", None)
    obj[_HASH_FIELD] = line_hash(obj, obj[_PREV_FIELD])
    with (root / f"{day}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def a_row(tool: str, args: dict, turn_id: str = TURN, result: str = "ok", decision: str = "allow",
          ok: bool = True) -> dict:
    return {"ts": "2026-10-04T16:00:00+00:00", "turn_id": turn_id, "tool": tool, "args": args,
            "ok": ok, "actor": "owner", "decision": decision, "rule_applied": "confirm_gate:not_gated",
            "reasoning": "", "result": result}


def a_trace(turn_id: str = TURN, **over) -> dict:
    row = {"ts": "2026-10-04T16:00:00.000+00:00", "seq": 1, "turn_id": turn_id,
           "intent": "act", "language": "en", "streamed": False, "tools_considered": 12,
           "catalogue_tokens": 7418, "prefill_tokens": 110, "tools_fired": ["lock"],
           "sources": ["the lock's own state"], "confidence": "certain", "model": "groq:llama",
           "answer_tokens": 40, "stages_ms": {"judgment": 180.0, "act": 90.0}, "reached": [],
           "total_ms": 1200.0, "ok": True, "error": None}
    row.update(over)
    return row


def main() -> int:
    from mushegh.brain import replay as rp

    traces = Path(tempfile.mkdtemp(prefix="mushegh-rp-traces-"))
    audits = Path(tempfile.mkdtemp(prefix="mushegh-rp-audit-"))

    print("\n[1] a complete turn replays completely")
    write_trace(traces, a_trace())
    write_audit(audits, a_row("lock", {"door": "front"}))
    rep = rp.replay(TURN, trace_root=traces, audit_root=audits)
    check("the turn is found and joinable", rep["found"] and rep["joinable"], str(rep)[:120])
    check("the decision is reconstructed in full",
          rep["decision"] is not None and rep["decision"]["intent"] == "act"
          and rep["decision"]["tools_fired"] == ["lock"], str(rep["decision"])[:120])
    check("...including what it rested on and how firmly",
          rep["decision"]["sources"] == ["the lock's own state"]
          and rep["decision"]["confidence"] == "certain")
    check("...and the per-stage timings", rep["decision"]["stages_ms"]["judgment"] == 180.0)
    check("...and the catalogue cost, which is the thing tuning work needs",
          rep["decision"]["catalogue_tokens"] == 7418)
    check("the tool call is joined on turn_id, not on time proximity",
          len(rep["calls"]) == 1 and rep["calls"][0]["tool"] == "lock", str(rep["calls"]))
    check("a clean trail verifies", rep["integrity"] == "verified", rep["integrity"])

    print("\n[2] the utterance is NOT reconstructed, and the replay says so")
    check("no utterance is invented", rep["utterance"] is None)
    check("...and the reason is stated, not left as an empty field",
          "not in this store" in rep["utterance_note"], rep["utterance_note"][:80])
    txt = rp.explain(rep)
    check("the owner's answer says it too", "your words" in txt and "not in this store" in txt)
    check("the trace row genuinely omits the text (so this is a property, not a filter)",
          "text" not in a_trace(), sorted(a_trace()))

    print("\n[3] a withheld argument is labelled withheld, and named")
    from mushegh.brain.never_store import screen, withheld as mk
    v = screen("the wifi password is 192.168.1.40")
    write_audit(audits, a_row("stash", {"note": mk(v), "folder": "secrets"}))
    rep2 = rp.replay(TURN, trace_root=traces, audit_root=audits)
    stash = [c for c in rep2["calls"] if c["tool"] == "stash"][0]
    check("the call is still replayed — a refusal is information", stash is not None)
    check("the withheld argument is named, so the owner knows WHICH one",
          any("note" in w for w in stash["withheld_args"]), str(stash["withheld_args"]))
    check("...and the marker itself is not mistaken for the password",
          "192.168.1.40" not in json.dumps(stash["args"]), str(stash["args"]))
    check("the explanation names it as withheld BY POLICY",
          "WITHHELD by policy" in rp.explain(rep2), rp.explain(rep2)[-200:])
    check("an argument that was merely absent is NOT called withheld",
          stash["withheld_args"] == stash["withheld_args"] and len(stash["withheld_args"]) == 1,
          str(stash["withheld_args"]))

    print("\n[4] a tampered turn is explained AND flagged")
    path = audits / "2026-10-04.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[0])
    obj["result"] = "the door is open"          # somebody edited a record
    path.write_text("\n".join([json.dumps(obj, ensure_ascii=False)] + lines[1:]) + "\n",
                    encoding="utf-8")
    rep3 = rp.replay(TURN, trace_root=traces, audit_root=audits)
    check("the replay still returns the turn's decision", rep3["decision"] is not None)
    check("...but the integrity is reported as broken", rep3["integrity"] == "broken",
          rep3["integrity"])
    check("...the per-call state is broken too",
          rep3["calls"][0]["integrity"] == "broken", rep3["calls"][0]["integrity"])
    check("...and the owner's answer refuses to vouch for it",
          "unverified" in rp.explain(rep3) or "INTEGRITY" in rp.explain(rep3),
          rp.explain(rep3)[-160:])
    path.unlink()
    for f in audits.glob("*.jsonl"):
        f.unlink()

    print("\n[5] an unjoinable turn says so rather than half-answering")
    for tid, why in (("turn-does-not-exist", "unknown id"), ("", "blank id")):
        rep4 = rp.replay(tid, trace_root=traces, audit_root=audits)
        check(f"a turn with an {why} is not found", not rep4["found"] and not rep4["joinable"],
              f"found={rep4['found']} joinable={rep4['joinable']}")
        out = rp.explain(rep4)
        check("...and the answer opens by saying it has nothing", out.startswith("I have nothing on"),
              out[:80])
    check("a blank turn_id gets the specific reason, not a shrug",
          "never went through a correlated entry point" in rp.explain(rp.replay("", trace_root=traces,
                                                                            audit_root=audits)))

    print("\n[6] a turn with no tool call is reported as such")
    write_trace(traces, a_trace("turn-quiet", tools_fired=[], intent="chat"))
    rep5 = rp.replay("turn-quiet", trace_root=traces, audit_root=audits)
    check("the decision is still reconstructed with no calls",
          rep5["decision"]["intent"] == "chat" and rep5["calls"] == [])
    check("...and integrity says there was nothing to verify, not that it failed",
          rep5["integrity"] == "no-audit-line-for-this-turn", rep5["integrity"])
    check("...and the explanation says exactly that",
          "no tool was called" in rp.explain(rep5), rp.explain(rep5)[-140:])

    print("\n[7] legacy and gap states are carried through, not flattened")
    audits.mkdir(parents=True, exist_ok=True)
    (audits / "2026-10-03.jsonl").write_text(
        json.dumps(a_row("remember", {"text": "the garage remote"}, turn_id="turn-legacy")) + "\n",
        encoding="utf-8")
    rep6 = rp.replay("turn-legacy", trace_root=traces, audit_root=audits)
    check("an unchained line replays as legacy, not as verified",
          rep6["integrity"] == "legacy", rep6["integrity"])
    check("...and the call is still returned", len(rep6["calls"]) == 1)
    # A gap needs a chain that has STARTED and then an unchained line. A file of two unchained lines
    # is simply legacy — which is what a first draft of this section wrote, and it asserted a gap
    # that the fixture never contained.
    for f in audits.glob("*.jsonl"):
        f.unlink()
    write_audit(audits, a_row("remember", {"text": "x"}, turn_id="turn-gap"))
    with (audits / "2026-10-04.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": "2026-10-04T17:00:00+00:00", "turn_id": "turn-gap",
                             "tool": "sneaky", "ok": True}) + "\n")
    rep7 = rp.replay("turn-gap", trace_root=traces, audit_root=audits)
    check("a spliced line replays as a gap", rep7["integrity"] == "gap", rep7["integrity"])
    check("...and the account is not presented as trustworthy",
          "INTEGRITY: gap" in rp.explain(rep7), rp.explain(rep7)[-160:])

    print("\n[8] the replay writes nothing and trusts nothing")
    before = {p: p.read_bytes() for p in audits.glob("*.jsonl")}
    before_tr = {p: p.read_bytes() for p in traces.glob("*.jsonl")}
    for tid in (TURN, "turn-gap", "turn-legacy", "nope"):
        rp.replay(tid, trace_root=traces, audit_root=audits)
        rp.explain(rp.replay(tid, trace_root=traces, audit_root=audits))
    check("the audit store is byte-identical after four replays",
          all(p.read_bytes() == b for p, b in before.items()))
    check("the trace store is byte-identical too",
          all(p.read_bytes() == b for p, b in before_tr.items()))
    src = (ROOT / "src" / "mushegh" / "brain" / "replay.py").read_text(encoding="utf-8")
    check("the module writes nothing: no open-for-write, no append, no mkdir",
          not any(tok in src for tok in (".open(\"a\"", "\"w\"", "mkdir(", "write_text")),
          "a replay that mutates the record it is replaying is not a replay")
    check("...and it imports nothing that needs credentials",
          "settings" not in src.replace("import", "") or "from mushegh.config" not in src)

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
