"""Is the travel-destination fact actually gone from memory, and does cleanup remove it?

The probe showed `tools fired: []` on every run even after calling `bs._cleanup()` after
each turn. Two candidate causes:

  1. the fact was already in memory when run 1 started, and cleanup only runs afterwards
  2. `STORE.forget(query)` does not actually remove it, so the suite has been measuring a
     chain that short-circuits on memory and never reaches the tools

(2) would mean the suite's own "all tools fired" and this probe's "no tools fired" were
both true, and the difference is *when* they ran. That is worth knowing precisely.

Usage:
    python tools/check_memory_state.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT), str(ROOT / "bench"), str(ROOT / "src")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import behavioral_suite as bs  # noqa: E402


async def probe() -> None:
    store = bs.STORE

    async def contains(label: str) -> None:
        found = None
        for name in ("recall", "search", "get", "facts", "query"):
            fn = getattr(store, name, None)
            if fn is None:
                continue
            try:
                result = fn("travel destination")
            except TypeError:
                try:
                    result = fn()
                except Exception:  # noqa: BLE001
                    continue
            except Exception:  # noqa: BLE001
                continue
            found = result
            break
        print(f"  {label}: {found!r}" if found is not None else f"  {label}: <no probe fn>")

    print("memory store methods:", [a for a in dir(store) if not a.startswith("_")])
    print()
    await probe("before cleanup")
    await bs._cleanup()
    await probe("after  cleanup")


if __name__ == "__main__":
    asyncio.run(probe())