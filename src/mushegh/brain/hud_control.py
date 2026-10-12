"""Bounded, process-local commands from Mushegh to the spatial HUD.

These commands only change presentation. They never execute an operating-system action, approve a
request, or mutate a live turn. The browser consumes them idempotently through the same typed reducer
used by pointer and keyboard controls.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

CANVAS_IDS = frozenset({
    "transcription", "pdf_reader", "3d_engine", "browser", "diagnostics", "decisions",
    "goals", "audio", "approvals", "cameras", "code", "agents", "home", "memory",
    "security", "finance", "calendar", "spectrum",
})
CANVAS_ACTIONS = frozenset({"open", "focus", "toggle", "background", "dismiss", "inspect", "explain"})
GLOBAL_ACTIONS = frozenset({"restore", "reset", "preset", "search"})
PRIMITIVES = frozenset({"box", "sphere", "cylinder", "cone", "torus"})
SIZES = frozenset({"quarter", "half_horizontal", "half_vertical", "full"})
PRESETS = frozenset({"quad", "split_vertical", "split_horizontal"})


class HudCommandError(ValueError):
    """A malformed presentation command. Messages contain no private payload values."""


class HudControlBus:
    def __init__(self, *, capacity: int = 32, stream_id: str | None = None) -> None:
        if not 1 <= capacity <= 128:
            raise ValueError("HUD command capacity must be between 1 and 128")
        self._commands: deque[dict] = deque(maxlen=capacity)
        self._lock = RLock()
        self._sequence = 0
        self._stream_id = stream_id or uuid4().hex

    def publish(self, action: str, *, canvas: str = "", size: str = "", query: str = "",
                preset: str = "", primitive: str = "", color: str = "") -> dict:
        action = str(action or "").strip().lower()
        canvas = str(canvas or "").strip().lower()
        size = str(size or "").strip().lower()
        preset = str(preset or "").strip().lower()
        primitive = str(primitive or "").strip().lower()
        query = str(query or "").strip()[:120]
        color = str(color or "").strip().lower()

        if action in CANVAS_ACTIONS and canvas not in CANVAS_IDS:
            raise HudCommandError("This HUD command needs a known canvas")
        if action == "resize" and (canvas not in CANVAS_IDS or size not in SIZES):
            raise HudCommandError("Resize needs a known canvas and size")
        if action == "preset" and preset not in PRESETS:
            raise HudCommandError("Preset needs a known layout")
        if action == "search" and not query:
            raise HudCommandError("Search needs a query")
        if action == "render_3d":
            if primitive not in PRIMITIVES:
                raise HudCommandError("3D rendering needs a supported primitive")
            if color and not _safe_color(color):
                raise HudCommandError("3D color must be a safe CSS hex color")
            canvas = "3d_engine"
        elif action not in CANVAS_ACTIONS | GLOBAL_ACTIONS | {"resize"}:
            raise HudCommandError("Unknown HUD command")

        with self._lock:
            self._sequence += 1
            command = {
                "sequence": self._sequence,
                "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "action": action,
            }
            for key, value in (("canvas", canvas), ("size", size), ("query", query),
                               ("preset", preset), ("primitive", primitive), ("color", color)):
                if value:
                    command[key] = value
            self._commands.append(command)
            return dict(command)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "stream_id": self._stream_id,
                "sequence": self._sequence,
                "commands": [dict(command) for command in self._commands],
            }


def _safe_color(value: str) -> bool:
    if not value.startswith("#") or len(value) not in {4, 7}:
        return False
    return all(char in "0123456789abcdef" for char in value[1:])


HUD_CONTROL = HudControlBus()
