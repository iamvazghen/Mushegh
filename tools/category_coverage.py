"""Which categories can the scorecard actually measure, and which are excluded?

The whole-suite run excluded 9 categories as UNDERPOWERED — fewer runnable scenarios than
`MIN_RUNNABLE_PER_CATEGORY`. An excluded category contributes nothing to the overall, so
this is not a cosmetic line: it is a capability the production-readiness number is
structurally blind to.

The question worth separating is *why* each one is thin. A category with one scenario is
thin by design. A category losing scenarios to a credential declaration is the same class
of bug as `web_search`, `telegram` and `calendar`, and is worth another look.

Usage:
    python tools/category_coverage.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))

import behavioral_suite as bs  # noqa: E402


def main() -> int:
    cat: dict[str, dict[str, object]] = defaultdict(
        lambda: {"total": 0, "runnable": 0, "blocked": []}
    )
    for scenario in bs.scenarios():
        entry = cat[scenario.category]
        entry["total"] = int(entry["total"]) + 1
        if scenario.needs:
            missing = bs.missing_credentials(scenario.needs)
            if missing:
                cast = entry["blocked"]
                assert isinstance(cast, list)
                cast.append((scenario.id, missing))
                continue
        entry["runnable"] = int(entry["runnable"]) + 1

    floor = bs.MIN_RUNNABLE_PER_CATEGORY
    print(f"MIN_RUNNABLE_PER_CATEGORY = {floor}\n")
    header = f"  {'category':<24}{'total':>6}{'runnable':>9}   status"
    print(header)
    print("  " + "-" * (len(header) - 2))

    underpowered, blocked_total = [], 0
    for name, entry in sorted(cat.items()):
        runnable = int(entry["runnable"])
        ok = runnable >= floor
        status = "ok" if ok else "UNDERPOWERED"
        print(f"  {name:<24}{entry['total']:>6}{runnable:>9}   {status}")
        for sid, missing in entry["blocked"]:  # type: ignore[index]
            blocked_total += 1
            print(f"        credential-blocked: {sid}  needs {missing}")
        if not ok:
            underpowered.append(name)

    print()
    print(f"  categories: {len(cat)}   underpowered: {len(underpowered)}   "
          f"credential-blocked scenarios: {blocked_total}")
    if underpowered:
        print(f"  invisible to the overall: {', '.join(underpowered)}")
        print("  Each contributes nothing. Whether that is honest depends on why they are")
        print("  thin — a category with one scenario by design, or one losing scenarios to")
        print("  a declaration like the three already corrected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())