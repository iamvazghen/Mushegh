"""One row per turn — what Mushegh decided, what it cost, and where the time went (SYSTEMS.md 01.F3).

Every tuning item in Wave 1 and half of Wave 2 is phrased as a number to beat: the 58-tool /
~10k-token prefill (03.F3), p50 to first audio (S01 budget), recall p95 (S30). None of those
numbers exist today. `METRICS` counts turns and tool calls in memory, and the brain restarts
daily, so the evidence for "which turns are expensive and why" was being thrown away every night.

A row carries exactly what 01.F3 names — intent class, tools considered, tools fired, prefill
tokens, wall clock per stage — and is written for **every** turn, including the ones that refuse
early, take the deterministic zero-arg fast path, or raise. That last part is the whole point: the
turns that end unusually are the ones worth seeing, and they are precisely the ones an
emit-on-success tracer drops. So the row is emitted from a `finally`, and `REQUIRED` below is the
contract a row must satisfy to count as complete.

Rows live in the current turn's context, so a helper deep in the tool path records into the right
turn without every signature growing a parameter. Fail-quiet throughout: a tracer that can break a
turn is worse than no tracer.

    from mushegh.brain.turn_trace import turn, current
    with turn("what's the weather?") as t:
        t.set_intent("lookup"); ...

ponytail: token counts are chars/4, not tiktoken. That is ±15% — plenty to watch 10k fall to 2.5k,
not enough to bill against. If 02.R1 (money per intent class) lands, swap `_tokens` for a real
encoder; nothing else here changes.
"""

from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from loguru import logger
from mushegh.shared.paths import state_dir

#: A row is COMPLETE only if it carries all of these. Each maps to something 01.F3 names:
#: intent class, tools considered (count + what they cost), tools fired, prefill tokens,
#: wall clock per stage. `test_metrics.py` asserts this mapping, so dropping a field from the
#: row fails the gate rather than quietly shrinking what the tuning work can see.
REQUIRED = ("ts", "intent", "tools_considered", "catalogue_tokens", "prefill_tokens",
            "tools_fired", "stages_ms", "total_ms", "ok")

#: The classes 01.R1 made explicit. "ambiguous" arrived with the classifier that can derive it
#: (`intent_router.classify`), and "emergency" was here all along in everything but name:
#: `agent.py` has always called `set_intent("emergency")`, and because the word was missing from
#: this tuple every one of those turns was silently coerced to "general". A vocabulary that
#: quietly rewrites what it is told is worse than a short one — the turns it loses are the ones
#: most worth counting.
#:
#: "general" stays, and means what it says: a turn that reached the tracer without reaching the
#: classifier. `turn_trace.classify` below mirrors `_prepare_turn`'s precedence rather than calling
#: `intent_router.classify`, because it answers from the signals the router has ALREADY computed
#: for the turn — no second parse, and `test_metrics.py` holds the two in step.
INTENTS = ("chat", "lookup", "act", "multi", "ambiguous", "emergency", "decision", "general", "refused")

#: Tool-name prefixes that CHANGE something. A narrowed turn is a lookup unless its one tool is
#: one of these. Deliberately the inverse of an allowlist of read verbs: most of the 142 tools are
#: reads named after their subject (`weather`, `crypto_price`, `now_playing`), so an allowlist has
#: to grow forever and mislabels every tool it has not met yet, while the set of verbs that mutate
#: the world is short and closed.
_WRITE_VERBS = frozenset({"add", "cancel", "complete", "create", "delete", "execute", "forget",
                          "invoke", "mark", "media", "move", "open", "play", "plan", "post",
                          "process", "remember", "remove", "run", "save", "schedule", "send",
                          "set", "stop", "update", "work", "write"})

KEEP_DAYS = 14

_RING: deque[dict] = deque(maxlen=200)
_LOCK = threading.Lock()
_CURRENT: contextvars.ContextVar["TurnTrace | None"] = contextvars.ContextVar(
    "mushegh_turn_trace", default=None)
