"""36.F6 — a hard ceiling on autonomous action: calls, spend, and wall-clock.

`TaskWorker` already bounds ONE run: a step budget and a wall-clock budget, declared before the
work starts. What nothing bounded was the *runs*. Five call sites construct a worker (the agent's
``work_on_task``, the backlog pass, the objectives pass, the co-pilot, the code self-improve loop),
several of them on a schedule, and every individual run can sit inside its own budget while the
day as a whole runs away.

That is not a hypothetical. It has already happened on this owner's infrastructure: an OpenClaw
heartbeat loop sent roughly 2,500 messages and burned roughly 565M tokens, one well-behaved
iteration at a time. Jev scored the autonomous worker's safety design 1.10/4 — *the action deferral
is right but there is no bound on volume, cost or time* — and made this a hard precondition of the
unpark (P=0.69).

So the ledger here is **per-window, not per-run**, and shared by every autonomous path.

Three properties it needs, and why:

* **It survives a restart.** An in-memory counter is reset by exactly the restart loop it exists to
  stop, and the brain restarts daily by design (``jarvis-brain-refresh``, 01:00 UTC). The ledger is
  one small JSON file in the state directory — not a new sqlite store, because the standing
  directive is to consolidate stores rather than add them.
* **It refuses deterministically.** The ceiling is enforced in code before a step runs, never by
  asking a model to behave. A refusal raises, and the caller stops.
* **A refusal is audited.** An autonomous run that was cut short is exactly the thing an incident
  review needs to find, and it is invisible if only the owner's own tool calls are logged.

ponytail: calls and seconds are measured exactly; spend is an estimate, because no provider in the
chain returns usage and `cost.py` prices a model rather than a receipt. The CALLS ceiling is
therefore the backstop that actually stops a flood — the spend ceiling is the one that notices an
expensive model early. Unpriced calls are counted, never treated as free, which is `cost.py`'s own
rule.

    uv run python -m afon.brain.governor
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class GovernorRefusal(RuntimeError):
    """Raised when an autonomous run would exceed a ceiling. Deterministic, not advisory."""

    def __init__(self, ceiling: str, used: float, limit: float, resets_at: str) -> None:
        self.ceiling = ceiling
        self.used = used
        self.limit = limit
        self.resets_at = resets_at
        super().__init__(
            f"autonomous {ceiling} ceiling reached: {used:g} of {limit:g} used in this window; "
            f"resets at {resets_at}"
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Governor:
    """A rolling-window ledger of autonomous consumption, with hard ceilings.

    The window is a fixed period that starts on the first charge and rolls over when it expires —
    not a sliding window over individual events. A sliding window needs every event retained and
    pruned; a fixed one needs four numbers and a timestamp, and for a ceiling whose job is
    "stop a runaway", the difference does not change a decision.
    """

    def __init__(
        self,
        *,
        max_calls: int | None = None,
        max_usd: float | None = None,
        max_seconds: float | None = None,
        window_hours: float | None = None,
        path: Path | None = None,
    ) -> None:
        from afon.config import settings

        self.max_calls = int(max_calls if max_calls is not None
                             else getattr(settings, "autonomy_max_calls", 200))
        self.max_usd = float(max_usd if max_usd is not None
                             else getattr(settings, "autonomy_max_usd", 2.0))
        self.max_seconds = float(max_seconds if max_seconds is not None
                                 else getattr(settings, "autonomy_max_seconds", 3600.0))
        self.window_hours = float(window_hours if window_hours is not None
                                  else getattr(settings, "autonomy_window_hours", 24.0))
        self._path = path
        self._state: dict[str, Any] | None = None

    # ---- state ---------------------------------------------------------
    def _state_path(self) -> Path:
        if self._path is not None:
            return self._path
        # AFON_GOVERNOR_LEDGER points the ledger somewhere else entirely. It exists so the hermetic
        # suite does not spend the real window: several tests drive a real worker, and a suite run
        # was measured consuming 64 of 200 calls - three pushes in a day would have started refusing
        # genuine autonomous work, which is the "gate gets disabled" failure this class exists to
        # avoid. Not a general-purpose knob; `bench/run_all_tests.py` sets it.
        override = os.environ.get("AFON_GOVERNOR_LEDGER", "").strip()
        if override:
            return Path(override)
        from afon.shared.paths import state_dir

        return state_dir() / "governor.json"

    def _fresh(self) -> dict[str, Any]:
        return {"window_started": _now().isoformat(), "calls": 0, "usd": 0.0,
                "seconds": 0.0, "unpriced_calls": 0, "refusals": 0}

    def _load(self) -> dict[str, Any]:
        if self._state is not None:
            return self._state
        state = self._fresh()
        try:
            raw = self._state_path().read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if isinstance(loaded, dict) and "window_started" in loaded:
                state = {**state, **loaded}
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001 — a corrupt ledger must not wedge the brain
            logger.warning(f"governor ledger unreadable, starting a fresh window: {type(e).__name__}")
        self._state = state
        self._roll_if_expired()
        return self._state

    def _roll_if_expired(self) -> None:
        state = self._state
        assert state is not None
        try:
            started = datetime.fromisoformat(str(state["window_started"]))
        except (ValueError, KeyError, TypeError):
            started = _now()
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if _now() - started >= timedelta(hours=self.window_hours):
            self._state = self._fresh()
            self._save()

    def _save(self) -> None:
        try:
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # noqa: BLE001 — ledger I/O must never break a turn
            logger.warning(f"governor ledger write failed: {type(e).__name__}: {e}")

    def resets_at(self) -> str:
        state = self._load()
        try:
            started = datetime.fromisoformat(str(state["window_started"]))
        except (ValueError, TypeError):
            started = _now()
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return (started + timedelta(hours=self.window_hours)).strftime("%Y-%m-%d %H:%M UTC")

    # ---- the gate ------------------------------------------------------
    def check(self, *, actor: str = "afon:autonomous", note: str = "") -> None:
        """Raise GovernorRefusal if any ceiling is already reached. Call BEFORE doing the work."""
        state = self._load()
        self._roll_if_expired()
        state = self._state
        assert state is not None
        for ceiling, used, limit in (
            ("calls", state["calls"], self.max_calls),
            ("spend", state["usd"], self.max_usd),
            ("runtime", state["seconds"], self.max_seconds),
        ):
            if used >= limit:
                state["refusals"] = int(state.get("refusals", 0)) + 1
                self._save()
                refusal = GovernorRefusal(ceiling, used, limit, self.resets_at())
                self._audit_refusal(refusal, actor=actor, note=note)
                raise refusal

    def _audit_refusal(self, refusal: GovernorRefusal, *, actor: str, note: str) -> None:
        """A cut-short autonomous run is precisely what an incident review looks for."""
        try:
            from afon.brain import audit

            audit.record(
                "governor",
                {"ceiling": refusal.ceiling, "used": refusal.used, "limit": refusal.limit,
                 "note": note},
                str(refusal),
                ok=False,
                actor=actor,
                decision="deny",
                rule=f"governor:{refusal.ceiling}_ceiling",
                reasoning=("an autonomous run was stopped at its window ceiling; this is a hard "
                           "limit in code, not a model deciding to stop"),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"governor refusal not audited: {type(e).__name__}")

    # ---- the meter -----------------------------------------------------
    def charge(
        self,
        *,
        calls: int = 0,
        seconds: float = 0.0,
        model: str = "",
        in_tokens: int = 0,
        out_tokens: int = 0,
    ) -> None:
        """Record consumption. Never raises — the ceiling is enforced by `check`, not here."""
        state = self._load()
        self._roll_if_expired()
        state = self._state
        assert state is not None
        state["calls"] = int(state["calls"]) + int(calls)
        state["seconds"] = float(state["seconds"]) + max(0.0, float(seconds))
        if model or in_tokens or out_tokens:
            from afon.brain.cost import usd

            money = usd(model, int(in_tokens), int(out_tokens))
            if money is None:
                # cost.py's rule: unknown is never silently zero.
                state["unpriced_calls"] = int(state.get("unpriced_calls", 0)) + 1
            else:
                state["usd"] = float(state["usd"]) + money
        self._save()

    def snapshot(self) -> dict[str, Any]:
        """What the window holds, for the HUD and the unattended-review surface."""
        state = dict(self._load())
        state.update({
            "max_calls": self.max_calls, "max_usd": self.max_usd,
            "max_seconds": self.max_seconds, "window_hours": self.window_hours,
            "resets_at": self.resets_at(),
            "usd": round(float(state.get("usd", 0.0)), 4),
            "seconds": round(float(state.get("seconds", 0.0)), 1),
        })
        return state

    def reset(self) -> None:
        """Start a fresh window. For the owner and for tests, not for the loop itself."""
        self._state = self._fresh()
        self._save()


#: The shared ledger every autonomous path charges against. One brain, one budget.
GOVERNOR = Governor()


def _selfcheck() -> None:
    """ponytail: the one runnable check — each ceiling refuses, and the window rolls."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "governor.json"

        g = Governor(max_calls=3, max_usd=1.0, max_seconds=60.0, window_hours=24.0, path=p)
        g.reset()
        g.check()                                   # empty ledger allows
        g.charge(calls=3, seconds=1.0)
        try:
            g.check()
        except GovernorRefusal as e:
            assert e.ceiling == "calls", e.ceiling
        else:
            raise AssertionError("the calls ceiling must refuse")

        # A ceiling refuses on SPEND even when calls are fine.
        g2 = Governor(max_calls=1000, max_usd=0.05, max_seconds=60.0, path=p)
        g2.reset()
        g2.charge(calls=1, model="minimax:MiniMax-Text-01", in_tokens=1_000_000, out_tokens=0)
        assert g2.snapshot()["usd"] > 0.05
        try:
            g2.check()
        except GovernorRefusal as e:
            assert e.ceiling == "spend", e.ceiling
        else:
            raise AssertionError("the spend ceiling must refuse")

        # An unpriced model is counted, never treated as free.
        g3 = Governor(max_calls=1000, max_usd=1.0, max_seconds=60.0, path=p)
        g3.reset()
        g3.charge(calls=1, model="a-model-nobody-priced", in_tokens=999_999, out_tokens=999)
        assert g3.snapshot()["unpriced_calls"] == 1
        assert g3.snapshot()["usd"] == 0.0

        # Runtime refuses independently.
        g4 = Governor(max_calls=1000, max_usd=1.0, max_seconds=2.0, path=p)
        g4.reset()
        g4.charge(seconds=2.5)
        try:
            g4.check()
        except GovernorRefusal as e:
            assert e.ceiling == "runtime", e.ceiling
        else:
            raise AssertionError("the runtime ceiling must refuse")

        # It survives a restart: a NEW instance over the same file still refuses.
        g5 = Governor(max_calls=1000, max_usd=1.0, max_seconds=2.0, path=p)
        try:
            g5.check()
        except GovernorRefusal:
            pass
        else:
            raise AssertionError("the ledger must survive a restart — that is the whole point")

        # An expired window rolls over and allows again.
        g5._state["window_started"] = (_now() - timedelta(hours=25)).isoformat()
        g5._save()
        g6 = Governor(max_calls=1000, max_usd=1.0, max_seconds=2.0, window_hours=24.0, path=p)
        g6.check()
        assert g6.snapshot()["seconds"] == 0.0

    print("selfcheck ok — calls, spend and runtime each refuse; ledger survives a restart")


if __name__ == "__main__":
    _selfcheck()
