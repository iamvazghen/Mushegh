"""26.R5 / D-66 — the detector's output channel carries metadata and cannot carry a frame.

Charter, verbatim: *detections stay local. **No video frame leaves the house** — never to a vision
model, never to a logger, never to a crash report. Only event metadata (zone, label, count,
timestamp) may cross to the brain.*

**There is no detector in this repository yet.** A search for `frigate`, `reolink` or `coral` under
`src/afon/` returns nothing and there is no RTSP client here, so every sentence anyone has written
about frames not leaving the house has been a rule on paper. That is the gap this module closes —
but it closes the *seam*, not the hardware, and the distinction matters more than it sounds:

  * what it makes real: the only way a detector's output can enter the brain is `accept()`, and
    `accept()` refuses any payload that carries frame bytes, a data URI, a base64 blob or a path to
    an image. There is no second door, because there is no second function that takes a detector
    result.
  * what it cannot make real: that a local accelerator produces correct events. No Coral, no
    Reolink, no Frigate, no camera. Until one exists, "the detector still works" is an untested
    claim about hardware nobody has connected, and the gate says so rather than implying otherwise.

**The cloud chain stays, deliberately.** `settings.vision_models` is MiniMax then Gemini — every
entry remote — and D-66 allows exactly one use of it: a screenshot the owner asked about. So this
module does NOT try to forbid vision. It makes vision a separate, explicitly owner-initiated path
and keeps the detector's output structurally incapable of reaching it. The rule enforced here is
narrower and therefore actually enforceable: *a detection may not become a vision call.*

Two decisions worth stating:

**The allowlist is on the payload, not on the destination.** An event may carry exactly `zone`,
`label`, `count`, `at` and an optional `camera` id. Anything else is refused by name, so a future
integrator who adds `{"image": ...}` to a Frigate event gets a refusal that says which key was
rejected — a legible failure at the boundary, rather than a frame that quietly crossed.

**Values are checked too, not only keys.** A key allowlist alone is defeated by
`{"label": "data:image/jpeg;base64,..."}` or `{"zone": "../../frames/front-door.jpg"}`, which are
schema-valid and carry a frame's worth of location or bytes. So a metadata string is refused if it
looks like a data URI, a long base64 run, or a path to an image file. The cost is that a zone named
after a `.jpg` cannot exist; that is a fair price and a small one.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from afon.shared.redact import looks_like_media

#: The four metadata fields D-66 names, plus an optional camera id so a multi-camera house can say
#: WHICH camera fired without anything about what it saw.
ZONE = "zone"
LABEL = "label"
COUNT = "count"
AT = "at"
CAMERA = "camera"
ALLOWED: frozenset[str] = frozenset({ZONE, LABEL, COUNT, AT, CAMERA})
REQUIRED: tuple[str, ...] = (ZONE, LABEL)

# A path at all — a zone named "porch" is fine, a zone named "s3://bucket/front.jpg" is not. Kept
# here rather than in `shared.redact` because this one is an *ingress* rule about a metadata value,
# not a redaction rule about text on its way to a log.
_PATHISH = re.compile(r"(/|\\){1,2}\w|[a-zA-Z]:\\")


class FrameEgressRefused(Exception):
    """A detector payload tried to bring a frame across the boundary. Payload-free by construction.

    The message names the offending KEY and never quotes the value. A refusal that echoed the base64
    it rejected would put a frame fragment into whatever log caught the exception, which is the third
    destination D-66 names.
    """

    def __init__(self, why: str, key: str = "") -> None:
        self.why = why
        self.key = key
        where = f" (rejected key {key!r})" if key else ""
        super().__init__(f"frame egress refused by D-66: {why}{where}")


def _check_value(value: Any, key: str) -> str:
    """One metadata string, screened. Returns it unchanged, or raises."""
    if not isinstance(value, str):
        raise FrameEgressRefused("metadata values must be strings", key)
    why = looks_like_media(value)
    if why:
        raise FrameEgressRefused(f"a metadata value carried {why}", key)
    if _PATHISH.search(value):
        raise FrameEgressRefused("a metadata value carried a path", key)
    if len(value) > 120:
        raise FrameEgressRefused(f"a metadata value is {len(value)} chars; metadata is not prose", key)
    return value


def _check_count(value: Any, key: str) -> int:
    """The count must be a real number. A bool is an int in Python and means nothing here; a string
    is either a detector that forgot to encode a type or something that is not a count."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FrameEgressRefused("count must be a number", key)
    if value < 0:
        raise FrameEgressRefused("count cannot be negative", key)
    return int(value)