_SCHEMA_TOKENS: dict[str, int] = {}
_pruned = False
_seq = 0


def trace_dir() -> Path:
    """Where rows land. Env-overridable so tests never write into the owner's real history."""
    return Path(os.environ.get("MUSHEGH_TRACE_DIR") or (state_dir() / "traces"))


def _tokens(text: str) -> int:
    return (len(text) + 3) // 4


def catalogue_tokens(tools: list[dict[str, Any]] | None) -> int:
    """Prefill cost of the presented tool catalogue — the number 03.F3 exists to drive down.

    Cached per tool name: the schemas are module-level constants that never change at runtime, and
    re-serialising ~58 of them on every turn would put JSON encoding in the latency path of the
    thing it is measuring.
    """
    if not tools:
        return 0
    total = 0
    for t in tools:
        try:
            name = t["function"]["name"]
        except (KeyError, TypeError):
            name = None
        if name is None:
            total += _tokens(json.dumps(t, separators=(",", ":"), default=str))
            continue
        cost = _SCHEMA_TOKENS.get(name)
        if cost is None:
            cost = _SCHEMA_TOKENS[name] = _tokens(json.dumps(t, separators=(",", ":"), default=str))
        total += cost
    return total


def message_tokens(messages: list[dict[str, Any]] | None) -> int:
    """Prefill cost of the message list. +4 per message for the role/delimiter framing every
    chat format adds."""
    if not messages:
        return 0
    total = 0
    for m in messages:
        c = m.get("content")
        total += 4 + _tokens(c if isinstance(c, str) else json.dumps(c, default=str))
    return total


def classify(*, pure_chat: bool = False, multi_intent: bool = False, work_intent: bool = False,
             ambiguous: bool = False, narrowed: bool = False,
             forced_name: str | None = None) -> str:
    """Name the turn from the signals the router already computed.

    Order mirrors `_prepare_turn`: a work intent takes precedence over the multi-intent nudge
    there, so it must here too, or the trace would disagree with the turn it describes.
    """
    if work_intent:
        return "act"
    if ambiguous:
        return "ambiguous"       # 01.R2 — a pointer with no antecedent is its own class
    if multi_intent:
        return "multi"
    if pure_chat:
        return "chat"
    if narrowed and forced_name:
        return "act" if forced_name.split("_", 1)[0] in _WRITE_VERBS else "lookup"
    return "general"


