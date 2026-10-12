"""What Mushegh actually read this turn, so a source he names is one he opened (41.F2).

A model that has just been handed a page of text will happily attribute a claim to a plausible URL
it never fetched. That failure is invisible in exactly the way that matters: the answer looks better
for having a citation, and the owner has no way to tell a real link from a well-formed one. The
research skill has said "cite the source" since the start; nothing checked.

So this is a per-turn ledger of retrievals. `web_search` and `scrape_url` record what they got back;
anything that reaches the owner's ears as a source is checked against it. "Checked to resolve" here
means the strongest thing available offline and the thing that actually fails: the URL must be one
Mushegh retrieved in this turn, not one that reads like it could exist.

Deliberately NOT done: re-fetching every cited URL to prove it is live. That turns every answer into
extra network calls, and a 200 from a page Mushegh never read is not evidence he read it. Provenance is
the question; reachability is not.

    uv run python -m mushegh.brain.citations     # self-check
"""

from __future__ import annotations

import re
import time
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.parse import urlsplit

from loguru import logger

#: Per-turn, per-task. A ContextVar rather than a module global because turns run concurrently and
#: one session's retrievals must never vouch for another's claim.
_LEDGER: ContextVar[dict[str, "Source"] | None] = ContextVar("citation_ledger", default=None)

_URL = re.compile(r"https?://[^\s<>\"'\)\]]+", re.I)

#: Hosts that are Mushegh's own plumbing, not sources. Naming r.jina.ai as a citation would be citing
#: the reader that fetched the page rather than the page.
_PLUMBING = {"r.jina.ai", "api.firecrawl.dev", "api.jina.ai"}


@dataclass(frozen=True)
class Source:
    url: str
    title: str = ""
    at: float = 0.0
    via: str = ""          # which tool retrieved it

    @property
    def host(self) -> str:
        return normalise(self.url)


def normalise(url: str) -> str:
    """The host a URL points at, lowercased, without `www.`. The unit a spoken citation names."""
    try:
        host = urlsplit(url.strip()).netloc.lower()
    except ValueError:
        return ""
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def start() -> None:
    """Begin a turn's ledger. Safe to call twice; the second call wins and the first is dropped."""
    _LEDGER.set({})


def record(url: str, title: str = "", via: str = "") -> None:
    """Note that Mushegh actually retrieved `url`. Fail-quiet — bookkeeping never costs a fetch."""
    try:
        url = (url or "").strip()
        if not url or normalise(url) in _PLUMBING:
            return
        led = _LEDGER.get()
        if led is None:
            led = {}
            _LEDGER.set(led)
        led.setdefault(url, Source(url, title, time.time(), via))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"citations: could not record {url!r} ({type(e).__name__})")


def sources() -> list[Source]:
    """Everything retrieved this turn, oldest first."""
    return sorted((_LEDGER.get() or {}).values(), key=lambda s: s.at)


def hosts() -> set[str]:
    return {s.host for s in sources() if s.host}


def unsupported(text: str) -> list[str]:
    """URLs in `text` that Mushegh never retrieved this turn — the fabricated citations.

    Matched by HOST, not by exact string: a model that shortens a real URL it was handed is
    citing the page it read, while one that invents a domain is not. The second is the failure.
    """
    known = hosts()
    bad: list[str] = []
    for url in _URL.findall(text or ""):
        host = normalise(url)
        if host and host not in known and host not in _PLUMBING and host not in bad:
            bad.append(host)
    return bad


def caveat(text: str) -> str:
    """One sentence to append when the reply cites something Mushegh never opened, else ""․"""
    bad = unsupported(text)
    if not bad:
        return ""
    named = " and ".join(bad[:2]) + (f" and {len(bad) - 2} others" if len(bad) > 2 else "")
    return (f" I should say, sir — I didn't actually open {named}. That reference is mine, "
            "not a source.")


#: 45.R2 — short-form attribution. The task asks for "from your calendar", "from the web", not a
#: list of URLs: this reply is spoken aloud to a man who is not holding a browser, and a butler who
#: recites a hostname is reciting something the owner cannot act on. Matched on the host, longest
#: pattern first, because `mail` must win over a bare `web` fallback and `notion` over `notes`.
_ATTRIBUTION: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("your calendar", ("calendar.google", "googleapis.com/calendar", "caldav", "ics.")),
    ("your mail", ("mail.google", "gmail", "imap.", "smtp.")),
    ("Notion", ("notion.so", "notion.com")),
    ("your vault", ("obsidian",)),
    ("the news", ("reuters", "bbc.", "ft.com", "guardian", "nytimes", "bloomberg", "wsj.")),
    ("the web", ()),                       # the fallback: any host that is not one of the above
)


def spoken() -> str:
    """Who this turn actually read from, in one spoken clause. "" when nothing was read.

    **Silence is the default and the most important behaviour here.** A reply that came entirely
    from Mushegh's own head must not be dressed up with a source: "from the web" on an answer nobody
    looked anything up for is noise, and noise is how an owner learns to stop believing attribution.
    So this returns "" on an empty ledger, and the reply is passed through byte-identical — which
    is the same property `test_citations.py` already asserts for the honesty caveat, and the reason
    attribution is a SEPARATE seam from it rather than bolted onto it.
    """
    got = hosts()
    if not got:
        return ""
    for phrase, needles in _ATTRIBUTION:
        if not needles:                      # the catch-all, only once nothing more specific matched
            break
        if any(n in h for h in got for n in needles):
            return f" {phrase[0].upper()}{phrase[1:]}, sir."
    return " The web, sir."                  # reached only via the catch-all above


def render() -> str:
    """The sources behind this turn, for the owner or the journal. "" when nothing was read."""
    got = sources()
    if not got:
        return ""
    lines = [f"{s.host}{' — ' + s.title if s.title else ''}" for s in got[:6]]
    more = f", and {len(got) - 6} more" if len(got) > 6 else ""
    return "Sources: " + "; ".join(lines) + more + "."


def _selfcheck() -> None:
    start()
    assert sources() == [] and unsupported("nothing here") == []

    record("https://www.reuters.com/world/article-123", "Reuters story", via="scrape_url")
    record("https://r.jina.ai/https://example.com", via="scrape_url")   # plumbing, not a source
    assert hosts() == {"reuters.com"}, hosts()
    assert "reuters.com" in render() and "jina" not in render(), render()

    # The failure this exists for: a plausible URL nobody fetched.
    assert unsupported("per https://bloomberg.com/x it rose") == ["bloomberg.com"]
    assert unsupported("see https://reuters.com/other-path") == []   # same host he did read
    assert unsupported("see https://WWW.Reuters.com/x") == []        # host match is case/www blind
    said = caveat("both https://bloomberg.com/x and https://ft.com/y agree")
    assert "bloomberg.com and ft.com" in said and "not a source" in said, said
    assert caveat("per reuters.com this morning") == "", "a bare host name is not a fabricated link"
    assert caveat("https://reuters.com/x says so") == ""

    # Recording the same page twice keeps the first title rather than blanking it.
    record("https://www.reuters.com/world/article-123", "", via="web_search")
    assert sources()[0].title == "Reuters story", sources()

    # A new turn starts empty: one session's reading must never vouch for another's claim.
    start()
    assert sources() == [] and unsupported("https://reuters.com/x") == ["reuters.com"]
    print("citations self-check OK")


if __name__ == "__main__":
    _selfcheck()