def _check_at(value: Any, key: str) -> str:
    """An ISO timestamp or an epoch number; anything else is refused rather than guessed at.

    Accepting a loose date and reformatting it would mean the freshness stamp the brain quotes is
    not the detector's timestamp but this module's opinion of it, and S26's whole rule is that a
    fact must not be able to pretend to be newer than it is.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    if isinstance(value, str):
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise FrameEgressRefused("at must be an ISO timestamp or an epoch number", key) from None
        return value
    raise FrameEgressRefused("at must be an ISO timestamp or an epoch number", key)


@dataclass(frozen=True)
class DetectionEvent:
    """One event from a local detector: where, what, how many, when. Never what it looked like."""

    zone: str
    label: str
    count: int = 0
    at: str = ""
    camera: str = ""

    def __post_init__(self) -> None:
        if not self.at:
            object.__setattr__(self, "at", datetime.now(timezone.utc).isoformat())

    def as_record(self) -> dict:
        """The wire shape. Five scalar metadata fields and nothing else — the whole point."""
        return asdict(self)

    def spoken(self) -> str:
        return f"{self.zone}: {self.label} x{self.count}"

    def __str__(self) -> str:
        return self.spoken()


def accept(payload: Mapping[str, Any]) -> DetectionEvent:
    """THE boundary. A detector's event becomes a `DetectionEvent` here, or it does not become one.

    This is the only function in the repository that turns a detector result into something the
    brain can hold, and that singleness is the guard. It is strict by construction: unknown keys are
    refused by name rather than dropped, because a dropped `image` key is a frame that crossed
    wearing a hat, and a refusal the caller can read is worth more than a silent omission.
    """
    if not isinstance(payload, Mapping):
        raise FrameEgressRefused(f"a detector payload must be a mapping, not {type(payload).__name__}")

    extra = sorted(set(payload) - ALLOWED)
    if extra:
        raise FrameEgressRefused("a detector payload carried keys that are not event metadata", extra[0])
    missing = [k for k in REQUIRED if k not in payload]
    if missing:
        raise FrameEgressRefused(f"a detector payload was missing {missing[0]!r}", missing[0])

    zone = _check_value(payload[ZONE], ZONE).strip()
    label = _check_value(payload[LABEL], LABEL).strip()
    if not zone or not label:
        raise FrameEgressRefused("zone and label must be non-empty")
    count = _check_count(payload.get(COUNT, 0), COUNT)
    at = _check_at(payload[AT], AT) if AT in payload else ""
    camera = _check_value(payload[CAMERA], CAMERA).strip() if CAMERA in payload else ""
    return DetectionEvent(zone=zone, label=label, count=count, at=at, camera=camera)


def accept_all(payloads) -> list[DetectionEvent]:
    """A batch of detector events, in order. One bad event refuses the whole batch rather than
    being skipped: a batch where the frame-bearing event was dropped is a batch that silently
    under-reports, and the caller cannot tell the difference from a quiet room."""
    return [accept(p) for p in payloads]


def publish(event: DetectionEvent) -> DetectionEvent:
    """Hand one accepted event to the brain as a perception fact. Metadata only, by construction.

    Goes to `perception.record_visual`, which is where every other visual fact already lives and
    which stamps freshness — so a detection from ninety seconds ago is reported as ninety seconds
    old rather than as now, which is S26 goal 2 and the reason the timestamp survives at all.
    """
    from afon.brain.perception import record_visual

    source = f"detector:{event.camera}" if event.camera else "detector"
    record_visual(event.spoken(), source=source)
    return event


if __name__ == "__main__":  # a quick look at the boundary
    samples = [
        {"zone": "front_door", "label": "person", "count": 1},
        {"zone": "garden", "label": "car", "count": 1, "camera": "cam2"},
        {"zone": "front_door", "label": "person", "image": "data:image/jpeg;base64,/9j/4AAQ"},
        {"zone": "garden", "label": "data:image/jpeg;base64,QUJDREVGR0hJSktMTU5PUFFSU1Q"},
        {"zone": "/var/lib/frigate/frames/front.jpg", "label": "person"},
        {"zone": "garden", "label": "person", "count": "two"},
    ]
    for s in samples:
        try:
            print(f"{'accept ':22} {accept(s).spoken()}")
        except FrameEgressRefused as e:
            print(f"{'REFUSE':22} {e}")
