"""Memory tools — Afon remembers and recalls across sessions (Phase 9, L1/L2).

`remember` writes a durable fact (he calls it when the owner says "remember that…", or on his own
when something is clearly worth keeping). `recall` searches what he's learned. `forget` removes a
fact. `read_journal` reads a day's continuity log. All back onto `brain/memory.py` (plain Markdown),
so they work offline and never crash the brain.
"""

from __future__ import annotations

from afon.brain.memory import STORE
from afon.brain.tools.base import missing_arg, tool_error
from afon.config import settings


def _arg(args: dict, *names: str) -> str:
    """First non-empty value among ``names``, joining a dict/list value into one string.

    Weak models get argument NAMES wrong far more often than they get intent wrong. Observed in
    production traces: ``recall({'entity': …, 'key': …})`` and ``recall({'text': …})`` where the
    schema says ``query``. The old code read only ``query``, found nothing, and returned the
    conversational string "What should I recall, sir?" — which the model then narrated back as its
    ANSWER. An independent audit scored several of those echoes as Afon failing to describe his own
    governance; the intent had been right every time and only the key was wrong.

    So: accept the obvious synonyms, and never let a missing argument produce a sentence that reads
    like a reply (see the callers, which now return a tool_error instead).
    """
    for n in names:
        v = args.get(n)
        if isinstance(v, dict):
            v = " ".join(str(x) for x in v.values() if x)
        elif isinstance(v, (list, tuple)):
            v = " ".join(str(x) for x in v if x)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


async def remember(args: dict) -> str:
    if not settings.memory_enabled:
        return "My long-term memory is switched off right now, sir."
    text = _arg(args, "text", "content", "note", "fact", "memory")
    if not text:
        return missing_arg("remember", args, "text", "content", "note", "fact", "memory", "tags",
                           ask="What would you like me to remember, sir?")
    tags = args.get("tags") or []
    if isinstance(tags, str):
        tags = [t for t in tags.replace(";", ",").split(",") if t.strip()]
    try:
        # He said it outright — nothing outranks that (30.F3).
        STORE.remember(text, tags=tags, source="owner")
        return "Noted, sir — I'll remember that."
    except Exception as e:  # noqa: BLE001
        return tool_error("remember", e)


async def recall(args: dict) -> str:
    """Cross-layer recall — searches L1 (learned) + L2 (journal) + L3 (vault) + L5 (semantic)."""
    if not settings.memory_enabled:
        return "My long-term memory is switched off right now, sir."
    query = _arg(args, "query", "text", "q", "topic", "entity", "key", "subject")
    if not query:
        # NOT a question. A tool that answers a bad call with "What should I recall, sir?" hands the
        # model a plausible sentence, and the model speaks it as the reply.
        return tool_error("recall", ValueError("no search text (expected a 'query' argument)"))
    layers = args.get("layers")  # optional: ['L1','L2','L3','L5'] to narrow
    try:
        # 30.F2: through the facade, not the store. This tool asked the L1/L2 store to fan out on
        # its behalf, which meant the open tasks — usually what "what's going on with X" means —
        # were not in the answer, and one slow layer could own the whole turn.
        from afon.brain.recall import recall as _recall_all
        hits = await _recall_all(query, limit=settings.memory_recall_limit,
                                 layers=tuple(layers) if layers else None)
        if not hits:
            return f"I don't have anything stored about '{query}', sir."
        tag = {"L1": "learned", "L2": "journal", "L3": "vault", "L5": "semantic",
               "L5b": "graph", "L4": "task"}
        lines = []
        for h in hits:
            layer = tag.get(h["layer"], h["layer"])
            text = h["text"].rstrip(".")
            lines.append(f"[{layer}] {text}.")
        return ("Here's what I remember across all layers: " + " ".join(lines))
    except Exception as e:  # noqa: BLE001
        return tool_error("recall", e)


async def forget(args: dict) -> str:
    if not settings.memory_enabled:
        return "My long-term memory is switched off right now, sir."
    # Deliberately NOT using _arg's synonym list here, unlike `recall`. This one DELETES. Guessing
    # which mistyped field held the owner's intent is fine when the worst case is an unhelpful
    # search; it is not fine when the worst case is dropping the wrong memory. A wrong key here
    # should fail loudly and let him say it again.
    query = (args.get("query") or "").strip()
    if not query:
        return tool_error("forget", ValueError("no target (expected a 'query' argument)"))
    try:
        # 37.F3 — every store, then a re-query. `STORE.forget` dropped ONE note and reported the
        # subject forgotten, leaving its siblings, its embedding, its graph relations and the
        # journal line that described it. A deletion that reports success on the strength of having
        # started is the failure this replaces.
        from afon.brain.forget import everywhere

        return everywhere(query).spoken()
    except Exception as e:  # noqa: BLE001
        return tool_error("forget", e)


