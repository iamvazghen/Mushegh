"""Shared helpers for Afon's Phase 3 tools.

Every tool follows one rule: **never crash the brain on a missing integration**. If a
tool's credentials aren't set, its handler returns a short, plain-English note (via
``not_configured``) that Afon simply re-voices to the owner ("Web search isn't wired up
yet, sir — you'd need to add a Tavily key"). Errors are caught and returned the same way
(``tool_error``). Handlers therefore always return a ``str`` the LLM can speak.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from afon.config import settings
from afon.brain.never_store import NeverStoreRefused


class ErrorKind(str, Enum):
    """J7.3 — why a tool failed, as a value instead of a sentence to grep.

    Every handler returns speakable prose, which is right for the model and useless to a caller that
    has to DECIDE something: retry, fall back, page the owner, or stay quiet. Without this, deciding
    meant substring-matching English — which is how the LLM permanent-error classifier and the
    degradation tests both ended up built on prose.
    """

    NOT_CONFIGURED = "not_configured"   # the capability exists but has no credentials — never retry
    AUTH = "auth"                       # credentials present and rejected — retrying cannot help
    NETWORK = "network"                 # unreachable/timed out — a retry is reasonable
    RATE_LIMIT = "rate_limit"           # retry, but later and slower
    UNAVAILABLE = "unavailable"         # remote reachable and failing (5xx) — retry later
    NOT_FOUND = "not_found"             # the thing asked for is not there — retrying is pointless
    BAD_ARGS = "bad_args"               # WE called it wrong — a different call might work
    REFUSED = "refused"                 # declined by policy, not by failure — 37.R5 / D-24
    UNKNOWN = "unknown"


class ToolResult(str):
    """A tool result that is a plain ``str`` everywhere, and additionally carries ``kind``.

    A str SUBCLASS rather than a new return type on purpose: `tool_error` is the most connected node
    in the system (132 edges), every handler is contracted to return something the model can speak,
    and results are json-dumped across the edge/brain link. Subclassing changes none of that — the
    kind is simply there for the callers that ask, and absent (None) for everyone else.

    It does NOT survive the wire: JSON has no room for it, so anything crossing to the edge arrives
    as prose again. In-process callers get the type; the spoken contract is unchanged.
    """

    kind: "ErrorKind | None"

    def __new__(cls, text: str, kind: "ErrorKind | None" = None) -> "ToolResult":
        obj = super().__new__(cls, text)
        obj.kind = kind
        return obj


def classify_error(err: Exception) -> ErrorKind:
    """Map an exception to the taxonomy. Status codes first — they are the specific evidence."""
    if isinstance(err, NeverStoreRefused):
        # 37.R5 / D-24. A refusal is its own kind rather than `unknown`, because the caller's next
        # move differs from every other failure: nothing is broken, retrying is pointless, and the
        # audit line must say `refused` rather than `allow`. Mapping it to UNKNOWN would file a
        # policy decision as an error and, worse, `tool_error`'s "I couldn't complete the ..."
        # wording would tell the owner his assistant malfunctioned when it deliberately declined.
        return ErrorKind.REFUSED
    if isinstance(err, httpx.HTTPStatusError):
        code = err.response.status_code
        if code in (401, 403):
            return ErrorKind.AUTH
        # 402 Payment Required was falling through to BAD_ARGS with everything else, which is the
        # worst of both: it told the owner "that call was malformed" when the call was fine and the
        # service wanted paying, and a caller that retries on bad_args retries forever. Measured
        # 2026-10-10 — Jina's scrape endpoint returns 402 for every URL on this account, so
        # scrape_url reported a malformed call for a quota problem on a correctly-built request.
        # It is an access/entitlement failure, which is what AUTH means.
        if code == 402:
            return ErrorKind.AUTH
        if code == 404:
            return ErrorKind.NOT_FOUND
        if code == 429:
            return ErrorKind.RATE_LIMIT
        if code >= 500:
            return ErrorKind.UNAVAILABLE
        if code >= 400:
            return ErrorKind.BAD_ARGS
    if isinstance(err, (httpx.TimeoutException, httpx.TransportError, ConnectionError,
                        TimeoutError, OSError)):
        return ErrorKind.NETWORK
    if isinstance(err, (ValueError, TypeError, KeyError, IndexError, AttributeError)):
        return ErrorKind.BAD_ARGS
    return ErrorKind.UNKNOWN


def not_configured(what: str, needs: str) -> ToolResult:
    """A speakable note that a capability exists but isn't set up yet."""
    return ToolResult(
        f"{what} isn't configured yet — it needs {needs}. Tell the owner and offer to help set it up.",
        ErrorKind.NOT_CONFIGURED)


