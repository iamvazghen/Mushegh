"""D-66 — a frame is not a secret, and that is why it needed its own redaction rule.

Charter: *no video frame leaves the house — never to a vision model, never to a logger, never to a
crash report.*

Every existing scrubber in this repository is a **credential** scrubber. `errors._scrub` blanks
`api_key=`, `Bearer x` and `sk-…`; `audit._redact` blanks argument values whose KEY looks secret.
Both are correct about their subject and blind to this one, because base64 is not a credential and
`b64` is not a password. A JPEG carried as `data:image/jpeg;base64,…` sails through both.

So the rule lives here on its own, in `shared/` because three unrelated layers need it and none of
them may depend on each other: the error journal (a crash report), the audit trail (a logger), and
the detector's ingress boundary (`mushegh.brain.detector`). One rule, three call sites, no copy-paste
that can drift.

The replacement token is `<withheld>`, not `<redacted>`, and the distinction is the point. "Redacted"
tells an operator reading a log at 2am that the value was a secret and has been hidden. "Withheld"
tells them the value was never ours to write down in the first place, which is the actual rule and a
different decision with a different consequence — a secret that leaked is an incident, a frame that
was withheld is the system working.
"""

from __future__ import annotations

import re

#: An image data URI — the form `LLMClient.see` puts a frame in when it builds the request.
DATA_URI_RE = re.compile(r"data:image/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]{16,}", re.IGNORECASE)

#: A frame in a structured field, with or without the `data:` prefix. The pc_agent's camera op
#: answers `{"b64": "..."}`, so the JSON form is the realistic one on this codebase.
MEDIA_FIELD_RE = re.compile(
    r"(?i)([\"']?\b(?:b64|image_b64|frame_bytes|jpeg_bytes|snapshot_b64|frame_data)\b"
    r"[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9+/]{32,}"
)

#: A bare base64 run with no key and no data-URI prefix. This is the form that actually leaks, and
#: it was missing from `withhold_media` until `bench/test_no_frame_egress.py` wrote one into an
#: error context field and read it back off disk — the keyed rules passed straight over it.
#:
#: 64 characters is the floor and it is a real trade: a SHA-1 is 40 and survives, a SHA-256 is 64 and
#: is withheld. A git hash in an error message is worth more to whoever is reading it at 2am than a
#: 32-byte sliver of the owner's face, but a frame is never shorter than kilobytes, so the floor can
#: sit far above anything short of certain.
BARE_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{64,}={0,2}\b")

#: What a value might be, if it is not text.
_IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|webp|bmp|gif|avif|h264|hevc|mp4|mkv)(\?|$)", re.IGNORECASE)

#: What a withheld value is replaced with. Named `MARKER` rather than `TOKEN` for the same reason
#: `CREDENTIAL_ID` is not `CREDENTIAL` in `mushegh.brain.never_store`: `check_public_clean.py` flags a
#: module-level constant whose name ends in a secret word, and it is right to — this is a marker,
#: not a credential, and the name should say so.
MARKER = "<withheld>"


def looks_like_media(value: str) -> str:
    """Why this value looks like frame bytes rather than metadata. Empty string if it looks fine.

    Used by the detector's ingress, where the question is "is this a frame?" and the answer has to be
    a reason the caller can act on.
    """
    if not isinstance(value, str):
        return ""
    if DATA_URI_RE.search(value):
        return "an image data URI"
    if MEDIA_FIELD_RE.search(value):
        return "a base64 media field"
    if BARE_B64_RE.search(value.strip()):
        return "a bare base64 blob"
    if _IMAGE_EXT_RE.search(value):
        return "an image file path"
    return ""


def withhold_media(text: str) -> str:
    """Replace any frame bytes in `text` with the withheld token. Used before anything is persisted."""
    if not text:
        return text
    out = DATA_URI_RE.sub(f"data:image/{MARKER}", text)
    out = MEDIA_FIELD_RE.sub(rf"\g<1>{MARKER}", out)
    # The bare run is applied on the REMAINDER only. Running it on the whole string first would eat
    # the two substitutions above — both replacement texts are short and neither matches, but the
    # order still matters for a payload where the data URI and a bare run overlap.
    return BARE_B64_RE.sub(MARKER, out)