@dataclass
class TurnTrace:
    """One turn's row. Mutated as the turn proceeds; frozen into a dict when it closes."""

    text: str = ""
    streamed: bool = False
    intent: str = "general"
    language: str = ""
    tools_considered: int = 0
    catalogue_tokens: int = 0
    prefill_tokens: int = 0
    tools_fired: list[str] = field(default_factory=list)
    # 01.F2 / B06 — the same reply scored under both hypotheses, because only the
    # caller knows whether the question was unknowable. See note_answer.
    calibration_if_unknowable: str | None = None
    calibration_if_answerable: str | None = None
    # 01.E1 — one entry per clause of a compound request, so a failure can be
    # attributed to routing or to completion. See note_clause / clause_verdicts.
    clauses: list[dict[str, Any]] = field(default_factory=list)
    stages_ms: dict[str, float] = field(default_factory=dict)
    reached: list[str] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    #: 45.F3 — what the answer RESTED on, and how firmly it was put. The trace already knew which
    #: tools fired and how long each stage took, which answers "what did you do" and answers
    #: nothing about "should I believe it". Sources come from the turn's citation ledger; the
    #: confidence label is read off the reply itself rather than invented, because a number Mushegh
    #: made up about his own certainty is the least trustworthy thing in the row.
    sources: list[str] = field(default_factory=list)
    confidence: str = "unstated"
    #: 02.R1 — which model was charged, and for how much output. Money per intent class cannot be
    #: computed from the prefill alone, and attributing every turn to the PRIMARY model would be a
    #: lie on exactly the turns that cost most: a failover answers on a different, differently
    #: priced model, and those are the slow expensive ones worth seeing.
    model: str = ""
    answer_tokens: int = 0
    seq: int = 0
    #: 31.F5 - the correlation id this turn shares with the edge's logs, the pc agent's, the
    #: error journal and every audit line the turn writes. Minted on the edge when the user stops
    #: speaking and adopted by the brain, so ONE key retrieves every record of a turn that went
    #: wrong. Blank only for a turn that reached the tracer without going through a correlated
    #: entry point, which is itself worth seeing.
    #: ponytail: deliberately NOT added to REQUIRED. That tuple gates rows already on disk, and
    #: 285 historical rows could not have carried a field that did not exist - failing the honesty
    #: gate on them would say something false about history. `test_correlation_id.py` gates the
    #: field on newly emitted rows instead, which is the claim actually being made.
    turn_id: str = ""
    _t0: float = field(default_factory=time.perf_counter)

    def set_intent(self, intent: str) -> None:
        self.intent = intent if intent in INTENTS else "general"

    def note_prompt(self, messages: list[dict] | None, tools: list[dict] | None) -> None:
        """Record what the first model pass will actually be charged for."""
        self.tools_considered = len(tools or [])
        self.catalogue_tokens = catalogue_tokens(tools)
        self.prefill_tokens = message_tokens(messages) + self.catalogue_tokens

    def fired(self, name: str) -> None:
        if name:
            self.tools_fired.append(name)
            # 01.E1 / open question 1: a clause counts as satisfied only when the tool
            # IT was routed to actually fires. A clause that routed to nothing can
            # never be satisfied - it has no tool to fire - so it must not absorb a
            # neighbouring clause's firing, or every unattributed tool would make an
            # unrouted clause look handled.
            for clause in self.clauses:
                if clause["tool"] == name and not clause["fired"]:
                    clause["fired"] = True
                    clause["fired_by"] = name
                    break

    def note_clause(self, text: str, *, tool: str | None) -> None:
        """Record one clause and the tool routed to it — ONE entry per clause.

        ``clause_tools()`` is reached more than once per turn: ``classify()``
        asks for the plan, then ``_prepare_turn`` asks again. A plain append
        therefore recorded every clause twice, and because the second pass
        re-added them with ``fired`` reset, a clause that had already succeeded
        reappeared as a completion failure. That inflated the counts and made
        the attribution wrong in exactly the direction that hides a routing
        fault, so the entry is upserted by its text and the ``fired`` flag from
        an earlier pass is preserved.

        ``tool is None`` means the clause routed to nothing at all, which is the
        signature of a routing failure. Every clause is written down, planned or
        not, so an unrecorded clause is impossible and cannot look satisfied.
        """
        key = str(text)[:160]
        for existing in self.clauses:
            if existing["text"] == key:
                existing["tool"] = tool
                existing["planned"] = tool is not None
                return
        self.clauses.append({
            "text": key,
            "tool": tool,
            "planned": tool is not None,
            "fired": False,
            "fired_by": None,
        })

    def clause_verdicts(self) -> list[dict[str, Any]]:
        """Per-clause outcome. Read the third value before trusting the first.

        * ``satisfied`` — the tool THIS clause was routed to actually fired.
        * ``completion_failure`` — the clause was routed and its tool did not fire.
        * ``unrouted`` — **no route exists for this kind of clause at all.**

        ``unrouted`` is NOT a router mistake and must not be reported as one. It
        means `_ROUTES` and `_CLAUSE_ONLY_ROUTES` have nothing to match, so
        `clause_tools()` returns fewer than two tools, the turn never enters the
        compound path, and any tool that does fire was the model's own choice
        from the full catalogue rather than something the tracer planned. A
        clause in this state is therefore **unmeasurable**: the tracer can only
        attribute a firing to a clause it planned. Making it measurable means
        writing the route.
        """
        return [
            {
                "text": clause["text"],
                "tool": clause["tool"],
                "outcome": ("satisfied" if clause["fired"]
                            else "completion_failure" if clause["planned"]
                            else "unrouted"),
                "measurable": clause["planned"],
            }
            for clause in self.clauses
        ]

    def note_model(self, model: str) -> None:
        """02.R1 — the model that actually answered, recorded where the chain knows it."""
        if model:
            self.model = str(model)

    def note_answer(self, reply: str) -> None:
        """Close the row's account of WHY: what was read, how firmly it was put, and what it cost."""
        self.answer_tokens = _tokens(reply or "")
        try:
            from mushegh.shared.uncertainty import calibration, hedged

            self.confidence = "hedged" if hedged(reply or "") else "flat"
            # 01.F2 / B06 — the verdict under BOTH hypotheses. The tracer cannot know
            # whether the QUESTION was unknowable, and nothing in a confident wrong
            # answer looks different from a confident right one, so guessing here would
            # be the scorer grading its own opinion. Recording both makes the row
            # answerable later: a turn that is `overconfident` under unknowable=True is
            # a candidate flat answer, and `overhedged` under unknowable=False is a
            # candidate refusal of something answerable. Aggregating the persisted rows
            # is what turns B06's 59-60% into a per-turn number nobody has to re-run.
            self.calibration_if_unknowable = calibration(reply or "", unknowable=True)
            self.calibration_if_answerable = calibration(reply or "", unknowable=False)
        except Exception as e:  # noqa: BLE001 — an unlabelled turn is better than a lost one
            logger.debug(f"turn trace: confidence unavailable ({type(e).__name__})")
        try:
            from mushegh.brain import citations

            self.sources = sorted(citations.hosts())
        except Exception as e:  # noqa: BLE001
            logger.debug(f"turn trace: sources unavailable ({type(e).__name__})")

    def add_ms(self, stage: str, ms: float) -> None:
        """Accumulate, don't overwrite — the model stage runs once per tool-resolution pass, and a
        turn that took four passes is exactly the turn this is meant to expose."""
        self.stages_ms[stage] = round(self.stages_ms.get(stage, 0.0) + ms, 1)
        if stage not in self.reached:
            self.reached.append(stage)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        t = time.perf_counter()
        try:
            yield
        finally:
            self.add_ms(name, (time.perf_counter() - t) * 1000.0)

    def row(self) -> dict:
        return {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "seq": self.seq,
            "turn_id": self.turn_id,
            "intent": self.intent,
            "language": self.language,
            "streamed": self.streamed,
            "tools_considered": self.tools_considered,
            "catalogue_tokens": self.catalogue_tokens,
            "prefill_tokens": self.prefill_tokens,
            "tools_fired": list(self.tools_fired),
            # The outcome is written into the row, not left to be re-derived. Rows
            # persist to ~/.mushegh/traces/ and are read days later, by someone who
            # should not have to reconstruct the verdict by hand.
            "clauses": [
                {**clause,
                 "outcome": ("satisfied" if clause["fired"]
                             else "completion_failure" if clause["planned"]
                             else "unrouted")}
                for clause in self.clauses
            ],
            "sources": list(self.sources),
            "confidence": self.confidence,
            "calibration_if_unknowable": self.calibration_if_unknowable,
            "calibration_if_answerable": self.calibration_if_answerable,
            "model": self.model,
            "answer_tokens": self.answer_tokens,
            "stages_ms": dict(self.stages_ms),
            "reached": list(self.reached),
            "total_ms": round((time.perf_counter() - self._t0) * 1000.0, 1),
            "ok": self.ok,
            "error": self.error,
        }