#: How a kind is described to the OWNER, in words. The exception's class name is deliberately
#: absent: it is logged above for the operator, and putting "HTTPStatusError" into a sentence the
#: model then reads aloud hands the owner a traceback class he cannot act on. Measured live on
#: 2026-10-10: `define_word` hit a dictionary API that 403s every request, and the owner heard
#: "I couldn't complete the definition just now (HTTPStatusError). I'll let the owner know." —
#: a raw exception name, and third person, to the owner himself. The repo's own rule is that tool
#: failures "speak in his voice and stay detectable as failures (not raw exception names)".
_KIND_PHRASE = {
    ErrorKind.AUTH: "the service turned that down, sir — the key or the plan needs attention",
    ErrorKind.NETWORK: "the connection failed",
    ErrorKind.RATE_LIMIT: "the service is rate-limiting",
    ErrorKind.UNAVAILABLE: "the service is unavailable",
    ErrorKind.NOT_FOUND: "there was nothing to read",
    ErrorKind.BAD_ARGS: "that call was malformed",
    ErrorKind.REFUSED: "it declined on purpose",
    ErrorKind.NOT_CONFIGURED: "it isn't set up",
}


def tool_error(what: str, err: Exception) -> ToolResult:
    kind = classify_error(err)
    logger.warning(f"tool '{what}' failed [{kind.value}]: {type(err).__name__}: {err}")
    phrase = _KIND_PHRASE.get(kind, "something went wrong")
    # "i couldn't complete the" must stay verbatim: `tool_failed()` keys on it, and a digest or
    # proactive caller would otherwise read a dead integration's failure aloud as though it were
    # data. Only the payload after the marker changed.
    return ToolResult(f"I couldn't complete the {what} just now — {phrase}, sir.", kind)


def missing_arg(tool: str, args: dict, *names: str, ask: str) -> str:
    """The one usable argument is absent: return an ERROR if the model used unknown keys, else ASK.

    A tool that answers a bad call with "Which URL, sir?" hands the model a fluent sentence, and the
    model speaks it as the reply — a fake answer with the tool never having run. That is exactly how
    `recall`'s "What should I recall, sir?" became a governance answer in the L3c audit.

    But asking is CORRECT when the owner genuinely left the detail out ("remind me" / "play
    something"), so a blanket sweep would trade one failure for another. The discriminator is which
    KEYS arrived, not whether a value is empty:

      * ``{}``                     -> the model relayed an underspecified request  -> ASK.
      * ``{"query": ""}``          -> right key, no content; still underspecified   -> ASK.
      * ``{"entity": …, "key": …}`` -> the model invented key names                  -> ERROR.

    Only the third case changes behaviour, and it is the documented bug: the intent was right and
    only the key was wrong, so an error lets the retry ladder fire instead of ending the turn on a
    sentence. ``names`` is the full set of accepted spellings, synonyms included.
    """
    if args and not (set(names) & set(args)):
        return tool_error(tool, ValueError(
            f"unknown argument(s) {sorted(args)}; expected one of {sorted(names)}"))
    return ask


# ponytail: handlers always return speakable prose and never raise, so a caller that consumes a
# tool result as DATA (proactive signals, digests) cannot tell "here are your events" from "I
# couldn't do that" — and will happily read the error aloud. `kind` (J7.3) answers this properly
# for anything built here; the substring markers remain the fallback for prose that arrives from
# somewhere else — across the wire, from an MCP server, or hand-written in a handler.
_NOT_CONFIGURED_MARKERS = ("isn't configured yet", "isn't configured", "not configured")
_ERROR_MARKERS = ("i couldn't complete the",)
_FAILURE_MARKERS = _ERROR_MARKERS + _NOT_CONFIGURED_MARKERS


def kind_of(result: object) -> ErrorKind | None:
    """The failure kind of a tool result, or None when it is data (or untyped prose)."""
    return getattr(result, "kind", None)


