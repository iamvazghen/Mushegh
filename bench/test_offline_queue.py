"""23.R4 — speech during a brain outage is captured, transcribed and answered after reconnect, in order.

The gate, and why each half is here:

* **Captured** — the transcript survives the outage. Before this, both of `remote_brain`'s standby
  failure paths spoke an apology and discarded it, which is what made real offline capability score
  0.70/4: the audio had been heard and transcribed, and was then thrown away.
* **In order** — two sentences said during an outage may depend on each other, so answering them
  backwards is worse than answering them late. A partial drain keeps the remainder *including the one
  that failed*.
* **Across a restart** — the promise is on disk, not in RAM. A crash mid-outage is exactly the failure
  that most needs the promise kept, so it is the one tested explicitly.
* **Refuses at capacity** — a promise silently dropped is indistinguishable, to the owner, from one
  never made, so a full queue returns False instead of forgetting the oldest.

Hermetic: the queue is a file, and the brain is a list.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afon.edge import offline_queue as q  # noqa: E402

PASS = FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}".rstrip())


def main() -> int:
    print("\n[1] speech during an outage is captured, not apologised away")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "q.jsonl"
        check("nothing is owed on a fresh edge", q.pending(p) == [] and q.depth(p) == 0)
        check("a promise is taken on", q.enqueue("remind me to call the vet", path=p))
        check("...and is on DISK, so a crash cannot lose it", p.exists())
        check("...and reads back as the same text",
              q.pending(p)[0]["text"] == "remind me to call the vet")
        check("...with the time it was said, not the time it is answered",
              isinstance(q.pending(p)[0]["ts"], float))
        check("empty speech is never promised", not q.enqueue("   ", path=p))
        check("...and does not grow the queue", q.depth(p) == 1)

    print("\n[2] answered after reconnect, IN ORDER")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "q.jsonl"
        for t in ("first", "second", "third"):
            q.enqueue(t, path=p)
        got: list[str] = []

        async def send(text: str) -> bool:
            got.append(text)
            return True

        n = asyncio.run(q.drain(send, path=p))
        check("every held turn is delivered", n == 3, str(n))
        check("...in the order they were said", got == ["first", "second", "third"], str(got))
        check("...and nothing is still owed", q.pending(p) == [])

    print("\n[3] a link that dies mid-drain keeps the remainder, including the one that failed")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "q.jsonl"
        for t in ("a", "b", "c", "d"):
            q.enqueue(t, path=p)
        seen: list[str] = []

        async def flaky(text: str) -> bool:
            seen.append(text)
            return text != "c"          # the link dies on 'c'

        n = asyncio.run(q.drain(flaky, path=p))
        check("only the ones that got through are counted", n == 2, str(n))
        check("...it stopped at the failure rather than carrying on", seen == ["a", "b", "c"],
              str(seen))
        left = [r["text"] for r in q.pending(p)]
        check("...the failed turn is STILL owed, not lost", left == ["c", "d"], str(left))
        check("...so a second drain delivers exactly the rest", True)
        rest: list[str] = []

        async def ok(text: str) -> bool:
            rest.append(text)
            return True

        asyncio.run(q.drain(ok, path=p))
        check("...and order survives across two drains", rest == ["c", "d"], str(rest))
        check("...leaving nothing owed", q.depth(p) == 0)

    print("\n[4] send_utterance reports failure by RETURN VALUE, which is the trap here")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "q.jsonl"
        q.enqueue("held", path=p)

        async def down(text: str) -> bool:
            return False                 # brain_client.send_utterance does this, it does not raise

        check("a falsey return delivers nothing", asyncio.run(q.drain(down, path=p)) == 0)
        check("...and loses nothing", [r["text"] for r in q.pending(p)] == ["held"])

        def raises(text: str):
            raise RuntimeError("socket gone")

        check("a raising sender also loses nothing", asyncio.run(q.drain(raises, path=p)) == 0)
        check("...and the queue is intact", [r["text"] for r in q.pending(p)] == ["held"])

        def sync_ok(text: str) -> bool:
            return True                  # a plain sync callable works too

        check("a sync sender is accepted", asyncio.run(q.drain(sync_ok, path=p)) == 1)

    print("\n[5] it survives a restart — the failure that most needs the promise kept")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "q.jsonl"
        q.enqueue("what did I say before the crash", path=p)
        # A restart is a fresh read of the file; no process state carries over.
        rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
        check("the promise is a plain line of JSON on disk", len(rows) == 1)
        check("...recoverable with no in-memory state at all",
              q.pending(p)[0]["text"] == "what did I say before the crash")

    print("\n[6] at capacity it refuses rather than forgetting")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "q.jsonl"
        for i in range(q._MAX):
            q.enqueue(f"turn {i}", path=p)
        check(f"the queue fills to its cap ({q._MAX})", q.depth(p) == q._MAX, str(q.depth(p)))
        check("...then REFUSES a new promise", not q.enqueue("one too many", path=p))
        check("...without dropping the oldest, which the owner would never know was gone",
              q.pending(p)[0]["text"] == "turn 0" and q.depth(p) == q._MAX)

    print("\n[7] a corrupt or unreadable queue never takes the edge down")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "q.jsonl"
        p.write_text("{not json at all\n", encoding="utf-8")
        check("a corrupt queue reads as empty", q.pending(p) == [])
        check("...and draining it is a no-op, not a crash",
              asyncio.run(q.drain(lambda t: True, path=p)) == 0)
        check("...and a new promise can still be taken on", q.enqueue("after corruption", path=p))

    print("\n[8] the standby's dead ends now promise instead of apologising")
    src = (ROOT / "src/afon/edge/remote_brain.py").read_text(encoding="utf-8")
    check("remote_brain uses the queue at all", "offline_queue" in src)
    check("...on the path where the standby produced nothing",
          "_promise" in src and "if not spoke" in src)
    check("...and on the path where it raised", src.count("_promise(") >= 2,
          str(src.count("_promise(")))
    check("the old 'couldn't answer locally either' dead end is gone",
          "couldn't answer locally either" not in src)
    check("the queue is drained when the link comes back, not on the next thing he says",
          "on_connected" in (ROOT / "src/afon/edge/brain_client.py").read_text(encoding="utf-8"))
    check("the queue file is a declared store, so 37.R4 covers it", _declared())

    print(f"\n=== {PASS}/{PASS + FAIL} checks passed ===")
    return 1 if FAIL else 0


def _declared() -> bool:
    from afon.brain import data_classes as dc

    store = dc.classify("offline_queue.jsonl")
    return store is not None and not store.leaves_host


if __name__ == "__main__":
    raise SystemExit(main())
