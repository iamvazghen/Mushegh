"""Fleet delegation — eighteen named specialists, one tool, and never Mushegh's identity.

**What changed, and why the old shape had to go.** This module used to talk to a single team
lead called ``ispir`` over the gateway's operator WebSocket, falling back to the ``openclaw``
CLI over SSH. Two things are now true that were not:

* ``ispir`` does not exist. The eight-agent fleet it led was deleted on 2026-10-08, and the
  eighteen-agent fleet that replaced it has **no router at all** — each agent owns a named
  slice of the eighty-three domains, exclusively. So the choice of specialist is Mushegh's to
  make, and :mod:`mushegh.brain.roster` is what he knows about who does what.
* The WebSocket path was never sanctioned. Operator access needs an Origin allowlist with
  ECDSA device identity, or presenting as a built-in client id — and this module's own
  docstring said that presenting as a built-in client to pass an allowlist is exactly what a
  sanctioned path should not have to do. It named three honest options and shipped none; the
  breaker that made the doomed handshake cheap was a workaround for a path that should not
  have existed. It is deleted rather than kept dark (D-46).

**The transport is now A2A**, a published protocol the gateway implements as a first-class
channel, where Mushegh is a peer with a peer's name and a peer's token. See
:mod:`mushegh.brain.a2a` for why that also closes the consent question for free: an A2A reply
comes back over the HTTP response, so an agent answering Mushegh cannot message the owner as a
side effect — including inside quiet hours. The nine Hermes agents have no A2A server and are
reached with their one-shot CLI behind the same ``ask()``.

**What has NOT changed.** The fleet is one of Mushegh's tools and never his voice (D-05). He
re-voices every answer as himself, a consult still needs ``fleet_authorized``, and nothing an
agent produces goes anywhere outward without the owner's say-so.

    uv run python bench/test_a2a_transport.py
    uv run python bench/test_fleet_fastpath.py
"""

from __future__ import annotations

from loguru import logger

from mushegh.brain import a2a, roster
from mushegh.config import settings


class FleetUnavailable(RuntimeError):
    """Raised when the fleet can't be reached or delegation is disabled."""


class FleetStalled(FleetUnavailable):
    """39.R2 — the fleet TOOK the work and did not answer in time. Not the same as being down.

    A subclass of `FleetUnavailable` so every existing caller keeps handling it, and a separate type
    so the two are never confused again. The distinction is the whole point: an unreachable fleet
    means the request never arrived, and re-sending it is safe; a stall means it MAY have arrived and
    may still be running, and re-sending it can execute a non-idempotent task — send this email,
    spawn this process, pay this — twice. Those two cases used to take the same path, because a
    `TimeoutError` was caught by a bare `except Exception` and reported as a gateway error before
    being retried over the CLI. The owner was told the bridge was broken when the bridge had
    answered and simply gone quiet.
    """


def resolve_agent(task: str, agent: str | None) -> str:
    """Which specialist gets this brief. A name is checked; no name is inferred, then checked.

    Code builds the candidate list and the model may only narrow it — the same rule the executor
    contract uses for picking a coding CLI, for the same reason. When the brief matches several
    domains this **refuses and names them**, because "the nearest thing" is how a legal question
    reaches the media agent. A refusal that says who to ask costs one more turn; a misroute costs
    the owner a wrong answer he has no reason to doubt.
    """
    if agent:
        try:
            roster.resolve(agent)
        except roster.UnknownAgent as e:
            raise FleetUnavailable(str(e)) from e
        return agent.strip().lower()
    hits = roster.suggest(task)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise FleetUnavailable(
            "no agent's domain matches that brief — name one of: " + ", ".join(roster.names())
        )
    raise FleetUnavailable(
        f"that brief touches {len(hits)} agents' domains ({', '.join(hits)}) — "
        f"name the one you mean"
    )


async def ask(agent: str, task: str, timeout_s: int | None = None, on_progress=None) -> str:
    """Put a brief to ONE named specialist and return the answer. The whole transport is here.

    Raises :class:`FleetUnavailable` (or :class:`FleetStalled` when the agent took the work and
    went quiet) rather than returning an empty string, so a caller can never mistake silence
    for an answer.
    """
    if not settings.openclaw_delegation_enabled:
        raise FleetUnavailable("fleet delegation is disabled (MUSHEGH_OPENCLAW_DELEGATION_ENABLED)")
    try:
        roster.resolve(agent)
    except roster.UnknownAgent as e:
        raise FleetUnavailable(str(e)) from e
    if not a2a.configured(agent):
        kind = roster.transport(agent)
        needs = ("MUSHEGH_A2A_BASE_URL and a token in MUSHEGH_A2A_TOKENS"
                 if kind == "a2a" else "MUSHEGH_OPENCLAW_CLI_SSH_TARGET")
        raise FleetUnavailable(f"{agent} has no configured route — needs {needs}")
    try:
        answer = await a2a.ask(agent, task, timeout_s=timeout_s, on_progress=on_progress)
    except a2a.AgentUnreachable as e:
        # "had not answered" is the one failure that must NOT be retried anywhere up the stack:
        # the brief may still be running over there, and re-sending a non-idempotent task runs
        # it twice. The type carries that, so no caller has to read the message to know.
        if "had not answered" in str(e):
            raise FleetStalled(
                f"{roster.resolve(agent)['person']} took the job and did not answer in time. I have "
                f"taken it back rather than send it a second time, because it may still be running "
                f"over there. Tell me if it turns up, and I will not re-send it without you saying so."
            ) from e
        raise FleetUnavailable(str(e)) from e
    _note_success(task)
    return answer