def tool_failed(result: str | None) -> bool:
    """True when a tool's string return is a failure / not-configured note rather than data."""
    if kind_of(result) is not None:
        return True
    if not result or not result.strip():
        return True
    low = result.lower()
    return any(m in low for m in _FAILURE_MARKERS)


def is_not_configured(result: str | None) -> bool:
    """True when a tool declined because a credential is missing (as opposed to erroring).

    Exists because the *contract* was centralised in ``not_configured()`` while the *assertions*
    were not: ten bench files each grepped the literal prose "isn't configured yet" for themselves,
    across 61 call sites. Rewording one sentence would have left every one of them passing while
    the guarantee they exist to protect was gone — a green suite over a broken degradation path.
    Callers ask this instead, so the wording lives in exactly one place.
    """
    if kind_of(result) is ErrorKind.NOT_CONFIGURED:
        return True
    if not result or kind_of(result) is not None:
        return False        # typed as some OTHER failure: definitively not a missing credential
    low = result.lower()
    return any(m in low for m in _NOT_CONFIGURED_MARKERS)


# A real User-Agent: some providers (e.g. Wikipedia) reject the default httpx UA with 403.
_USER_AGENT = "AfonAssistant/1.0 (+https://github.com/; personal voice assistant)"


# ---- 20.F3: one table, not thirty scattered numbers -----------------------------------------
# The timeout was already central; the RETRY policy was not, because there wasn't one. Every
# integration got exactly one attempt, so a single dropped packet to the weather API read to the
# owner as "I couldn't reach the weather service" — a sentence that describes an outage and was
# caused by a hiccup. The opposite failure is worse and is why this is a table rather than a
# blanket rule: retrying a slow scrape three times turns a 30-second wait into ninety, and
# retrying an authentication failure just spends quota to be told "no" again.


@dataclass(frozen=True)
class HttpPolicy:
    timeout: float
    #: EXTRA attempts after the first. 0 means one attempt.
    retries: int
    why: str


#: Matched on a hostname suffix, longest first, so "api.openweathermap.org" can differ from the
#: default without either being restated. Add a row when an integration's shape actually differs;
#: an integration with nothing special about it should keep using the default, not copy it.
HTTP_POLICIES: dict[str, HttpPolicy] = {
    "r.jina.ai": HttpPolicy(45.0, 0, "renders JS server-side, so it is slow by design; a retry "
                                     "doubles an already-long wait for the same rendered page"),
    "api.firecrawl.dev": HttpPolicy(45.0, 0, "same shape as Jina, and it costs credits per call"),
    "api.openweathermap.org": HttpPolicy(10.0, 2, "small, cheap and idempotent — a dropped packet "
                                                  "should not read as an outage"),
    "api.open-meteo.com": HttpPolicy(10.0, 2, "as above, and keyless"),
    "nominatim.openstreetmap.org": HttpPolicy(10.0, 1, "free geocoding, rate-limited: one retry, "
                                                       "never a storm"),
    "backend.composio.dev": HttpPolicy(30.0, 1, "fans out over connected apps; one retry covers a "
                                                "blip without doubling a fan-out"),
    "api.telegram.org": HttpPolicy(20.0, 2, "delivery to the owner — worth retrying"),
    "ntfy.sh": HttpPolicy(15.0, 2, "same: a push that silently never arrives is the whole failure "
                                   "the delivery ledger exists to catch"),
    "oauth2.googleapis.com": HttpPolicy(15.0, 1, "the token refresh gates mail, calendar and "
                                                 "vitals, so one retry is cheap insurance"),
    "www.googleapis.com": HttpPolicy(20.0, 1, "Gmail and Calendar reads; a retry covers a blip "
                                              "without re-sending anything"),
    "api.github.com": HttpPolicy(20.0, 0, "filing an issue is not idempotent — a retry after an "
                                          "ambiguous failure files it twice"),
    "api.jina.ai": HttpPolicy(10.0, 1, "embeddings: small, idempotent, and on the recall path, so "
                                       "a long wait is worse than a second try"),
    "api.deepgram.com": HttpPolicy(60.0, 0, "uploads a whole audio clip and transcribes it; a "
                                            "retry re-uploads the same bytes for the same answer"),
    "api.giphy.com": HttpPolicy(10.0, 1, "a GIF is a garnish — it should never hold up a reply"),
    "api.elevenlabs.io": HttpPolicy(60.0, 0, "synthesises and returns audio; a retry re-synthesises "
                                             "and costs characters twice"),
    "api.typesafe.ai": HttpPolicy(
        settings.jev_timeout_seconds,
        0,
        "typed contextual judgment: an outage asks the owner instead of retrying or silently "
        "delegating the decision to a language model",
    ),
}

