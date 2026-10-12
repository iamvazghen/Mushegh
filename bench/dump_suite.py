"""Dump the suite's own shape for the docs site, so its numbers cannot go stale.

The docs site quoted "264 checks / 262 offline" by hand. Three times in one
session, adding a check made that sentence wrong again — each time it was caught
by reading the built HTML, not by any gate, because
`test_website_claims.py` checks that cited PATHS exist and cited SETTINGS are
real, and says nothing about arithmetic. A number typed into prose is not a
contract; this is the same arrangement the tool page already uses via
`bench/dump_tools.py`, applied to the figure that has actually drifted.

    uv run python bench/dump_suite.py > website/app/suite.generated.json

Prints UTF-8 JSON on stdout. Redirect it in a POSIX shell or write the bytes
from Python -- PowerShell's `>` emits UTF-16 with a BOM and `import` will choke.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "bench" / "run_all_tests.py"


def load_tests() -> list[tuple]:
    spec = importlib.util.spec_from_file_location("run_all_tests_under_dump", RUNNER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return list(module.TESTS)


def main() -> None:
    tests = load_tests()
    by_tag = Counter(t[2] for t in tests)
    scripts = {t[1] for t in tests}
    bench_tests = sorted(p.name for p in (ROOT / "bench").glob("test_*.py"))

    payload = {
        "checks": len(tests),
        "scripts": len(scripts),
        "by_tag": dict(sorted(by_tag.items())),
        "offline": by_tag.get("offline", 0),
        "network": by_tag.get("network", 0),
        "test_files_on_disk": len(bench_tests),
    }
    sys.stdout.write(json.dumps(payload, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()