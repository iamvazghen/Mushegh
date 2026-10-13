"""errors.read() must not lose the window to a disordered file.

`read()` used to `break` at the first entry older than the cutoff, with the
comment "file is append-ordered, so everything older follows". That premise is
false for this repo's journal: entries carry the timestamp of whichever process
wrote them, the faked-clock gate appended dates in 2026 and 2028 straight into
the owner's live file, and rotation keeps a tail rather than a sorted one.

The cost was silent and total. errors.summary() reported 453 operations for a
week that actually held ~21,000 — and 31.R3's weekly self-report, whose whole
purpose is to say what went wrong, was reporting "157 of 355" on that basis.
A health view that under-reports by an order of magnitude is worse than none,
because it reads as reassurance.

This builds a deliberately disordered journal — newest, an old one, then more
new ones — and asserts the new ones are still returned. A test for the premise
rather than for the current file, so it holds whatever the journal looks like
tomorrow.

Hermetic: writes to a temp file, never the owner's.

    uv run python bench/test_error_journal_window.py
"""

from __future__ import annotations

import datetime
import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.shared import errors  # noqa: E402

passed = failed = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    # INSIDE the window queried below (60 minutes), not merely "recent".
    recent_ts = (now - datetime.timedelta(minutes=5)).isoformat()
    old_ts = (now - datetime.timedelta(days=400)).isoformat()

    tmp = Path(tempfile.mkdtemp()) / "errors.jsonl"
    # Newest, then ONE ancient entry, then more recent ones. Exactly the shape
    # that made the old `break` throw away everything after the first old line.
    rows = [
        {"ts": recent_ts, "subsystem": "a", "level": "OK", "message": "new-1"},
        {"ts": old_ts, "subsystem": "ancient", "level": "ERROR", "message": "old"},
        {"ts": recent_ts, "subsystem": "b", "level": "ERROR", "message": "new-2"},
        {"ts": recent_ts, "subsystem": "c", "level": "WARNING", "message": "new-3"},
        {"ts": old_ts, "subsystem": "ancient2", "level": "ERROR", "message": "old-2"},
        {"ts": recent_ts, "subsystem": "d", "level": "ERROR", "message": "new-4"},
    ]
    tmp.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    saved = errors.JOURNAL
    errors.JOURNAL = tmp
    try:
        window = errors.read(limit=1000, since_minutes=60, include_ok=True)
        got = sorted(str(e.get("message")) for e in window)
        check(got == ["new-1", "new-2", "new-3", "new-4"],
              "every in-window entry survives an out-of-order file", str(got))

        # The old entry must still be excluded — this is a window, not a scan.
        check(all("old" not in m for m in got),
              "entries outside the window are still excluded", str(got))

        # new-1 is OK; new-2 ERROR, new-3 WARNING, new-4 ERROR are not.
        fails = errors.read(limit=1000, since_minutes=60, include_ok=False)
        check(sorted(str(e.get("message")) for e in fails) == ["new-2", "new-3", "new-4"],
              "include_ok=False narrows rather than changing the window",
              str(sorted(str(e.get("message")) for e in fails)))

        # And a window that genuinely contains nothing must still be empty.
        none_in_window = errors.read(limit=1000, since_minutes=1, include_ok=True)
        check(none_in_window == [],
              "a window in the future is empty, not everything", str(len(none_in_window)))

        s = errors.summary(60)
        check(s["operations"] == 4,
              "summary() counts the whole window, not the first sorted-looking run",
              str(s["operations"]))
    finally:
        errors.JOURNAL = saved

    print(f"\n  {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())