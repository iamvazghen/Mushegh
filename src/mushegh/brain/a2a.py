"""A2A — the sanctioned transport to the fleet, and the answer ``fleet.py`` was waiting for.

``fleet.py``'s docstring spent a long time explaining why there was no honest way in. Operator
access to the OpenClaw gateway needs either an Origin allowlist with ECDSA device identity, or
presenting as a built-in client id — and presenting as a built-in client to pass an allowlist is
exactly what a sanctioned path should not have to do. It named three honest options and took
none of them.

**Agent2Agent is the fourth, and it is the right one.** It is a published protocol the gateway
implements as a first-class channel, not a control-plane surface borrowed from the human UI.
Mushegh is a *peer*, with a peer's name and a peer's token, and the gateway decides what a peer
may do: an A2A peer can send a text task and read the answer, and cannot run an operator slash
command (the gateway rejects anything starting with ``/`` before a model sees it). That
restriction is the point. The transport itself now carries D-05's line — the fleet is a tool and
never the assistant — instead of a prompt asking nicely.

**Two things it buys for free, both of which were open problems.**

* *Per-agent addressing.* Nine tokens, nine peers, and the gateway's own ``bindings`` map peer
  ``jarvis.<agent>`` to agent ``<agent>``. Mushegh addresses a specialist by name, verified
  server-side. There is no router to misroute through, and a wrong token is a 401 rather than a
  brief delivered to the wrong desk.
* *Nothing is sent anywhere.* An A2A reply goes back over the HTTP response to the caller. It is
  not a channel delivery, so an agent answering Mushegh cannot message the owner as a
  side effect — the consent gate holds in the transport, including inside quiet hours.

**The nine Hermes agents do not speak it**, because Hermes ships no A2A server. They are reached
with ``hermes -z`` against the profile home that holds the agent's charter, over the SSH target
the fleet path already uses. Same ``ask()``, same timeout, same refusal on a non-zero exit; the
roster records which transport an agent has so no caller has to keep a list.

    uv run python bench/test_a2a_transport.py
"""

from __future__ import annotations

import asyncio
import json
import shlex
import subprocess
import time
from typing import Any

import httpx
from loguru import logger

from mushegh.brain import roster
from mushegh.brain.tools.base import _client
from mushegh.config import settings

__all__ = ["AgentUnreachable", "ask", "agent_card", "configured", "tokens", "ping"]

#: Terminal A2A task states, from the gateway's own enum. Anything else means keep polling.
_DONE = {"TASK_STATE_COMPLETED"}
_FAILED = {"TASK_STATE_FAILED", "TASK_STATE_REJECTED", "TASK_STATE_CANCELLED", "TASK_STATE_UNKNOWN"}


class AgentUnreachable(RuntimeError):
    """One agent could not be reached or refused the task. Never a silent empty answer."""


