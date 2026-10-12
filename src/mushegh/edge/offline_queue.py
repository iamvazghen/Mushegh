"""23.R4 — promises kept across an outage: capture, transcribe locally, answer when the brain returns.

Real offline capability scored **0.70/4** in the Jev evaluation — *barely: audio capture survives, but
nothing useful can be answered or done* — and the fix is p = 0.92, conf 0.90, one of the strongest
mandates in the whole plan. This is *"a promise correction as much as a feature"*, which is exactly
what the old behaviour got wrong.

**What actually happened before this module.** The edge already degrades twice: if the VPS brain is
unreachable, `remote_brain._route_utterance` answers on a **local standby agent** instead. But that
standby is an `MusheghAgent`, and its model comes from a remote proxy — so when the *network* is down
rather than just the brain, the standby cannot answer either. Both of its failure paths ended the same
way: Mushegh spoke an apology (*"I couldn't answer locally either"*) and **the transcript was discarded.**
The speech had been heard and transcribed, and was then thrown away. That is the 0.70/4.

So the queue is deliberately a queue of **text, not audio**: the transcription already happened
locally, which is the half that was working. Queuing audio would re-do work that succeeded and store
far more sensitive material to boot.

**Durable on disk, not in memory** — unlike `brain_client`'s error spool, which is in-memory by
design because it runs inside a logging sink and the journal is already the durable copy. A promise has
the opposite requirement: an edge restart during an outage must not silently break it. If these
survived only in RAM, the one failure that most needs the promise (a crash) is the one that loses it.

**At capacity it refuses rather than forgets.** `_MAX` is a hard stop that returns False, so the caller
can say it cannot hold any more. Dropping the oldest promise would be worse than declining a new one:
a promise silently discarded is indistinguishable, to the owner, from one that was never made.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from mushegh.config import settings
from mushegh.shared.paths import state_dir

#: A hard stop, not a ring buffer. See the module docstring: at capacity this refuses.
_MAX = 200


def queue_path() -> Path:
    return Path(settings.offline_queue_path or (state_dir() / "offline_queue.jsonl"))


def _read(path: Path | None = None) -> list[dict]:
    try:
        return [json.loads(ln) for ln in (path or queue_path()).read_text(
            encoding="utf-8").splitlines() if ln.strip()]
    except FileNotFoundError:
        return []
    except Exception as e:  # noqa: BLE001 — a corrupt queue must not take the edge down with it
        logger.warning(f"offline queue unreadable ({type(e).__name__}); treating as empty")
        return []


def _write(rows: list[dict], path: Path | None = None) -> None:
    p = path or queue_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    tmp = p.with_suffix(p.suffix + ".tmp")
    # Rewrite via a temp file: a half-written queue read back after a crash mid-drain would either
    # lose promises or replay them twice, and both are worse than the extra write.
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(p)


def pending(path: Path | None = None) -> list[dict]:
    """Everything still owed, oldest first."""
    return _read(path)


def depth(path: Path | None = None) -> int:
    return len(_read(path))


def enqueue(text: str, *, ts: float | None = None, path: Path | None = None) -> bool:
    """Take on a promise to answer `text` later. False means it was NOT taken on — say so out loud.

    Returns False for empty text and when the queue is full, and those are different situations the
    caller may want to phrase differently; `depth()` distinguishes them.
    """
    text = (text or "").strip()
    if not text:
        return False
    rows = _read(path)
    if len(rows) >= _MAX:
        logger.warning(f"offline queue full at {len(rows)}; refusing to promise {text[:40]!r}")
        return False
    rows.append({"text": text, "ts": ts if ts is not None else time.time()})
    try:
        _write(rows, path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"offline queue write failed ({type(e).__name__}); promise NOT taken on")
        return False
    return True


async def drain(send: Callable[[str], Any | Awaitable[Any]], path: Path | None = None) -> int:
    """Answer what is owed, **in order**, and return how many were handed over.

    `send` is awaited if it returns an awaitable and must report success as a truthy value —
    `brain_client.send_utterance` returns False rather than raising when the link is down, so a
    try/except here would look correct and silently drop the remainder of the queue.

    Stops at the first failure and keeps everything from that point on, including the one that failed.
    Order is the property that matters: two sentences spoken during an outage may depend on each
    other, and answering them backwards is worse than answering them late.
    """
    rows = _read(path)
    if not rows:
        return 0
    sent = 0
    for row in rows:
        ok = False
        try:
            result = send(row["text"])
            ok = bool(await result if hasattr(result, "__await__") else result)
        except Exception as e:  # noqa: BLE001 — belt and braces; a drain must never raise into a turn
            logger.warning(f"offline queue drain stopped ({type(e).__name__})")
            ok = False
        if not ok:
            break
        sent += 1
    remaining = rows[sent:]
    try:
        _write(remaining, path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"offline queue could not be trimmed ({type(e).__name__})")
    if sent:
        logger.info(f"offline queue: delivered {sent} held turn(s), {len(remaining)} still owed")
    return sent
