"""45.R6 — spatial HUD shell and Mushegh presentation-control seam (hermetic).

The gate is deliberately split across both sides of the seam: the brain can only publish bounded,
validated presentation commands, and the client exposes only the command surface plus the spatial
mesh while consuming those commands idempotently through its typed reducer.

    uv run python bench/test_hud_modes.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.hud import hud_snapshot  # noqa: E402
from mushegh.brain.hud_control import CANVAS_IDS, HudCommandError, HudControlBus  # noqa: E402
from mushegh.brain.tools import hudui  # noqa: E402
from mushegh.brain.tools import group_tool_schemas, groups_for_text, tool_handlers  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


class _Empty:
    def active(self):
        return []

    def pending(self):
        return []

    def current_line(self):
        return ""


class _BrokenBus:
    def snapshot(self):
        raise RuntimeError("display unavailable")


def rejects(bus: HudControlBus, action: str, **kwargs) -> bool:
    try:
        bus.publish(action, **kwargs)
    except HudCommandError:
        return True
    return False


def main() -> int:
    print("\n[1] bounded, typed presentation commands")
    bus = HudControlBus(capacity=2, stream_id="test-stream")
    first = bus.publish("open", canvas="goals")
    bus.publish("resize", canvas="goals", size="half_vertical")
    third = bus.publish("render_3d", primitive="sphere", color="#00f0ff")
    snap = bus.snapshot()
    check("sequence is monotonic", first["sequence"] == 1 and third["sequence"] == 3)
    check("queue is bounded", [c["sequence"] for c in snap["commands"]] == [2, 3], str(snap))
    check("stream identity is stable", snap["stream_id"] == "test-stream")
    check("3D instructions target only the 3D canvas", third.get("canvas") == "3d_engine")
    check("unknown canvases are rejected", rejects(bus, "open", canvas="not_real"))
    check("unsafe CSS colors are rejected", rejects(bus, "render_3d", primitive="box", color="url(x)"))
    check("approval is not a HUD action", rejects(bus, "approve", canvas="approvals"))
    check("all 18 declared canvases are supported", len(CANVAS_IDS) == 18, str(sorted(CANVAS_IDS)))

    print("\n[2] the authenticated HUD snapshot carries the fail-quiet command stream")
    empty = _Empty()
    projected = hud_snapshot(objectives=empty, tasks=empty, approvals=empty, presence=empty, hud_control=bus)
    check("snapshot exposes the current command sequence", projected["hud_control"]["sequence"] == 3)
    broken = hud_snapshot(objectives=empty, tasks=empty, approvals=empty, presence=empty, hud_control=_BrokenBus())
    check("a broken display bus cannot sink /hud.json", broken["hud_control"] == {"stream_id": "", "sequence": 0, "commands": []})

    print("\n[3] Mushegh can discover and call the HUD tool without making it core")
    schemas = group_tool_schemas("hud")
    check("HUD group advertises exactly control_hud", [s["function"]["name"] for s in schemas] == ["control_hud"])
    check("voice-shaped text activates the HUD group", "hud" in groups_for_text("bring the goals canvas on screen"))
    check("handler is registered", tool_handlers().get("control_hud") is hudui.control_hud)
    previous = hudui.HUD_CONTROL
    try:
        local = HudControlBus(stream_id="handler-test")
        hudui.HUD_CONTROL = local
        reply = asyncio.run(hudui.control_hud({"action": "background", "canvas": "diagnostics"}))
        check("handler emits a speakable acknowledgement", "queued" in reply and "diagnostics" in reply)
        check("handler only publishes a presentation command", local.snapshot()["commands"][0]["action"] == "background")
    finally:
        hudui.HUD_CONTROL = previous

    print("\n[4] client shell contract")
    app = (ROOT / "clients/hud-spatial/src/App.tsx").read_text(encoding="utf-8")
    state = (ROOT / "clients/hud-spatial/src/state.ts").read_text(encoding="utf-8")
    styles = (ROOT / "clients/hud-spatial/src/styles.css").read_text(encoding="utf-8")
    model = (ROOT / "clients/hud-spatial/src/canvases/ModelCanvas.tsx").read_text(encoding="utf-8")
    check("no persistent header/nav/footer chrome remains", all(tag not in app for tag in ("<header", "<nav", "<footer")))
    check("old rail, dock and toolbar are absent", all(name not in app for name in ("canvas-rail", "background-dock", "layout-toolbar", "executive-strip")))
    check("one command surface drives search and commands", app.count('className="command-form"') == 1 and 'role="search"' in app)
    check("all canvas definitions have honest descriptions", state.count("description:") == 18)
    check("backgrounded canvases remain mounted", "const opened = [...state.tiles.map" in app and "is-background" in app)
    check("the initial 3D scene is empty", "SCENE EMPTY" in model and "calibration" not in model.lower())
    check("shared loaders cover async canvas work", app.count("<CanvasLoader") >= 2 and "loader-scan" in styles and "prefers-reduced-motion" in styles)
    check("remote command cursor is persisted", "CONTROL_CURSOR" in app and "command.sequence <= last" in app)
    check("no external font or asset origin was added", "https://" not in styles and "http://" not in styles)

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
