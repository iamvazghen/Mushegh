# S06 — Document Creation

> **One line:** One creation path that writes, reads back, and only then says the document exists — reading was always the strong half.
> **Status:** half-built — reading is strong, *creation* is three ad-hoc writers · **Registry:** S06 · 3/3 floor, 0/4 raise, 0/1 elite
> **Milestones:** none assigned in [../ROADMAP.md](../ROADMAP.md) · **Decisions:** D-22, D-25, D-54, D-57, D-71

## Purpose

The registry's own status string is the honest summary: half-built, because reading
documents was good and creating them was three separate writers with no shared owner.
`write_vault` wrote a file and announced success. `notion_create_page` POSTed, threw away
the response including the page id, and announced success. Nothing wrote local markdown
at all. Each reported success on the strength of not having raised, which is a different
claim from "it is there".

That distinction is the whole floor, and it is why `create()` writes, reads back, and
compares. Success is reported only when the words come back. When they do not, Afon says
which half happened — "I wrote it but could not confirm it" and "I could not write it" are
different sentences, and the owner needs to know which. The failures hiding in this gap
are not exotic: a Notion parent id that resolves to an archived page, a vault path on a
mount that went read-only since startup, a title that sanitises down to nothing. Every
one of them previously ended with Afon reporting a document that did not exist.

Creating a document is also the point where the vault earns its authority. Markdown in
the vault is the source of truth and the database is a cache (D-22), so a document the
owner will read in a text editor in 2036 has to land in markdown, with a reconciliation
path that can lose to a file (D-22), and — once in-place editing lands — with superseded
versions tombstoned rather than silently replaced (D-25, which has no writer in the code
today; see `../REGISTRY-RECONCILIATION.md` §2c)
wiped (D-25).

**A Brother HL-L2350DW in the office is this system's physical surface** — local laser, no
vendor print cloud, and the first hard-copy destination the vault has ([../HARDWARE.md](../HARDWARE.md)
H7). One constraint is real and worth stating plainly: the owner's intended use includes
1Password paper emergency sheets, which means **secrets on paper**. The print action itself is
local and fine. The rule is **D-71**: a print job's *content* never enters the agent's
context, a tool argument, the audit trail or a log. The tool call is "print the emergency
sheet", never the sheet's contents — D-57 with paper instead of git. There is no print tool
in the codebase today, so the constraint is currently satisfied by the absence of the thing
that would break it.

If this is absent, Afon can discuss a document and cannot leave one behind.

## Structure

```
create_document(kind, title, body, destination)
   │
   ├──> brain/documents.py    create(): write → read back → compare → report
   │        │
   │        ├── local markdown ──> the vault (authoritative, D-22)
   │        ├── vault note      ──> src/afon/brain/tools/vault.py
   │        └── Notion page     ──> src/afon/brain/tools/documents.py handlers
   │
   └── reading side (strong): brain/docstore.py  temporary one-document index
        tools/documents.py  open local file · ask grounded question · close
```

| Concern | Where |
|---|---|
| The single creation tool and read-back verification | `src/afon/brain/documents.py` |
| Addressability afterwards (06.F3) | `src/afon/brain/documents.py`; `test_documents_routing.py` [7] |
| Reading, grounded answers | `src/afon/brain/tools/documents.py` over `src/afon/brain/docstore.py` |
| Vault writes | `src/afon/brain/tools/vault.py` |
| Vault as source of truth, reconciliation | `src/afon/brain/docstore.py`, `memory.py` (D-22) |
| Generated documents from a day's work | `routine_draft.py`, `daily_digest.py` |
| Local laser printing, office (H7) | **planned** — no print tool exists; the path is a destination of `create_document`, not a new system (D-71) |

**Process ownership:** brain. Note the asymmetry recorded in the module: reading a
"local" file means the owner's **laptop**, so the bytes are read there and parsed
brain-side. Shipping the whole document would have swapped a missing-file bug for a
broken-PDF one. **What it stores:** the document in the destination, plus the addressing
record needed for "the note you wrote yesterday about X" to resolve.

**A printer does not make the creation path less ad-hoc.** The registry's status for S06 is
still "half-built — reading is strong, *creation* is three ad-hoc writers", and that is
re-checked against the code rather than assumed: `create_document` is the single entry point
(06.F1) and the read-back is the invariant, but templates, in-place revision and export
(06.R1–06.R3, 06.R4) are all open, so the 0/4 in the raise tier is untouched by owning a
laser printer. Paper is a *destination*; it adds no writer and no verification path.

## Goals

1. **Every document is created through one tool**, with a kind, a title, a body and an
   explicit destination (06.F1).
