"""Verify candidate open-source repos against the live GitHub API and record licence + activity.

Why this exists
---------------
A repository name recalled from memory is not evidence. This script turns a bare
`owner/repo` string into a record with the fields that actually decide whether the project
can be adopted: licence, star count, last push, archived flag, and fork status.

Rate-limit reality
------------------
Unauthenticated GitHub allows 60 core calls/hour and 10 search calls/hour. One
`/search/repositories?q=user:<owner>&per_page=100` call returns every repo for an owner
WITH full metadata, so grouping candidates by owner is the cheapest way to verify a large
list. A direct `/repos/{owner}/{repo}` call costs the same but verifies exactly one repo.
This script therefore prefers the owner-grouped search, falling back to a direct call only
for owners with a single candidate.

Usage
-----
    python tools/verify_repos.py candidates.json [--out verified.json]

`candidates.json` is either `["owner/repo", ...]` or `{"repo": "reason", ...}`.
Everything it cannot verify is reported in `unverified`, not silently dropped.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "https://api.github.com"
UA = {"User-Agent": "mushegh-utility-research", "Accept": "application/vnd.github+json"}


def _get(url: str) -> tuple[int, object | None]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:  # noqa: BLE001 - network shapes vary; report, never guess
        print(f"  ! {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0, None


def rate_remaining() -> tuple[int, int]:
    status, body = _get(f"{API}/rate_limit")
    if status != 200 or not isinstance(body, dict):
        return (-1, -1)
    core = body.get("resources", {}).get("core", {})
    search = body.get("resources", {}).get("search", {})
    return (int(core.get("remaining", -1)), int(search.get("remaining", -1)))


def normalise(name: str) -> str:
    """`owner/repo`, tolerant of URLs, whitespace, and a missing owner."""
    n = name.strip().rstrip("/")
    if n.startswith("http"):
        parts = [p for p in n.split("/") if p]
        n = "/".join(parts[-2:])
    n = n.removesuffix(".git")
    n = n.lstrip("@").strip()
    return n


def verify_direct(name: str) -> dict | None:
    status, body = _get(f"{API}/repos/{name}")
    if status != 200 or not isinstance(body, dict):
        return None
    return body


def verify_by_owner(owner: str, wanted: set[str]) -> dict[str, dict]:
    """One search call returns up to 100 repos for an owner, each with full metadata."""
    found: dict[str, dict] = {}
    page = 1
    while len(found) < len(wanted) and page <= 3:
        status, body = _get(
            f"{API}/search/repositories?q=user:{owner}&per_page=100&page={page}"
        )
        if status != 200 or not isinstance(body, dict):
            break
        items = body.get("items") or []
        if not items:
            break
        for repo in items:
            full = (repo.get("full_name") or "").lower()
            if full in wanted:
                found[full] = repo
        if len(items) < 100:
            break
        page += 1
    return found


def summarise(repo: dict, reason: str = "") -> dict:
    lic = repo.get("license") or {}
    return {
        "repo": repo.get("full_name"),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "licence": (lic.get("spdx_id") or lic.get("name") or "NOASSERTION"),
        "pushed_at": repo.get("pushed_at"),
        "archived": bool(repo.get("archived")),
        "fork": bool(repo.get("fork")),
        "open_issues": repo.get("open_issues_count"),
        "description": (repo.get("description") or "")[:220],
        "topics": repo.get("topics") or [],
        "reason": reason,
        "verified": True,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    out_path = None
    if "--out" in sys.argv:
        out_path = sys.argv[sys.argv.index("--out") + 1]

    raw = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        candidates = {normalise(k): str(v) for k, v in raw.items()}
    else:
        candidates = {normalise(c): "" for c in raw}

    by_owner: dict[str, set[str]] = defaultdict(set)
    for full in candidates:
        if "/" not in full:
            continue
        owner, repo = full.split("/", 1)
        by_owner[owner].add(f"{owner}/{repo}".lower())

    core_left, search_left = rate_remaining()
    print(f"budget: core={core_left} search={search_left}  candidates={len(candidates)}")

    verified: dict[str, dict] = {}
    unverified: dict[str, str] = {}
    budget_hit = False

    for owner, wanted in sorted(by_owner.items()):
        if budget_hit:
            for w in wanted:
                unverified[w] = candidates.get(w, "")
            continue

        if len(wanted) > 1 and search_left > 0:
            search_left -= 1
            found = verify_by_owner(owner, wanted)
            for full in wanted:
                if full in found:
                    verified[full] = summarise(found[full], candidates.get(full, ""))
                else:
                    unverified[full] = candidates.get(full, "")
        else:
            if core_left <= 0:
                budget_hit = True
                for w in wanted:
                    unverified[w] = candidates.get(w, "")
                continue
            core_left -= 1
            full = sorted(wanted)[0]
            repo = verify_direct(full)
            if repo:
                verified[full] = summarise(repo, candidates.get(full, ""))
            else:
                unverified[full] = candidates.get(full, "")

        if (len(verified) + len(unverified)) % 10 == 0:
            print(f"  progress: {len(verified)} verified / {len(unverified)} unverified")

    missing_syntax = [c for c in candidates if "/" not in normalise(c)]
    for m in missing_syntax:
        unverified[m] = candidates[m]

    result = {
        "verified": verified,
        "unverified": unverified,
        "budget_exhausted": budget_hit,
        "counts": {
            "candidates": len(candidates),
            "verified": len(verified),
            "unverified": len(unverified),
        },
    }

    if out_path:
        Path(out_path).write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"wrote {out_path}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    print(
        f"\nVERIFIED {len(verified)}  UNVERIFIED {len(unverified)}  "
        f"budget_exhausted={budget_hit}"
    )
    if unverified:
        print("\nunverified (do NOT present these as confirmed):")
        for name, why in sorted(unverified.items()):
            print(f"  - {name}  {why[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())