#: Hosts whose policy depends on a configured URL rather than a fixed domain. Registered at
#: import by the modules that own them, so the number still lives in this table and not at the
#: call site.
def register_policy(host: str, policy: HttpPolicy) -> None:
    HTTP_POLICIES[host.lower()] = policy


DEFAULT_HTTP_POLICY = HttpPolicy(settings.http_timeout_seconds, 1,
                                 "one retry: enough for a dropped packet, not enough to turn a "
                                 "dead host into a long silence")

#: Retried. A 429 is included deliberately — it is the one 4xx that means "later", not "no".
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

#: Seconds to wait before attempt N (1-indexed). Short and finite: this is a voice assistant, and
#: an owner waiting on an answer would rather hear a failure than a longer pause.
_BACKOFF = (0.5, 1.5)


def policy_for(url: str) -> HttpPolicy:
    """The declared policy for a URL. Never guesses: an unlisted host gets the stated default."""
    host = (urlparse(url).hostname or "").lower()
    best: tuple[int, HttpPolicy] | None = None
    for suffix, pol in HTTP_POLICIES.items():
        if host == suffix or host.endswith("." + suffix):
            if best is None or len(suffix) > best[0]:
                best = (len(suffix), pol)
    return best[1] if best else DEFAULT_HTTP_POLICY


#: Reused clients, keyed by the event loop that created them and by the arguments that
#: change the client's identity (timeout, headers, redirect policy).
#:
#: This exists because a client PER REQUEST cost a full TLS handshake on every outbound
#: call - measured 2026-10-08 at ~1174 ms cold against ~232 ms warm on the same request.
#: That is most of JEv's 400 ms arbitration budget spent on the socket rather than on the
#: question, and it is paid by all 124 call sites in this module's reach.
#:
#: Keyed by loop because an httpx.AsyncClient is bound to the loop that created it. This
#: repo's tests call asyncio.run repeatedly, so a module-global client works in production
#: and fails across the suite. Dead loops are pruned so a long test run cannot accumulate
#: clients; nothing is awaited on their behalf, because _client is synchronous and cannot.
_CLIENTS: dict[int, tuple[Any, tuple[Any, ...], httpx.AsyncClient]] = {}


def _hashable(value: Any) -> Any:
    """A stable, content-based key for a client-construction argument.

    Content, not identity, for containers: `_client` builds a fresh `headers` dict on every
    call, so keying on `id()` handed back a different signature each time and the cache never
    hit - which silently put the per-request handshake straight back. Identity is the honest
    key only for objects with no value semantics (a MockTransport swapped per scenario).
    """
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_hashable(v) for v in value)
    try:
        hash(value)
        return value
    except TypeError:
        return ("<id>", id(value))


def _client_signature(kw: dict[str, Any]) -> tuple[Any, ...]:
    """Everything that makes one client different from another.

    Built from ALL of kw, not a hand-picked few. Picking was the bug: `test_api_policy.py`
    swaps a MockTransport in and out between scenarios through `_client`, and a key that
    ignored `transport` handed back a cached client still wired to the previous one - four
    checks failed because the second scenario quietly reused the first scenario's transport.
    A cache key has to cover everything that affects the constructed object; anything less
    is a correctness bug wearing a performance hat.
    """
    return tuple(sorted((name, _hashable(kw[name])) for name in kw))


def close_http_clients() -> None:
    """Drop the cached clients. Safe to call at any time; used at shutdown and by tests."""
    _CLIENTS.clear()


