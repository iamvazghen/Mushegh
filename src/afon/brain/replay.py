"""45.R3 — reconstruct a past turn, and say exactly how much of it can be reconstructed.

The question behind this module is the one the owner asks when something comes out wrong: *what did
you think I said, and why did you do that?* Answering it from a log is easy and answering it
honestly is not, because the two stores that hold a turn's history were each built for a different
job and neither was built to be a witness.

**What a replay CAN reconstruct, completely** — the decision, from the turn trace
(`turns-YYYY-MM-DD.jsonl`, keyed on `turn_id`): the intent class, the detected language, how many
tools were considered and what the advertised catalogue cost in tokens, which tools actually fired,
what the answer rested on (`sources`), the confidence label read off the reply, which model was
charged, and the wall clock per stage. That is the whole of *what Afon decided* and none of it is
inferred after the fact.

**What a replay CANNOT reconstruct, and must not pretend to:**

  * **The words.** `TurnTrace.text` exists in memory and is deliberately left out of the persisted
    row. The owner's utterances are not in this store, so a replay shows the decision and not the
    input it was deciding about. That is a privacy property, not a gap in the logging, and the
    replay says so in words instead of rendering an empty field that reads like data loss.
  * **A withheld argument.** Since 37.R5 the audit trail replaces a D-24 payload with a
    `<withheld: …>` marker, and secrets are redacted. A replay therefore shows the marker. It
    labels those arguments *withheld by policy* — a different thing from absent, and the difference
    is the whole point: "Afon decided not to keep this" is information, "we lost it" is not.
  * **A turn with a blank `turn_id`.** It is unjoinable to the audit, and the replay says that
    rather than returning a half-answer that looks complete.

**The replay verifies what it replays.** Each audit line it returns carries the chain state from
`audit_verify`, so a replay of a tampered turn says the turn is not trustworthy *in the same breath*
as it explains the turn. Quoting a decision from a file that was edited afterwards is the failure
mode that matters here, and it is cheap to avoid.

Nothing in this module writes, and nothing re-derives. It reads two stores, joins them on one key,
and reports what it found and what it could not find.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: The marker `afon.brain.never_store` puts in place of a D-24 payload.
_WITHHELD = "<withheld:"

#: What a replay says when the utterance is not there. Stated once, used every time, so the two
#: cannot drift into saying different things in different callers.
NO_UTTERANCE = ("the owner's words are not in this store — the turn trace records the DECISION "
                "(intent, tools, sources, confidence, timings) and deliberately does not persist "
                "the utterance")

_ABSENT = "absent"
_LEGACY = "legacy"
_GAP = "gap"
_BROKEN = "broken"
_NO_AUDIT = "no-audit-line-for-this-turn"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _trace_files(trace_root: Path) -> list[Path]:
    return sorted(trace_root.glob("turns-*.jsonl"))


def find_trace(turn_id: str, trace_root: Path) -> dict | None:
    """The persisted turn row for this id, or None. Newest file wins if an id were ever reused."""
    if not turn_id:
        return None
    for path in reversed(_trace_files(trace_root)):
        for row in _read_jsonl(path):
            if row.get("turn_id") == turn_id:
                return row
    return None


def calls_for(turn_id: str, audit_root: Path) -> list[dict]:
    """Every audit line this turn wrote, oldest first, each annotated with its chain state."""
    from afon.brain.audit_verify import chain

    if not turn_id:
        return []
    out: list[dict] = []
    for path in sorted(audit_root.glob("*.jsonl")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        states = {r["line"]: r for r in chain(lines) if r.get("line")}
        for i, raw in enumerate(lines, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or obj.get("turn_id") != turn_id:
                continue
            st = states.get(i, {}).get("state", _ABSENT)
            out.append({
                "ts": obj.get("ts"),
                "tool": obj.get("tool"),
                "ok": obj.get("ok"),
                "actor": obj.get("actor"),
                "decision": obj.get("decision"),
                "rule_applied": obj.get("rule_applied"),
                "reasoning": obj.get("reasoning") or "",
                "args": obj.get("args"),
                "result": obj.get("result"),
                "integrity": st,
                "withheld_args": _withheld_keys(obj.get("args")),
            })
    out.sort(key=lambda c: (c.get("ts") or ""))
    return out


def _withheld_keys(args: Any) -> list[str]:
    """Which argument keys carry a D-24 marker. Named explicitly so a replay can say WHICH one."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            if _WITHHELD in node:
                found.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    if isinstance(args, dict):
        for k, v in args.items():
            before = len(found)
            walk(v)
            if len(found) > before and not any(f.startswith(f"{k}:") for f in found):
                found[-1] = f"{k}: {found[-1]}"
    else:
        walk(args)
    return found


