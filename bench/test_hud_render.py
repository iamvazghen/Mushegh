"""P1.2 — the HUD page must render everything the brain sends it (hermetic, no network).

The defect this exists to prevent, found 2026-09-20: ``/hud.json`` emitted twelve top-level sections
and ``clients/hud/index.html`` rendered eight. ``loops``, ``turns_trace``, ``llm_providers`` and
``unattended`` were computed on every poll, serialised, sent over the wire — and dropped. The
``unattended`` section is the 45.F4 safety surface, so *the one safety addition that must exist
first* was invisible. No existing test caught it, because every HUD test asserts on the JSON.

So the gate is the **seam**, not either side of it:

  [1] every top-level key of ``hud_snapshot()`` is referenced by the page;
  [2] every element id the page's script reaches for exists in its markup (the same drift, mirrored);
  [3] the four formerly-dropped sections by name, so a regression reads as a regression;
  [4] the **value contracts** across the language boundary — a producer that changes the shape of a
      string the page parses (``"64/200"``) or the spelling of an outcome the page styles would
      otherwise silently draw nothing, which is the exact failure mode all over again.

    uv run python bench/test_hud_render.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Never charge the real autonomy ledger from a test (see governor._state_path).
os.environ.setdefault(
    "MUSHEGH_GOVERNOR_LEDGER", str(Path(tempfile.gettempdir()) / "mushegh-test-governor.json")
)

PAGE = ROOT / "clients/hud/index.html"

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class _Obj:
    text, project, updated = "ship it", "mushegh", "2026-09-20"
    progress: list = []
    deferred: list = []


class _Task:
    title, kind, last_progress = "indexing", "background", "half done"

    def human_elapsed(self) -> str:
        return "3m"


class _Appr:
    summary, origin = "send the email", "worker"


class _Src:
    """One stand-in for all four injectable sources."""

    def active(self):
        return [_Obj()]

    def pending(self):
        return [_Appr()]

    def current_line(self):
        return "at the desk"


class _Tasks(_Src):
    def active(self):
        return [_Task()]


def main() -> int:
    from mushegh.brain.hud import hud_snapshot

    page = PAGE.read_text(encoding="utf-8")
    src = _Src()
    snap = hud_snapshot(objectives=src, tasks=_Tasks(), approvals=src, presence=src)

    print("\n[1] THE GATE: every section the brain sends is referenced by the page")
    # A section is "referenced" if the script reads it off the payload. Matching `d.<key>` and
    # `d["<key>"]` only — a bare mention in a comment must not count, or the gate is decorative.
    missing = []
    for key in snap:
        if not re.search(rf"\bd\.{re.escape(key)}\b|d\[[\"']{re.escape(key)}[\"']\]", page):
            missing.append(key)
    check(f"all {len(snap)} top-level sections are read by the page",
          not missing, f"unrendered: {missing}")
    check("the snapshot is not trivially small (the gate would pass on an empty dict)",
          len(snap) >= 12, f"only {len(snap)} keys")

    print("\n[2] the mirror: every id the script reaches for exists in the markup")
    ids_used = set(re.findall(r'\$\(\s*"([A-Za-z0-9_-]+)"\s*\)', page))
    ids_declared = set(re.findall(r'id="([A-Za-z0-9_-]+)"', page))
    orphans = sorted(ids_used - ids_declared)
    check(f"all {len(ids_used)} script targets exist as elements", not orphans, f"orphans: {orphans}")
    check("and the page actually has ids to find", len(ids_declared) >= 10, str(len(ids_declared)))

    print("\n[3] the four sections that were being dropped, by name")
    for key in ("loops", "turns_trace", "llm_providers", "unattended"):
        check(f"`{key}` is rendered", bool(re.search(rf"\bd\.{key}\b", page)))

    print("\n[4] value contracts across the language boundary")
    u = snap["unattended"]
    check("unattended carries a budget block", isinstance(u.get("budget"), dict), str(u)[:120])
    # The page turns "64/200" into a bar with this regex. If hud.py ever changes that format the
    # bar silently vanishes, which is the same invisible-surface failure in a smaller shape.
    # `(?:\\.|[^/\\])*` and not `[^/]*`: the JS literal contains an escaped slash (`\/`), so a
    # naive character class stops halfway through the pattern it is trying to lift out.
    m = re.search(r"const m = /(\^(?:\\.|[^/\\])*\$)/\.exec", page)
    check("the page's budget-pair regex is findable", bool(m), "pattern moved or was renamed")
    if m:
        py = re.compile(m.group(1).replace(r"\/", "/"))
        for field in ("calls", "usd", "seconds"):
            val = str(u.get("budget", {}).get(field, ""))
            check(f"budget.{field}={val!r} parses with the page's own regex",
                  bool(py.match(val)), "the bar would render as nothing")
    # The page styles two outcome spellings specially; they must be spellings review.py can produce.
    from mushegh.brain.review import _OUTCOMES

    produced = set(_OUTCOMES.values())
    for styled in ("refused", "awaiting approval"):
        check(f"the page styles {styled!r}, and review.py can produce it",
              styled in produced, str(sorted(produced)))
    check("every outcome review.py can produce is displayable text",
          all(isinstance(v, str) and v for v in produced), str(sorted(produced)))

    print("\n[5] the page still degrades honestly")
    check("a missing brain is reported, not hidden", "Can't reach the brain" in page)
    check("the assistant name comes from the brain, not the markup",
          "d.assistant" in page and "WATARI · HUD" not in page,
          "a hardcoded name goes stale — this project has renamed twice")
    check("zero traced turns is shown as a warning, not as blank",
          re.search(r'metric\("Traced turns", 0, "warn"\)', page) is not None)
    check("a loop that never ran is a row, not an absence", "never_ran" in page)
    check("unpriced calls are flagged so spend reads as a floor", "unpriced_calls" in page)

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
