"""Doc integrity gate for the Afon documentation tree.

This exists because a shell write corrupted `01-brain-core-intelligence.md`
during development: two control characters were injected into words, and a whole
`## Open questions` section was silently dropped. Neither was noticed until the
file was read back afterwards. A gate that had run immediately would have
caught both.

What it checks, across every markdown file in docs/:

  1. **No control characters.** Anything below 0x20 other than tab/newline is
     corruption, not content.
  2. **No U+FFFD.** A replacement character means text was decoded wrong.
  3. **Structure.** Every file that had a `##` heading still has one, and each
     document ends with a newline rather than mid-sentence.
  4. **No phantom source paths.** Rule 1 of subsystems/README.md: a cited
     `src/...`, `bench/...`, `tools/...`, `scripts/...` or `deploy/...` path that
     does not exist is a path someone will trust. Paths the documents
     themselves record as *not yet written* are allowed and listed separately.
  4. **No dead surfaces.** A cited path can exist and still be a lie, if nothing
     imports it and nothing launches it. That is harder to see than a phantom path,
     because a dead module reads as finished work.
  5. **Decision numbers.** DECISIONS.md must have no duplicates and no gaps.

Usage:
    python bench/test_doc_integrity.py           # all documents
    python bench/test_doc_integrity.py --verbose # print every check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PATH_RE = re.compile(
    r"`((?:src/afon|bench|tools|scripts|deploy)/[A-Za-z0-9_./-]+)`"
)
DECISION_RE = re.compile(r"^## D-(\d+)", re.M)

#: Paths the documents explicitly record as planned but not yet written. These
#: are named as gaps, so they are allowed to be absent - and are reported, so
#: that a gap silently becoming real is noticed.
KNOWN_PLANNED = {
    "bench/test_document_revise.py",
    "bench/test_health_ingest.py",
    "bench/test_media_queue.py",
    "bench/test_vacuum_schedule.py",
    "bench/test_adversarial_prompts.py",
    "bench/test_print_no_content_leak.py",
    "bench/test_egress_log.py",
    "bench/test_digest_timing.py",
    "tools/coding.py",
}

#: `tools/call` and `tools/list` are JSON-RPC method names, not files. They match
#: the path pattern but are never paths, and a gate that cries wolf gets ignored.
NOT_PATHS = {"tools/call", "tools/list"}

#: Files cited on purpose because the citation IS the record: a decision removed
#: them, a cancelled migration proposed them, or a plan that was wrong named
#: them. Allowed to not resolve, and listed so the removal stays visible.
HISTORICALLY_REMOVED = {
    # D-26 deleted S24's relation layer; DECISIONS.md names the deleted modules.
    "src/afon/brain/graph.py",
    "src/afon/brain/tools/graphmem.py",
    # D-02 cancelled the Postgres/vector migration, so S30-MIGRATION.md describes
    # a set of files that were never built. That is the document's subject.
    "bench/test_postgres_vectors.py",
    "bench/test_store_migration_snapshot.py",
    "src/afon/brain/sql/postgres_vectors.sql",
    # ...and the same migration named its client in 30-persistent-memory.md.
    "src/afon/brain/postgres_client.py",
    "src/afon/brain/postgres_vectors.py",
    # 27-contextual-awareness.md records this as the gate a planned room-presence
    # source still owes. It has not been written, and the document says so.
    "bench/test_room_presence.py",
    # MASTER-PLAN.md names this as part of the plan that was wrong, which is the
    # sentence's whole point.
    "bench/train_wakeword.py",
}

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    (PASSED if ok else FAILED).append(label)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    files = sorted(DOCS.rglob("*.md"))
    print(f"checking {len(files)} markdown documents under {DOCS}\n")

    print("=== 1. no control characters, no replacement characters ===")
    dirty: list[tuple[Path, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        bad = [(i, hex(ord(c))) for i, c in enumerate(text)
               if ord(c) < 9 or 11 <= ord(c) < 32]
        if bad:
            dirty.append((path, f"{len(bad)} control char(s), first at offset {bad[0][0]} {bad[0][1]}"))
        if "�" in text:
            dirty.append((path, "contains U+FFFD replacement character"))
    check("no document carries a control or replacement character", not dirty,
          "; ".join(f"{p.name}: {why}" for p, why in dirty)[:200])

    print("\n=== 2. structure: headings present, files end cleanly ===")
    unheaded = [p for p in files
                if len(p.read_text(encoding="utf-8", errors="replace")) > 800
                and "## " not in p.read_text(encoding="utf-8", errors="replace")]
    check("every substantial document has a section heading", not unheaded,
          ", ".join(p.name for p in unheaded))
    unterminated = [p for p in files
                    if not p.read_text(encoding="utf-8", errors="replace").rstrip().endswith((".", "?", "!", ")", "`", "|", ")", "\"", "—", "*"))]
    check("no document ends mid-sentence", not unterminated,
          ", ".join(p.name for p in unterminated))

    print("\n=== 3. no phantom source paths (subsystems/README.md rule 1) ===")
    phantoms: list[tuple[Path, str]] = []
    planned_present: list[str] = []
    historic: list[str] = []
    total_refs = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for rel in sorted(set(PATH_RE.findall(text))):
            if rel in NOT_PATHS:
                continue
            total_refs += 1
            if (ROOT / rel).exists():
                if rel in KNOWN_PLANNED:
                    planned_present.append(rel)
                continue
            # The subsystem Structure tables use a house shorthand: `tools/x.py`
            # means `src/afon/brain/tools/x.py`. Resolve it before calling it a
            # phantom, or the gate cries wolf on the docs' own convention.
            shorthand = None
            if rel.startswith("tools/"):
                candidate = ROOT / "src" / "afon" / "brain" / rel
                if candidate.exists():
                    shorthand = candidate
            if shorthand is not None:
                continue
            if rel in HISTORICALLY_REMOVED:
                historic.append(rel)
                continue
            # A path may legitimately be named as missing, in which case the
            # sentence around it says so.
            line = next((l for l in text.splitlines() if f"`{rel}`" in l), "")
            if rel in KNOWN_PLANNED or re.search(
                    r"not (?:yet )?(?:exist|built|written|created)|planned|does not exist|"
                    r"no such|absent|missing|removed|deleted|cancelled|canceled", line, re.I):
                continue
            phantoms.append((path, rel))
    check(f"every cited source path exists ({total_refs} references)", not phantoms,
          "; ".join(f"{rel} in {p.name}" for p, rel in phantoms[:5])[:220])
    if historic:
        print(f"         allowed: {len(historic)} historical citation(s) of code a decision "
              f"removed: {', '.join(sorted(historic))}")
    if planned_present:
        print(f"         note: {len(planned_present)} recorded gap(s) now EXIST and the text "
              f"should be updated: {', '.join(sorted(planned_present)[:4])}")

    print("\n=== 4. no dead surface claims: a 'Surfaces' module nothing reaches ===")
    # A path that exists but is imported by nothing is harder to catch than a phantom
    # path, because it reads as finished work. mynews.py was exactly that: on disk,
    # named as S41's surface, unreachable since 41.R4 closed the D-34 path.
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import verify_surface_claims as vsc  # type: ignore

        result = vsc.analyze()
        claims = result["claims"]
        unwired = result["unwired"]
        bad_controls = result["bad_controls"]
        check(f"every 'Surfaces' module is reachable ({len(claims)} claims)", not unwired,
              ", ".join(f"{rel}:{line}" for rel, line in unwired[:5])[:220])
        check("the surface checker's own control cases hold", not bad_controls,
              ", ".join(c[0] for c in bad_controls)[:200])
    except Exception as error:  # noqa: BLE001
        check("surface-claim checker ran", False, f"{type(error).__name__}: {error}")

    print("\n=== 5. decision numbers: no duplicates, no gaps ===")
    decisions = DOCS / "DECISIONS.md"
    if decisions.is_file():
        numbers = [int(n) for n in DECISION_RE.findall(decisions.read_text(encoding="utf-8"))]
        dupes = sorted({n for n in numbers if numbers.count(n) > 1})
        gaps = [n for n in range(1, (max(numbers) if numbers else 0) + 1) if n not in numbers]
        check("no duplicate decision numbers", not dupes, ", ".join(map(str, dupes)))
        check("no gaps in the decision range", not gaps, ", ".join(map(str, gaps)))
        print(f"         D-01..D-{max(numbers) if numbers else 0}, {len(numbers)} decisions")
    else:
        check("DECISIONS.md exists", False)

    print(f"\nPASSED {len(PASSED)}   FAILED {len(FAILED)}")
    for name in FAILED:
        print(f"  - {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
