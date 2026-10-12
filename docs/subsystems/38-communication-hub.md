# S38 — Communication Hub

> **One line:** one answer to "what is waiting for me", and a refusal to send any of it
> without the owner in the room.
> **Status:** built, not well structured · **Registry:** S38 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** none assigned — the D-13 refusal is exercised in M27 (S36, S03, S37) ·
> **Decisions:** D-13, D-62

## Purpose

A communication hub's obvious job is sending, and the sharpest constraint in this system
is that it does not send. D-13 puts external email and messaging dispatch inside the blast
radius: Mushegh can never touch it without the owner physically present. That is not a
missing feature to be scheduled — it is the design. A hub that could send on its own
would have a failure mode with an external, irreversible, third-party blast radius, which
is precisely the category D-13 exists to close.

What is left after the refusal is still the useful half: a single deduplicated view
across channels, contact resolution, and the judgement about what actually deserves the
owner's attention. Triage matters more than volume here. An inbox with fifty items and no
ranking is work the owner already had; an inbox with four items, one of which is
genuinely urgent and two of which can wait until he asks, is the job done.

It also refuses to grow. D-62 sets the credential set at four tokens, total, and every
additional credential has to beat that list. This system is the one where that pressure is
felt hardest, because each new channel is exactly one more token and the temptation is
one API call away.

If it were absent, the owner opens two clients in the morning and triages by hand, and
the value of the system is limited to whatever a single script could have done.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/mushegh/brain/tools/inbox.py` | brain | 38.F2 — one "what's waiting for me" view, merged across channels and deduplicated by thread |
| `src/mushegh/brain/tools/gmail.py`, `src/mushegh/brain/google.py` | brain | 38.F1 — read, draft and send mail through one OAuth app |
| `src/mushegh/brain/tools/telegram.py`, `src/mushegh/brain/telegram_bridge.py` | brain | The Telegram path; the bridge doubles as the 24/7 reach channel for S23 |
| `src/mushegh/brain/contacts.py`, `src/mushegh/brain/tools/contacts.py` | brain | 38.F1 — "email John" is useless until John is an address |
| `src/mushegh/brain/approvals.py` | brain | 38.F3 — deferred outward steps become APPROVABLE actions; the send gate, and the place that refuses email, publishing, spending and deleting while unattended |
| `src/mushegh/brain/delivery.py` | brain | What happened to a notification after it left, per channel (13.F3) |
| `src/mushegh/brain/tools/notify.py` | brain | The delivery surface every message is charged against (D-29) |

**Data flow.** The brain process polls or receives on each channel, resolves senders and
recipients through the local contact book, merges threads in `inbox.py`, and hands the
result to `delivery.py`. Nothing crosses the outward boundary without a row in the
approval queue first; a draft is materialised, shown, and only then is a send possible.

**The honest gap.** The merge exists and the judgement does not. 38.R1 (triage) and 38.R2
(thread awareness) are both open and both carry planned assertions on the same
`test_unified_inbox.py` that currently only tests the merge. Nothing is structurally
preventing the inbox view from becoming a feed, which would be D-34, and nothing in the
credential accounting stops a fifth token from being added.

## Goals

1. One view of what is waiting, deduplicated by thread across channels (38.F2).
2. A name resolves to a real send target, or the tool refuses (38.F1).
3. Nothing is sent without the owner approving the exact draft, and drafts are shown
   first (38.F3, D-13).
4. Triage into urgent / needs reply / FYI / ignore, learned from what the owner actually
   did with each item (38.R1) — the judgement, not the volume.
5. A reply knows the conversation, not just the last message in it (38.R2).
6. The credential set stays at the D-62 four; a new channel has to beat that list.
7. Every message that reaches the owner is charged against the interruption budget
   (D-29) — the hub gets no audio channel of its own.

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | `uv run python bench/test_unified_inbox.py` | one row per thread across channels; 0 duplicate threads; 0 channel shown raw | registry records 38.F2 done; run not reproduced here — not yet measured |
| 2 | B1 | `uv run python bench/test_contacts.py` | a name resolves to exactly one target, or the tool refuses; 0 ambiguous sends | not yet measured |
| 3 | B1 | `uv run python bench/test_approvals.py` [38.F3] plus the M27 dispatch refusal | a send with no approval produces 0 sends; an unattended worker refuses email, publish, spend and delete | registry records 38.F3 done; M27 open — not yet measured |
| 4 | B1 | `uv run python bench/test_unified_inbox.py` [triage] | every item lands in exactly one of the four buckets; 0 unclassified; 0 item in two buckets | not yet measured (38.R1 open) |
| 5 | B1 | `uv run python bench/test_unified_inbox.py` [thread] | a reply to a three-message thread carries the thread, not the last message alone | not yet measured (38.R2 open) |
| 6 | B4 | `systemctl show openmushegh-brain -p Environment`, then diff the credentials against the D-62 four | exactly 4 tokens; 0 credentials beyond Home Assistant, CalDAV, Matrix and one weather/transit API | not yet measured — the running configuration was not audited here, and two channels already sit outside the four |
| 7 | B1 | `uv run python bench/test_phase11_integrations.py` | nothing in the hub raises an audio interruption above the daily budget of 3; 0 during a focus block | not yet measured |

Goal 3 is the one that cannot be allowed to regress silently: `approvals.py` states it
refuses to send while running unattended, and that property is what makes the rest of
this system tolerable.

## Failure modes

**The hub becomes a send bot.** A turn drafts, the approval gate is misread as a
formality, and a message leaves that the owner never read. This is the D-13 failure and
the only one here with an irreversible external effect. Diagnose:
`journalctl -u openmushegh-brain -n 200 | grep -iE 'approv|send'`, then the approval rows
and the audit line for the same timestamp.

**The merge lies about volume.** One conversation arriving on two channels is reported
twice, the owner triages it twice, and he stops trusting the view — which loses the only
thing this system provides. Diagnose: `uv run python bench/test_unified_inbox.py`, then
the thread keys in the merged output.

**A credential is added because a channel was easy.** D-62 names four and the machine
carries roughly fifteen: the mail OAuth app and the Telegram bot token are both outside
the four, so the fifth arrives without ceremony. D-62 was amended on 2026-10-03 for
exactly this reason. It now carries a table mapping every credential in `.env.example`
to a system, to the decision it answers to, and to whether it is configured — plus the
rule that no credential may be added without a row. Diagnose: `systemctl show
openmushegh-brain -p Environment`, then read each entry against that table instead of
against a four-item list that no longer describes the machine. `36.R4` tracks building
the inventory from the code; this document only names the gate.

**Triage decays into a feed.** A view that pushes unprompted is D-34 and, past three a
day, D-29. Diagnose: `journalctl -u openmushegh-brain -n 200 | grep -iE 'proactive|triage'`,
then the daily interruption count.

## Open questions

1. Is triage a rule the owner writes, or something inferred from his actions — and if
   inferred, from which record? `src/mushegh/brain/tool_usage.py` holds durable per-tool
   counts, not per-message outcomes.
2. When the owner approves a reply, does approval bind that exact text, or may the model
   revise it afterwards? D-09 says a confirmation never authorises the next action, which
   argues for the first, and the gate does not currently say.
