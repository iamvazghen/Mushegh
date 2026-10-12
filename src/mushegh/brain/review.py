"""45.F4 — one surface for reviewing everything Mushegh did unattended.

Jev p=0.74, conf 0.65: *the one safety addition that must exist first.* It is the exception to
"build the visible surface after the first real week" (p=0.88) — that directive is about the control
room; this is about being able to answer "what did it do while I wasn't watching", which has to be
answerable **before** anything runs unattended, not after.

It could not be built until now, and the reason is worth recording. Two things had to land first:

* **36.F7** — unattended actions were not audited at all. `agent.py` records tool calls in *its*
  dispatch loop; `TaskWorker` called the tool registry directly and bypassed it, so the only actions
  in the log were the owner's own. There was nothing to review.
* **31.F5** — without a correlation id, twelve audit lines from one background run were twelve
  unrelated events. A review surface that cannot group a run into a run is a log viewer.

So this module is a **projection**, exactly like `hud.py`: it reads the audit log and groups it. No
new datastore, no new process, no new runtime — which is also the standing directive on how to build
any surface here (p=0.99, conf 0.99: extend what exists against the brain's own HTTP surface).

What counts as unattended is deliberately defined by exclusion: **any actor that is not the owner**.
Naming the autonomous drivers instead would silently miss a new one, and missing an unattended actor
is the single failure this surface exists to prevent.

ponytail: reads the daily jsonl files directly and groups in memory. At six audit lines a turn and a
handful of unattended runs a day this is a rounding error, and an index would be a second store to
keep true. If the log ever outgrows that, the fix is a date range on the read, not a database.

    uv run python -m mushegh.brain.review
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from loguru import logger

#: The one actor that is not unattended. Everything else — `mushegh:worker`, `mushegh:backlog`,
#: `mushegh:objectives`, `mushegh:copilot`, `mushegh:code_improve`, a future driver nobody has written yet,
#: and `unattributed` — is work the owner did not personally ask for in the moment.
OWNER = "owner"

#: Outcomes a reviewer actually distinguishes. `decision` answers "was it allowed", `ok` answers
#: "did it work", and conflating them is the mistake 36.F7's docstring records: a blocked action and
#: a failed action were both once simply `ok: false`.
_OUTCOMES = {
    ("allow", True): "done",
    ("allow", False): "failed",
    ("defer", False): "awaiting approval",
    ("defer", True): "awaiting approval",
    ("deny", False): "refused",
    ("deny", True): "refused",
}


def _audit_dir():
    from mushegh.shared.paths import audit_dir

    return audit_dir()


def outcome_of(line: dict) -> str:
    """One word a reviewer can scan a column of."""
    decision = str(line.get("decision") or "allow")
    ok = bool(line.get("ok"))
    return _OUTCOMES.get((decision, ok), "unknown")


def _read_lines(days: int) -> list[dict]:
    """Audit lines from the last `days` daily files, oldest first. Fail-quiet per file."""
    try:
        directory = _audit_dir()
        if not directory.is_dir():
            return []
        today = datetime.now(timezone.utc).date()
        # The window must be built from the OWNER's day, not UTC's — `audit.record` names the
        # daily file that way. Reading UTC here meant that between 00:00 and 02:00 local this
        # surface looked for files that were not written yet and reported an EMPTY review: the
        # owner's unattended work became invisible for two hours a night, with no error. A blank
        # unattended surface is the single failure this module exists to prevent, so it reads the
        # same rule the writer does (`audit._owner_day`, pinned in test_audit_integrity.py).
        try:
            from mushegh.brain.audit import _owner_day

            today = datetime.strptime(_owner_day(datetime.now(timezone.utc)), "%Y-%m-%d").date()
        except Exception:  # noqa: BLE001 - never let the clock take the surface down
            logger.warning("review: owner-day lookup failed; falling back to the UTC day")
        wanted = {(today - timedelta(days=n)).isoformat() for n in range(max(1, days))}
        out: list[dict] = []
        for path in sorted(directory.glob("*.jsonl")):
            if path.stem not in wanted:
                continue
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not raw.strip():
                    continue
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue      # one unreadable line must not hide the rest of the day
        return out
    except Exception as e:  # noqa: BLE001 — a review surface must never break the brain
        logger.debug(f"review: could not read the audit log ({type(e).__name__})")
        return []


def unattended_runs(days: int = 7, limit: int = 50) -> list[dict]:
    """Unattended actions grouped into the runs that produced them, newest run first.

    A run is one correlation id. Lines with a blank id cannot be grouped — that is a real gap and it
    is reported as one rather than merged into a single misleading bucket, so each blank-id action
    becomes its own single-action run tagged `uncorrelated`.
    """
    lines = [ln for ln in _read_lines(days) if str(ln.get("actor") or "") != OWNER]
    runs: dict[str, dict] = {}
    for index, line in enumerate(lines):
        turn = str(line.get("turn_id") or "")
        # A blank id gets a synthetic per-line key so it is never grouped with an unrelated action.
        key = turn or f"uncorrelated:{index}"
        run = runs.setdefault(key, {
            "turn_id": turn,
            "correlated": bool(turn),
            "actors": [],
            "started": line.get("ts", ""),
            "ended": line.get("ts", ""),
            "actions": [],
            "outcomes": {},
        })
        actor = str(line.get("actor") or "unattributed")
        if actor not in run["actors"]:
            run["actors"].append(actor)
        result = outcome_of(line)
        run["outcomes"][result] = run["outcomes"].get(result, 0) + 1
        run["ended"] = line.get("ts", run["ended"])
        run["actions"].append({
            "ts": line.get("ts", ""),
            "tool": line.get("tool", ""),
            "actor": actor,
            "outcome": result,
            "rule": line.get("rule_applied", ""),
            "why": (line.get("reasoning") or "")[:200],
            "args": line.get("args", {}),
            "result": (line.get("result") or "")[:200],
        })

    ordered = sorted(runs.values(), key=lambda r: r["started"], reverse=True)
    for run in ordered:
        run["action_count"] = len(run["actions"])
        # The summary a reviewer reads before deciding whether to open the run at all.
        run["needs_attention"] = any(
            a["outcome"] in ("failed", "awaiting approval", "refused", "unknown")
            for a in run["actions"]
        )
    return ordered[:limit]


def review_snapshot(days: int = 7, limit: int = 20) -> dict:
    """The whole surface: what ran unattended, what it spent, and what still wants the owner.

    Deliberately carries the governor's ledger alongside the actions. "What did it do" and "how much
    of its budget is left" are the same question asked twice, and a reviewer who has to open two
    pages to answer it will answer neither.
    """
    runs = unattended_runs(days=days, limit=limit)
    totals: dict[str, int] = {}
    actors: dict[str, int] = {}
    for run in runs:
        for action in run["actions"]:
            totals[action["outcome"]] = totals.get(action["outcome"], 0) + 1
            actors[action["actor"]] = actors.get(action["actor"], 0) + 1

    def _governor() -> dict:
        try:
            from mushegh.brain.governor import GOVERNOR

            return GOVERNOR.snapshot()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"review: governor unreadable ({type(e).__name__})")
            return {}

    uncorrelated = sum(1 for r in runs if not r["correlated"])
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_days": days,
        "runs": runs,
        "run_count": len(runs),
        "action_count": sum(r["action_count"] for r in runs),
        "outcomes": totals,
        "actors": actors,
        "needs_attention": [r for r in runs if r["needs_attention"]],
        # A run nobody can reconstruct is the gap 31.F5 exists to close. Reported, not hidden, so it
        # stays countable rather than becoming a silent zero.
        "uncorrelated_runs": uncorrelated,
        "governor": _governor(),
    }


def _selfcheck() -> None:
    """ponytail: the one runnable check — grouping, outcomes, and the blank-id gap."""
    import tempfile
    from pathlib import Path

    global _audit_dir
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        today = datetime.now(timezone.utc).date().isoformat()
        rows = [
            # The owner's own work: must not appear.
            {"ts": f"{today}T10:00:00", "turn_id": "aaa", "tool": "weather", "actor": "owner",
             "decision": "allow", "ok": True, "result": "18C"},
            # One unattended run, three actions, one deferred.
            {"ts": f"{today}T11:00:00", "turn_id": "bbb", "tool": "web_search",
             "actor": "mushegh:backlog", "decision": "allow", "ok": True, "result": "found"},
            {"ts": f"{today}T11:00:05", "turn_id": "bbb", "tool": "scrape_url",
             "actor": "mushegh:backlog", "decision": "allow", "ok": False, "result": "timeout"},
            {"ts": f"{today}T11:00:09", "turn_id": "bbb", "tool": "send_email",
             "actor": "mushegh:backlog", "decision": "defer", "ok": False, "result": "DEFERRED"},
            # A governor refusal.
            {"ts": f"{today}T12:00:00", "turn_id": "ccc", "tool": "governor",
             "actor": "mushegh:objectives", "decision": "deny", "ok": False,
             "rule_applied": "governor:calls_ceiling", "result": "ceiling reached"},
            # An unattributed action with no correlation id: its own run, flagged.
            {"ts": f"{today}T13:00:00", "turn_id": "", "tool": "mystery",
             "actor": "unattributed", "decision": "allow", "ok": True, "result": "?"},
        ]
        (directory / f"{today}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        _audit_dir = lambda: directory  # noqa: E731

        runs = unattended_runs()
        ids = {r["turn_id"] for r in runs}
        assert "aaa" not in ids, "the owner's own actions must not appear in an unattended review"
        assert {"bbb", "ccc"} <= ids, ids
        by_id = {r["turn_id"]: r for r in runs}
        assert by_id["bbb"]["action_count"] == 3, by_id["bbb"]
        assert by_id["bbb"]["outcomes"] == {"done": 1, "failed": 1, "awaiting approval": 1}
        assert by_id["bbb"]["needs_attention"] is True
        assert by_id["ccc"]["outcomes"] == {"refused": 1}
        assert sum(1 for r in runs if not r["correlated"]) == 1, "the blank id must stay visible"

        snap = review_snapshot()
        assert snap["action_count"] == 5, snap["action_count"]
        assert snap["uncorrelated_runs"] == 1
        assert snap["actors"] == {"mushegh:backlog": 3, "mushegh:objectives": 1, "unattributed": 1}
        # Two RUNS want the owner: bbb (a failure and a deferral) and ccc (a refusal). The
        # uncorrelated "mystery" action succeeded, so it does not.
        assert len(snap["needs_attention"]) == 2, snap["needs_attention"]
        print(f"selfcheck ok — {snap['run_count']} unattended runs, "
              f"{snap['action_count']} actions, outcomes {snap['outcomes']}")


if __name__ == "__main__":
    _selfcheck()