def is_complete(row: dict) -> bool:
    """A row counts only if every field 01.F3 asks for is present and typed. `None` in any of them
    means the turn ended somewhere the tracer does not actually cover."""
    if any(k not in row or row[k] is None for k in REQUIRED):
        return False
    return (isinstance(row["tools_fired"], list) and isinstance(row["stages_ms"], dict)
            and row["intent"] in INTENTS)


def current() -> TurnTrace | None:
    """The turn being traced on this task, or None outside a turn."""
    return _CURRENT.get()


def fired(name: str) -> None:
    """Record a tool firing against the current turn, if there is one. Safe anywhere."""
    trace = current()
    if trace is not None:
        trace.fired(name)


def note_clause(text: str, *, tool: str | None) -> None:
    """Record one clause and its routed tool against the current turn. Safe anywhere."""
    trace = current()
    if trace is not None:
        trace.note_clause(text, tool=tool)


def clause_verdicts() -> list[dict[str, Any]]:
    """Per-clause outcomes for the current turn, or [] outside one."""
    trace = current()
    return trace.clause_verdicts() if trace is not None else []


def add_stage(name: str, ms: float) -> None:
    """Add already-measured milliseconds to a stage of the current turn. For callers that time
    themselves anyway — the LLM chain measures its own route latency across failovers, and
    re-timing it from outside would only produce a second, slightly different number."""
    t = _CURRENT.get()
    if t is not None:
        t.add_ms(name, ms)


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Time a stage of the current turn. A no-op outside a turn, so instrumented helpers stay
    callable from crons and tests."""
    t = _CURRENT.get()
    if t is None:
        yield
        return
    with t.stage(name):
        yield


@contextmanager
def turn(user_text: str = "", streamed: bool = False) -> Iterator[TurnTrace]:
    """Trace one turn. The row is emitted from `finally`, so a turn that refuses early, returns on
    the fast path, or raises still leaves evidence — those are the turns worth having."""
    global _seq
    with _LOCK:
        _seq += 1
        seq = _seq
    # 31.F5 - adopt whatever correlation id is already in flight on this task. `current_turn()`
    # returns the id the edge minted and the server adopted; outside a correlated entry point it
    # is blank, and a blank id is recorded as blank rather than invented, so an unjoinable turn
    # is visible as one.
    from mushegh.shared.errors import current_turn

    t = TurnTrace(text=user_text[:120], streamed=streamed, seq=seq,
                  turn_id=current_turn() or "")
    token = _CURRENT.set(t)
    try:
        yield t
    except BaseException as e:   # noqa: BLE001 — recorded, then re-raised untouched
        t.ok = False
        t.error = f"{type(e).__name__}: {e}"[:200]
        raise
    finally:
        try:
            _CURRENT.reset(token)
        except ValueError:
            # An abandoned async generator is closed by the event loop, in a different context
            # from the one that opened it, and the token will not reset there. The row still has
            # to be written — a barge-in is exactly the turn worth seeing.
            _CURRENT.set(None)
        _emit(t.row())


def last() -> dict | None:
    """The most recently CLOSED turn, or None. 45.F3 — "why" is a question about the one before."""
    with _LOCK:
        return dict(_RING[-1]) if _RING else None


def note_model(model: str) -> None:
    """02.R1 — record the answering model on the turn in flight, if there is one."""
    t = _CURRENT.get()
    if t is not None:
        t.note_model(model)


def note_answer(reply: str) -> None:
    """Record what the turn in flight actually answered. No-op outside a turn."""
    t = _CURRENT.get()
    if t is not None:
        t.note_answer(reply)


def _emit(row: dict) -> None:
    with _LOCK:
        _RING.append(row)
    try:
        _append(row)
    except Exception as e:  # noqa: BLE001 — a trace that can break a turn is worse than no trace
        logger.debug(f"turn trace not persisted: {type(e).__name__}: {e}")
    from mushegh.brain.metrics import METRICS
    METRICS.observe("turn_total_ms", row["total_ms"])
    METRICS.observe("turn_prefill_tokens", float(row["prefill_tokens"]))
    METRICS.incr(f"intent.{row['intent']}")
    # 02.R1 — the same breakdown /metrics already had for turn COUNTS, now for what they cost.
    METRICS.incr(f"prefill_tokens.{row['intent']}", int(row.get("prefill_tokens") or 0))
    METRICS.incr(f"answer_tokens.{row['intent']}", int(row.get("answer_tokens") or 0))


def _append(row: dict) -> None:
    global _pruned
    d = trace_dir()
    d.mkdir(parents=True, exist_ok=True)
    if not _pruned:
        _pruned = True
        _prune(d)
    path = d / f"turns-{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def _prune(d: Path) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for p in d.glob("turns-*.jsonl"):
        if p.stem[len("turns-"):] < cutoff:
            p.unlink(missing_ok=True)


def recent(n: int = 20) -> list[dict]:
    with _LOCK:
        return list(_RING)[-n:]


def summary(n: int = 50) -> dict:
    """What the HUD shows: are rows complete, and what do the last n turns cost?"""
    rows = recent(n)
    if not rows:
        return {"turns": 0, "complete": 0, "incomplete": 0}
    bad = [r for r in rows if not is_complete(r)]
    prefills = sorted(r["prefill_tokens"] for r in rows)
    totals = sorted(r["total_ms"] for r in rows)
    mid = lambda s: s[len(s) // 2]  # noqa: E731
    by_intent: dict[str, int] = {}
    for r in rows:
        by_intent[r["intent"]] = by_intent.get(r["intent"], 0) + 1
    return {
        "turns": len(rows),
        "complete": len(rows) - len(bad),
        "incomplete": len(bad),
        "p50_prefill_tokens": mid(prefills),
        "max_prefill_tokens": prefills[-1],
        "p50_total_ms": mid(totals),
        "by_intent": by_intent,
        "cost_by_intent": _cost_by_intent(rows),
        "failed": sum(1 for r in rows if not r["ok"]),
    }


def _cost_by_intent(rows: list[dict]) -> dict:
    """02.R1 — tokens and estimated money per intent class, for the HUD.

    Carries `priced_on` and `estimate` with the numbers rather than beside them: a dollar figure
    that travels without the date its price table was checked gets read as a fact.

    Fail-quiet: a HUD section is never worth losing the rest of the summary over.
    """
    try:
        from mushegh.brain.cost import PRICED_ON, by_intent as _by

        return {"estimate": True, "priced_on": PRICED_ON, "by_class": _by(rows)}
    except Exception as e:  # noqa: BLE001
        logger.debug(f"cost breakdown unavailable: {type(e).__name__}: {e}")
        return {}


def load(days: int = 3) -> list[dict]:
    """Rows from the last `days` files — the evidence 01.F3 asks to collect before tuning."""
    out: list[dict] = []
    d = trace_dir()
    if not d.is_dir():
        return out
    for p in sorted(d.glob("turns-*.jsonl"))[-days:]:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _selfcheck() -> None:
    """python -m mushegh.brain.turn_trace — the smallest thing that fails if the row contract breaks."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        os.environ["MUSHEGH_TRACE_DIR"] = td
        with turn("hello", streamed=False) as t:
            t.set_intent(classify(pure_chat=True))
            t.note_prompt([{"role": "user", "content": "hello"}], [])
            with t.stage("llm"):
                pass
        try:
            with turn("boom") as t:
                t.note_prompt([], [])
                raise ValueError("x")
        except ValueError:
            pass
        rows = load(1)
        assert len(rows) == 2, rows
        assert all(is_complete(r) for r in rows), rows
        assert rows[0]["intent"] == "chat"
        assert rows[1]["ok"] is False and "ValueError" in rows[1]["error"]
        assert current() is None
    os.environ.pop("MUSHEGH_TRACE_DIR", None)
    print("turn_trace selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
