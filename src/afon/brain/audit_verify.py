"""45.R10 — the audit trail is VERIFIABLE, or the word "tamper-evident" comes out of every document.

Until now this module's own first line called the trail "tamper-evident" and nothing verified
anything. That is the state D-25 and D-43 both warn about: a claim of a property nothing checks is
worse than no claim, because it teaches the reader to trust a guarantee that is not being made.
`45.R10` says either the JSONL carries an integrity check a reader can run **without the
framework**, or the word is struck. This is the first half.

**The chain.** Every line carries the digest of the line before it:

    prev = sha256(previous line's content, including its own prev)
    hash = sha256(this line's content without `hash`, plus `prev`)

so line N's digest is a function of every line before it, and editing line 3 invalidates every
digest from 3 onward. The first line chains onto `GENESIS` (64 zeros). A line is written with its
`hash` computed *after* the value-level secret scrub, because a digest of a line that is about to
be rewritten would be a digest of a line that never existed.

**What this does and does not prove, stated plainly because the temptation to overclaim is the
whole failure mode here.** It proves the file has not been altered *since it was written* — a
modified, reordered, or spliced line is found. It does **not** prove:

  * **truncation of the LAST line** is invisible. A file cut at the tail is indistinguishable from
    a day that simply ended. Fixing that needs an external witness, not a self-contained chain.
  * that nobody deleted a whole day, or rewrote the entire file and recomputed every digest. Anyone
    who can write the file can rebuild a perfectly valid chain. The defence is that the file is
    append-only on a host the owner controls, ideally with an off-host copy.
  * anything about a line that was never written.

There is a fourth state beyond clean/broken, and it exists because of the first gate run. A line
that carries no digest partway through a chain is a **GAP**, and a gap has two causes that cannot be
told apart from the file: `record()` failed to compute a digest (it never drops the line — losing an
audit line is worse than an unchained one), or someone spliced a line in. Calling it tampering would
make a crash look like an attack; calling it fine would let a splice through. So it is named,
counted, printed, and fails verification — the reader is told there is a gap, and is *not* told
which cause it has, because the file cannot say.

So: tamper-EVIDENT, not tamper-proof, and the distinction is the difference between a property
this codebase can honestly claim and one it cannot.

**Reading it needs no framework.** `python -m afon.brain.audit --verify <file-or-dir>` prints one
line per file and exits non-zero if anything is broken. It reads the file as text, recomputes
digests, and reports. No `afon` import, no settings, no keys — which matters because the reader who
most needs to check this is whoever is auditing, and they should not have to trust the thing they
are auditing in order to check it.

**Old files are not failures.** Any line written before this existed has no `hash` and is reported
`legacy` — unchained, so unverifiable, and said so rather than silently passing. A file whose
first line is `legacy` and whose later lines chain is reported as a chain that *starts* at that
line, because that is what it is.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

#: The digest the first line of a chain chains onto. 64 zeros reads as "nothing before this".
GENESIS = "0" * 64

#: A line's own digest covers its content EXCLUDING this field, plus the previous line's digest.
#: Excluding it is what makes the definition non-circular: the hash cannot contain itself.
_HASH_FIELD = "hash"
_PREV_FIELD = "prev"

LEGACY = "legacy"
CHAINED = "chained"
GAP = "gap"
BROKEN = "broken"


def canonical(line: dict) -> str:
    """The exact bytes a digest is taken over.

    Sorted keys and no whitespace, so the digest does not depend on the JSON formatter and a reader
    with a different one still recomputes the same value. `ensure_ascii=False` because the trail
    legitimately contains Cyrillic, French and German text, and escaping it would make the digest
    depend on an encoding choice rather than on the content.
    """
    return json.dumps(line, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def line_hash(line: dict, prev: str) -> str:
    """The digest for one line: its own content without `hash`, plus the previous line's digest."""
    body = {k: v for k, v in line.items() if k != _HASH_FIELD}
    return hashlib.sha256((prev + canonical(body)).encode("utf-8")).hexdigest()


