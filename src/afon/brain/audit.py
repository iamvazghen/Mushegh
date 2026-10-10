"""Audit log — a hash-chained, verifiable trail of every tool action Afon takes (cross-cutting, Phase X).

Trust comes from being able to see what he did. Each tool call appends one JSON line to a daily
file under ``audit_log_dir`` (default ``<repo>/audit/YYYY-MM-DD.jsonl``): when, which tool, the
arguments, and a clipped result. **Secrets are never written** — argument keys that look like a
password / token / secret are redacted before the line is built (protocol passwords especially must
never land on disk), and since 37.R5 the D-24 never-store classes are withheld as well: a payload
that matches one is replaced by a marker and the line is marked `refuse`. Key-based redaction alone
is not enough, because the key that carries a pasted password is usually `text`.

It is best-effort and fail-quiet: a logging error must never break a turn, so every write is wrapped
and a failure is dropped (with a warning), not raised.

**Since 45.R10 each line carries the digest of the line before it**, so the file can be checked
without trusting the code that wrote it: ``python -m afon.brain.audit_verify --verify <path>`` exits
non-zero if any line was edited, removed or reordered. Two things this deliberately does NOT claim,
because the difference is the difference between a property this codebase can honour and one it
cannot: it cannot detect truncation of the LAST line, and it cannot stop anyone who can write the
file from rebuilding a whole valid chain. It is tamper-EVIDENT. The reasoning, the file format and
the limits are in ``afon/brain/audit_verify.py``; the gate is ``bench/test_audit_integrity.py``.
Lines written before 45.R10 have no digest and verify as ``legacy`` — unchained, which is the past,
not tampering.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from pydantic import SecretStr

from afon.config import settings
from afon.brain.never_store import screen as _screen, withheld as _withheld
from afon.shared.redact import withhold_media as _withhold_media

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Argument keys whose values must be redacted before anything is written.
_SECRET_KEYS = ("password", "token", "secret", "api_key", "apikey", "auth", "credential", "dsn")

#: How deep `_withhold` walks a nested args structure before it stops descending.
_MAX_WITHHOLD_DEPTH = 4


def _withhold(value, found: set[str], depth: int = 0):
    """37.R5 / D-24 — replace any never-store payload in `value` with a marker, recursively.

    This is the SECOND door, and it is the one that made the first one cosmetic. `_redact` below
    only blanks a value whose KEY looks like a secret, so ``remember({"text": "my password is
    hunter2"})`` sailed straight past it: the key is `text`. Every tool call Afon dispatches is
    recorded by `agent.py` with its arguments verbatim, which means a password pasted into a
    conversation was refused by the store and then written to the audit trail one layer below the
    refusal that was supposed to protect it. Refusing in `memory.py` and recording in `audit.py` is
    a guard with a hole in the floor.

    So the trail **withholds** rather than refuses. It cannot raise — this module's contract is that
    auditing never breaks a turn — and it must not drop the line either, because "the guard fired"
    is the only question D-24's proof can answer. The line is written, the payload is replaced by a
    marker carrying the class and the fingerprint, and the decision becomes `refuse`.

    Args are walked at every depth because a tool may nest its payload (``{"creds": {...}}``), and a
    nested password is still a password. Past the depth cap the value is screened as text rather
    than descended into: returning it unseen would leave exactly the hole this closes.
    """
    if depth > _MAX_WITHHOLD_DEPTH:
        verdict = _screen(value if isinstance(value, str) else str(value))
        if verdict.refused:
            found.add(verdict.refused)
            return _withheld(verdict)
        return value
    if isinstance(value, str):
        # 26.R5 / D-66. The audit trail IS a logger, and the charter names loggers as a place a
        # frame may never reach. `_withhold_media` is applied first because a frame is not a
        # credential, so nothing above would have caught it: a macro step that returned a data URI
        # would have written 500 characters of the owner's face into a daily JSONL file.
        value = _withhold_media(value)
        verdict = _screen(value)
        if verdict.refused:
            found.add(verdict.refused)
            return _withheld(verdict)
        return value
    if isinstance(value, dict):
        return {k: _withhold(v, found, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_withhold(v, found, depth + 1) for v in value]
    return value


def _secret_values() -> list[str]:
    """Actual secret VALUES from settings, to scrub from the whole line (defence in depth).

    Key-based redaction only catches obvious arg keys; this also removes a secret that leaks via a
    tool *result* (e.g. PowerShell echoing an env var) or an unexpectedly-named field.

    `*_password` fields are ALWAYS scrubbed (any length — even 4-digit codes count as secrets).
    Other secret-keyed fields are scrubbed only when long enough (>=6) to avoid mangling ordinary
    English words that happen to contain "secret" or "token" substrings.
    """
    vals: list[str] = []
    for name in getattr(settings, "model_fields", {}):
        v = getattr(settings, name, None)
        if isinstance(v, SecretStr):
            if v.get_secret_value():
                vals.append(v.get_secret_value())
            continue
        if not isinstance(v, str) or not v:
            continue
        if name.endswith("_password"):
            vals.append(v)   # ANY password — even short numeric codes
        elif any(s in name.lower() for s in _SECRET_KEYS) and len(v) >= 6:
            vals.append(v)
    return vals


def _audit_dir() -> Path:
    # One spelling, shared with protocols/auditpack.py — which used to keep its own and so
    # archived an empty directory for months while reporting success (J3.6).
    from afon.shared.paths import audit_dir
    return audit_dir()


def _owner_day(now: datetime) -> str:
    """The owner's calendar day for `now`, as ``YYYY-MM-DD`` — used to name the daily file.

    This used to be ``now.strftime("%Y-%m-%d")`` on a UTC timestamp, which filed the trail by the
    UTC day while the rest of the system files by the owner's day. For any timezone ahead of UTC
    that means the first two hours of the local day land in *yesterday's* file: a voice command at
    half past midnight is on the record as the previous evening's work, and `recent()` — which
    takes the last file alphabetically — reads back the wrong day during exactly that window.

    It was found on 2026-10-10 by `test_audit_integrity.py` failing just after local midnight, and
    it had survived every prior run because it can only fail inside a two-hour band each night.
    That is the same shape as the clock-dependent failures D-43 exists to catch, one timezone over.

    Only the FILE NAME is local. The `ts` inside the line stays UTC, because an instant is an
    instant and the verifier hashes the line itself.
    """
    try:
        from afon.config import settings

        tz = (settings.user_tz or "").strip()
        if not tz:
            raise ValueError("no owner timezone configured")
        from zoneinfo import ZoneInfo

        return now.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001 - a bad tz must not stop the trail being written
        return now.strftime("%Y-%m-%d")


def _redact(args: dict | None, secret_values: list[str] | tuple[str, ...] = ()) -> dict:
    out: dict = {}
    for k, v in (args or {}).items():
        if isinstance(v, str):
            for secret in secret_values:
                v = v.replace(secret, "***redacted***")
        if any(s in k.lower() for s in _SECRET_KEYS):
            out[k] = "***redacted***"
        elif isinstance(v, str) and len(v) > 300:
            out[k] = v[:300] + "…"
        else:
            out[k] = v
    return out


def record(
    tool: str,
    args: dict | None,
    result: str,
    *,
    ok: bool = True,
    actor: str = "owner",
    decision: str = "allow",
    rule: str = "",
    reasoning: str = "",
    turn: str = "",
) -> None:
    """Append one audit line for a tool call. Never raises.

    ``actor``/``decision``/``rule``/``reasoning`` were added 2026-08-09 after an independent audit
    (iFixAi B03, "audit records carry required fields") scored this log 0%. The original line held
    ``ts/tool/args/ok/result``, where ``ok`` means *the call succeeded* — not *the call was
    allowed*. Those are different questions, and only the second one matters after an incident:
    the log could not answer "who asked for this, and under what rule was it permitted?" A blocked
    action and a failed action were both simply ``ok: false``.

    Defaults keep every existing call site valid and truthful: Afon is single-principal, so an
    unattributed action is the owner's, and a call that reaches the audit line was not blocked.

    36.F7 (Jev p=1.00, conf 0.99) hardened that default. ``actor`` is now guaranteed non-empty on
    every line: a caller that passes a blank one gets ``unattributed`` and a warning, rather than a
    record with an empty field that reads as fine in a grep and answers nothing in a review. The
    ``owner`` default stays for the owner's own dispatch path, but the autonomous drivers name
    themselves (``afon:worker``, ``afon:backlog``, ``afon:objectives``, ``afon:copilot``,
    ``afon:code_improve``) - an unattended action attributed to the owner is not a missing field,
    it is a false one.
    """
    # 31.F5 - the correlation id, so this line joins the turn trace, the error journal and the
    # edge's own logs for the same turn. Taken from the in-flight turn unless a caller overrides
    # it; blank when there is genuinely no turn (a scheduled job outside any correlated entry
    # point), which is recorded as blank rather than fabricated.
    if not (turn or "").strip():
        try:
            from afon.shared.errors import current_turn

            turn = current_turn() or ""
        except Exception:  # noqa: BLE001 - auditing must never break a turn
            turn = ""
    if not (actor or "").strip():
        logger.warning(f"audit line for {tool!r} had a blank actor; recording as unattributed")
        actor = "unattributed"
    try:
        now = datetime.now(timezone.utc)
        d = _audit_dir()
        d.mkdir(parents=True, exist_ok=True)
        secrets = sorted(_secret_values(), key=len, reverse=True)
        result = result or ""
        # Redact before clipping: a long DSN otherwise becomes an unmatchable secret prefix.
        for secret in secrets:
            result = result.replace(secret, "***redacted***")
        line = {
            "ts": now.isoformat(),
            "turn_id": turn,
            "tool": tool,
            "args": _redact(args, secrets),
            "ok": ok,
            "actor": actor,
            "decision": decision,
            "rule_applied": rule or ("confirm_gate:not_gated" if decision == "allow" else "unspecified"),
            "reasoning": reasoning,
            "result": (result or "")[:500],
        }
        # 37.R5 / D-24, applied to the line as built rather than to the inputs: the payload can
        # arrive in the RESULT too (a tool that echoed what it was given), and a line that already
        # says ok=true is the last place to notice. Refusal here rewrites the verdict fields rather
        # than skipping the write, because a silent drop is how a guard stops being auditable.
        found: set[str] = set()
        line["args"] = _withhold(line["args"], found)
        line["result"] = _withhold(line["result"], found)
        if found:
            line["ok"] = False
            line["decision"] = "refuse"
            line["rule_applied"] = f"never_store:{'|'.join(sorted(found))}"
            line["reasoning"] = (
                "D-24: this call carried a never-store class. The payload was withheld from the "
                "trail rather than recorded, and the call is marked refused."
            )
        payload = json.dumps(line, ensure_ascii=False)
        # Value-level scrub: remove any real secret that slipped into args or the result text.
        for sv in secrets:
            payload = payload.replace(json.dumps(sv, ensure_ascii=False)[1:-1], "***redacted***")
        path = d / f"{_owner_day(now)}.jsonl"
        # 45.R10: chain the line, so `python -m afon.brain.audit_verify --verify` can prove this file
        # was not edited after it was written. The digest is computed AFTER the scrub above, because
        # a hash of a line that is about to be rewritten is a hash of a line that never existed — and
        # the scrub is exactly that kind of rewrite. Legacy files opened with no chain: their lines
        # simply have no `prev`, and the verifier reports them as unchained rather than as tampering.
        try:
            from afon.brain.audit_verify import GENESIS, _PREV_FIELD, _HASH_FIELD, line_hash

            line[_PREV_FIELD] = _last_hash(path) or GENESIS
            line[_HASH_FIELD] = line_hash(line, line[_PREV_FIELD])
            payload = json.dumps(line, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001 — a missing chain is not a lost audit line
            logger.debug(f"audit chain skipped ({type(e).__name__})")
        with path.open("a", encoding="utf-8") as f:
            f.write(payload + "\n")
    except Exception as e:  # noqa: BLE001 — auditing must never break a turn
        logger.warning(f"audit write failed: {type(e).__name__}: {e}")


def _last_hash(path: Path) -> str | None:
    """The digest of the file's last line, or None if it has none.

    Read from the TAIL rather than the whole file, because this runs on every tool call and an
    audit day is thousands of lines — reading it whole each time would be quadratic on the turn path
    for no benefit. Seeks backwards in blocks, which is the only thing that makes chaining affordable.
    """
    try:
        if not path.exists() or path.stat().st_size == 0:
            return None
        with path.open("rb") as f:
            block = 4096
            pos = f.seek(0, 2)
            tail = b""
            while pos > 0:
                step = min(block, pos)
                pos -= step
                f.seek(pos)
                tail = f.read(step) + tail
                lines = [ln for ln in tail.split(b"\n") if ln.strip()]
                if lines and (pos == 0 or len(lines) > 1):
                    try:
                        obj = json.loads(lines[-1].decode("utf-8", "replace"))
                    except (json.JSONDecodeError, ValueError):
                        return None
                    return obj.get("hash") if isinstance(obj, dict) else None
            return None
    except OSError:
        return None


def recent(limit: int = 10) -> list[dict]:
    """Return the most recent audit entries (today's file), newest last. For self-review/tests."""
    try:
        d = _audit_dir()
        if not d.is_dir():
            return []
        files = sorted(d.glob("*.jsonl"))
        if not files:
            return []
        lines = files[-1].read_text(encoding="utf-8", errors="ignore").splitlines()
        out = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out
    except Exception:  # noqa: BLE001
        return []
