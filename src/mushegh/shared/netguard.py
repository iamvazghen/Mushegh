"""Whether a URL supplied by someone else is safe for Mushegh to fetch.

Two entry points take a URL that did not originate on this machine: ``browser``
navigates to whatever it is handed, and ``scrape_url`` fetches it. Both are
reachable from a page Mushegh has just read, so both are reachable from whatever
that page said — which is the injection path D-5 exists to close, one layer up.

So the check lives here, in the shared layer, rather than in either tool: a
security check copied into two modules is a security check that will be fixed in
one of them.

**What this closes, and what it does not.** Scheme, credential and literal-address
checks refuse the whole class of obvious attempts and cost nothing. This module
additionally *resolves* the hostname and refuses any answer that lands on a
private, loopback, link-local or reserved address — which the parallel guard in
``jarvis-fleet`` explicitly leaves to the connector, because a name that resolves
publicly at check time and privately at fetch time defeats a check that does not
resolve at all.

The residual gap is stated rather than papered over: a server that answers the
resolution below with a public address and the real connection with a private one
(DNS rebinding) still wins, because closing that requires pinning the socket to
the resolved address, which httpx does not expose. ``Verdict.rebind_possible`` is
therefore part of the return value and callers are expected to propagate it rather
than claim a URL is safe. Redirects carry the same gap and are guarded by the
per-hop hook in ``tools.base``.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

#: Schemes Mushegh will fetch. Everything else — file:, gopher:, data:, ftp: — is a
#: local-file read or a protocol nothing here needs.
FETCHABLE_SCHEMES = ("https", "http")

#: Suffixes that name something inside an infrastructure rather than on the internet.
PRIVATE_SUFFIXES = (".localhost", ".internal", ".local", ".lan", ".home.arpa")

#: Hosts that are their own special case. The first is obvious; the second is the
#: cloud metadata service by name rather than only by address.
PRIVATE_HOSTS = ("localhost", "metadata.google.internal", "metadata.goog")


@dataclass(frozen=True)
class Verdict:
    """The result of checking one URL."""

    ok: bool
    reason: str
    #: True when the host was a name (not a literal) and we resolved it. A name
    #: that resolves is still not proof against rebinding — see the module note.
    rebind_possible: bool = False
    resolved: tuple[str, ...] = field(default_factory=tuple)

    def __bool__(self) -> bool:
        return self.ok


def _blocked(reason: str) -> Verdict:
    return Verdict(ok=False, reason=reason)


def classify_host(host: str) -> tuple[bool, str]:
    """Is this host string plausibly a public destination, by name alone?

    A hostname that is not a literal address is reported public *pending
    resolution* — a statement about this function's limits, not about the host.
    """
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return False, "missing host"
    if host in PRIVATE_HOSTS or host.endswith(PRIVATE_SUFFIXES):
        return False, "host names an internal destination"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True, "public hostname pending resolution"
    if _address_blocked(address):
        return False, "literal address is not public"
    return True, "public literal address"


def _address_blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Is this address one Mushegh must never reach from a model-supplied URL?"""
    if getattr(address, "ipv4_mapped", None):
        # ::ffff:127.0.0.1 is a loopback wearing an IPv6 costume.
        address = address.ipv4_mapped
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


#: Resolver signature. Injectable so the policy is testable without DNS.
Resolver = Callable[[str, int], Iterable[tuple]]


def _system_resolver(host: str, port: int) -> Iterable[tuple]:
    return socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)


def resolve_and_classify(host: str, *, resolver: Resolver | None = None) -> Verdict:
    """Resolve `host` and refuse if ANY answer is not a public address.

    "Any", not "the first": a name resolving to one public and one private address
    is a rebinding setup, and accepting it because the first answer looked clean
    is exactly the bug this is here to prevent.

    A resolution failure is not a pass. It is reported as blocked, because a name
    that cannot be resolved now is not one to be fetched later.
    """
    resolve = resolver or _system_resolver
    port = 443
    try:
        answers = list(resolve(host, port))
    except OSError as exc:
        return _blocked(f"host does not resolve ({type(exc).__name__})")
    if not answers:
        return _blocked("host does not resolve")

    addrs: list[str] = []
    for info in answers:
        sockaddr = info[4]
        literal = str(sockaddr[0]) if sockaddr else ""
        if not literal:
            return _blocked("resolution returned no address")
        addrs.append(literal)
        try:
            address = ipaddress.ip_address(literal)
        except ValueError:
            return _blocked("resolution returned an unparseable address")
        if _address_blocked(address):
            return Verdict(
                ok=False,
                reason=f"host resolves to a non-public address ({literal})",
                rebind_possible=True,
                resolved=tuple(sorted(set(addrs))),
            )
    return Verdict(ok=True, reason="resolves to a public address", rebind_possible=True, resolved=tuple(sorted(set(addrs))))


def check_url(
    url: str,
    *,
    allow_private_hosts: Iterable[str] = (),
    resolver: Resolver | None = None,
) -> Verdict:
    """Is `url` safe for Mushegh to request?

    `allow_private_hosts` is for endpoints Mushegh genuinely owns — its own brain on
    loopback, a paired device on the tailnet. It is an explicit, per-call-site
    exception, never a default, because a default exception here is a default
    hole.
    """
    if not isinstance(url, str) or not url.strip():
        return _blocked("empty URL")
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return _blocked("unparseable URL")

    if parts.scheme.lower() not in FETCHABLE_SCHEMES:
        return _blocked(f"scheme {parts.scheme!r} is not fetchable")

    if parts.username or parts.password:
        # Credentials in a URL leak into logs, referrers and error messages, and
        # on this host they would be handed to whatever the model asked for.
        return _blocked("URL carries embedded credentials")

    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        return _blocked("missing host")

    if host in {h.strip().lower() for h in allow_private_hosts}:
        return Verdict(ok=True, reason="host is on the explicit local allowlist")

    public, why = classify_host(host)
    if not public:
        return _blocked(why)

    # A literal address was fully decided above; only a name needs resolving.
    try:
        ipaddress.ip_address(host)
        return Verdict(ok=True, reason="public literal address")
    except ValueError:
        pass

    return resolve_and_classify(host, resolver=resolver)


def is_safe(url: str, **kw: object) -> bool:
    """Boolean form of `check_url`, for call sites that only need the answer."""
    return bool(check_url(url, **kw))  # type: ignore[arg-type]