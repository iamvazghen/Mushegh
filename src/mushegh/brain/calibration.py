"""Is a reported confidence a truthful one? The measurement that does not exist yet.

**Why this file exists.** The Calibration behavioural category measured **63.5/100**, with eight
of eleven `unknowable_*` prompts scoring exactly 40.0 — a flat number, which is what a model
produces when it is guessing or when the scorer cannot tell a guess from a calculation. The
pending owner decision is whether to change the JEv contract or accept the measured deficit, and
**that decision cannot be made without a calibration curve**, because "it feels overconfident"
and "it is overconfident by 18 points in the 0.8 bin" are different claims and only one of them
is checkable.

**What was missing.** JEv already returns a real confidence (`DecisionVerdict.confidence`, e.g.
"Reported confidence: 90%") and the agent already speaks it aloud. But nothing ever compared
that number to what actually happened, so the curve could not be drawn. This module records the
pair and computes it.

**Why not just install `lm-evaluation-harness`.** Because it needs a probability *and* an
outcome, and Mushegh had neither recorded — so the package would have had nothing to score. The
statistics here are the standard ones (ECE, Brier, reliability bins) so a harness can be pointed
at this file later; the recording is the part that had to be built first.

**The failure mode this is written against.** Returning `0.0` for "no data" would render as
*perfectly calibrated*, which is the exact lie this module exists to prevent. Every metric here
returns `None` when there is nothing to say, and `summary()` says `sufficient=False`.

Usage
-----
    from mushegh.brain.calibration import record_prediction, resolve, summary

    rid = record_prediction("jev_arbitration", confidence=0.9, detail="office vs cafe")
    ... later, when it is knowable ...
    resolve(rid, outcome=True)

    summary()   # -> {"ece": 0.07, "brier": 0.11, "n": 24, "sufficient": True, ...}
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

#: Below this many resolved points the curve is noise. Reporting an ECE over 3 samples invites
#: acting on a number that a single flipped outcome would move by 0.2.
MIN_POINTS = 12


@dataclass(frozen=True)
class CalibrationPoint:
    """One predicted-and-resolved confidence."""

    confidence: float
    outcome: bool
    kind: str
    record_id: str
    detail: str = ""
    ts: str = ""

    @property
    def error(self) -> float:
        return abs(self.confidence - (1.0 if self.outcome else 0.0))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(explicit: Path | str | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    from mushegh.shared.paths import state_dir

    return state_dir() / "calibration.jsonl"


def _clamp(value: float) -> float:
    """A confidence outside [0,1] is not data, it is a bug upstream — clamp rather than crash."""
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else float(value))


def _append(row: dict, path: Path | str | None = None) -> bool:
    """Append one JSONL row. Never raises: losing a metric is better than losing the turn."""
    try:
        p = _path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception as exc:  # noqa: BLE001 - metrics must not break a live turn
        logger.warning("calibration: could not record (%s)", type(exc).__name__)
        return False


def record_prediction(
    kind: str,
    confidence: float | None,
    detail: str = "",
    path: Path | str | None = None,
) -> str | None:
    """Record a reported confidence that has not been resolved yet.

    Returns the record id to pass to `resolve`, or None when there is no usable confidence —
    "not reported" is a real state (JEv is optional) and is not silently treated as 0.5.
    """
    if confidence is None:
        return None
    try:
        c = _clamp(float(confidence))
    except (TypeError, ValueError):
        return None
    rid = uuid.uuid4().hex[:12]
    _append(
        {"id": rid, "kind": kind, "confidence": c, "detail": detail[:160],
         "outcome": None, "ts": _now()},
        path,
    )
    return rid


def resolve(record_id: str, outcome: bool, path: Path | str | None = None) -> bool:
    """Mark a recorded prediction as right or wrong once the answer is knowable."""
    p = _path(path)
    if not p.is_file():
        logger.warning("calibration: cannot resolve %s — no store", record_id)
        return False
    rows: list[dict] = []
    found = False
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue          # a torn line is not worth failing the rewrite over
                if row.get("id") == record_id and row.get("outcome") is None:
                    row["outcome"] = bool(outcome)
                    row["resolved_ts"] = _now()
                    found = True
                rows.append(row)
        if not found:
            return False
        tmp = p.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                       encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("calibration: resolve failed (%s)", type(exc).__name__)
        return False


def load(path: Path | str | None = None, kind: str | None = None) -> list[CalibrationPoint]:
    """Every resolved point. Unresolved predictions are excluded — they are not evidence."""
    p = _path(path)
    if not p.is_file():
        return []
    out: list[CalibrationPoint] = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("outcome") is None:
                    continue
                if kind is not None and row.get("kind") != kind:
                    continue
                out.append(CalibrationPoint(
                    confidence=_clamp(row.get("confidence", 0.0)),
                    outcome=bool(row.get("outcome")),
                    kind=str(row.get("kind", "")),
                    record_id=str(row.get("id", "")),
                    detail=str(row.get("detail", "")),
                    ts=str(row.get("ts", "")),
                ))
    except Exception as exc:  # noqa: BLE001
        logger.warning("calibration: load failed (%s)", type(exc).__name__)
    return out


def reliability_bins(points: Sequence[CalibrationPoint], bins: int = 10) -> list[dict]:
    """Equal-width bins over [0,1]: how accurate was each confidence band?"""
    if bins <= 0:
        raise ValueError("bins must be positive")
    width = 1.0 / bins
    out: list[dict] = []
    for i in range(bins):
        lo, hi = i * width, (i + 1) * width
        # The top bin is closed so a confidence of exactly 1.0 is counted, not dropped.
        members = [
            pt for pt in points
            if (lo <= pt.confidence < hi) or (i == bins - 1 and pt.confidence == 1.0)
        ]
        n = len(members)
        mean_conf = sum(pt.confidence for pt in members) / n if n else None
        acc = (sum(1 for pt in members if pt.outcome) / n) if n else None
        out.append({
            "lo": round(lo, 4), "hi": round(hi, 4), "n": n,
            "mean_confidence": round(mean_conf, 4) if mean_conf is not None else None,
            "accuracy": round(acc, 4) if acc is not None else None,
            "gap": round(abs(acc - mean_conf), 4) if n else None,
        })
    return out


def expected_calibration_error(points: Sequence[CalibrationPoint], bins: int = 10) -> float | None:
    """Mean |accuracy - confidence|, weighted by bin population.

    None when there is nothing to measure. Never 0.0 for empty input: that would read as
    "perfectly calibrated" on the day the curve was never drawn.
    """
    if not points:
        return None
    table = reliability_bins(points, bins)
    total = len(points)
    acc = sum((b["n"] / total) * b["gap"] for b in table if b["n"])
    return round(acc, 4)


def brier_score(points: Sequence[CalibrationPoint]) -> float | None:
    """Mean squared error of the probability. 0 = perfect, 1 = always maximally wrong."""
    if not points:
        return None
    total = sum(pt.error ** 2 for pt in points) / len(points)
    return round(total, 4)


def overconfidence_index(points: Sequence[CalibrationPoint]) -> float | None:
    """Positive when claims outrun outcomes; negative when the reverse.

    This is the single number the "is it overconfident?" argument is really about, and unlike
    ECE it carries a SIGN — a model can be badly calibrated by being too cautious, and calling
    that overconfidence would be wrong.
    """
    if not points:
        return None
    total = sum(pt.confidence - (1.0 if pt.outcome else 0.0) for pt in points) / len(points)
    return round(total, 4)


def summary(points: Sequence[CalibrationPoint] | None = None,
            path: Path | str | None = None,
            kind: str | None = None) -> dict:
    """The whole picture in one dict. `sufficient` is what stops it being over-read."""
    pts = load(path, kind) if points is None else list(points)
    return {
        "n": len(pts),
        "ece": expected_calibration_error(pts),
        "brier": brier_score(pts),
        "overconfidence": overconfidence_index(pts),
        "mean_confidence": round(sum(p.confidence for p in pts) / len(pts), 4) if pts else None,
        "accuracy": round(sum(1 for p in pts if p.outcome) / len(pts), 4) if pts else None,
        "sufficient": len(pts) >= MIN_POINTS,
        "min_points": MIN_POINTS,
        "bins": reliability_bins(pts) if pts else [],
    }


def describe(result: dict) -> str:
    """One honest sentence for a log or a HUD row.

    Deliberately refuses to characterise a curve built on too few points. A number quoted
    without its sample size is how "calibration is fine" gets said about three samples.
    """
    if not result.get("n"):
        return "calibration: no resolved predictions yet"
    if not result.get("sufficient"):
        return (f"calibration: {result['n']} point(s) — below the {result['min_points']} needed "
                f"to characterise it")
    sign = "overconfident" if (result["overconfidence"] or 0) > 0 else "underconfident"
    return (f"calibration: {result['n']} points, ECE {result['ece']}, "
            f"{sign} by {abs(result['overconfidence'])}")