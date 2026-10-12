"""J5.1 — one canonical roadmap, and no roadmap may cite a file that is not there.

Two roadmaps existed side by side: TODO.md (live, edited daily) and docs/MASTER-PLAN.md (dated
2026-06-24 and still opening with "single source of remaining work"). Nothing said which one to
believe, and the failure that produces is not confusion but confident citation — MASTER-PLAN
asserted a `bench/train_wakeword.py` that has never existed in this repo, and the claim propagated
to four places (.env, config.py, edge/wake_word.py) before `ls bench/` caught it.

So two checks, and the second is the one with teeth:

  * exactly one file claims to be canonical, and the other points at it by name;
  * every repo path a roadmap cites in backticks exists — resolved from the repo root OR under
    src/mushegh/, because these documents cite modules both ways (`brain/tools/base.py` and
    `src/mushegh/config.py` both appear).

A doc must be able to say that something is ABSENT — half of TODO.md's value is recording what was
found missing. So a citation is exempt when its own sentence says so ("there is no X", "X has never
existed", "New `X`" for planned work). The cue is looked for in a small window around the line
rather than on the line itself, because these entries wrap: the negation usually sits one line
above the path it negates.

Hermetic: reads markdown and stats files. No network, no imports from src/.

    uv run python bench/test_doc_paths.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]

#: The roadmap surface. Deliberately not skills/ (test_skill_docs_resolve.py owns those) and not
#: every markdown file in the tree — this gate is about documents that direct future work.
DOCS = ["TODO.md", "README.md", "SECURITY.md", *sorted(p.name for p in (ROOT / "docs").glob("*.md"))]

#: Top-level directories whose backticked mentions are real path claims. A bare `config.py` is
#: ambiguous prose; `src/mushegh/config.py` or `brain/tools/base.py` is a claim about the tree.
_ROOTS = ("bench", "src", "scripts", "clients", "personality", "docs", "vps", "termux",
          "brain", "edge", "shared", "skills", "website")
_PATH_RE = re.compile(r"`([A-Za-z0-9_.\-/]+\.(?:py|sh|md|json|ts|onnx|npy|toml|yml|yaml))(?::\d+)?`")
#: Directories too, and for the same reason. README advertised a `glasses/` TypeScript bridge as a
#: shipped, "on" integration for weeks after the scaffold was deleted (commit 2d078f4) — a reader
#: cloning the repo goes looking for a capability that is not there. A file-only rule cannot see it.
_DIR_RE = re.compile(r"`([A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*/)`")

#: Cues that a citation is deliberately about something absent, planned, or removed.
_ABSENT_CUES = (
    "never existed", "does not exist", "doesn't exist", "no longer exists", "there is no",
    "is gone", "was deleted", "deleted", "removed", "planned", "new `", "would be", "unfinished",
    "does not yet", "not yet", "to be created", "absent", "missing", "stale", "instead of",
)
_WINDOW = 2   # lines either side: these entries wrap, and the negation usually leads the path

#: State directories the RUNTIME creates under ~/.mushegh, named in docs (SECURITY.md's never-commit
#: list, the memory-hygiene job's output). They are correct citations of things that are correctly
#: absent from the tree, so requiring them to exist would be requiring the repo to be dirty.
#: Directories that live under the STATE root (`~/.mushegh`), not in the repo — so their absence from a
#: checkout is correct, not a phantom path. `traces/` and `screenshots/` joined the list when 37.R4
#: started naming stores by their state-relative names.
_RUNTIME_DIRS = {"audit/", "backups/", "memory/learned/archive/", "memory/journal/archive/",
                 "traces/", "screenshots/", "faces/", "run/", "shell/"}

passed = failed = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def _exists(cited: str) -> bool:
    """True if the path resolves from the repo root or under src/mushegh/ (docs cite both ways)."""
    return (ROOT / cited).exists() or (ROOT / "src" / "mushegh" / cited).exists()


def _exempt(lines: list[str], i: int) -> bool:
    window = " ".join(lines[max(0, i - _WINDOW):i + _WINDOW + 1]).lower()
    return any(cue in window for cue in _ABSENT_CUES)


def main() -> None:
    print("[1] exactly one roadmap is canonical, and the other says so")
    todo = (ROOT / "TODO.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "MASTER-PLAN.md").read_text(encoding="utf-8")
    check("TODO.md" in plan[:2000],
          "MASTER-PLAN.md points at TODO.md in its opening",
          "a superseded roadmap that does not name its successor is still cited")
    check("superseded" in plan[:2000].lower(),
          "MASTER-PLAN.md is marked superseded up front")
    check("single source of remaining work" not in plan[:2000].lower()
          or "superseded" in plan[:2000].lower(),
          "MASTER-PLAN.md no longer claims to be the single source")
    check("canonical" in todo[:3000].lower(),
          "TODO.md states that it is the canonical roadmap")

    print("\n[2] every repo path a roadmap cites is really there")
    for name in DOCS:
        path = ROOT / name if (ROOT / name).exists() else ROOT / "docs" / name
        if not path.exists():
            check(False, f"{name} exists to be checked")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        bad = []
        for i, line in enumerate(lines):
            for cited in _PATH_RE.findall(line):
                if not cited.startswith(_ROOTS) or "/" not in cited:
                    continue        # bare filenames are prose, not path claims
                if not _exists(cited) and not _exempt(lines, i):
                    bad.append(f"{name}:{i + 1} `{cited}`")
            for cited in _DIR_RE.findall(line):
                if cited in _RUNTIME_DIRS:
                    continue
                if not _exists(cited.rstrip("/")) and not _exempt(lines, i):
                    bad.append(f"{name}:{i + 1} `{cited}` (directory)")
        check(not bad, f"{name}: {len(lines)} lines, no phantom paths",
              "\n        " + "\n        ".join(bad[:12]))

    # O1.5 (p=0.77): "local-first" as a PROJECT label overpromises — state is self-hosted, but the
    # reasoning models are remote by default and the VPS has no GPU. Component-level uses stay
    # legitimate (the audio path really is local), so this guards only the four places that speak
    # for the whole project. A tagline is exactly the kind of claim that drifts back.
    # A *quoted* "local-first" is discussing the label; an unquoted one is claiming it. That
    # distinction is the whole rule, and it needs no exemption list to maintain.
    unquoted = re.compile(r'(?<![\'"`])local-first', re.I)
    for name in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "src/mushegh/__init__.py"):
        hits = [
            f"{name}:{i + 1}"
            for i, ln in enumerate((ROOT / name).read_text(encoding="utf-8").splitlines())
            if unquoted.search(ln)
        ]
        check(not hits, f"{name}: no project-level 'local-first' claim", str(hits))

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
