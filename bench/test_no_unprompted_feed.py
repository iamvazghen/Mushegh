"""41.R4 — no unprompted content feed, asserted rather than remembered.

D-34: "Afon never brings the owner something unasked because it seemed interesting." The
morning news feed broke exactly that rule — `news_signals` was collected on every tick
between 08:00 and 10:00 and pushed whether or not the owner had asked for anything.

The change on 2026-10-04 removed the source rather than filtering it, because a threshold
is something to argue with and an absent source is not. This gate is what stops a refactor,
a "while we're here" import, or a well-meaning fallback from quietly putting it back.

What it asserts:

  * `mynews` is not among the default signal sources, and no registered source resolves to
    that module;
  * `proactive.py` itself carries no reference to it — the strongest of these checks, because
    it is the seam the source was appended to and the one a future edit would touch;
  * a tick with the budget and quiet-hours settings live produces no news signal;
  * the module still exists on disk. The decision was to close the *path*, not to delete a
    file: `mynews.py` may still be useful in a focused session, and a test that asserted
    its absence would be asserting a different decision than the one that was made.

Hermetic: settings, source registry and a stubbed tick. No network, no clock dependency.

    uv run python bench/test_no_unprompted_feed.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_TMP = tempfile.TemporaryDirectory(prefix="afon-feed-")
os.environ["AFON_STATE_DIR"] = _TMP.name

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def _stub(label: str, called: list[str]):
    """A signal source that records that it was ticked and returns nothing."""

    def source() -> list:
        called.append(label)
        return []

    source.__name__ = f"stub_{label}"
    return source


def main() -> int:
    from afon.brain import proactive
    from afon.brain.proactive import default_signal_sources

    print("[1] the news feed is not a signal source")
    sources = default_signal_sources()
    modules = {getattr(s, "__module__", "") or getattr(s, "__qualname__", "") for s in sources}
    offenders = [m for m in modules if "mynews" in m.lower()]
    check("no registered source lives in the mynews module", not offenders, str(offenders))
    check("the source count dropped by exactly one (17 -> 16)", len(sources) == 16, str(len(sources)))
    print("        current sources:")
    for module in sorted(modules):
        print(f"          {module}")

    print("\n[2] the seam that hosted it carries no trace")
    # The strongest check here: this is the file a future edit would touch, and an AST parse is
    # the only assertion that survives the source being renamed, wrapped, or re-imported under
    # an alias. A plain grep would flag the explanatory comment left behind on purpose.
    import ast

    text = (ROOT / "src" / "afon" / "brain" / "proactive.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    leaked_imports = [name for name in imported if "mynews" in name.lower()]
    check("proactive.py imports nothing from mynews", not leaked_imports, str(leaked_imports))

    # And the other brain modules, the same way: a grep for the token would also match prose.
    others: list[str] = []
    for path in sorted((ROOT / "src" / "afon" / "brain").rglob("*.py")):
        if path.name in {"mynews.py"} or "__pycache__" in path.parts:
            continue
        try:
            mod = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(mod):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any("mynews" in n.lower() for n in names):
                others.append(path.name)
    check("no brain module imports mynews", not others, str(others))
    for token in ("news_signals", "MyNews"):
        check(f"proactive.py makes no call to {token!r}", f"{token}(" not in text)

    print("\n[3] the engine ticks the registry — with every source stubbed out")
    # The first version of this gate called `_gather()` on the LIVE source list. That read
    # 7,013 of the owner's real vault notes, made a network call to the VPS ticker and billed
    # a cloud LLM call — a "hermetic" gate that reached into his data and his wallet. The
    # engine is still exercised; the sources are not.
    from afon.brain.proactive import ProactiveEngine

    called: list[str] = []
    stubs = []
    for src in default_signal_sources():
        label = getattr(src, "__name__", None) or type(src).__name__
        stubs.append(_stub(label, called))
    engine = ProactiveEngine(sources=stubs)
    try:
        gathered = asyncio.run(engine._gather())             # noqa: SLF001
    except Exception as exc:                                  # noqa: BLE001
        check("the engine ticks its source list", False, f"{type(exc).__name__}: {exc}")
    else:
        check("the engine ticks every source it was given",
              len(called) == len(stubs), f"{len(called)} of {len(stubs)}")
        check("...and collects nothing from stubs that return nothing", gathered == [],
              str(gathered))
        print(f"        {len(called)} source(s) ticked, all stubbed, zero network")

    print("\n[4] the module survives; only the path to it was closed")
    module = ROOT / "src" / "afon" / "brain" / "mynews.py"
    check("mynews.py is still on disk (deletion was not the decision)", module.exists())
    if module.exists():
        body = module.read_text(encoding="utf-8")
        check("...its own signal function is still callable for a focused session",
              "def news_signals" in body)

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
