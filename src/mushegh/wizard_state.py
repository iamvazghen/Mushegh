"""Wizard progress — so a half-finished setup can be finished, not restarted.

Without this, a setup wizard is only usable in one sitting. Someone gets to step
5, closes the laptop, and comes back to a blank form that cannot tell which of
their twenty answers it already has. The honest options are both bad: re-answer
everything, or hand-edit `.env` and hope.

So progress is written as it happens, not at the end. The file is small, lives
next to the rest of the state, and is written **atomically** — a temp file and a
replace — because the failure this guards against is a power cut mid-write
leaving a truncated JSON file that makes the next run refuse to start. A resume
feature that breaks on an unclean shutdown is worse than none.

The record is deliberately coarse: which steps completed, and when. It does NOT
store the answers, because those already live in `.env` and duplicating them
creates a second source of truth that will disagree with the first. `doctor`
reads `.env` for what is actually set; this file only says how far the wizard got.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE_VERSION = 1


def state_dir() -> Path:
    """Where progress lives. `mushegh.shared.paths` is the single owner of that answer.

    This used to carry its own copy — `settings.state_dir or Path.home() / ".mushegh"` — wrapped in
    a try/except so a broken config could not stop the wizard writing. That was a second answer to
    the same question, and second answers drift: it did not honour the same expanduser handling, and
    the gate that exists to keep one owner of the state root flagged it on 2026-10-10. A broken
    config is no longer survivable here, and it is not survivable anywhere else either — every other
    writer goes through the same helper.
    """
    from mushegh.shared.paths import state_dir as shared_state_dir

    return shared_state_dir()


def state_path() -> Path:
    return state_dir() / "wizard-state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict:
    """Read progress. A missing or corrupt file reads as "not started".

    Corrupt reads as not-started rather than raising: refusing to run would strand
    the user with a wizard they cannot get past and no way to clear it without
    finding and deleting a file by hand.
    """
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": STATE_VERSION, "completed": [], "started_at": None, "updated_at": None}
    if not isinstance(data, dict) or not isinstance(data.get("completed"), list):
        return {"version": STATE_VERSION, "completed": [], "started_at": None, "updated_at": None}
    return data


def save(data: dict) -> None:
    """Write progress atomically. Same-directory temp + os.replace."""
    path = state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".wizard-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
                handle.write("\n")
            os.replace(tmp, path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError:
        # Progress is a convenience, never a precondition. If the disk is read-only
        # the wizard must still be able to run to completion.
        pass


def completed() -> set[str]:
    return {str(x) for x in load().get("completed", [])}


def is_done(key: str) -> bool:
    return key in completed()


def mark_done(key: str) -> None:
    data = load()
    done = {str(x) for x in data.get("completed", [])}
    done.add(key)
    stamp = _now()
    save({
        "version": STATE_VERSION,
        "completed": sorted(done),
        "started_at": data.get("started_at") or stamp,
        "updated_at": stamp,
    })


def reset() -> None:
    """Forget progress. The `.env` answers are deliberately left alone."""
    save({"version": STATE_VERSION, "completed": [], "started_at": None, "updated_at": None})