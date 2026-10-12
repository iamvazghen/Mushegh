"""Existence-check candidate repos without consuming the GitHub API rate limit.

`api.github.com` allows 60 core calls/hour unauthenticated and we just exhausted it.
A plain `HEAD https://github.com/<owner>/<repo>` is an ordinary web request: it costs
nothing from the API budget and answers exactly the question we care about here — does
this path exist, or did the model invent it?

This proves EXISTENCE ONLY. It says nothing about licence or activity, so its output is
recorded separately and must never be presented as a verified licence.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mushegh-utility-research",
}


def exists(full: str) -> tuple[bool | None, str]:
    url = f"https://github.com/{full}"
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return (resp.status == 200), f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302):
            return None, f"redirect {exc.code} (repo may have moved/renamed)"
        if exc.code in (403, 429):
            return None, f"HTTP {exc.code} (rate-limited, not a 404)"
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    out: dict[str, dict] = {}
    dead: list[str] = []
    unknown: list[str] = []
    ok = 0

    for name, reason in raw.items():
        if isinstance(reason, str) and reason.startswith("{"):
            reason = ""
        found, detail = exists(name)
        entry = {
            "repo": name,
            "exists": found,
            "detail": detail,
            "reason": reason,
            "existence_verified": found is True,
            "licence_verified": False,
        }
        out[name] = entry
        if found is True:
            ok += 1
        elif found is False:
            dead.append(name)
        else:
            unknown.append(name)
        print(f"{'OK  ' if found else ('DEAD' if found is False else '????')} {name}  {detail}")

    result = {
        "exists": ok,
        "does_not_exist": dead,
        "unknown": unknown,
        "results": out,
    }
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("tools/existence_checked.json")
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nEXISTS {ok}   DOES-NOT-EXIST {len(dead)}   UNKNOWN {len(unknown)}")
    if dead:
        print("DO NOT CITE (no such repo):")
        for d in dead:
            print(f"  - {d}")
    if unknown:
        print("could not determine (redirect/rate-limit):")
        for u in unknown:
            print(f"  - {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())