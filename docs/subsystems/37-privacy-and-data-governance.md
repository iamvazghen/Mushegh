# S37 — Privacy & Data Governance

> **One line:** what Mushegh is allowed to keep, what it must refuse to keep, and the proof
> that it did not keep it.
> **Status:** built, unproven by use — hygiene real, policy now enforced at the write boundary · **Registry:** S37 · 3/3 floor, 1/5 raise, 0/1 elite
> **Milestones:** M27 · **Decisions:** D-24, D-21, D-25, D-22

## Purpose

The hygiene half is real and was built first: every store is inventoried, retention is
per store and enforced by a job rather than by intention, and `forget` removes a thing
from every store and then re-queries to prove it is gone. The audit trail is
**append-only and best-effort, not tamper-evident**: `src/mushegh/brain/audit.py` appends
one JSON line per action with no hash chain and no signature, and wraps every write so a
failure is dropped rather than raised. So the trail records what happened; it does not
prove that nothing was taken out of it. `45.R10` now tracks making that check verifiable
— or striking the word from every document. On the strength of the hygiene that does
exist, the registry calls this half-built rather than missing, and it is not wrong.

The policy half now exists, and it was the half that mattered. The store classification landed
(37.R4) and the hard part was still prose: the D-24 never-store set — plaintext passwords, raw
biometric sensor feeds, banking credentials, unfiltered health-crisis journaling — appeared nowhere
in `src/mushegh/`, and a grep for `D-24`, `never store` and `NEVER_STORE` across the package returned
nothing. Those four categories are **not retention questions**. A TTL cannot fix data that should
never have arrived; a 30-day expiry on a plaintext password is a slower leak, not a policy.

`37.R5` built it at the write boundary. `src/mushegh/brain/never_store.py` names the four classes and
screens text against them; `MemoryStore.remember()` and `journal_append()` refuse rather than store;
and `ErrorKind.REFUSED` is its own outcome, so a refusal is reported as a refusal instead of filed
as an error. The gate is `bench/test_never_store.py` (50/50).

### Proposed addition — close the one hole the guard admits (D-93)

The guard is honest about its own gap: an unlabelled secret passes, and **a
credential in a language the patterns do not cover passes**. The owner speaks
five languages, and with `34.R4` un-deferred a real export is now the first
plausible route for a sensitive note to reach a store.

**[Yelp/detect-secrets](https://github.com/Yelp/detect-secrets)** (Apache-2.0,
actively maintained) supplies the keyword, regex and entropy coverage the four
tuned patterns do not have. Its failure direction also matches this document's
stated trade-off exactly: a false positive is an unremembered harmless sentence
and a false negative is the leak.

**Door: subprocess adapter, not in-process.** `detect-secrets scan` over
`audit_log/` on the hygiene schedule. Importing it would pull its transitive
dependency set into the brain's interpreter for a *secondary* screen.

**It does not change what the guard claims.** `never_store.py` remains the only
thing on the write path, and the ceiling stays `declared=` with no override. This
is a second opinion behind the guard, not a replacement for it — which is also
why it does not touch the 50/50 gate.

**Gate:** `bench/test_never_store.py`, which exists, plus a sweep over the audit
log in a language the patterns miss. PRINCIPLES §1 three commands, in order:

```
uv run python bench/test_never_store.py
detect-secrets scan audit_log/
grep -c '"decision": "refuse"' audit_log/*.jsonl
```

**Not proposed:** trufflehog, which detects better and is the wrong shape — a
second binary, an AGPL dependency, and live credential *verification* beside a
write-boundary screen. See [INTEGRATIONS.md](../INTEGRATIONS.md) §6.


**The finding worth more than the feature: refusing in the store was not enough.** `agent.py`
records the arguments of every tool call it dispatches, and audit redaction is key-based — so
`remember({"text": "my password is …"})` was refused by the memory store and then written to the
audit trail one layer below the refusal that was supposed to protect it. Both doors are closed now:
the trail **withholds** a refused payload, replacing it with the class and a fingerprint and marking
the decision `refuse`. A guard with a hole in the floor is not a guard, and that hole was only
visible because the gate was written to ask "and where else does this text go?" rather than "does
the write fail?".

