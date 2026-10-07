"""31.R3 — a weekly self-report that answers the three questions, and says when it cannot.

31.R3 asks for three things: **what broke, what repaired itself, what needs the owner.** The data
for all three already exists and is not being composed:

  * **what broke** — `afon.shared.errors.summary(window)` returns counts by level and by subsystem,
    the worst offender, and the latest entry.
  * **what repaired itself** — `afon.brain.reliability.attempt_repair_and_escalate` records
    `repaired: true` per component in `health_escalation.json`.
  * **what needs the owner** — the same file, `alerted: true` for a component that went red on
    consecutive probes.

What exists instead is a weekly *activity* digest (`proactive_signals.weekly_digest`) that says
"you learned 12 new facts this week". That is a different question, and on a week where three things
broke and self-repair quietly fixed two of them, the activity digest is the wrong report: it looks
like a healthy week.

**The dangerous failure mode here is silence, and it is worth being blunt about it.** On this
machine `health_escalation.json` does not exist — the health probe has not run, because the brain is
not reachable. So two of the three answers are currently **unmeasurable**. A report that rendered
"nothing needed you" would be *wrong by absence of evidence*, and it would be wrong in the most
expensive direction available: it would make you stop looking. So every section carries a status:

    "measured"  the reader had data and the section is a real answer
    "no-data"   the reader had nothing, and the report SAYS SO out loud

There is no third state in which a missing file is reported as health. That is the whole design,
and the gate asserts it by constructing a missing-escalation case and requiring the words to appear
in the rendered output rather than a reassuring nothing.

The weekly digest is left alone: it answers a real question and its callers expect it. This is the
incident half, and it says so.
"""

from __future__ import annotations

import json
from pathlib import Path

MEASURED = "measured"
NO_DATA = "no-data"

#: 31.R3 names three questions. They are named here so the report and its gate cannot drift into
#: answering three others.
QUESTIONS = ("what broke", "what repaired itself", "what needs the owner")


def _no_data(why: str) -> dict:
    return {"status": NO_DATA, "why": why, "count": 0, "items": []}


def _broke(summary: dict | None, why_if_none: str) -> dict:
    """What broke, from the error journal's own summary. Never inferred from an empty journal."""
    if not summary or not summary.get("operations"):
        return _no_data(why_if_none)
    by_level = summary.get("by_level") or {}
    failed = {k: v for k, v in by_level.items() if str(k).upper() != "OK"}
    subs = summary.get("by_subsystem") or {}
    return {
        "status": MEASURED,
        "window_minutes": summary.get("window_minutes"),
        "operations": summary.get("operations", 0),
        "failed": sum(int(v) for v in failed.values()),
        "by_level": failed,
        "by_subsystem": dict(sorted(subs.items(), key=lambda kv: -int(kv[1]))[:5]),
        "top": summary.get("top"),
        "latest": summary.get("latest"),
        "count": sum(int(v) for v in failed.values()),
        "items": [summary.get("top")] if summary.get("top") else [],
    }


def _escalation_state(path: Path) -> tuple[dict | None, str]:
    """The escalation state, or the reason there is none. Reads the file; never assumes it."""
    try:
        if not path.exists():
            return None, (f"no escalation record at {path.name} — the health probe has not run, so "
                          f"nothing is known about repairs or escalations")
        raw = path.read_text(encoding="utf-8", errors="replace")
        state = json.loads(raw) if raw.strip() else {}
        if not isinstance(state, dict) or not state:
            return None, f"{path.name} is empty — the probe has not recorded any component yet"
        return state, ""
    except (OSError, json.JSONDecodeError) as e:
        return None, f"{path.name} unreadable ({type(e).__name__}) — repairs and escalations unknown"


def _component_flags(state: dict) -> tuple[list[str], list[str]]:
    """(repaired itself, needs the owner) from the state. A repaired component is NOT an
    escalation — it is the opposite, and listing it as one would page the owner about a problem
    that is already fixed."""
    repaired, needs = [], []
    for name, rec in (state or {}).items():
        if not isinstance(rec, dict):
            continue
        if rec.get("repaired"):
            repaired.append(name)
        if rec.get("alerted") and not rec.get("repaired"):
            needs.append(name)
    return sorted(repaired), sorted(needs)


def self_report(window_minutes: int = 7 * 24 * 60, *, state_dir: Path | None = None,
                summary: dict | None = None) -> dict:
    """Compose 31.R3's three answers. Reads two places and reports which of them it could read.

    `summary` is injectable so the gate can drive it with a real-shaped journal summary rather than
    a mock of this function's own output; by default it asks `errors.summary` for real.
    """
    from afon.shared.errors import summary as journal_summary

    if summary is None:
        try:
            summary = journal_summary(since_minutes=window_minutes)
        except Exception as e:  # noqa: BLE001 — an unreadable journal is a no-data section
            summary = None
            journal_why = f"the error journal could not be summarised ({type(e).__name__})"
        else:
            journal_why = "the error journal has no operations in this window"
    else:
        journal_why = "the error journal has no operations in this window"

    root = state_dir or (Path(__file__).resolve().parents[2] / ".state")
    state, why = _escalation_state(Path(root) / "health_escalation.json")
    repaired, needs = _component_flags(state)

    return {
        "window_minutes": window_minutes,
        "broke": _broke(summary, journal_why),
        "repaired": ({"status": MEASURED, "count": len(repaired), "items": repaired}
                     if state is not None else _no_data(why)),
        "needs_owner": ({"status": MEASURED, "count": len(needs), "items": needs}
                        if state is not None else _no_data(why)),
    }


def render(rep: dict) -> str:
    """The spoken weekly line. Reads every section, INCLUDING the ones with no data.

    A section that cannot be answered is spoken as unknown. That is the whole point of the module:
    a self-report that quietly omits the part it could not measure is worse than no report, because
    an omitted question reads as a clear one.
    """
    days = max(1, round(rep.get("window_minutes", 0) / 1440))
    parts: list[str] = []

    b = rep["broke"]
    if b["status"] == MEASURED:
        if b["failed"]:
            worst = f", worst was {b['top']}" if b.get("top") else ""
            parts.append(f"{b['failed']} of {b['operations']} operations failed{worst}")
        else:
            parts.append(f"nothing failed across {b['operations']} operations")
    else:
        parts.append(f"I cannot tell you what broke — {b['why']}")

    r = rep["repaired"]
    if r["status"] == MEASURED:
        parts.append(f"{r['count']} thing(s) I fixed myself" if r["count"]
                     else "nothing needed fixing")
    else:
        parts.append(f"I cannot tell you what I fixed — {r['why']}")

    n = rep["needs_owner"]
    if n["status"] == MEASURED:
        parts.append(f"these need you: {', '.join(n['items'])}" if n["count"]
                     else "nothing needs you")
    else:
        parts.append(f"I cannot tell you what needs you — {n['why']}")

    return f"Over the last {days} day(s), sir — " + "; ".join(parts) + "."


def asks_all_three() -> tuple[str, ...]:
    """The three questions, in the order the report answers them. Kept as a function so the gate
    asserts the real list rather than a copy of it."""
    return QUESTIONS


__all__ = ["MEASURED", "NO_DATA", "QUESTIONS", "self_report", "render", "asks_all_three",
           "_component_flags", "_broke"]
