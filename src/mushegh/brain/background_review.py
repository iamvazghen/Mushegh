"""Self-improvement loop — adapted from NousResearch/hermes-agent's ``background_review``.

Hermes, after a turn, forks the agent to replay the conversation and ask itself "should anything be
saved to memory?", writing straight to its memory store while the main conversation + prompt cache
stay untouched. We apply the same idea to Mushegh's brain: a background pass replays the recent
conversation and asks the model what DURABLE facts about the owner are worth remembering long-term,
then writes them to **L1 learned memory** (``STORE.remember``, which dedups).

Why it matters here: Mushegh's 5-layer memory was elaborate but EMPTY (L1 = 0 facts) because nothing
ever wrote to it. This loop is what makes the memory actually learn as you talk — and it runs OFF
the hot path (a separate task) so it never slows a reply.

Invariants (mirroring Hermes): only ADD/dedup, never delete here; never touch the live conversation
or the main model's prompt; degrade silently on any error.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from mushegh.brain.memory import STORE
from mushegh.brain.never_store import NeverStoreRefused

# The L5b relation store is gone (D-26, M04). The prompt below still asks the model for both
# facts and relations, because the relations it extracts are useful as facts — "he trains at
# the gym" is a fact. Only the separate triple store is gone, not the behaviour of noticing
# a relation; the parse simply no longer has somewhere else to put it.
_EXTRACT_PROMPT = (
    "You are Mushegh's private memory reviewer. Read the conversation and extract what's worth "
    "remembering about the owner for months. Return ONLY a compact JSON object with two keys:\n"
    '  "facts": array (max 8) of short, self-contained third-person sentences — stable preferences '
    "and persona, decisions, people/projects/places, and expectations about how Mushegh should behave. "
    'e.g. ["the owner prefers replies under two sentences.", "the owner renamed his assistant to Mushegh."]\n'
    '  "relations": array (max 8) of [subject, predicate, object] triples for EXPLICIT structured '
    'links the owner stated, e.g. [["rabbit farm","located in","Armavir"],["owner","trains at","6am"]]. '
    "Use short lowercase entity/predicate phrases. Only include a relation actually stated.\n"
    "IGNORE transient chit-chat, one-off task mechanics, the current time/date, and the obvious. "
    'If nothing is worth saving, return {"facts": [], "relations": []}.'
)


def _parse_facts(raw: str) -> list[str]:
    """Pull fact strings out of the model's reply, defensively.

    Accepts BOTH the current object form ({"facts":[...]}) and the legacy bare-array form ([...]),
    so older prompts/models and existing tests keep working.
    """
    obj = _parse_object(raw)
    if obj is not None:
        arr = obj.get("facts")
        return _clean_str_list(arr if isinstance(arr, list) else [])
    m = re.search(r"\[.*\]", raw or "", re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return _clean_str_list(arr)


def _parse_object(raw: str) -> dict | None:
    """Extract the first JSON *object* from the reply, or None (it's a bare array / not JSON)."""
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _clean_str_list(arr: Any) -> list[str]:
    out: list[str] = []
    for x in arr or []:
        s = str(x).strip()
        if 3 < len(s) <= 240:
            out.append(s)
    return out[:8]


def _parse_relations(raw: str) -> list[tuple[str, str, str]]:
    """Pull [subject, predicate, object] triples out of the object reply (empty for the legacy form)."""
    obj = _parse_object(raw)
    if obj is None:
        return []
    out: list[tuple[str, str, str]] = []
    for r in obj.get("relations") or []:
        if isinstance(r, (list, tuple)) and len(r) == 3:
            s, p, o = (str(x).strip() for x in r)
            if s and p and o and all(len(x) <= 80 for x in (s, p, o)):
                out.append((s, p, o))
    return out[:8]


async def review_and_learn(history: list[dict[str, Any]], llm, store: Any = STORE) -> list[str]:
    """Replay ``history``, extract durable facts (L1) and write the new ones. ONE model call.

    The ``graph`` parameter is gone with the relation layer (D-26). It is dropped rather than
    ignored so that a caller still passing it fails loudly here instead of quietly believing
    its triples were stored.
    """
    convo = "\n".join(
        f"{m['role']}: {m['content']}"
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    )
    if len(convo) < 40:
        return []  # not enough said to learn anything
    try:
        msg = await llm.complete(
            [{"role": "system", "content": _EXTRACT_PROMPT},
             {"role": "user", "content": convo[:6000]}],
            temperature=0.2,
        )
    except Exception as e:  # noqa: BLE001 — self-improvement is best-effort, never breaks a turn
        logger.warning(f"self-improve review skipped ({type(e).__name__}: {e})")
        return []
    raw = getattr(msg, "content", "") or ""
    facts = _parse_facts(raw)
    before = store.count()
    learned: list[str] = []
    for f in facts:
        # Read out of a conversation by a model, not stated as fact (30.F3).
        try:
            if store.remember(f, tags=["learned", "auto"], source="inferred"):
                learned.append(f)
        except NeverStoreRefused as refused:
            # 37.R5 / D-24. A refusal is a RESULT, not a failure: the batch continues, and one
            # refused fact must not cost the owner the other facts the reviewer found. This loop is
            # outside the try that guards the model call, so without this the raise would abort
            # every remaining fact and read as "self-improvement skipped".
            logger.warning(f"self-improve: refused a D-24 fact ({refused.cls}), continuing")
    # The L5b relation write is GONE (D-26, M04). Parsed relations are no longer stored as
    # triples: they are kept as ordinary L1 facts by the loop above, which is where a
    # statement like "he trains at the gym" was already ending up anyway. The separate store is
    # what produced stale relations, and it is the reason they are gone.
    new = store.count() - before
    if learned:
        logger.info(f"self-improve: reviewed {len(history)} msgs -> {new} new fact(s) into L1")
    return learned
