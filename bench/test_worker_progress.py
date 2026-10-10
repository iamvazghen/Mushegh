"""The unattended worker's progress sentence — announce, then settle.

The claim: a tool call is only ever reported as *used* once it has actually
returned, and one that raised is reported as failed. The owner reads this line
and acts on it, so a step that did nothing must not read like a step that worked.

    uv run python bench/test_worker_progress.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from afon.brain.worker import progress_line  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> None:
    print("[1] a step that worked says what it used")
    check("single tool", progress_line(1, ["web_search"], []) == "step 1: used web_search")
    check("several tools", progress_line(2, ["vault", "notes"], []) == "step 2: used vault, notes")

    print("[2] a step that raised is reported as FAILED, never as used")
    line = progress_line(1, [], ["calendar"])
    check("failed is named", line == "step 1: failed calendar", line)
    check("and 'used' does not appear", "used" not in line, line)

    print("[3] a mixed step reports both, separately")
    line = progress_line(3, ["vault"], ["calendar"])
    check("both halves present", "used vault" in line and "failed calendar" in line, line)
    check("used comes first", line.index("used") < line.index("failed"), line)

    print("[4] an empty step does not invent a claim")
    line = progress_line(4, [], [])
    check("says nothing to report", line == "step 4: nothing to report", line)
    check("and does not say 'used'", "used" not in line, line)

    print("[5] the step number is always the caller's, never guessed")
    check("step 0", progress_line(0, ["x"], []).startswith("step 0:"))
    check("step 99", progress_line(99, ["x"], []).startswith("step 99:"))

    print(f"\n=== checks passed ===\n{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()