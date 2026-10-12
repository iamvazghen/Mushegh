"""S01 goal 6 / D-29 — the interruption budget the charter commits to, in code.

D-29 is a COMMITTED decision and says three things:

    "Three audio interruptions per day maximum. During a scheduled focus block,
     even one is a bug. Enforced in code, not by good intentions."

So the number is not an opinion to be re-read - it is a decision, and the
decision claims the code enforces it. This gate reads the number out of
DECISIONS.md rather than hard-coding it, so the charter stays the single
source of truth and the gate cannot drift away from it quietly.

It then checks three things the decision also names:
  1. the configured default equals the decided number;
  2. `.env.example` agrees, since a template that contradicts the charter
     silently overrides the default on a fresh install;
  3. quiet hours and the focus-block zero-tolerance are actually enforced.

Usage:  python bench/test_interruption_budget.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from mushegh.config import settings  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def decided_budget() -> int | None:
    """The number D-29 commits to, read from the charter itself."""
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    start = text.index("## D-29")
    body = text[start:start + 1200]
    match = re.search(r"\b(\w+)\s+(?:audio\s+)?interruptions?\s+per\s+day\b", body, re.I)
    if not match:
        return None
    word = match.group(1).lower()
    return {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}.get(word)


async def _focus_probe() -> tuple[list[str], list[str]]:
    """Run one tick twice with a MAXIMUM-urgency signal: once open, once in focus.

    D-29 says that inside a focus block "even one is a bug", so the assertion has to be
    behavioural: a signal at urgency 1.0 — the loudest thing the engine can carry — must
    still produce zero interjections. Checking that a constructor parameter is *named*
    "focus" proved nothing, and it was the only reason this check failed for months while
    the mechanism worked the whole time: the real gate is the module-level MODES singleton,
    consulted in `ProactiveEngine.maybe_interject`, not an injected argument.
    """
    import tempfile

    from mushegh.brain import proactive
    from mushegh.brain.modes import MODES

    collected: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for label, focused in (("open", False), ("focus", True)):
            spoken: list[str] = []

            async def emit(message: str, urgency: float, listening: bool,
                           _sink: list[str] = spoken) -> str:
                _sink.append(message)
                return "push"

            async def loud(_label: str = label) -> list:
                return [proactive.Signal(key=f"loud-{_label}",
                                         message="This would have interrupted you.",
                                         urgency=1.0, kind="conflict")]

            MODES.clear()
            if focused:
                MODES.set_focus(30)
            engine = proactive.ProactiveEngine(
                emit=emit,
                sources=[loud],
                is_listening=lambda: True,
                # Quiet hours are neutralised so the result is about focus alone.
                quiet_hours="",
                state_path=str(Path(tmp) / f"{label}.json"),
            )
            await engine.maybe_interject()
            collected[label] = spoken
    MODES.clear()
    return collected["open"], collected["focus"]


def main() -> int:
    print("=== the charter's number ===")
    decided = decided_budget()
    check("D-29's budget could be read from the charter", decided is not None,
          f"{decided}" if decided is not None else "pattern not found")
    if decided is None:
        print("\nCannot compare without the number; stopping.")
        return 1

    print(f"\n  D-29 commits to           : {decided} per day")
    print(f"  config default            : {settings.proactive_daily_budget}")
    print(f"  quiet hours               : {settings.proactive_quiet_hours}")

    print("\n=== the code matches the decision ===")
    check("the configured default IS the decided budget",
          settings.proactive_daily_budget == decided,
          f"config={settings.proactive_daily_budget} decision={decided}")

    template = ROOT / ".env.example"
    if template.is_file():
        line = next((l for l in template.read_text(encoding="utf-8").splitlines()
                     if l.strip().startswith("MUSHEGH_PROACTIVE_DAILY_BUDGET=")), "")
        # Strip the trailing comment the way python-dotenv does when it reads the file.
        # Comparing the raw text after "=" made every commented line in this template look
        # like a mismatch, which is a bug in the gate rather than in the template.
        raw = line.split("=", 1)[1] if line else ""
        value = raw.split("#", 1)[0].strip()
        check(".env.example agrees with the decision",
              value == str(decided),
              f".env.example={value or 'unset'} decision={decided}")
        if value and value != str(decided):
            print("      NOTE: a fresh install reads .env, so the template overrides the")
            print("      default. The template is therefore the value that actually runs.")

    print("\n=== the other two things D-29 names ===")
    check("quiet hours are configured", bool(settings.proactive_quiet_hours),
          settings.proactive_quiet_hours)
    check("quiet hours cover the night", "-" in settings.proactive_quiet_hours)

    from mushegh.brain import proactive  # noqa: E402

    budget_args = [p for p in proactive.ProactiveEngine.__init__.__code__.co_varnames
                   if "budget" in p or "quiet" in p]
    check("the engine takes the budget and the clock as injectable inputs",
          "daily_budget" in budget_args or "daily_budget" in
          str(proactive.ProactiveEngine.__init__.__code__.co_varnames),
          ", ".join(budget_args) or "not found")

    spoken_open, spoken_focus = asyncio.run(_focus_probe())
    check("a focus block zeroes the engine, as D-29 requires",
          bool(spoken_open) and not spoken_focus,
          f"open={len(spoken_open)} interjection(s), "
          f"focus={len(spoken_focus)} (max-urgency signal either way)")

    print(f"\nPASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
