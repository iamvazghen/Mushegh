"""The outbound-URL guard — what Mushegh refuses to fetch, and why it cannot promise safety.

The claim under test is narrow and worth stating: obvious attempts are refused at
parse time, a hostname that resolves privately is refused, and one resolving BOTH
ways is refused too. The rebinding gap is asserted as a *reported* property rather
than a prevented one, because pretending otherwise would be the dangerous part.

    uv run python bench/test_netguard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.shared.netguard import (  # noqa: E402
    Verdict,
    check_url,
    classify_host,
    is_safe,
    resolve_and_classify,
)

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def fake_resolver(table: dict[str, list[str]]):
    """A resolver that answers from a fixed table, so no DNS is touched."""
    def resolve(host: str, port: int):
        if host not in table:
            raise OSError("no such host")
        # getaddrinfo-shaped: (family, type, proto, canonname, sockaddr)
        return [(10, 1, 6, "", (ip, 0)) for ip in table[host]]
    return resolve


PUBLIC = fake_resolver({"example.com": ["93.184.216.34"], "cdn.example.com": ["1.1.1.1"]})
PRIVATE = fake_resolver({"internal.corp": ["10.0.0.5"], "split.example.com": ["93.184.216.34", "127.0.0.1"]})


def main() -> None:
    print("[1] scheme and shape are refused before anything is resolved")
    for bad, why in [
        ("", "empty"),
        ("   ", "empty"),
        ("file:///C:/Users/iamva/.env", "file"),
        ("gopher://example.com", "gopher"),
        ("data:text/html,<script>", "data"),
        ("ftp://example.com/x", "ftp"),
        ("javascript:alert(1)", "javascript"),
    ]:
        v = check_url(bad)
        check(f"refused {why}: {bad[:34]!r}", not v.ok, v.reason)

    check("unparseable is refused", not check_url("http://").ok)
    check("a non-string is refused, not raised on", not check_url(None).ok)  # type: ignore[arg-type]

    print("[2] embedded credentials are refused — they leak into logs and referrers")
    for bad in (
        "https://user:pass@example.com/",
        "https://token@example.com/",
        "https://:secret@example.com/",
    ):
        v = check_url(bad)
        check(f"refused {bad}", not v.ok and "credential" in v.reason, v.reason)

    print("[3] literal addresses are judged by what they are")
    for bad in (
        "http://127.0.0.1:8766/hud.json",
        "http://localhost:8766/",
        "http://10.0.0.5/",
        "http://192.168.1.1/admin",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://0.0.0.0/",
        "http://metadata.google.internal/",
        "http://printer.local/",
        "http://db.internal/",
        "http://host.lan/",
        "http://foo.home.arpa/",
    ):
        v = check_url(bad)
        check(f"refused {bad}", not v.ok, v.reason)

    print("[4] an IPv4-mapped IPv6 loopback cannot hide behind its costume")
    check("::ffff:127.0.0.1 refused", not check_url("http://[::ffff:127.0.0.1]/").ok)
    check("::ffff:10.0.0.1 refused", not check_url("http://[::ffff:10.0.0.1]/").ok)

    print("[5] a name that resolves privately is refused")
    v = check_url("https://internal.corp/secret", resolver=PRIVATE)
    check("private answer refused", not v.ok, v.reason)
    check("and it says which address gave it away", "10.0.0.5" in v.reason, v.reason)

    print("[6] a name that resolves BOTH ways is refused, not allowed on the first answer")
    v = check_url("https://split.example.com/", resolver=PRIVATE)
    check("split-horizon refused", not v.ok, v.reason)
    check("the private answer is named", "127.0.0.1" in v.reason, v.reason)

    print("[7] a name that will not resolve is not a pass")
    v = check_url("https://nowhere.invalid/", resolver=PUBLIC)
    check("unresolvable refused", not v.ok, v.reason)
    check("empty answer refused", not resolve_and_classify("x", resolver=lambda h, p: []).ok)

    print("[8] a genuinely public URL passes")
    v = check_url("https://example.com/page", resolver=PUBLIC)
    check("public name allowed", v.ok, v.reason)
    check("public literal allowed", check_url("https://93.184.216.34/page").ok)
    check("http is allowed too (some local sites have no TLS)", check_url("http://93.184.216.34/").ok)

    print("[9] the rebinding gap is REPORTED, never claimed closed")
    v = check_url("https://example.com/", resolver=PUBLIC)
    check("a resolved name is flagged rebind_possible", v.rebind_possible, "claimed safe")
    check("a literal address is not", not check_url("https://93.184.216.34/").rebind_possible)
    check("a parse-time refusal is not", not check_url("http://127.0.0.1/").rebind_possible)

    print("[10] the local allowlist is explicit and per-call")
    ok = check_url("http://127.0.0.1:8766/hud.json", allow_private_hosts=("127.0.0.1",))
    check("allowlisted loopback passes when named", ok.ok, ok.reason)
    check("and does not pass when not named", not check_url("http://127.0.0.1:8766/hud.json").ok)
    check("allowlist is case-insensitive",
          check_url("http://localhost:8766/", allow_private_hosts=("LOCALHOST",)).ok)
    check("allowlist does not leak to other hosts",
          not check_url("http://10.0.0.5/", allow_private_hosts=("127.0.0.1",)).ok)

    print("[11] host classification agrees with the full check")
    for host, expect in [
        ("example.com", True), ("", False), ("localhost", False),
        ("a.local", False), ("10.0.0.1", False), ("8.8.8.8", True),
        ("EXAMPLE.com.", True),
    ]:
        check(f"classify {host!r} -> {expect}", classify_host(host)[0] is expect, classify_host(host)[1])

    print("[12] the boolean form agrees with the verdict form")
    check("is_safe mirrors check_url for public", is_safe("https://example.com/", resolver=PUBLIC))
    check("is_safe mirrors check_url for private", not is_safe("http://127.0.0.1/", resolver=PUBLIC))
    check("Verdict is falsy when blocked", not bool(Verdict(ok=False, reason="x")))
    check("Verdict is truthy when allowed", bool(Verdict(ok=True, reason="x")))

    print("[13] the tools' shared guard refuses what the policy refuses")
    # The policy existing is not the claim; the tools USING it is. This asserts
    # the call sites, so a later refactor cannot quietly stop consulting it.
    try:
        from mushegh.brain.tools.base import guard_url
    except Exception as exc:  # noqa: BLE001 — report, do not hide a broken import
        check("tools.base imports", False, f"{type(exc).__name__}: {exc}")
    else:
        check("a public URL passes silently", guard_url("https://example.com/") == "")
        refusal = guard_url("http://169.254.169.254/latest/meta-data/")
        check("metadata endpoint refused", bool(refusal) and "sir" in refusal, refusal)
        check("and the refusal names the reason", "not public" in refusal or "internal" in refusal, refusal)
        check("loopback refused", bool(guard_url("http://127.0.0.1:8766/")))
        check("an allowlisted local endpoint is permitted",
              guard_url("http://127.0.0.1:8766/hud.json", allow_private_hosts=("127.0.0.1",)) == "")

    print(f"\n=== checks passed ===\n{passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()