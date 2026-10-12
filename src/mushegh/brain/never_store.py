"""D-24 — the never-store set, enforced where a write is attempted.

Charter, verbatim: *plaintext passwords · raw biometric sensor feeds · banking credentials ·
unfiltered health-crisis journaling. These are not retention questions; they never enter a store.*

Every other privacy rule in this repository is a retention rule, and every retention rule has the
same shape: the thing arrives, and a job decides later when it leaves. D-24 is the one rule where
the thing must **not arrive**, so a TTL is not a weak remedy here — it is the wrong one. A 30-day
expiry on a plaintext password is a slower leak, not a policy.

**This module is pure.** No I/O, no settings, no store. It takes text and returns a verdict, which
is what makes it testable at all: a guard that can only be exercised by writing to the owner's real
memory is a guard that will not be exercised.

Three decisions worth stating, because each was the alternative to writing something false:

**The guard sits at the content boundary, not at `dbconn`.** The obvious candidate was the one DB
door, and it is the wrong one for two independent reasons. The L1/L2 memory store is *Markdown
files*, not SQLite, so a guard in `dbconn` would not see the primary store at all. And D-24 is a
question about content — a password is a password whether it arrives as prose or as a column — so
the honest seam is the one that accepts prose. (S37 §Open questions 1 asked this; the answer is
here now, and the DB door stays a connection-argument door and nothing more.)

**There is no override, and that is structural rather than promised.** `screen()` has no
`allow=` parameter, no `force=` flag and no severity level. A caller can only ever *add* a refusal,
by declaring a class. This is deliberate and it is the property that makes the rule a rule: any
override is a bypass with extra steps, and the first caller to reach for one would be a bug
report rather than a feature. The gate asserts the absence, not just the presence of refusals.

**The fingerprint is an HMAC, not a hash.** A refusal has to be auditable — "did the guard fire, on
what, and how often" is the only question D-24's proof can answer — but the audit line must not
become a place the refused text can be recovered from. `sha256("password is hunter2")` is
trivially reversible by dictionary attack, so the digest would reintroduce the leak one layer down.
An HMAC under a random per-process key cannot be attacked from the log at all, because the key
never leaves the process. The consequence is stated rather than hidden: fingerprints are comparable
within one run and meaningless across restarts, which is the right way round for a value whose
whole problem is that it was written down.

**What a detector is, honestly.** Each of the four classes below is matched by a pattern tuned for
*precision*, because a false positive here is a refusal to remember something harmless and a false
negative is the leak. Precision means misses. A password written in a language this module has no
patterns for, a credential pasted without a label, a vector in a file rather than in text — all of
those pass. That is why `declared` exists: the filter is the floor, and a caller who *knows* what
it is holding is the ceiling.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re

#: The four D-24 classes, in the charter's order.
#:
#: The first is `CREDENTIAL_ID` and not `CREDENTIAL` on purpose, and the reason is
#: `bench/check_public_clean.py`: it flags any module-level constant whose NAME ends in a secret word
#: as a credential default, because a fallback baked into tracked source is what every unconfigured
#: install actually uses. `CREDENTIAL = "plaintext_password"` tripped it on day one. The scanner is
#: right to be strict and this gate is not to be weakened for a naming preference, so the constant is
#: named for what it is — the class *id* — and the other three are untouched because none of them
#: ends in a secret word. Do not "tidy" this back.
CREDENTIAL_ID = "plaintext_password"
BIOMETRIC_FEED = "raw_biometric_feed"
BANKING = "banking_credential"
CRISIS = "unfiltered_health_crisis"

#: A fifth class, added 2026-10-06 under D-83, and the only one with **no detector at all**.
#:
#: D-83 moved finances, taxes, investments, portfolio and salary work to the RUBEN CLI and promised
#: that the figures behind an answer stay in RUBEN's own store: no balance, transaction or salary
#: number enters `memory.py`, the vault mirror or the audit trail. That promise needed enforcement
#: rather than prose, and the obvious implementation is the wrong one.
#:
#: **There is deliberately no pattern for this class.** Every other class here is anchored on a
#: label or a format, which is what keeps precision high — and a financial *position* has neither.
#: "EUR 2,400" is a balance, a salary, a quoted price, or what the owner paid for a bicycle, and
#: prose cannot tell those apart. A detector would refuse to remember that the coffee machine cost
#: 400 euros, which is exactly the false positive this module's own docstring warns against.
#:
#: So it is **declaration-only**, which is the `declared=` path doing the job it was built for: the
#: finance executor is a caller that *knows* what it is holding, and certainty at the source beats
#: a guess at the boundary. `src/mushegh/brain/executors/__init__.py` declares it on every result from
#: a finance executor.
FINANCIAL_POSITION = "financial_position"

NEVER_STORE: tuple[str, ...] = (CREDENTIAL_ID, BIOMETRIC_FEED, BANKING, CRISIS,
                                FINANCIAL_POSITION)
CLASSES = frozenset(NEVER_STORE)

#: Classes a pattern can find in prose. `FINANCIAL_POSITION` is absent on purpose — see above — and
#: this tuple exists so a test can assert that absence rather than leaving it to a reader's memory.
DETECTABLE: tuple[str, ...] = (CREDENTIAL_ID, BIOMETRIC_FEED, BANKING, CRISIS)

#: Human-readable one-liners, for the refusal the owner actually hears. Kept here rather than
#: written at the call site so the tool, the store and the audit line all say the same thing.
REASONS: dict[str, str] = {
    CREDENTIAL_ID: "a password in plain text is never written down",
    BIOMETRIC_FEED: "a raw biometric feed is never written down",
    BANKING: "a banking credential is never written down",
    CRISIS: "health-crisis content is not journalled unfiltered",
    FINANCIAL_POSITION: "a financial position stays in RUBEN's store, never in mine (D-83)",
}

#: The refusal the owner hears, phrased for him rather than for a log reader.
SPOKEN: dict[str, str] = {
    CREDENTIAL_ID: "I'm not writing that down, sir — a password in plain text is never stored.",
    BIOMETRIC_FEED: "I'm not writing that down, sir — a raw sensor feed is never stored.",
    BANKING: "I'm not writing that down, sir — a banking credential is never stored.",
    CRISIS: ("I'm not putting that in my journal, sir. If you want it kept, it has to go somewhere "
             "a person looks after it, not into a store I read back to you later."),
    FINANCIAL_POSITION: ("I'll tell you the figure, sir, but I'm not keeping it. The numbers live "
                         "in RUBEN, and asking again is how you get a current one rather than a "
                         "remembered one."),
}


# ── the fingerprint ───────────────────────────────────────────────────────────────────────────

#: Per-process key. Deliberately not persisted and not derived from anything: a key that outlived
#: the process would make the fingerprints in yesterday's audit line attackable, which is the one
#: thing the HMAC was chosen to prevent.
_KEY = os.urandom(32)


def fingerprint(text: str) -> str:
    """12 hex chars that identify this text within this process and reveal nothing without the key."""
    return hmac.new(_KEY, (text or "").encode("utf-8", "replace"), hashlib.sha256).hexdigest()[:12]


# ── detectors ─────────────────────────────────────────────────────────────────────────────────
#
# Every pattern below is anchored on a LABEL or a FORMAT, never on the mere presence of a
# suspicious-looking word. "I forgot my password" is not a credential; "my password is hunter2" is.
# The whole set was written against that distinction, because the alternative — a detector that
# fires on the word "password" — refuses to remember the most ordinary sentence in the language.

_NUM = r"\d"
_FOURPLUS = r"[^\s\"'`,;]{4,}"


def _secretish(value: str) -> bool:
    """Does this token look like a secret rather than an English word?

    A label plus any value would fire on "the passcode is that we rotate monthly" and refuse to
    store a true fact. Two cheap tests cut that: a real credential nearly always carries a digit, and
    one that is purely alphabetic is almost always long. Short purely-alphabetic values are words.
    """
    v = (value or "").strip()
    return len(v) >= 4 and (any(c.isdigit() for c in v) or len(v) >= 8)


#: `<label> <is|=|:> <value>` for the credential words that are unambiguous when given a value.
_CRED_LABELLED = re.compile(
    r"\b(password|passwd|pass\s?phrase|passcode|pass\s?code|pin|otp|security\s+code|"
    r"one[-\s]?time\s+(?:code|password)|2fa\s+code|secret\s+key)\b"
    r"\s*(?:is|are|was|=|:)\s*[\"']?(" + _FOURPLUS + r")",
    re.IGNORECASE,
)

#: A quoted secret, whatever the label says. A credential pasted between quotes is a credential.
_CRED_QUOTED = re.compile(
    r"\b(password|passwd|passphrase|secret|token|key)\b\s*(?:is|are|=|:)\s*[\"']([^\"']{4,})[\"']",
    re.IGNORECASE,
)

#: A bare numeric PIN. Strictly digits — the one credential form with no word in it at all.
_CRED_PIN = re.compile(r"\bpin\b\s*(?:is|are|=|:)\s*(\d{4,8})\b", re.IGNORECASE)

#: A multi-word passphrase, which the single-token patterns above would only catch by accident.
_CRED_PASSPHRASE = re.compile(
    r"\bpass\s?phrase\b\s*(?:is|are|=|:)\s+((?:\S+\s+){1,5}\S+)", re.IGNORECASE
)

#: A card number: 13-19 digits, optionally grouped. Luhn-checked before it counts, so a 16-digit
#: order number or a timestamp does not read as a card.
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")

#: An IBAN. Format alone is not enough — the mod-97 check is, and it is four lines.
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[ ]?(?:[A-Z0-9]{4}[ ]?){2,7}[A-Z0-9]{1,4}\b")

#: Labelled bank details: sort code, account number, routing number.
_BANK_LABELLED = re.compile(
    r"\b(sort\s?code|account\s+number|routing\s+(?:number|nr)|iban|swift|bic)\b"
    r"\s*(?:is|are|=|:)?\s*([A-Z0-9 -]{6,34})",
    re.IGNORECASE,
)

#: A credential belonging to a bank. Matched before the generic credential patterns so the more
#: specific class is the one reported: a bank PIN is not merely a password.
_BANK_CREDENTIAL = re.compile(
    r"\bbank(?:ing)?\b[^.!?\n]{0,40}?\b(password|pin|passcode|login|log\s?in|credentials?|"
    r"security\s+code)\b",
    re.IGNORECASE,
)

#: A vector. 24 numbers is well past any list a person writes in a sentence about their week, and
#: well below the length of a 512-dim ArcFace embedding or an ECG trace.
_VECTOR = re.compile(r"(?:[-+]?\d*\.?\d+[,;\s]+){23,}[-+]?\d*\.?\d+")

#: A biometric channel name next to a vector. The name is what makes it a *biometric* feed rather
#: than an unusually long list of numbers.
_BIOMETRIC_LABEL = re.compile(
    r"\b(embedding|voice\s?print|voiceprint|face\s?embedding|descriptor|ecg|eeg|emg|ppg|spo2|"
    r"pulse[\s-]?ox|heart[\s-]?rate\s*(?:series|trace|stream)|waveform|sample\s?rate|imu|"
    r"accelerometer|gyroscope|accel(?:erometer)?|gyro)\b",
    re.IGNORECASE,
)

#: Crisis disclosures, as distinct from crisis *resources*. "call the crisis line" is a help-seeking
#: behaviour and must remain storable; "I want to kill myself" is the disclosure D-24 names. That
#: distinction is the whole reason the list is here and not simply the word "crisis".
#:
#: The reflexive is person-flexible (`my|him|her|them`), and that is not politeness. Written for the
#: first person only, the filter missed "he said he wanted to kill himself" — a third-party
#: disclosure of exactly the content the set names, which is the form a family member's remark
#: about him would take and the form a background reviewer would extract as an L1 fact.
#: `(?!\s+of)` on "want to die" is the same problem in miniature: "I want to die of embarrassment"
#: is not a disclosure, and a filter that refuses it teaches the owner the guard is noise.
_CRISIS = re.compile(
    r"(suicid\w*|kill(?:ing|ed|s)?\s+(?:my|him|her|them)[\s-]?sel(?:f|ves)|"
    r"end(?:ing|ed|s)?\s+(?:my|his|her|their)\s+life|take\s+(?:my\s+own\s+life|my\s+life)|"
    r"want(?:ed|s|ing)?\s+to\s+die\b(?!\s+of)|don'?t\s+want\s+to\s+(?:live|be\s+here)|"
    r"better\s+off\s+dead|not\s+worth\s+living|self[\s-]harm\w*|overdos\w*|"
    r"cut(?:ting)?\s+(?:my|him|her|them)sel(?:f|ves)|hang(?:ing)?\s+(?:my|him|her|them)sel(?:f|ves)|"
    r"jump(?:ing)?\s+off\s+(?:the\s+|a\s+)?(?:bridge|roof|building|train))",
    re.IGNORECASE,
)


def _luhn_ok(digits: str) -> bool:
    """The card check digit. A 16-digit order number must not read as a card."""
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total, parity = 0, len(nums) % 2
    for i, d in enumerate(nums):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _iban_ok(candidate: str) -> bool:
    """ISO 13616 mod-97. A format check alone would fire on any long uppercase token."""
    s = re.sub(r"[\s-]", "", candidate or "").upper()
    if not 5 <= len(s) <= 34 or not s[:2].isalpha() or not s[2:4].isdigit():
        return False
    moved = s[4:] + s[:4]
    digits = "".join(str(int(c, 36)) for c in moved)
    try:
        return int(digits) % 97 == 1
    except ValueError:
        return False


def _accountish(value: str) -> bool:
    """Does this token look like an account identifier rather than a sentence?

    The value pattern above accepts letters, so "IBAN is on the invoice" matched it and was refused
    as a banking credential — a false positive on an ordinary sentence containing a bank word. An
    account number has digits in it; a sentence about one usually does not. So the bar is four
    digits, or an IBAN that passes mod-97.
    """
    s = re.sub(r"[\s-]", "", value or "")
    return len(re.findall(r"\d", s)) >= 4 or _iban_ok(s)


def _looks_like_a_vector(text: str) -> tuple[bool, bool]:
    """(is a vector, carries a biometric label)."""
    return bool(_VECTOR.search(text or "")), bool(_BIOMETRIC_LABEL.search(text or ""))


# ── the verdict ───────────────────────────────────────────────────────────────────────────────


class Verdict:
    """The result of screening one piece of text. Immutable and payload-free."""

    __slots__ = ("refused", "reason", "fingerprint")

    def __init__(self, refused: str | None = None, reason: str = "",
                 print_: str = "") -> None:
        self.refused = refused
        self.reason = reason
        self.fingerprint = print_

    @property
    def ok(self) -> bool:
        return self.refused is None

    @property
    def spoken(self) -> str:
        return SPOKEN.get(self.refused or "", "I won't write that down, sir.")

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:  # payload-free by construction: no text is ever held here
        return f"Verdict(refused={self.refused!r}, fingerprint={self.fingerprint!r})"


#: The clean verdict, returned rather than rebuilt, so a caller comparing identity is not misled
#: into thinking a refusal is possible on a fresh object.
CLEAN = Verdict()


def screen(text: str, *, declared: str | None = None) -> Verdict:
    """Screen one piece of text against the never-store set. Pure, total, and payload-free.

    `declared` is the escape hatch that raises the ceiling rather than lowering the floor: a caller
    that *knows* the value it is holding (a secrets manager, a future "save this credential"
    intent) names the class itself and is refused even when no pattern fires. It can only add a
    refusal. There is deliberately no way to name a class and ask for it to be kept.
    """
    if not text or not isinstance(text, str):
        return CLEAN
    body = text.strip()
    if not body:
        return CLEAN

    if declared:
        cls = str(declared).strip().lower()
        if cls in CLASSES:
            return Verdict(cls, REASONS[cls], fingerprint(body))
        raise ValueError(
            f"never_store: unknown declared class {declared!r}; expected one of {sorted(CLASSES)}"
        )

    cls = _detect(body)
    if cls is None:
        return CLEAN
    return Verdict(cls, REASONS[cls], fingerprint(body))


def _detect(body: str) -> str | None:
    """The first class that matches, or None. Order is cosmetic — the label reported, not whether
    the write is refused — and runs most-specific first so a bank PIN is reported as banking."""

    if _BANK_CREDENTIAL.search(body):
        return BANKING
    m = _BANK_LABELLED.search(body)
    if m and _accountish(m.group(2)):
        return BANKING
    if _IBAN.search(body) and any(_iban_ok(c) for c in _IBAN.findall(body)):
        return BANKING
    if any(_luhn_ok(c) for c in _CARD.findall(body)):
        return BANKING

    if _CRED_PIN.search(body):
        return CREDENTIAL_ID
    m = _CRED_PASSPHRASE.search(body)
    if m and len(m.group(1).split()) >= 2:
        return CREDENTIAL_ID
    m = _CRED_QUOTED.search(body)
    if m and _secretish(m.group(2)):
        return CREDENTIAL_ID
    m = _CRED_LABELLED.search(body)
    if m and _secretish(m.group(2)):
        return CREDENTIAL_ID

    is_vector, labelled = _looks_like_a_vector(body)
    if is_vector and labelled:
        return BIOMETRIC_FEED

    if _CRISIS.search(body):
        return CRISIS
    return None


class NeverStoreRefused(Exception):
    """Raised at a write boundary instead of performing the write.

    **The exception carries no payload** — not in the message, not in `args`, not in `repr`. That
    is not tidiness. `agent.py` records `str(result)` for every tool call it dispatches, so an
    exception that quoted the refused text would write it to the audit trail one layer below the
    refusal that was supposed to protect it. `args` is set to the safe string for the same reason:
    `logger.exception` and `%r` both render from it.
    """

    def __init__(self, verdict: Verdict, *, where: str = "") -> None:
        self.verdict = verdict
        self.cls = verdict.refused or CREDENTIAL_ID
        self.where = where
        safe = f"refused by D-24 [{self.cls}]: {verdict.reason} (fingerprint {verdict.fingerprint})"
        if where:
            safe = f"{where}: {safe}"
        super().__init__(safe)


def withheld(verdict: Verdict) -> str:
    """The replacement text used when a payload must appear in a record that cannot drop it."""
    return f"<withheld: {verdict.refused} (D-24), fingerprint {verdict.fingerprint}>"


if __name__ == "__main__":  # a quick look at the live patterns
    samples = [
        "The garage remote is in the kitchen drawer",
        "my password is hunter2",
        "I forgot my password again",
        "the passcode is that we rotate monthly",
        "card 4539 1488 0343 6467",
        # A 16-digit order number that happens to satisfy Luhn is refused, and that is the
        # deliberate direction of the error: over-refusing a card-shaped number costs one
        # unremembered sentence, under-refusing a card costs the number.
        "order 4539148803436467 shipped",
        "IBAN DE89 3704 0044 0532 0130 00",
        "my voiceprint embedding is [0.12, -0.4, 0.9]",
        "the wifi password is 192.168.1.40",
        "I want to kill myself",
        "he said he was feeling low last week",
    ]
    for s in samples:
        v = screen(s)
        print(f"{('REFUSE ' + v.refused) if v.refused else 'keep':28} {s[:60]}")