def _client(url: str = "", **kw: Any) -> httpx.AsyncClient:
    kw.setdefault("timeout", policy_for(url).timeout)
    # Follow 3xx so a provider that moved hosts (e.g. an API that now 301s to a new domain)
    # still resolves instead of surfacing the redirect as an error.
    kw.setdefault("follow_redirects", True)
    headers = {"User-Agent": _USER_AGENT}
    headers.update(kw.pop("headers", None) or {})
    kw["headers"] = headers

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop: nothing to key on and nothing to reuse. This is the path the
        # synchronous setup code takes, and it must keep working exactly as before.
        return httpx.AsyncClient(**kw)

    signature = _client_signature(kw)
    key = id(loop)

    # A closed loop's client can never be used again and holds a reference to that loop.
    for stale in [k for k, (owner, _, _) in _CLIENTS.items() if owner.is_closed()]:
        _CLIENTS.pop(stale, None)

    cached = _CLIENTS.get(key)
    if cached is not None and cached[1] == signature:
        return cached[2]

    client = httpx.AsyncClient(**kw)
    _CLIENTS[key] = (loop, signature, client)
    return client


def _retryable(exc: Exception) -> bool:
    """Transient by nature: a timeout, a refused connection, or a status that means 'later'."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError,
                        httpx.RemoteProtocolError)):
        return True
    return (isinstance(exc, httpx.HTTPStatusError)
            and exc.response.status_code in _RETRY_STATUS)


async def _request(method: str, url: str, **kw: Any) -> httpx.Response:
    """One HTTP call under the declared policy. Retries only what retrying can fix."""
    pol = policy_for(url)
    attempts = max(1, pol.retries + 1)
    last: Exception | None = None
    for i in range(attempts):
        try:
            # NOT `async with`: the client is shared, and closing it here would drop the
            # connection pool every time - which is the cost this change exists to remove.
            r = await _client(url).request(method, url, **kw)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            if i + 1 >= attempts or not _retryable(e):
                raise
            wait = _BACKOFF[min(i, len(_BACKOFF) - 1)]
            logger.debug(f"http {method} {url}: {type(e).__name__}, retrying in {wait}s "
                         f"({i + 2} of {attempts})")
            await asyncio.sleep(wait)
    raise last if last else RuntimeError("unreachable")


async def http_get(url: str, **kw: Any) -> httpx.Response:
    return await _request("GET", url, **kw)


async def http_post(url: str, **kw: Any) -> httpx.Response:
    return await _request("POST", url, **kw)


async def http_patch(url: str, **kw: Any) -> httpx.Response:
    return await _request("PATCH", url, **kw)


def guard_url(url: str, *, allow_private_hosts: tuple[str, ...] = ()) -> str:
    """Refuse a model-supplied URL that points somewhere it must not.

    Returns an empty string when the URL is safe to fetch, or a refusal the tool
    returns to the model verbatim. The message names the reason because "refused"
    with no reason teaches the model to retry the same thing.

    The rebinding caveat is not hidden: a hostname that resolves publicly here can
    resolve privately when the client actually connects, and this check does not
    close that (see ``afon.shared.netguard``). It refuses the obvious attempts
    and every literal or plainly-internal destination, which is the class that
    matters for a URL arriving from a page Afon has just read.
    """
    from afon.shared.netguard import check_url

    verdict = check_url(url, allow_private_hosts=allow_private_hosts)
    if verdict.ok:
        return ""
    return f"I won't open that — {verdict.reason}, sir."


def clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …(truncated)"


#: The backstop, not a policy (J1.4). ``clip()`` above is a per-tool sizing decision — the limits
#: across the tree run from 80 to 4000 characters because a label, an excerpt and a document are
#: different things. This is the ceiling for a tool that made no such decision at all.
TOOL_RESULT_CEILING = settings.tool_result_ceiling


def bound_tool_result(result: str, tool: str) -> str:
    """Cap one tool result before it enters a message list, and SAY that it was capped.

    Both paths that append ``{"role": "tool", ...}`` used the raw string. On the live turn that puts
    an oversized scrape or document straight into the next request's prefill — already the dominant
    per-turn cost. In the autonomous worker it is worse: the loop keeps the message list and pays for
    it again on every subsequent step, with nobody watching.

    The marker is not decoration. A model that can see its input was truncated, by which tool, and
    how much there was, can narrow the query or ask for the rest; one that cannot answers
    confidently from half a document — which is the failure mode this repo calls fabrication.
    """
    text = result or ""
    if len(text) <= TOOL_RESULT_CEILING:
        return text
    head = text[:TOOL_RESULT_CEILING].rstrip()
    return (f"{head}\n\n[truncated: {tool} returned {len(text)} characters, "
            f"{TOOL_RESULT_CEILING} shown — narrow the query or ask for the rest]")
