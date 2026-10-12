"""23.R2 — with no LLM reachable, still answer time, reminders and status.

The pair to `23.R4`. Real offline capability scored **0.70/4** — *barely: audio capture survives, but
nothing useful can be answered or done.* `23.R4` fixed the first half: nothing said during an outage is
lost. This fixes the second: some of it does not need to be *held* at all, because the answer never
needed a model.

**`shared/degraded.py` already promises this.** Its `brain-down` mode says, in the owner's own terms,
*"I can still hear you and answer simple things from here."* That was a **claim with no code behind
it** — the only locally-answerable turns were time and date, in `reflexes.py`. A declared mode that
overstates what is kept is worse than no mode at all, because it is the sentence he plans around.

Three answers, and the split from `reflexes.py` is deliberate:

* **Time / date** stay in `reflexes.py`. Those are answered *always*, because they are a latency win
  even when everything is healthy.
* **Status and reminders are answered only while degraded.** When the brain is up they must go to the
  brain, which knows strictly more — the live scheduler rather than a cached copy of it. Answering them
  locally in full health would be a downgrade disguised as a speed-up.

**Every cached answer states its age, out loud, without being asked.** A reminder list read back from
a cache taken forty minutes ago is not the same object as a live one, and this project's standing rule
is that a stale record costs more than no record because it is trusted. So the age is part of the
sentence, not a footnote — and when there is no cache at all, that is said plainly rather than
answered with silence or an invented empty list.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from loguru import logger

from mushegh.config import settings
from mushegh.shared import degraded
from mushegh.shared.paths import state_dir

#: How many upcoming reminders the brain sends and the edge will read back. Enough for "what's on
#: today", short enough to speak.
MAX_REMINDERS = 8


def cache_path() -> Path:
    return Path(settings.degraded_digest_path or (state_dir() / "degraded_digest.json"))


def save(reminders: list[dict], *, now: float | None = None, path: Path | None = None) -> bool:
    """Persist the brain's digest so it survives the outage AND an edge restart. Fail-quiet."""
    p = path or cache_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "generated": now if now is not None else time.time(),
            "reminders": reminders[:MAX_REMINDERS],
        }, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:  # noqa: BLE001
        logger.debug(f"degraded digest not saved ({type(e).__name__})")
        return False


def load(path: Path | None = None) -> dict | None:
    """The last digest the brain sent, or None. A corrupt cache is None, never a crash."""
    try:
        d = json.loads((path or cache_path()).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and "reminders" in d else None
    except FileNotFoundError:
        return None
    except Exception as e:  # noqa: BLE001
        logger.debug(f"degraded digest unreadable ({type(e).__name__})")
        return None


def _age_phrase(seconds: float) -> str:
    """How old the cached copy is, in words he would use. Never precise past the point of use."""
    if seconds < 90:
        return "a moment ago"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minutes ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'' if hours == 1 else 's'} ago"
    days = int(seconds // 86400)
    return f"{days} day{'' if days == 1 else 's'} ago"


# High-precision and anchored, exactly like reflexes.py: a question this cannot answer WELL must fall
# through to the standby (and then to 23.R4's queue) rather than be answered badly from a cache.
_WAKE = r"(?:hey\s+\w+[,\s]+)?"

_STATUS_RE = re.compile(
    rf"^\s*{_WAKE}(?:"
    r"(?:what(?:'?s| is)\s+)?(?:your\s+)?status(?:\s+report)?|"
    r"what(?:'?s| is)\s+(?:wrong|broken|down|up)|"
    r"what(?:'?s| is)\s+(?:still\s+)?working|"
    r"what\s+can\s+you\s+(?:still\s+)?do|"
    r"are\s+you\s+(?:ok|okay|alright|still\s+there)"
    r")\s*\??\s*$",
    re.IGNORECASE,
)

_REMINDERS_RE = re.compile(
    rf"^\s*{_WAKE}(?:"
    r"what\s+(?:are\s+)?my\s+reminders|"
    r"what(?:'?s| is)\s+on\s+(?:today|my\s+(?:day|calendar))|"
    r"what(?:'?s| is)\s+(?:coming\s+up|next|due)|"
    r"(?:do\s+i\s+have\s+)?any\s+reminders|"
    r"list\s+my\s+reminders|"
    r"what\s+have\s+i\s+got\s+(?:on|coming\s+up)"
    r")\s*\??\s*$",
    re.IGNORECASE,
)


def _status_answer(mode_name: str) -> str:
    mode = degraded.MATRIX.get(mode_name) or degraded.MATRIX[degraded.FULL]
    if not mode:                                    # Mode.__bool__ is False only for FULL
        return "Everything's working, sir — brain, network and this machine all reachable."
    return f"Right now, sir, I've lost {mode.lost}. I've still got {mode.kept}."


def _reminders_answer(digest: dict | None, now: float) -> str:
    if digest is None:
        return ("I can't reach the brain, sir, and I've no copy of your reminders from before the "
                "link dropped — so I genuinely don't know. I'll tell you the moment it's back.")
    rows = digest.get("reminders") or []
    age = _age_phrase(max(0.0, now - float(digest.get("generated") or now)))
    if not rows:
        return (f"Nothing was scheduled as of {age}, sir — though that's a cached copy, so anything "
                "set since then I won't have.")
    listed = "; ".join(f"{r.get('name') or 'a reminder'} at {r.get('next') or 'an unknown time'}"
                       for r in rows[:MAX_REMINDERS])
    return (f"From a copy taken {age}, sir — the brain's unreachable, so this may be out of date: "
            f"{listed}.")


def answer(text: str, *, mode_name: str, now: float | None = None,
           digest: dict | None = None, path: Path | None = None) -> str | None:
    """A locally-answerable question while degraded -> the spoken answer; else None.

    Returns None when the mode is FULL: with the brain reachable these questions belong to the brain,
    which has the live scheduler instead of a copy of it.
    """
    if mode_name == degraded.FULL:
        return None
    if _STATUS_RE.match(text or ""):
        return _status_answer(mode_name)
    if _REMINDERS_RE.match(text or ""):
        d = digest if digest is not None else load(path)
        return _reminders_answer(d, now if now is not None else time.time())
    return None
