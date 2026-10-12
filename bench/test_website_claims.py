"""The docs site may not claim things the code does not have.

`test_doc_paths.py` holds the repository's own documents to this rule. The website was not held to
anything, and it showed: on 2026-09-14 it advertised 80 tools when the registry had 152, eighteen
skills when there were twenty, a `glasses/` client deleted in commit 2d078f4, a wake-word trainer at
a path that never existed, and — worst of the set — two Porcupine settings the config had removed
because nothing read them. That last one is not a typo, it is a reader buying a Picovoice key for a
capability that is not there.

A docs site is a promise to someone who has not cloned the repo yet. They cannot check it, so this
has to.

What it holds:
  * every `MUSHEGH_*` setting the site names is real (a `Settings` field, or a declared env-read);
  * every file path the site cites exists in the tree;
  * the generated tool data matches the live registry, so the tool page cannot silently go stale;
  * the skills the site lists are the skills on disk.

SKIPS cleanly when `website/` is absent: the site is deployed from a gitignored directory, so a
fresh clone legitimately does not have it, and a gate that fails on a clean checkout teaches people
to ignore gates.

    uv run python bench/test_website_claims.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  [{detail}]")


#: Names read straight from the environment rather than through `Settings` — the VPS ticker and the
#: deploy script own these, and they are real despite not being config fields.
ENV_ONLY = {
    "MUSHEGH_TICKER_HOST", "MUSHEGH_TICKER_PORT", "MUSHEGH_TICKER_TZ", "MUSHEGH_TICKER_TOKEN",
    "MUSHEGH_VPS", "MUSHEGH_VPS_DIR", "MUSHEGH_PROTOCOL_", "MUSHEGH_STATE_DIR", "MUSHEGH_TRACE_DIR",
}

_SETTING_RE = re.compile(r"MUSHEGH_[A-Z0-9_]+")
_PATH_RE = re.compile(r"<code>([A-Za-z0-9_./\-]+\.(?:py|sh|md|json|ts|tsx|onnx|npy|toml|yml|yaml))</code>")


def main() -> None:
    site = ROOT / "website" / "app"
    if not site.is_dir():
        print("  SKIP  website/ is not present (it is deployed from a gitignored directory)")
        print("\n=== 0/0 checks passed ===")
        return

    pages = sorted(site.rglob("*.tsx"))
    text = {p: p.read_text(encoding="utf-8") for p in pages}
    check(f"the site has pages to check ({len(pages)} .tsx files)", len(pages) >= 20, str(len(pages)))

    print("\n[1] every setting the site documents is one the code reads")
    from mushegh.config import Settings

    known = {("MUSHEGH_" + n).upper() for n in Settings.model_fields} | ENV_ONLY
    bad: dict[str, list[str]] = {}
    for p, t in text.items():
        for name in sorted(set(_SETTING_RE.findall(t))):
            if name not in known:
                bad.setdefault(name, []).append(p.name)
    for name, where in sorted(bad.items()):
        print(f"        {name} cited in {', '.join(sorted(set(where)))}")
    check("no page names a setting that nothing reads", not bad,
          f"{len(bad)} phantom settings — a reader will set them and nothing will happen")

    print("\n[2] every path the site cites exists")
    missing: list[str] = []
    for p, t in text.items():
        for cited in sorted(set(_PATH_RE.findall(t))):
            if "/" not in cited:
                continue                       # a bare filename is prose, not a path claim
            if not any((ROOT / (base + cited)).exists() for base in ("", "src/mushegh/")):
                missing.append(f"{p.name}: {cited}")
    for m in missing:
        print(f"        {m}")
    check("no page cites a file that is not in the tree", not missing, str(missing))

    print("\n[3] the generated tool data is the live registry")
    from mushegh.brain.tools import tool_names

    gen = ROOT / "website" / "app" / "tools" / "tools.generated.json"
    check("the generated tool file exists", gen.is_file(), str(gen))
    if gen.is_file():
        data = json.loads(gen.read_text(encoding="utf-8"))
        live = set(tool_names())
        listed = {t["name"] for t in data["tools"]}
        check(f"the count matches the registry ({data['count']} vs {len(live)})",
              data["count"] == len(live),
              "regenerate: uv run python bench/dump_tools.py --json > "
              "website/app/tools/tools.generated.json")
        check("...and so do the names, not just the total",
              listed == live, str(sorted(live ^ listed))[:200])
        check("every listed tool declares which group advertises it",
              all(t.get("group") for t in data["tools"]))

    print("\n[4] the skills the site lists are the skills on disk")
    on_disk = {p.stem for p in (ROOT / "skills").glob("*.md")}
    skills_page = (site / "skills" / "page.tsx")
    if skills_page.is_file():
        listed_skills = set(re.findall(r'name:\s*"([a-z0-9\-]+)"', skills_page.read_text(encoding="utf-8")))
        check(f"every skill on disk is documented ({len(on_disk)} files)",
              on_disk <= listed_skills, f"undocumented: {sorted(on_disk - listed_skills)}")
        check("...and no documented skill is missing from disk",
              listed_skills <= on_disk, f"phantom: {sorted(listed_skills - on_disk)}")
        head = re.search(r"Skills — the (\d+) on-demand playbooks", skills_page.read_text(encoding="utf-8"))
        check("the headline count matches the files",
              bool(head) and int(head.group(1)) == len(on_disk),
              f"page says {head.group(1) if head else '?'}, disk has {len(on_disk)}")

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