def tokens() -> dict[str, str]:
    """The agent -> bearer token map, parsed once per call from the single setting.

    A malformed value is a configuration error and says so. It is NOT treated as "no tokens":
    an empty map and an unparseable one look identical downstream and only one of them is
    something the owner can fix without being told.
    """
    raw = (settings.a2a_tokens or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AgentUnreachable(f"MUSHEGH_A2A_TOKENS is not valid JSON: {e}") from e
    if not isinstance(parsed, dict) or not all(isinstance(v, str) and v for v in parsed.values()):
        raise AgentUnreachable("MUSHEGH_A2A_TOKENS must be an object of agent -> non-empty token")
    return {str(k).strip().lower(): v for k, v in parsed.items()}


def configured(agent: str) -> bool:
    """Can this agent be reached at all with what is in the environment right now?

    Measured, not remembered. The same reason the executor table calls ``shutil.which`` on every
    dispatch: a setting that says "configured" is one more thing that can be wrong.
    """
    try:
        kind = roster.transport(agent)
    except roster.UnknownAgent:
        return False
    if kind == "a2a":
        try:
            return bool(settings.a2a_base_url) and agent in tokens()
        except AgentUnreachable:
            return False
    return bool(settings.openclaw_cli_ssh_target)


async def ask(agent: str, text: str, *, timeout_s: int | None = None,
              on_progress=None) -> str:
    """Put ``text`` to one named agent and return its answer. Raises, never returns a guess.

    ``agent`` is validated against the roster before anything leaves this process, so a brief
    addressed to a name nobody owns is refused here rather than delivered to the nearest desk.
    """
    row = roster.resolve(agent)          # UnknownAgent propagates: a bad name is a caller bug
    name = row["person"]
    kind = roster.transport(agent)
    if not text.strip():
        raise AgentUnreachable("an empty brief is not a task")
    if text.lstrip().startswith("/"):
        # The gateway rejects this server-side; saying so here explains it instead of a -32000.
        raise AgentUnreachable(
            "A2A peers cannot run slash commands — send the task in plain text"
        )
    if on_progress:
        on_progress(f"putting that to {name}")
    if kind == "a2a":
        return await _ask_a2a(agent, text, timeout_s, on_progress)
    return await _ask_hermes(agent, text, timeout_s)


# ---- A2A 1.0 over JSON-RPC (the nine OpenClaw agents) --------------------------------------
# SendMessage + tasks/get is the whole protocol surface the gateway supports: it advertises
# streaming:false and pushNotifications:false in its own agent card, and rejects CancelTask. So
# this submits with returnImmediately and polls, rather than holding a socket open for minutes.


def _rpc(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": f"mushegh-{int(time.time() * 1000)}", "method": method,
            "params": params}


def _headers(agent: str) -> dict[str, str]:
    token = tokens().get(agent)
    if not token:
        raise AgentUnreachable(
            f"no A2A token for {agent} — add it to MUSHEGH_A2A_TOKENS "
            f"(the gateway knows it as peer {settings.a2a_peer_prefix}.{agent})"
        )
    return {"authorization": f"Bearer {token}", "content-type": "application/json"}


def _endpoint() -> str:
    base = (settings.a2a_base_url or "").rstrip("/")
    if not base:
        raise AgentUnreachable("MUSHEGH_A2A_BASE_URL is not set, so the fleet has no address")
    return f"{base}/a2a/v1"


def _result(payload: dict[str, Any], what: str) -> dict[str, Any]:
    """Unwrap a JSON-RPC envelope. An ``error`` member is a failure even with HTTP 200."""
    if not isinstance(payload, dict):
        raise AgentUnreachable(f"{what}: the gateway did not return a JSON-RPC object")
    err = payload.get("error")
    if err:
        code = err.get("code") if isinstance(err, dict) else ""
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise AgentUnreachable(f"{what}: gateway refused ({code}) {msg}")
    out = payload.get("result")
    if not isinstance(out, dict):
        raise AgentUnreachable(f"{what}: no result in the gateway's reply")
    return out


def _artifact_text(task: dict[str, Any]) -> str:
    """The answer, from the task's artifacts. Empty string when the task carries none."""
    parts: list[str] = []
    for artifact in task.get("artifacts") or []:
        for part in (artifact or {}).get("parts") or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return "\n".join(p for p in parts if p.strip()).strip()


async def _ask_a2a(agent: str, text: str, timeout_s: int | None, on_progress) -> str:
    deadline_s = timeout_s or settings.openclaw_request_timeout_seconds
    url, headers = _endpoint(), _headers(agent)
    send = _rpc("message/send", {
        "message": {
            "messageId": f"mushegh-{int(time.time() * 1000)}",
            "role": "ROLE_USER",
            # A stable contextId per agent keeps a conversation with that specialist on one
            # thread across turns, which is what makes a follow-up brief make sense to them.
            "contextId": f"ctx-mushegh-{agent}",
            "parts": [{"text": text}],
        },
        # Submit and poll. Blocking costs a held connection for up to the gateway's
        # replyTimeoutMs (five minutes here) and gives up the ability to report progress.
        "configuration": {"returnImmediately": True},
    })

    # The POOLED client, not a fresh one — 01.J12. This was the last module in the tool belt still
    # building its own `httpx.AsyncClient`, so every `send_to_agent` call opened a full TLS
    # handshake to a gateway the next call would handshake to again. §01.J2 replaced the per-request
    # client with a loop-keyed pool across 58 modules and measured the cost at ~700 ms; a2a.py was
    # missed by that sweep and kept paying it. `test_api_policy.py` is what noticed.
    #
    # NOT `async with`: the client is shared, and closing it here would drop the connection pool
    # every time — which is the cost this change exists to remove. See `base._request`.
    client = _client(url, timeout=30.0)
    task = _result((await _post(client, url, headers, send)), f"{agent} submit").get("task")
    if not isinstance(task, dict) or not task.get("id"):
        raise AgentUnreachable(f"{agent}: the gateway accepted no task")
    task_id = task["id"]
    started = time.monotonic()
    announced = False
    while True:
        state = ((task.get("status") or {}).get("state")) or ""
        if state in _DONE:
            answer = _artifact_text(task)
            if not answer:
                # Invariant borrowed from the executor contract: a completed task with no
                # text is a failure, not an answer. Prose never decides; artefacts do.
                raise AgentUnreachable(f"{agent} completed the task and returned no text")
            return answer
        if state in _FAILED:
            raise AgentUnreachable(f"{agent} did not do the task ({state.lower()})")
        if time.monotonic() - started > deadline_s:
            # The task is still running over there. Do NOT resubmit — the same reasoning
            # fleet.py's FleetStalled carries: a non-idempotent brief would then happen twice.
            raise AgentUnreachable(
                f"{agent} took the task and had not answered after {deadline_s}s; it may still "
                f"be running (task {task_id}). Nothing was re-sent."
            )
        if on_progress and not announced and time.monotonic() - started > 5:
            on_progress(f"{roster.resolve(agent)['person']} is working on it")
            announced = True
        # Outside the branch above, deliberately. Indented INTO it, the sleep happens on exactly
        # one iteration and every other poll fires with no delay at all — a tight `tasks/get`
        # loop until the deadline. The gateway rate-limits per peer, so the symptom is not a hot
        # CPU but `-32000 Peer is rate limited` on a task that was going to succeed.
        await asyncio.sleep(settings.a2a_poll_seconds)
        get = _rpc("tasks/get", {"id": task_id})
        task = _result(await _post(client, url, headers, get), f"{agent} poll")


async def _post(client: httpx.AsyncClient, url: str, headers: dict[str, str],
                body: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        raise AgentUnreachable(f"the gateway is unreachable: {type(e).__name__}") from e
    if resp.status_code == 401:
        raise AgentUnreachable(
            "the gateway rejected the token — check MUSHEGH_A2A_TOKENS against "
            "channels.a2a.peers on the gateway"
        )
    if resp.status_code >= 400:
        raise AgentUnreachable(f"the gateway answered HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as e:
        raise AgentUnreachable("the gateway's reply was not JSON") from e


async def agent_card() -> dict[str, Any]:
    """The gateway's published A2A agent card. Discovery is public; no token needed."""
    base = (settings.a2a_base_url or "").rstrip("/")
    if not base:
        raise AgentUnreachable("MUSHEGH_A2A_BASE_URL is not set")
    # Pooled for the same reason as `_ask_a2a`, and for a sharper one: this runs at BOOT to
    # discover the roster, so the fresh handshake it used to pay landed on the first thing the
    # owner saw. Also not closed — see `base._request`.
    client = _client(base, timeout=15.0)
    for path in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
        try:
            resp = await client.get(f"{base}{path}")
        except httpx.HTTPError:
            continue
        if resp.status_code == 200:
            return resp.json()
    raise AgentUnreachable(f"no agent card at {base}")


# ---- hermes -z (the nine Hermes profiles) ---------------------------------------------------


async def _ask_hermes(agent: str, text: str, timeout_s: int | None) -> str:
    """One-shot a Hermes profile over the SSH target the fleet path already uses.

    Hermes publishes no A2A server, so this is the honest transport rather than a worse one
    dressed as A2A. ``HERMES_HOME`` is what selects the agent: each profile home holds that
    agent's DOMAIN.md charter and its vault symlink, so the agent that answers is the one whose
    charter was loaded — the same per-agent guarantee the A2A bindings give on the other half.
    """
    target = settings.openclaw_cli_ssh_target
    if not target:
        raise AgentUnreachable(
            "no SSH target configured, so the Hermes half of the fleet has no address "
            "(MUSHEGH_OPENCLAW_CLI_SSH_TARGET)"
        )
    deadline_s = timeout_s or settings.hermes_request_timeout_seconds
    home = f"{settings.hermes_profiles_root.rstrip('/')}/{agent}"
    # No login shell, unlike the OpenClaw CLI path: `hermes_cli_path` is the pinned launcher
    # inside the checkout, which resolves its own interpreter and tools, so it needs nothing
    # from PATH. One fewer shell is one fewer place the brief gets re-parsed.
    inner = (
        f"HERMES_HOME={shlex.quote(home)} {shlex.quote(settings.hermes_cli_path)} "
        f"-z {shlex.quote(text)}"
    )
    argv = ["ssh", target, inner]

    def _run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, text=True, capture_output=True, timeout=deadline_s + 30,
                              stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")

    try:
        proc = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired as e:
        raise AgentUnreachable(
            f"{agent} had not answered after {deadline_s}s; nothing was re-sent"
        ) from e
    except Exception as e:  # noqa: BLE001
        raise AgentUnreachable(f"could not reach {agent}: {type(e).__name__}") from e
    if proc.returncode != 0:
        detail = " | ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-2:])
        raise AgentUnreachable(f"{agent} exited {proc.returncode}: {detail[:200]}")
    answer = (proc.stdout or "").strip()
    if not answer:
        raise AgentUnreachable(f"{agent} exited 0 and returned no text")
    return answer


# ---- liveness ------------------------------------------------------------------------------


async def ping(agent: str, *, timeout_s: int = 90) -> tuple[bool, str]:
    """Ask one agent to say its own name back. ``(ok, detail)`` — never raises.

    This is the check behind ``fleet_status``, and it is a real round trip on purpose: the
    gateway being up proves a process runs, not that this agent's config resolves, its model
    answers, or its token maps to it. A liveness check is not a survival check.
    """
    if not configured(agent):
        return False, "not configured"
    want = agent.upper()
    try:
        reply = await ask(agent, f"Reply with exactly this one word and nothing else: {want}",
                          timeout_s=timeout_s)
    except (AgentUnreachable, roster.UnknownAgent) as e:
        return False, str(e)[:160]
    ok = want in reply.upper()
    if not ok:
        logger.debug(f"a2a ping {agent}: answered without the token word: {reply[:120]!r}")
    return ok, reply.strip()[:160]