def integrity_of(calls: list[dict]) -> str:
    """The weakest link in the chain for this turn, because one broken line taints the account."""
    states = {c["integrity"] for c in calls}
    for bad in (_BROKEN, _GAP, _ABSENT, _LEGACY):
        if bad in states:
            return bad
    return "verified" if calls else _NO_AUDIT


def replay(turn_id: str, *, trace_root: Path | None = None,
           audit_root: Path | None = None) -> dict:
    """Reconstruct one turn. Pure apart from reading two directories; writes nothing."""
    from afon.shared.paths import state_dir

    if trace_root is None:
        trace_root = state_dir() / "traces"
    if audit_root is None:
        audit_root = state_dir() / "audit"

    trace = find_trace(turn_id, trace_root)
    calls = calls_for(turn_id, audit_root)
    return {
        "turn_id": turn_id,
        "found": trace is not None or bool(calls),
        "joinable": bool(turn_id) and (trace is not None or bool(calls)),
        "unjoinable_reason": "" if turn_id else "no turn_id — this turn never went through a "
                                                 "correlated entry point, so there is nothing to join on",
        "utterance": None,
        "utterance_note": NO_UTTERANCE,
        "decision": None if trace is None else {
            "intent": trace.get("intent"),
            "language": trace.get("language"),
            "tools_considered": trace.get("tools_considered"),
            "catalogue_tokens": trace.get("catalogue_tokens"),
            "prefill_tokens": trace.get("prefill_tokens"),
            "tools_fired": trace.get("tools_fired"),
            "sources": trace.get("sources"),
            "confidence": trace.get("confidence"),
            "model": trace.get("model"),
            "stages_ms": trace.get("stages_ms"),
            "total_ms": trace.get("total_ms"),
            "ok": trace.get("ok"),
            "error": trace.get("error"),
        },
        "calls": calls,
        "integrity": integrity_of(calls),
    }


def explain(rep: dict) -> str:
    """The owner's answer, in his language. Says what is missing; never fills a gap with a guess."""
    if not rep["joinable"]:
        return (f"I have nothing on turn {rep['turn_id'] or '(no id)'}. "
                f"{rep['unjoinable_reason'] or 'it may be older than the trace store, or it never fired a tool.'}")
    lines = [f"Turn {rep['turn_id']}:"]
    d = rep["decision"]
    if d is None:
        lines.append("  - no turn trace: the decision record is missing, so I cannot tell you what I "
                     "decided. The tool calls below are what I did, not why.")
    else:
        lines.append(f"  - heard: intent {d['intent']}, language {d['language'] or 'unstated'}")
        lines.append(f"  - considered {d['tools_considered']} tool(s), advertised "
                     f"{d['catalogue_tokens']} schema tokens, {d['prefill_tokens']} prefill tokens")
        lines.append(f"  - fired: {', '.join(d['tools_fired']) if d['tools_fired'] else 'nothing'}")
        lines.append(f"  - rested on: {', '.join(d['sources']) if d['sources'] else 'nothing cited'}")
        lines.append(f"  - confidence: {d['confidence']}; model {d['model'] or 'unstated'}")
        lines.append(f"  - took {d['total_ms']}ms; ok={d['ok']}"
                     + (f"; error {d['error']}" if d.get("error") else ""))
    lines.append(f"  - your words: {rep['utterance_note']}")
    for c in rep["calls"]:
        line = (f"  - {c['ts']} {c['tool']}: ok={c['ok']}, decision={c['decision']}, "
                f"rule={c['rule_applied']}")
        if c["withheld_args"]:
            line += f" [WITHHELD by policy: {'; '.join(c['withheld_args'])}]"
        if c["integrity"] in (_BROKEN, _GAP, _LEGACY):
            line += f" [chain: {c['integrity']}]"
        lines.append(line)
    state = rep["integrity"]
    if state == "verified":
        lines.append("  - this turn's record is hash-chained and verified.")
    elif state == _NO_AUDIT:
        lines.append("  - no tool was called, so there is no audit line to verify.")
    else:
        lines.append(f"  - INTEGRITY: {state}. Treat the account above as unverified.")
    return "\n".join(lines)