#: Words for a day, resolved against the owner's clock rather than parsed as a date.
_WHEN_WORDS = {"today": 0, "yesterday": 1, "the day before yesterday": 2}


def _journal_date(text: str):
    """A date the owner named, or None. Accepts YYYY-MM-DD and the two words people actually say."""
    from datetime import datetime, timedelta

    t = (text or "").strip().lower()
    if not t:
        return None
    if t in _WHEN_WORDS:
        return datetime.now() - timedelta(days=_WHEN_WORDS[t])
    try:
        return datetime.strptime(t[:10], "%Y-%m-%d")
    except ValueError:
        return None


async def read_journal(args: dict) -> str:
    """07.R1 — by date, by topic, or the most recent.

    This used to ignore its arguments and always return the newest file, while its own description
    offered "what did we do yesterday". A tool that answers a different question from the one asked
    is worse than one that refuses: what comes back is a real journal entry, so nothing looks wrong.
    """
    if not settings.memory_enabled:
        return "My journal is switched off right now, sir."
    try:
        about = (args.get("about") or args.get("topic") or args.get("query") or "").strip()
        when_raw = (args.get("date") or args.get("when") or args.get("day") or "").strip()

        if when_raw:
            when = _journal_date(when_raw)
            if when is None:
                return (f"I can't read '{when_raw}' as a day, sir — give me a date like 2026-09-14, "
                        "or say today or yesterday.")
            text = STORE.read_journal(when)
            if not text:
                return f"Nothing in my journal for {when:%A %d %B}, sir."
            if not about:
                return text
            keep = [ln for ln in text.splitlines()
                    if ln.strip().startswith("- ") and about.lower() in ln.lower()]
            return ("\n".join(keep) if keep
                    else f"Nothing about '{about}' on {when:%A %d %B}, sir.")

        if about:
            hits = STORE.search_journal(about)
            if not hits:
                return (f"I have nothing in my journal about '{about}', sir. It may have been "
                        "before I started keeping one, or we never got to it.")
            return "\n".join(f"{d}: {line}" for d, line in hits)

        text = STORE.read_journal()
        return text or "My journal is empty so far, sir."
    except Exception as e:  # noqa: BLE001
        return tool_error("read journal", e)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Save a durable fact to long-term memory so you recall it in future sessions. "
                "Use when the owner says 'remember that…/note that…/for future', or proactively when "
                "you learn something clearly worth keeping (a preference, a person, a decision, an "
                "ongoing thread). Keep each fact short and self-contained."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The fact to remember, one sentence."},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional topic tags (e.g. 'preference', 'rabbit-farm').",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": (
                "Search across ALL memory layers — L1 learned facts, L2 journal entries, L3 vault "
                "notes, L5 semantic — for what you know about a topic or person. Use for "
                "'what do you know about X / did I tell you about Y / what did we do yesterday'. "
                "Each hit is tagged with its layer ([learned], [journal], [vault]) so the owner "
                "knows where it came from."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or person to recall."},
                    "layers": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["L1", "L2", "L3", "L5"]},
                        "description": "Optional: limit to specific layers (default = all).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            # Names the three tools that used to steal this call. "forget" is the owner's word for
            # four different erasures, and drop_objective even advertised 'forget X' as its trigger.
            "description": "Delete a remembered subject from long-term memory — every matching "
                           "fact, its embedding, its relations and the journal lines about it, "
                           "then verified by asking again (37.F3). Use for 'forget that I…', "
                           "'delete what you know about X'. Personal facts only — not macros "
                           "(delete_macro), objectives (drop_objective) or to-dos (delete_task).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Which fact to forget."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_journal",
            "description": (
                "Read the daily journal of past sessions. No arguments = the most recent day; "
                "`date` for a specific day ('2026-09-14', 'yesterday'); `about` to search every "
                "day for a topic. Use for 'what did we do yesterday', 'what have we said about "
                "the flat', 'remind me what we decided last week'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string",
                             "description": "A day: YYYY-MM-DD, 'today' or 'yesterday'."},
                    "about": {"type": "string",
                              "description": "A topic to search the journal for."},
                },
                "required": [],
            },
        },
    },
]

HANDLERS = {"remember": remember, "recall": recall, "forget": forget,
            "read_journal": read_journal}
