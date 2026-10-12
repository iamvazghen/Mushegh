"""The eighteen agents, their eighty-three domains, and how Mushegh addresses each one.

Mushegh used to delegate to a single team lead called ``ispir``, who re-read the brief and
chose a specialist himself. That agent does not exist any more — the eight-agent fleet it
belonged to was deleted on 2026-10-08 — and the fleet that replaced it has no router at all.
Eighteen agents each own a named slice of the work, exclusively: one owner per domain, across
two frameworks. So the choice of specialist moved *here*, into Mushegh, and this module is
the whole of what he knows about who does what.

**One source of truth, and it is not this file.** The roster is defined in the vault at
``20-Agents/fleet18.json``, which is what the agents themselves read. ``fleet18.json`` beside
this module is a generated copy so routing still works on a laptop with no vault mounted;
``scripts/sync_fleet_roster.py`` regenerates it, and :func:`drift` reports a disagreement
rather than letting the stale copy win quietly. A stale roster costs more than no roster,
because it is trusted.

**Two frameworks mean two transports, and the roster is where that is recorded.** Nine agents
run under the OpenClaw gateway and speak A2A; nine run as Hermes profiles and do not. Callers
ask :func:`transport` rather than hardcoding a list, because the split is a fact about the
fleet and not about the code.

    uv run python bench/test_roster.py
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_PACKAGED = Path(__file__).with_name("fleet18.json")

#: How an agent is reached. ``a2a`` is the Agent2Agent JSON-RPC channel on the OpenClaw
#: gateway; ``hermes`` is the ``hermes -z`` one-shot CLI against that agent's profile home.
#: Derived from the roster's own ``host`` field, never from a list kept somewhere else.
_TRANSPORT_BY_HOST = {"openclaw": "a2a", "hermes": "hermes"}


class UnknownAgent(KeyError):
    """A name that is not one of the eighteen. Raised instead of guessing the nearest match."""


@lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    data = json.loads(_PACKAGED.read_text(encoding="utf-8"))
    agents = data.get("agents", data)
    if len(agents) != 18:
        raise ValueError(f"{_PACKAGED} holds {len(agents)} agents, not 18")
    return agents


def agents() -> dict[str, dict]:
    """The full roster, keyed by agent id (``gagas``, ``goharik``, ...)."""
    return _load()


def names() -> list[str]:
    """The eighteen ids, in roster order (A01..A18)."""
    return sorted(_load(), key=lambda n: _load()[n]["agent_id"])


def resolve(name: str) -> dict:
    """One agent's row, or :class:`UnknownAgent`.

    Deliberately strict. The failure this prevents is the one the old router had in a different
    form: a brief addressed to a name nobody recognised going to "the nearest thing", which is
    how a legal question reaches the media agent.
    """
    key = (name or "").strip().lower()
    row = _load().get(key)
    if row is None:
        raise UnknownAgent(f"{name!r} is not one of the eighteen agents: {', '.join(names())}")
    return row


def transport(name: str) -> str:
    """``"a2a"`` or ``"hermes"`` — which channel reaches this agent."""
    host = resolve(name)["host"]
    try:
        return _TRANSPORT_BY_HOST[host]
    except KeyError:  # a roster that grew a third framework should stop, not improvise
        raise UnknownAgent(f"agent {name!r} declares host {host!r}, which has no transport") from None


def domains(name: str) -> list[dict]:
    """The utilities (domains) this agent owns: ``id``, ``title``, ``connections``, ``skill``."""
    return list(resolve(name).get("utilities", []))


def owner_of(utility_id: int) -> str:
    """Which agent owns domain *n*. One owner each, which is why this can return a single name."""
    for name, row in _load().items():
        for util in row.get("utilities", []):
            if int(util.get("id", -1)) == int(utility_id):
                return name
    raise UnknownAgent(f"no agent owns domain {utility_id}")


def directory() -> str:
    """The eighteen agents and their domains as one compact block, for the tool description.

    Short on purpose: it is charged against the system prompt's token budget on every turn that
    exposes the delegation tool. The *titles* of the eighty-three domains are an order of
    magnitude longer and are fetched per agent through :func:`domains` when a brief needs them.
    """
    rows = _load()
    return "\n".join(
        f"{n} — {rows[n]['domain']} ({len(rows[n].get('utilities', []))} domains)"
        for n in names()
    )


def suggest(task: str, limit: int = 3) -> list[str]:
    """Candidate agents for a free-text brief, best first, by word overlap with their domains.

    Code produces the list and the model may only narrow it — the same shape the executor
    contract uses for choosing a coding CLI. This is deliberately a word count and not a
    model: it costs nothing, it is explainable at 2 AM, and the caller already has a model.

    ponytail: bag-of-words over domain + utility titles. Embeddings if it misroutes in practice.
    """
    words = {w for w in _tokens(task) if len(w) > 3}
    if not words:
        return []
    scored: list[tuple[int, str]] = []
    for name, row in _load().items():
        hay = {name, *_tokens(row["domain"]), *_tokens(row.get("reason", ""))}
        for util in row.get("utilities", []):
            hay |= _tokens(util.get("title", "")) | _tokens(util.get("connections", ""))
        hit = len(words & hay)
        if hit:
            scored.append((hit, name))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [n for _, n in scored[:limit]]


def _tokens(text: str) -> set[str]:
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split() if w}


def drift() -> str:
    """Compare the packaged copy with the vault's canonical roster. ``""`` when they agree.

    Returns a sentence when they differ and when the vault is simply not mounted, because
    "could not check" and "checked and matched" are different states and only one of them
    justifies trusting the copy.
    """
    from mushegh.config import settings

    root = settings.vault_path or os.environ.get("MUSHEGH_VAULT_PATH")
    if not root:
        return "vault path not configured, so the packaged roster could not be checked"
    src = Path(root) / "20-Agents" / "fleet18.json"
    try:
        canonical = json.loads(src.read_text(encoding="utf-8"))
    except OSError:
        return f"vault roster unreadable at {src}, so the packaged roster could not be checked"
    if canonical == _load():
        return ""
    return (
        f"the packaged roster disagrees with {src}; "
        "run scripts/sync_fleet_roster.py — the vault's copy is the authority"
    )


def demo() -> None:
    """uv run python -c 'from mushegh.brain.roster import demo; demo()'"""
    assert len(names()) == 18, names()
    assert sum(len(domains(n)) for n in names()) == 83
    # One owner each: no domain id appears under two agents.
    seen: dict[int, str] = {}
    for n in names():
        for util in domains(n):
            uid = int(util["id"])
            assert uid not in seen, f"domain {uid} owned by both {seen[uid]} and {n}"
            seen[uid] = n
    assert len([n for n in names() if transport(n) == "a2a"]) == 9
    assert len([n for n in names() if transport(n) == "hermes"]) == 9
    assert owner_of(13) == "arsen", owner_of(13)
    assert "zara" in suggest("review our security posture for a credential leak")
    try:
        resolve("ispir")
    except UnknownAgent:
        pass
    else:  # the deleted router must not resolve to the nearest thing
        raise AssertionError("ispir resolved; it is not one of the eighteen")
    print(f"roster ok: 18 agents, 83 domains, drift={drift() or 'none'}")


if __name__ == "__main__":
    demo()
