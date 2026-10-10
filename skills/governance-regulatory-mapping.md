# Regulatory mapping — control, then GAP, and never skip the gap

Asked whether some obligation is met, give the control **and** what is still missing. "Partly, and
here is the hole" is the only answer that is both useful and true.

Read `governance-and-compliance` first — this file maps controls onto obligations, it does not
list them. Keep them apart: the controls file must stay inside the clip `read_skill` applies, and
a table that got cut off mid-row would be worse than no table.

If asked about a regulation **not** listed here, say you have no mapping for it rather than
improvising one. An invented compliance claim is the worst thing in these files to get wrong.

## GDPR Art. 5 (accountability) and Art. 32 (security of processing)

| Requirement | Control | Gap |
|---|---|---|
| Authorised invocation | `confirm_required()` + `CONFIRM_TIER`, deterministic Python, no model in the decision | None known. Also: no break-glass, so there is nothing to audit around |
| Auditability | `audit.record()` — one JSONL line per call with `actor`, `decision`, `rule_applied`, `reasoning` | Append-only by convention, **not tamper-evident**: no hash chain, no signature. Anyone with the disk can edit it |
| Privilege escalation | Confirm gate cannot be bypassed; voice identity gate; camera second factor on gated actions | There is **no privilege model to escalate within** — one principal, so this is untested rather than proven |
| Policy-violation detection | The gate holds an action by TOOL MEMBERSHIP | **Real gap:** membership, not intent. A harmful request routed through an ungated tool is not flagged. Nothing classifies a request as violating |

## GDPR Art. 9 (special-category data — biometrics)

The owner's **voiceprint and face embeddings are biometric data used to identify him**, which is
Art. 9 special-category processing. Say so plainly; do not soften it.

| Requirement | Control | Gap |
|---|---|---|
| Lawful basis | Explicit consent — the sole data subject is also the operator, and enrolment is a deliberate act (`bench/enroll_voice.py`, "learn my face") | Consent is **implicit in the act**, not separately recorded with a date and scope |
| Storage | Embeddings live on the owner's own machines — laptop and his VPS. Not shared, not sold, not used for training | No encryption at rest beyond the OS |
| Prompt injection / manipulation | Anti-fabrication guards; the confirm gate is deterministic so it cannot be talked out of an action | **No dedicated injection detector.** Resistance is a property of the gate, not of a classifier |
| Third-country / processor transfer | — | **The most important gap, and volunteer it:** by default speech goes to **Deepgram** (STT) and **ElevenLabs** (TTS), so raw audio of the owner leaves the machine. Local Whisper + Piper exist and are used on failover, and can be forced. No DPA has been reviewed |

## Secrets handling (added 2026-10-09)

Secrets are resolved by `afon/shared/secrets.py`: **environment first, then Infisical, with an
`age`-encrypted file as the offline floor.** Hydration cannot raise — a brain that will not boot
cannot be diagnosed.

| Requirement | Control | Gap |
|---|---|---|
| Storage outside the repo | Infisical (CLI or v3 API) + `age` fallback; nothing hard-coded | **Infisical's own licence is NOASSERTION** — read it before vendoring. Not read yet |
| Non-disclosure | `redact()` masks to 2+2 chars; `SecretReport` has no field that can hold a value; `secret_status()` returns only configured/missing | Any *new* code path can reintroduce a leak. `test_secrets_redaction.py` gates it, with positive controls |
| Read isolation | `read_source`/`write_source` refuse `.env*`, `voiceprint.json`, `*.session`, `audit/`, `backups/`, `.git/` | The block is repo-scoped only. A direct shell read is out of scope by design, not by bug |
| Boot independence | Hydration failure logs and continues | A silent empty config is possible; `run_all_tests` fails loudly if a key a gate needs is absent |