async def delegate_to_fleet(
    task: str,
    agent: str | None = None,
    timeout_s: int | None = None,
    on_progress=None,
) -> str:
    """Hand `task` to the specialist who owns its domain and return the final answer text.

    ``agent`` is the agent id from the roster (``zara``, ``goharik``, ...). Omitting it is
    allowed but not encouraged: :func:`resolve_agent` will only guess when exactly one agent's
    domains match, and otherwise refuses with the candidates named.

    `on_progress(note)` is called with short status strings for spoken progress. This performs a
    LIVE round trip to shared infrastructure — only call after the user has authorized delegation.
    """
    chosen = resolve_agent(task, agent)
    if on_progress and not agent:
        logger.debug(f"fleet: no agent named, routing to {chosen} by domain match")
    return await ask(chosen, task, timeout_s=timeout_s, on_progress=on_progress)


async def status() -> list[tuple[str, str, bool, str]]:
    """``(agent, transport, ok, detail)`` for all eighteen, by real round trip.

    Deliberately not a gateway health check. A liveness check is not a survival check: the
    gateway being up proves a process runs, not that this agent's config resolves, its model
    answers, or its token maps to it. This fleet has produced that mistake twice.
    """
    out: list[tuple[str, str, bool, str]] = []
    for name in roster.names():
        ok, detail = await a2a.ping(name)
        out.append((name, roster.transport(name), ok, detail))
    return out


# ---- routing memory -----------------------------------------------------------------------
# Mushegh learns WHICH domains he ends up delegating, so the system prompt can pre-bias him to
# hand those over confidently instead of re-deliberating every turn. Plain keyword tagging into
# a prefs counter — no model, no store. ponytail: keywords, embeddings if tagging misroutes.
_DOMAIN_KEYWORDS = {
    "finance/markets": ("stock", "etf", "market", "portfolio", "invest", "dividend", "bond"),
    "real estate": ("apartment", "house", "rent", "is24", "immobilien", "property", "listing"),
    "crypto": ("crypto", "bitcoin", "btc", "eth", "wallet", "token", "defi"),
    "deep research": ("research", "report", "analysis", "compare", "investigate", "brief"),
    "coding": ("code", "repo", "bug", "refactor", "script", "implement"),
}


def _note_success(task: str) -> None:
    """Bump the routing counter for each domain this delegated task matches. Fail-quiet."""
    try:
        from mushegh.brain import prefs

        t = task.lower()
        counts: dict = prefs.get("fleet_domains", {}) or {}
        for domain, words in _DOMAIN_KEYWORDS.items():
            if any(w in t for w in words):
                counts[domain] = int(counts.get(domain, 0)) + 1
        if counts:
            prefs.set("fleet_domains", counts)
    except Exception:  # noqa: BLE001
        pass


def routing_hint() -> str:
    """One system-prompt line naming domains the owner routinely delegates (>=2 successes)."""
    try:
        from mushegh.brain import prefs

        counts: dict = prefs.get("fleet_domains", {}) or {}
        learned = [d for d, n in sorted(counts.items(), key=lambda kv: -int(kv[1])) if int(n) >= 2]
        if not learned:
            return ""
        # Terse AND capped on purpose: this line is charged on EVERY turn and the system prompt has a
        # hard 2000-token budget (bench/test_finetune). The un-capped, chatty version pushed a real
        # user's prompt to 2006 tok as soon as they'd delegated twice.
        return "Auto-delegate: " + ", ".join(learned[:2]) + "."
    except Exception:  # noqa: BLE001
        return ""


# Tool schema Mushegh's LLM sees. The eighteen agents and their domains are IN the description,
# because the routing decision is now his and he cannot make it from a name he has never read.
# The eighty-three domain titles are an order of magnitude longer and are not here: they are
# fetched per agent through `roster.domains()` when a brief actually needs them.
FLEET_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delegate_to_fleet",
        "description": (
            "Hand a task to ONE of your eighteen specialist agents for deep domain work you "
            "can't do yourself: live multi-step research, security analysis, legal obligations, "
            "infrastructure, media production, inbox and calendar work, vendor and sales "
            "operations. Each agent owns its domains exclusively — there is no team lead and no "
            "router, so YOU choose, by name, and the brief goes straight to that desk.\n\n"
            + roster.directory()
            + "\n\nUse only when your own knowledge or your own tools (web_search, scrape_url, "
            "vault) aren't enough. Give the agent a clear, self-contained brief: the goal, any "
            "context, and what a good answer looks like. You remain Mushegh and re-voice the "
            "answer in your own words. An agent's answer comes back to you only — it is never "
            "sent anywhere on its own."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "A clear, self-contained brief for that one agent: the goal, relevant "
                        "context, and the desired form of the answer. The agent sees only this "
                        "text, so state intent fully."
                    ),
                },
                "agent": {
                    "type": "string",
                    "enum": roster.names(),
                    "description": (
                        "Which specialist. Pick the one whose domain owns the work; if two could "
                        "plausibly own it, pick the one whose domain names it more specifically."
                    ),
                },
                "background": {
                    "type": "boolean",
                    "description": (
                        "Set TRUE for long or open-ended work (a website rebuild, deep multi-step "
                        "research, a big coding job) so you hand it off and keep talking: you get a "
                        "task id immediately, can answer 'how's that going?' later, and Mushegh "
                        "announces completion by voice. Leave FALSE (default) for a quick consult "
                        "where you wait a few seconds for the answer to relay right now."
                    ),
                },
            },
            "required": ["task", "agent"],
        },
    },
}