What the guard is **not**: complete. Each class is matched by a pattern tuned for precision, because
a false positive is an unremembered harmless sentence and a false negative is the leak. Precision
means misses — an unlabelled secret passes, and a credential in a language the patterns do not cover
passes. The gate asserts that limitation as a test rather than leaving it in prose, so it cannot
quietly become a claim of completeness. The ceiling is `declared=`, where a caller that *knows* what
it is holding names the class itself and is refused even when no pattern fires. And there is no
override at all: no `allow=`, no `force=`, no severity level, asserted structurally rather than
promised.

What the guard replaced was a gap in policy, not plumbing. The four categories are now refused
where a write is attempted. What is still missing is evidence: the guard has never fired on a real
conversation, because the owner's `.env` has never had him paste a password into a chat, and D-43
requires seven days of real use before any of this is called done. The 2:00 AM question ("what do
you have on me, and where?") now has a mechanism behind it and no measurement in front of it.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/mushegh/brain/data_classes.py` | brain | 37.R4 — four classes (biometric, medical, financial, ordinary), one declaration per store, `leaves_host`, and the discovery walk `unclassified()` |
| `src/mushegh/brain/maintenance.py` | brain | The hygiene job — dedup, per-store TTL, the work that makes D-21's 30 days real rather than aspirational |
| `src/mushegh/brain/forget.py` | brain | 37.F3 — remove from every store, then go back and check |
| `src/mushegh/brain/memory.py` | brain | The learned and journal layers the TTLs act on |
| `src/mushegh/brain/dbconn.py` | brain | The one DB door; the surface an inventory has to walk to be complete |
| `src/mushegh/brain/audit.py` | brain | Append-only, best-effort trail — where a forget, a refusal and a policy decision are recorded. It **withholds** a D-24 payload rather than writing it. No integrity check a reader can run today, and a failed write is dropped; that gap is `45.R10` |
| `src/mushegh/brain/never_store.py` | brain | 37.R5 — the D-24 set as code: four classes, pattern detectors, a payload-free verdict, and a fingerprint that is an HMAC under a random per-process key |
| `src/mushegh/shared/redact.py` | shared | 26.R5's counterpart for frames — a frame is not a secret, so the credential scrubbers can never see it; one media rule shared by the error journal, the audit trail and the detector ingress |
| `src/mushegh/brain/tools/privacy.py` | brain | 37.F1 — answers "what do you know about me" out loud, from the inventory |
| `src/mushegh/brain/tools/` | brain | The typed boundary (D-04), which is where a pre-ingest never-store guard was considered and rejected in favour of the store's own content seam |

**Data flow.** The brain process runs the hygiene job on a schedule: it reads the
declarations in `data_classes.py`, applies the per-store rules in `maintenance.py`, and
writes an audit line. `forget` is a tool call, not a shell command, because a store the
inventory missed is exactly the store a manual `rm` would miss. Classification is
declaration-based and each store declares the **strictest** class it *may* hold rather
than the one it usually does — a container that can hold a medical fact is handled as
though it does.

**Egress and the never-store set are two different questions, and only one of them is now
answered.** `leaves_host` in `data_classes.py` answers "may these bytes cross the network" — egress
control. D-24 asks the prior question: should this ever have been written. The two are not
substitutes; 37.R5 answered the second and egress accounting (37.R2) still has no test. A store can
be perfectly classified for egress and still be the wrong place for a plaintext password, which is
why one of them cannot be derived from the other.

## Goals

1. Every store declares its class before any retention rule is written (37.R4).
2. The inventory is discovery-based, not list-based: a new store appearing beside the
   declared ones fails the gate (37.F1).
3. Retention is per store and enforced by the hygiene job, not by intention (37.F2,
   D-21: 30 days for the ephemeral, forever-but-manually-deleted for curated facts).
4. `forget X` removes X from every store and proves it by re-querying (37.F3).
5. The four D-24 categories never enter a store — a guard at the write boundary, not a TTL, and
   not a documentation note (37.R5). No override exists.
6. Egress is accounted for: what left the machine, to which provider, when (37.R2).
7. The owner can read one privacy report in five minutes and act on it (37.E1).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_data_classification.py` | every store declares a class; 0 unclassified | registry records 37.R4 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_data_inventory.py` | every memory and audit store appears; a store added beside the declarations fails the gate | registry records 37.F1 done; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_memory_hygiene.py` [per-store TTL] | ephemeral rows older than 30 days absent; curated facts still present; 0 stores exempt by default | registry records 37.F2 done; run not reproduced here — not yet measured |
| 4 | B1 | `uv run python bench/test_right_to_forget.py` | after `forget X`, 0 rows matching X in any store, including the vault mirror | registry records 37.F3 done; run not reproduced here — not yet measured |
| 5 | B1 | `uv run python bench/test_never_store.py` | a write of each of the four D-24 categories is refused at the boundary; 0 accepted, 0 merely warned | **50/50 on 2026-10-04** — registry records 37.R5 `hermetic-green`; the gate also proves the audit trail withholds the payload, that no override parameter exists, and — stated as a test — that an unlabelled secret is *not* caught |
| 6 | B1 | new `bench/test_egress_log.py` (planned, 37.R2 — does not exist yet) | every outbound payload carries a provider and a timestamp; 0 unattributed egress | not yet measured |
| 7 | B2 | generate the report and read it in five minutes | the owner names at least one thing to delete; 0 minutes over budget | not yet measured |

M27 covers the *action* half of this system's blast radius (external dispatch refuses,
one test each) and lands in S36, S03 and S37. The store-side half — goal 5 — does have a
milestone: M29 (S30, S37) names the assertion that each never-store class is refused at
the write boundary, under D-21 and D-24. What was missing was the code, not the
milestone. On 2026-10-03 a grep for `D-24`, `NEVER_STORE` and `never_store` across
`src/mushegh/` returned nothing, so no registry task enforced the set and goal 5 had no
test; `37.R5` landed it on 2026-10-04 with `bench/test_never_store.py`.

## Failure modes

**A credential lands in a journal.** The owner pastes a password or a banking
credential into a conversation and it is written to the learned layer, where the hygiene
job treats it as an ordinary ephemeral row with a 30-day clock. A TTL is the wrong remedy
here, not a weak one. 37.R5 is the first line against it: `remember()` and
`journal_append()` refuse before anything is written, and the refusal lands in the audit
trail as a class and a fingerprint. Diagnose: `uv run python bench/test_never_store.py`,
then `grep -i "never_store" ` over the audit files, which is where a real refusal would
show up.

**The store refuses it and the audit trail keeps it.** The failure the gate was written to
catch, and the reason the trail now withholds rather than merely records. `agent.py` audits
every dispatched tool call's arguments, redaction is key-based, and the key carrying a
pasted password is `text` — so a write refused in the store was still written to the daily
JSONL one layer below. A guard with a hole in the floor reads exactly like a guard from the
outside. Diagnose: `grep -c '"decision": "refuse"' ` over the audit files; a day with
refusals and no `<withheld>` marker in the same lines is a trail that recorded something it
should not have.

**Classification drifts silently.** A new store is created beside the declared ones and
nothing fails, because a gate that only compares declarations to each other passes
forever. That is the exact failure `unclassified()` exists to catch. Diagnose:
`python -m mushegh.brain.data_classes` — it prints the undeclared list — then
`journalctl -u openmushegh-brain -n 100 | grep -i class`.

**`forget` clears SQLite and the vault keeps it.** Markdown is authoritative (D-22), so
a forget that only touched the runtime cache leaves the real copy in place, and the
database now disagrees with the file that wins. Diagnose: run
`uv run python bench/test_right_to_forget.py`, then read the vault file for the same
string.

**Retention is a policy with no job behind it.** TTLs exist in prose and
`maintenance.py` never runs, so nothing expires and the owner assumes it does.
Diagnose: `journalctl -u openmushegh-brain -n 200 | grep -i hygiene` — an empty result is
the finding — then compare the oldest row against the declared TTL.

## Open questions

1. ~~Where does the never-store guard live: the tool boundary, or `dbconn.py`?~~ **Answered
   2026-10-04: the content boundary** — `MemoryStore.remember()` and `journal_append()` in
   `memory.py`. `dbconn` would have been wrong for two independent reasons: the L1/L2 store is
   Markdown files, not SQLite, so a DB-door guard would not see the primary store at all; and
   D-24 is a question about content, and a password is a password whether it arrives as prose
   or as a column. The tool boundary was rejected for the other half of the same reason — it
   is bypassable by any other writer, and the point of the rule is that the refusal is not the
   caller's to forget.
2. Does the vault mirror need its own declaration? Markdown wins (D-22), so a
   SQLite-side classification can be wrong by construction.
3. Is the egress log a table in the existing store or a separate append-only file?
   37.R2 has a gate and no test, and the answer decides where the writer goes.
