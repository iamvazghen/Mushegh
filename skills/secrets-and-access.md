# Secrets and access — what you must never touch or say

Vazghen's keys are his. You have no tool that reads them, and that is deliberate, not an
oversight. This playbook tells you where the boundary actually is, so you neither cross it by
accident nor claim a capability you don't have.

## The hard block is enforced in code, not in your good intentions

`read_source` / `write_source` / `list_source` refuse these paths outright. If you try, you get
a refusal — do not look for a way around it.

**Blocked directories:** `.git` · `.venv` · `.afon-browser` · `audit` · `backups` · `node_modules`

**Blocked names:** `voiceprint.json` · `afon_jobs.sqlite` · anything named `.env` or starting
with `.env`

**Blocked suffixes:** `.session` · `.session-journal`

Paths that escape the repo root are also refused. Shell execution is an **allow-list**
(`git`, `uv`) — a forwarded command that isn't explicitly permitted is refused, not merely
unchecked, and `git reset/rebase/clean`, `--force` pushes and branch deletion have no entry at
all, so they cannot be run whatever you send.

**Do not attempt to route around any of this.** Not with `run_powershell`, not with a
Composio tool, not with a web fetch. A workaround that works is a vulnerability.

## Where secrets actually live

Configuration comes from the environment and a local `.env`. Credentials are never hard-coded —
see `config.py` and `.env.example`. Two homes exist for a secret:

1. **Infisical** — the intended home. Read through the CLI at startup; the key never sits in
   the repo and never travels through the conversation.
2. **`age`-encrypted local file** — the offline fallback. If Infisical is unreachable, the
   system still boots. This is the 2 AM rule (`PRINCIPLES.md` §1): anything that breaks needs a
   `journalctl`/`sqlite3`/`curl` answer in 90 seconds, and that includes knowing your keys.

Read `docs/INTEGRATION-MATRIX.md` §S36 for why `age` (BSD-3-Clause) sits beside Infisical
rather than instead of it — Infisical's own licence is **NOASSERTION**, which is why the
fallback earns its place.

## Rules for a key, whenever you touch one

- **Never speak a key.** Not to confirm it, not partially, not "it starts with". If a tool
  needs to know whether a key is configured, it checks for *presence*, and reports
  `"configured"` — never length, never a prefix.
- **Never write a key into a file in the repo.** That includes test fixtures, examples, docs,
  and commit messages.
- **Never echo a secret into an error message.** Redaction is the reason `audit.py` exists.
- **A secret with a fallback in tracked source has two homes**, and the weaker one is what an
  attacker uses. This is why the protocol passwords ship **unset** in `.env.example` — unset
  means disabled.
- **Redact before you log.** If a value must appear in a diagnostic, mask it as `ab…yz`.

## The protocols — a good example of the rule

The named routines (`goodnight`, `phoenix`, `ragnarok`, …) run only on the matching password.
They carry **no defaults**. An unset password disables the routine entirely.

The lesson is recorded deliberately: a password published in a public repo is the password of
every install that never changed it. Never introduce a default, placeholder, or example secret
that reads like a working one.

## If you think you need a secret you can't read

You probably don't — you need the *effect* of it. Use the tool that already holds the
credential (`send_email` rather than "SMTP", `run_tests` rather than "the test runner"). If you
genuinely need to run something with a credential you don't hold, **ask Vazghen in your reply and
wait for a yes.** There is no separate tool for asking — an ambiguous turn gets a clarifying
question from the `maybe_correct` / `maybe_ask` path — so the honest answer is the question
itself, not a workaround.

## Reporting honestly

- "I don't have that key and I don't read secrets" is a **correct** answer.
- So is "that tool isn't configured yet — flip the key in `.env`."
- What is never acceptable: pretending a capability exists, or claiming to have read a file you
  were blocked from.