"""Does the suite's cleanup actually remove its own test facts?

`behavioral_suite._cleanup()` is:

    try:
        from mushegh.brain.memory import STORE
        for q in (...): STORE.forget(q)
    except Exception:
        pass

The bare `pass` means a failing forget is indistinguishable from a succeeding one. This
checks the two things that matters: whether `forget` raises, and whether the fact is
actually gone afterwards. A cleanup that silently does nothing would let every later run
short-circuit on memory and score a chain it never exercised.

Usage:
    python tools/check_cleanup_works.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT), str(ROOT / "bench"), str(ROOT / "src")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from mushegh.brain.memory import STORE  # noqa: E402

QUERIES = ("tea over coffee", "next travel destination", "capital of Japan", "London flight")


def facts_matching(needle: str) -> list[str]:
    """Everything the store holds that mentions the needle, whatever its accessor is."""
    out: list[str] = []
    for name in dir(STORE):
        if name.startswith("_"):
            continue
        fn = getattr(STORE, name)
        if not callable(fn):
            continue
        for args in ((needle,), ()):
            try:
                result = fn(*args)
            except Exception:  # noqa: BLE001
                continue
            if result is None:
                continue
            rows = result if isinstance(result, (list, tuple)) else [result]
            for row in rows:
                text = str(row)
                if needle in text or "tokyo" in text.lower() or "japan" in text.lower():
                    out.append(f"{name}{args}: {text[:160]}")
            break
    return out


async def main() -> int:
    print("store accessors tried:", [n for n in dir(STORE) if not n.startswith("_")][:10])
    print()
    before = facts_matching("travel destination")
    print(f"  before cleanup: {len(before)} matching entr(ies)")
    for line in before[:6]:
        print(f"    {line}")

    print("\n  calling STORE.forget for each cleanup query, reporting failures:")
    for q in QUERIES:
        try:
            STORE.forget(q)
            print(f"    forget({q!r}) -> ok")
        except Exception as exc:  # noqa: BLE001
            print(f"    forget({q!r}) -> RAISED {type(exc).__name__}: {exc}")

    after = facts_matching("travel destination")
    print(f"\n  after cleanup : {len(after)} matching entr(ies)")
    for line in after[:6]:
        print(f"    {line}")
    if after:
        print("\n  THE CLEANUP DID NOT REMOVE IT. The suite's `except Exception: pass` hides")
        print("  exactly this, so a run that short-circuits on stale memory looks like a")
        print("  brain failure rather than a broken fixture.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))