def chain(lines: list[str]) -> list[dict]:
    """What a reader gets back: one verdict per line, in order, with the reason when it is bad.

    Pure and framework-free on purpose — it takes the raw text of a file and returns data, so it can
    be used by anything, including the verification of a trail this codebase later regrets writing.
    """
    out: list[dict] = []
    prev = GENESIS
    started = False
    for i, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            out.append({"line": i, "state": BROKEN, "why": f"not valid JSON: {e.msg}"})
            continue
        if not isinstance(obj, dict):
            out.append({"line": i, "state": BROKEN, "why": "a line is not a JSON object"})
            continue
        claimed = obj.get(_HASH_FIELD)
        if not claimed:
            # Unchained lines are the PAST, and only at the start of a file. Once a chain has
            # begun it is contiguous, so an unchained line after that is a GAP.
            #
            # A gap is deliberately NOT called tampering, and the reason is worth stating. Two very
            # different things produce one: `record()` failing to compute a digest (it never loses
            # the line — losing an audit line would be worse), and someone splicing a line in. An
            # unchained line carries no information, so nothing links across it and the two are
            # genuinely indistinguishable. Calling it "tampered" would make a crash look like an
            # attack; calling it "fine" would let a splice hide. So it is reported as its own state,
            # counted, printed, and fails the verification — the reader is told there is a gap and
            # not told which of the two causes it has.
            if started:
                out.append({"line": i, "state": GAP,
                            "why": "the chain has a gap here: a line that could not be chained, or "
                                   "one that was inserted. The two look identical, and both are worth "
                                   "knowing about"})
                continue
            out.append({"line": i, "state": LEGACY, "why": "no hash field (written before the chain)"})
            continue
        if not started:
            # The chain's first hashed line chains onto whatever came before it, which for a file
            # that opened with legacy lines is the last legacy line's position, not a real digest.
            prev = obj.get(_PREV_FIELD, GENESIS)
            started = True
        if obj.get(_PREV_FIELD) != prev:
            out.append({"line": i, "state": BROKEN,
                        "why": f"prev {str(obj.get(_PREV_FIELD))[:12]}… does not match the previous "
                               f"line's hash {prev[:12]}… — a line was removed, reordered or spliced"})
            continue
        want = line_hash(obj, prev)
        if want != claimed:
            out.append({"line": i, "state": BROKEN,
                        "why": f"content does not match its own hash (claims {claimed[:12]}…, "
                               f"recomputes {want[:12]}…) — this line was edited"})
            continue
        out.append({"line": i, "state": CHAINED, "hash": want})
        prev = want
    return out


def verify_text(text: str) -> dict:
    """Verify a whole file's text. Returns counts plus the first few problems.

    `ok` is False for a BROKEN line and for a GAP — neither is something a reader should be able to
    wave through. It stays True for a file that is entirely LEGACY, because a day of old unchained
    lines is the past, not a problem.
    """
    results = chain(text.splitlines())
    counts = {LEGACY: 0, CHAINED: 0, GAP: 0, BROKEN: 0}
    for r in results:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    problems = [r for r in results if r["state"] in (BROKEN, GAP)]
    return {"ok": not problems, "counts": counts, "lines": len(results),
            "problems": problems, "results": results}


def verify_path(path: Path) -> dict:
    """Verify one .jsonl file, or every .jsonl in a directory."""
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    per_file = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            per_file.append({"file": f.name, "ok": False, "why": f"unreadable: {e}"})
            continue
        rep = verify_text(text)
        per_file.append({"file": f.name, **rep})
    ok = all(r.get("ok") for r in per_file) if per_file else True
    return {"ok": ok, "files": per_file}


def main(argv: list[str] | None = None) -> int:
    """`python -m afon.brain.audit --verify <file-or-dir>` — no framework needed to trust this.

    Exits 0 when every chained line verifies, 1 when any line is broken. A file that is entirely
    `legacy` exits 0 with a warning, because an unchained old file is not tampering — it is the
    past. Pretending otherwise would train the reader to ignore the exit code.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip().splitlines()[0])
        print()
        print("usage: python -m afon.brain.audit_verify --verify <file.jsonl | directory>")
        print("exit 0 = every chained line verifies; 1 = something is broken or there is a gap.")
        return 0
    if argv[0] != "--verify":
        print(f"unknown argument {argv[0]!r}; the only verb is --verify", file=sys.stderr)
        return 2
    if len(argv) < 2:
        print("--verify needs a path", file=sys.stderr)
        return 2
    target = Path(argv[1])

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rep = verify_path(target)
    for f in rep["files"]:
        if "why" in f:
            print(f"  [FAIL] {f['file']}: {f['why']}")
            continue
        c = f["counts"]
        mark = "ok  " if f["ok"] else "FAIL"
        print(f"  [{mark}] {f['file']}: {c[CHAINED]} chained, {c[LEGACY]} legacy (unchained), "
              f"{c[GAP]} gap, {c[BROKEN]} broken, of {f['lines']} line(s)")
        for p in f["problems"][:10]:
            print(f"         line {p['line']}: {p['why']}")
        if len(f["problems"]) > 10:
            print(f"         ...and {len(f['problems']) - 10} more")
        if c[GAP] and not c[BROKEN]:
            print("         a gap is a line that could not be chained OR one that was inserted; the "
                  "two are indistinguishable from the file alone")
    print()
    print("VERIFIED" if rep["ok"] else "NOT VERIFIED — do not rely on this file")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