2. **No creation is reported successful until the content is read back** from the
   destination it claims to be in (06.F2).
3. **A created document is addressable afterwards** — "the note you wrote yesterday about
   X" resolves to it (06.F3).
4. **A local markdown document lands in the vault**, where markdown remains the source
   of truth and can lose to the file (D-22).
5. **A partial failure names which half happened**, not a binary success.
6. **Templates exist for the four kinds the owner writes** — meeting note, decision
   record, project brief, weekly review (06.R1) — not yet built.
7. **An existing document is revised in place, keeping the prior version** (06.R2), and
   can be exported where the destination needs another format (06.R3) — neither built.
8. **A print job's contents never enter the system** (D-71): the tool call names the sheet,
   never its contents, and no context, tool argument, audit line or log carries the bytes.
   A local laser printer is the surface (H7); the print tool does not exist yet.

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | One creation path | B1 | `bench/test_document_create.py` | 3/3 destinations write successfully | 06.F1 carries a `recorded-note` dated **2026-09-13**; the gate text says three destinations, each written and read back. This is the one S06 task with a dated record |
| 2 | Read-back before success | B1 | `bench/test_document_create.py` [read-back] | 0 successes reported without a read-back comparison | not yet measured |
| 3 | Addressable afterwards | B1 | `bench/test_documents_routing.py` [7] | 7/7 references resolve to the right document | not yet measured |
| 4 | Vault is the destination | B4 | Markdown written where the vault can lose to it; a manual file edit wins on the next read (D-22) | 0 database records that contradict a newer file | not yet measured |
| 5 | Partial failure is named | B1 | `bench/test_document_create.py` — plant a read-only destination and an archived Notion parent | both report the correct half, 0 false successes | not yet measured |
| 6 | Templates | B1 | `bench/test_document_create.py` [template fidelity] | 4/4 kinds render their required sections | not yet measured — 06.R1 open |
| 7 | Revise and export | B1 | `bench/test_document_revise.py` — **planned gate, the file does not exist** | in-place edit keeps the prior version; export produces a readable file | not yet measured — nothing built |
| 8 | Print contents stay out | B1 | new `bench/test_print_no_content_leak.py` — **planned gate; no print tool exists to call** | 0 print-job bytes in the context, tool arguments, the audit trail or any log; the call names the sheet only (D-71) | not yet measured |

The read-back invariant is the one that earns the *reading* half of this system's status —
"half-built — reading is strong, *creation* is three ad-hoc writers" — and the 0/4 in the
raise tier is the other half: templates, in-place revision and export are all open tasks
whose benchmarks have no script behind them yet. That status string's own evidence is
`unverified-import`, so the read-back claim rests on an imported record rather than on a
verified run.
`bench/test_doc_paths.py` exists specifically so a path claimed in a document of this
shape cannot be a phantom — a roadmap once named a script that never existed.

## Failure modes

**A false creation.** The vault write lands on a read-only mount, or the Notion parent
is an archived page, and Afon says "Done — created X" about a document that does not
exist. The 2026-09-13 record on 06.F1 is the fix; the failure mode is what happens if
the read-back is ever removed. Reproduce by pointing a destination at a read-only path.

**The page id is thrown away.** `notion_create_page` discards the response, so the
document it just made can never be referred to again — and 06.F3's addressing then has
nothing to address. The symptom is a document that exists and that the owner cannot
ask about.

**A title sanitises to nothing.** The destination is chosen from the title, the title
reduces to an empty or reserved string, and the write lands somewhere unexpected or
nowhere.

**The index and the file disagree.** A document is edited in the vault by hand and the
brain keeps answering from its cached copy. This is a D-22 violation and the
reconciliation path is the mitigation; the tell is an answer that quotes text the file no
longer contains.

**A revision destroys the prior version.** Not yet reachable, because 06.R2 is open —
but when in-place editing lands, D-25 requires the superseded version be tombstoned, not
overwritten. That constraint should land with the feature, not after it.

## Open questions

1. 06.R1 asks for four templates, but nothing records which kinds the owner actually
   writes. Should the template set be chosen from the existing vault contents, or is
   the four-kind list in the task already the decision?
2. 06.R2 (revise in place) and 06.R3 (export to pdf/docx) share a planned gate,
   `bench/test_document_revise.py`, which does not exist. Are they one file, and does
   export belong here at all or in a tools module?
3. The vault is the source of truth (D-22) and the database is a cache, but no test
   asserts that a hand edit wins on the next read. Which layer owns that assertion —
   `test_document_create.py` or a memory-layer test?
