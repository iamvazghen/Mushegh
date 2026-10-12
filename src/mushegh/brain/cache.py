"""Mushegh's L4 hot-cache — front the slow paths so repeated questions are near-instant.

One tier: a small bounded in-process TTL cache. Costs nothing, needs no service, and makes a
repeated lookup inside one session essentially free.

**There used to be a second tier (Redis/Valkey) and it was dropped on 2026-09-20** — O3.2, Jev
p = 0.98, conf 0.96, the most one-sided technology verdict in the evaluation: *three of four uses
are better served without it, Postgres covers the fourth, and a second daemon on a host that has
OOMed is not earned by one use case.* Two things made it clear-cut rather than a judgement call:
``redis_url`` defaulted to ``None``, so the tier had never actually run in this deployment; and the
VPS OOMed on a single extra worker in 2026-08. A cross-process cache that is never enabled is not
resilience — it is an unexecuted code path sitting in the read path of every cached tool.

If a shared, restart-surviving cache is ever genuinely wanted, it goes in Postgres — already the
only datastore the brain speaks to — not in a new daemon.

Everything still degrades: a miss, or any error at all, runs the caller's real function as if no
cache existed. The cache is therefore *never* a source of failure, only of speed.

Usage (see ``tools/utility.py`` and ``tools/web.py``):

    from mushegh.brain.cache import CACHE
    val = await CACHE.cached("weather", key=f"{lat},{lon}", ttl=600, factory=lambda: _fetch())
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Awaitable, Callable


class _InProcessTTL:
    """A tiny bounded TTL cache. Newest-used kept; oldest evicted past ``max_items``."""

    def __init__(self, max_items: int = 512) -> None:
        self._max = max_items
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < time.time():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)  # mark as recently used
        return value

    def set(self, key: str, value: str, ttl: int) -> None:
        self._data[key] = (time.time() + ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)  # evict least-recently-used

    def clear(self) -> None:
        self._data.clear()


class Cache:
    """L4 hot-cache: in-process, async, fail-open."""

    def __init__(self) -> None:
        self._local = _InProcessTTL()

    @property
    def backend(self) -> str:
        """Always ``"memory"``. Kept as a property rather than deleted because self-health reports it
        (``health.py``), and naming the backend stays useful even when there is only one: "memory" is
        the answer to "where is the cache", not a placeholder for a missing one."""
        return "memory"

    @staticmethod
    def _k(namespace: str, key: str) -> str:
        return f"mushegh:{namespace}:{key}"

    async def get(self, namespace: str, key: str) -> str | None:
        return self._local.get(self._k(namespace, key))

    async def set(self, namespace: str, key: str, value: str, ttl: int) -> None:
        self._local.set(self._k(namespace, key), value, ttl)

    async def cached(
        self,
        namespace: str,
        key: str,
        ttl: int,
        factory: Callable[[], Awaitable[str]],
    ) -> str:
        """Return the cached value for (namespace, key), or run ``factory`` and cache its result.

        A blank/falsey factory result is NOT cached (don't pin transient errors or empties).
        Any cache error falls through to a plain ``factory()`` call — caching never blocks work.
        """
        try:
            hit = await self.get(namespace, key)
            if hit is not None:
                return hit
        except Exception:  # noqa: BLE001 — fail open: behave as a cache miss
            pass
        value = await factory()
        if value:
            try:
                await self.set(namespace, key, value, ttl)
            except Exception:  # noqa: BLE001
                pass
        return value

    def clear(self) -> None:
        """Drop everything (used by tests)."""
        self._local.clear()


# Process-wide cache used by tools.
CACHE = Cache()
