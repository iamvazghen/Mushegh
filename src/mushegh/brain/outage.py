"""02.E1 — a full outage must be AUDIBLE, and must be described accurately.

A full outage of the primary model and the first fallback is journalled (`llm.py` records
`agentic/llm_chain_exhausted` with every model's error attached) and the code beside it says what
the owner actually experiences: *"Mushegh going mute or apologising."* So the system knows the answer,
writes it down, and does not say it. That is what this module is for.

**The part that matters more than being audible is being ACCURATE.** The server used to answer every
failure with one sentence — "I'm having trouble reaching my reasoning right now" — and that sentence
is a claim about the models. It was also what the owner heard when a `KeyError` in a tool or a bug in
the router took the turn down. Two consequences, and the second is the serious one:

  * the owner was told to "give me a moment" for a bug that a moment will never fix, and
  * the owner was sent to look at the model chain when the fault was in Mushegh's own code.

A voice assistant that cannot tell those two apart is worse than a silent one, because it points the
person who is trying to fix it in the wrong direction at three in the morning. So every failure is
classified before a word is chosen, and the three cases get three different sentences:

  * **the models are down** — the chain is exhausted. Say that, and say the work will be there.
  * **one model went quiet** — a timeout that did not exhaust the chain.
  * **something in me broke** — anything else. This one says plainly that it is Mushegh's own fault and
    not the network, because that is the truth and because it is the sentence that sends the owner to
    the right log.

Pure and total: an exception in, a sentence out. No settings, no I/O, no model — so the mapping can
be checked exhaustively rather than trusted, which matters for the sentence that has to be right
when nothing else is.
"""

from __future__ import annotations

import asyncio

#: The three states a failed turn can be in. Named because the sentence is chosen from the name.
MODELS_DOWN = "models-down"
MODEL_QUIET = "model-quiet"
INTERNAL = "internal"

#: ChainExhausted is named rather than imported so this module stays importable when the LLM chain
#: itself cannot be built — which is exactly when it is needed.
_CHAIN_ERRORS = ("ChainExhausted",)
_TIMEOUTS = (asyncio.TimeoutError, TimeoutError)

_SENTENCES = {
    MODELS_DOWN: (
        "My reasoning chain is down, sir — every model refused. Nothing is lost: ask me again in a "
        "minute and I will pick it up where we left off."),
    MODEL_QUIET: (
        "The model went quiet on me, sir. I have logged it; try me once more."),
    INTERNAL: (
        "Something in me broke, sir — that is my own fault, not the network. It is written down, and "
        "I would rather tell you that than blame the connection."),
}


def classify(exc: BaseException) -> str:
    """Which of the three states this failure is. Total: anything unknown is INTERNAL.

    Unknown → INTERNAL is the safe direction, and deliberately so. A failure nobody has classified
    is far more likely to be a bug in Mushegh than an outage the code failed to recognise, and "I broke"
    sends the owner to the right log while "the models are down" sends him to the wrong one.
    """
    if isinstance(exc, _TIMEOUTS):
        return MODEL_QUIET
    if type(exc).__name__ in _CHAIN_ERRORS:
        return MODELS_DOWN
    return INTERNAL


def spoken_for(exc: BaseException) -> str:
    """The sentence the owner hears. Never raises — a broken classifier must not cost a sentence."""
    try:
        return _SENTENCES[classify(exc)]
    except Exception:  # noqa: BLE001
        return _SENTENCES[INTERNAL]
