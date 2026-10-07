"""14.R4 — the one path from a stated goal to an interruption.

Every other companion source in this engine is *structurally* unable to interrupt the owner, and not
by accident: `urgency` is a hardcoded literal per source, coaching / presence / learned-patterns /
news are all pinned at **0.62**, and the bar to interrupt him while he is busy or watching media is
`proactive_context_override_urgency = 0.85`. `coaching.py`'s own docstring states this as intended.
Exactly one source has ever cleared that bar — `interventions.conflict_signals()` at 0.90 — and it
requires media playing AND an imminent *calendar event*. So before this module there was **no code
path in Afon from a goal the owner stated to a moment where Afon said something about it.** The
autopilot he asked for was never a missing engine; it was a missing signal source.

**The deviation is about WHAT he is doing, not how long he has been at it.** That is the whole
discriminator, and it is why this cannot be built out of `continuous_active_minutes()`: a four-hour
coding run and a four-hour film are identical by elapsed time and opposite in meaning. A long session
in a *discretionary* category, while a stated goal has a deadline bearing down, is a deviation. The
same session length in `coding` or `docs` is a goal being met, and interrupting it is the expensive
error.

**Urgency is computed here, deterministically, and this module owns no thresholds.** Jev was asked
whether a judgment model should produce the urgency float and answered no at **0.97, conf 0.95** — the
model judges severity, code owns the arithmetic and the gate. `14.R5` may later refine *severity*;
it may never move a threshold, and with no key configured this file's behaviour is unchanged.

**Silence produces no evidence** (Jev **0.76**). There is no event for "should have spoken and did
not", so a source biased toward quiet is unfalsifiable in operation — it looks identical to a working
one. Hence `record()`: every judged moment is written with its reason *whether or not it was voiced*.
Whether to err toward interrupting or toward silence returned **0.49 across three framings** and is
the owner's tolerance, not a property of the system. It is deliberately NOT guessed here. The log is
the instrument it gets read off, which is why it is load-bearing rather than diagnostic.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from loguru import logger

from afon.config import settings
from afon.shared.paths import state_dir

#: Categories that are discretionary by nature. `browsing` is deliberately ABSENT: it is both how the
#: owner works and how he wastes an afternoon, and a false interruption of real work is the expensive
#: error here. Browsing only counts when the window title says it is media (`_looks_like_media`),
#: which is a fact rather than a guess.
DISCRETIONARY: tuple[str, ...] = ("media", "gaming")

#: The deterministic urgency ladder. Stated as data so the reason string can name the exact rung that
#: fired, and so a change to it is a visible diff rather than an edited expression.
BASE_URGENCY = 0.62                       #: a deviation with no deadline pressure is still just a nudge
DEADLINE_BONUS: tuple[tuple[int, float], ...] = ((1, 0.18), (3, 0.12), (7, 0.06))
SUSTAINED_BONUS = 0.06                    #: past the minimum stretch
PROLONGED_BONUS = 0.12                    #: past twice the minimum stretch
#: Below `proactive_quiet_override_urgency` (0.95) on purpose: a goal deviation is never worth waking
#: him in quiet hours. It can interrupt a film; it cannot interrupt sleep.
URGENCY_CEILING = 0.94


@dataclass(frozen=True)
class Judgement:
    """One evaluated moment — the unit the log stores, voiced or not."""

    deviating: bool
    urgency: float
    reason: str                  #: why, in one line, naming the rung that fired
    category: str = ""
    run_minutes: float = 0.0
    goal_id: str = ""
    goal_text: str = ""
    days_until: int | None = None


def _days_until(deadline: str | None, now: datetime) -> int | None:
    """Whole days from `now` to an ISO date. None when absent or unparseable — never raises."""
    if not deadline:
        return None
    try:
        return (date.fromisoformat(str(deadline)[:10]) - now.date()).days
    except ValueError:
        return None


def judge(*, category: str, run_minutes: float, goals: list, now: datetime,
          min_minutes: int | None = None, deadline_days: int | None = None) -> Judgement:
    """Decide whether this moment is a deviation from a stated goal, and how urgent it is.

    Pure: no clock, no database, no settings lookup that is not overridable. All of 14.R4's behaviour
    lives here, so all of it is testable without a sqlite fixture or a running brain.

    `goals` is anything with `.text`, `.deadline` and `.id` — `world_model.Goal` in the live brain.
    """
    min_minutes = settings.goal_deviation_min_minutes if min_minutes is None else min_minutes
    deadline_days = (settings.goal_deviation_deadline_days if deadline_days is None
                     else deadline_days)

    if category not in DISCRETIONARY:
        return Judgement(False, 0.0, f"{category or 'unknown'} is not a discretionary category",
                         category=category, run_minutes=run_minutes)
    if run_minutes < min_minutes:
        return Judgement(False, 0.0,
                         f"{run_minutes:.0f}m of {category} is under the {min_minutes}m stretch",
                         category=category, run_minutes=run_minutes)

    # The nearest *pressing* deadline is what makes discretionary time a deviation rather than a
    # legitimate evening off. No deadline in the window -> he has earned it; say nothing.
    pressing = []
    for g in goals:
        d = _days_until(getattr(g, "deadline", None), now)
        if d is not None and 0 <= d <= deadline_days:
            pressing.append((d, g))
    if not pressing:
        return Judgement(False, 0.0,
                         f"{run_minutes:.0f}m of {category}, but no goal deadline inside "
                         f"{deadline_days}d", category=category, run_minutes=run_minutes)
    days, goal = min(pressing, key=lambda p: p[0])

    urgency = BASE_URGENCY
    rungs = [f"base {BASE_URGENCY:.2f}"]
    for limit, bonus in DEADLINE_BONUS:
        if days <= limit:
            urgency += bonus
            rungs.append(f"deadline in {days}d +{bonus:.2f}")
            break
    if run_minutes >= 2 * min_minutes:
        urgency += PROLONGED_BONUS
        rungs.append(f"{run_minutes:.0f}m sustained +{PROLONGED_BONUS:.2f}")
    elif run_minutes >= min_minutes:
        urgency += SUSTAINED_BONUS
        rungs.append(f"{run_minutes:.0f}m sustained +{SUSTAINED_BONUS:.2f}")
    urgency = round(min(urgency, URGENCY_CEILING), 4)

    return Judgement(True, urgency, " / ".join(rungs), category=category, run_minutes=run_minutes,
                     goal_id=getattr(goal, "id", ""), goal_text=getattr(goal, "text", ""),
                     days_until=days)


def _message(j: Judgement) -> str:
    when = ("today" if j.days_until == 0 else
            "tomorrow" if j.days_until == 1 else f"in {j.days_until} days")
    mins = int(j.run_minutes)
    return (f"Sir — that's {mins} minutes of {j.category} now, and '{j.goal_text}' is due {when}. "
            "Worth a push at it, or is tonight written off?")


def log_path() -> Path:
    return Path(settings.goal_deviation_log_path or (state_dir() / "goal_deviation_log.jsonl"))


#: Keep the log bounded without a scheduled job: trim on write once it passes this. A month of
#: 5-minute ticks in discretionary time is well inside it.
_MAX_LINES = 5000


def record(j: Judgement, *, emitted: bool, key: str = "", path: Path | None = None) -> None:
    """Append one judged moment. Fail-quiet: a log that cannot be written must not stop a tick.

    `emitted` is what this module knows at judgement time: whether it handed a signal to the engine.
    It is deliberately NOT called "voiced", because the source cannot know that — the engine decides,
    against busy state, quiet hours, the daily budget and the per-kind dismissal penalty, all after
    this function has returned. `confirm()` supplies the other half.
    """
    p = path or log_path()
    row = dict(asdict(j))
    row.update({"ts": datetime.now().isoformat(timespec="seconds"), "emitted": emitted, "key": key})
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        # ponytail: trim by rewrite, checked by line count. Fine to a few thousand lines; if this log
        # ever needs to hold a year, it wants sqlite, not a bigger constant.
        lines = p.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_LINES + 1000:
            p.write_text("\n".join(lines[-_MAX_LINES:]) + "\n", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"goal_deviation log skipped: {type(e).__name__}: {e}")


def confirm(key: str, path: Path | None = None) -> None:
    """Record that a signal was ACTUALLY interjected. Travels on `Signal.action`, which the engine
    runs only when it really speaks — the same mechanism that makes the conflict source's "I've paused
    it" truthful. Without this the log could not tell a voiced moment from a held one, because every
    deviation clears the base relevance threshold (BASE_URGENCY 0.62 > 0.60) and is therefore always
    emitted; *all* of this source's silence is decided engine-side, after `record()`.
    """
    p = path or log_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"voiced_key": key,
                                 "ts": datetime.now().isoformat(timespec="seconds")}) + "\n")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"goal_deviation confirm skipped: {type(e).__name__}: {e}")


def _rows(path: Path | None = None) -> list[dict]:
    try:
        return [json.loads(ln) for ln in (path or log_path()).read_text(
            encoding="utf-8").splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001
        return []


def held(path: Path | None = None, limit: int = 50) -> list[dict]:
    """The would-have-saids: moments judged a deviation that the owner never actually heard.

    A deviation is "held" when it was judged, handed over, and no `confirm()` followed — the engine
    dropped it for busyness, quiet hours, budget or an accumulated dismissal penalty. This is the
    review surface the owner's interrupt/silence preference gets read off (Jev 0.49 three times: it is
    his tolerance, not a system property) rather than guessed now. Fail-quiet.
    """
    rows = _rows(path)
    voiced = {r["voiced_key"] for r in rows if r.get("voiced_key")}
    return [r for r in rows
            if r.get("deviating") and r.get("key") not in voiced][-limit:]


def voiced(path: Path | None = None, limit: int = 50) -> list[dict]:
    """The other half: deviations he actually heard. Together with `held()`, the whole record."""
    rows = _rows(path)
    keys = {r["voiced_key"] for r in rows if r.get("voiced_key")}
    return [r for r in rows if r.get("deviating") and r.get("key") in keys][-limit:]


def _current_activity(now: float) -> tuple[str, float]:
    """(category, minutes in the current unbroken run of that category). ('', 0.0) when unknown.

    Its own walk rather than `continuous_active_minutes()`, which measures time at the screen
    regardless of what is on it — the one quantity that cannot tell a deviation from a goal being met.
    """
    from afon.brain.presence import PRESENCE, _category

    if not PRESENCE.enabled:
        return "", 0.0
    snap = PRESENCE.current()
    if snap is None or not PRESENCE._fresh(snap, now):
        return "", 0.0
    if snap.idle >= settings.presence_idle_threshold_seconds:
        return "", 0.0
    raw = _category(snap.app)
    category = raw
    if raw == "browsing":
        from afon.brain.interventions import _looks_like_media

        if _looks_like_media(snap.app, snap.title, raw):
            category = "media"
    try:
        poll = max(10, settings.presence_poll_seconds)
        idle_max = settings.presence_idle_threshold_seconds
        with PRESENCE._conn() as c:
            rows = c.execute("SELECT ts, app, idle FROM activity WHERE ts >= ? ORDER BY ts DESC",
                             (now - 12 * 3600,)).fetchall()
    except sqlite3.Error:
        return category, 0.0
    run_start, prev_ts = None, None
    for r in rows:
        ts, idle, app = r["ts"], (r["idle"] or 0), (r["app"] or "")
        # The run is a run of the SAME category, which is what makes elapsed time meaningful here.
        if idle >= idle_max or _category(app) != raw:
            break
        if prev_ts is not None and (prev_ts - ts) > 3 * poll:
            break
        run_start, prev_ts = ts, ts
    return category, 0.0 if run_start is None else max(0.0, (now - run_start) / 60.0)


async def goal_deviation_signals(now: datetime | None = None) -> list:
    """Proactive source (14.R4): one interruptible signal when discretionary time collides with a
    stated goal's deadline. Every evaluated moment is logged, voiced or not. ``now`` is injectable
    so the source-level gate does not decay with wall-clock time. Fail-quiet -> []."""
    from afon.brain.proactive import Signal

    if not settings.goal_deviation_enabled:
        return []
    try:
        category, run_minutes = _current_activity(time.time())
        if not category:
            return []
        from afon.brain.world_model import WORLD

        moment = now or datetime.now()
        j = judge(category=category, run_minutes=run_minutes, goals=WORLD.active_goals(), now=moment)
        key = f"goal-deviation-{j.goal_id}-{moment.date().isoformat()}-{int(j.urgency * 100)}"
        record(j, emitted=j.deviating, key=key if j.deviating else "")
        if not j.deviating:
            return []
        # The action is how the log learns what the engine decided: it runs only on a real
        # interjection, so an absent confirmation IS the record of a held moment.
        return [Signal(key=key, kind="goal-deviation", urgency=j.urgency, message=_message(j),
                       action=lambda: confirm(key))]
    except Exception as e:  # noqa: BLE001 — a broken source must never throw into the tick
        logger.debug(f"goal_deviation_signals skipped: {type(e).__name__}: {e}")
        return []
