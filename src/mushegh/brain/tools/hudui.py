"""Voice-addressable spatial HUD controls.

This tool publishes presentation-only intents. It cannot click approvals, invoke another tool, or
touch the operating system. The HUD applies each intent through its existing typed layout reducer.
"""

from __future__ import annotations

from mushegh.brain.hud_control import CANVAS_IDS, HUD_CONTROL, HudCommandError


async def control_hud(args: dict) -> str:
    try:
        command = HUD_CONTROL.publish(
            args.get("action", ""),
            canvas=args.get("canvas", ""),
            size=args.get("size", ""),
            query=args.get("query", ""),
            preset=args.get("preset", ""),
            primitive=args.get("primitive", ""),
            color=args.get("color", ""),
        )
    except HudCommandError as exc:
        return f"I couldn't change the HUD, sir — {exc}."
    action = command["action"].replace("_", " ")
    subject = command.get("canvas") or command.get("primitive") or command.get("preset") or command.get("query", "")
    return f"HUD {action} queued{f': {subject}' if subject else ''}, sir."


SCHEMAS = [{
    "type": "function",
    "function": {
        "name": "control_hud",
        "description": (
            "Control the owner's spatial HUD after a voice request. Open, focus, toggle, resize, "
            "background, restore, dismiss, inspect or explain a canvas; search the canvas library; "
            "change the grid preset; or render a safe primitive in the empty 3D canvas. This changes "
            "presentation only and never authorizes an action."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": [
                    "open", "focus", "toggle", "background", "dismiss", "inspect", "explain",
                    "resize", "restore", "reset", "preset", "search", "render_3d",
                ]},
                "canvas": {"type": "string", "enum": sorted(CANVAS_IDS)},
                "size": {"type": "string", "enum": ["quarter", "half_horizontal", "half_vertical", "full"]},
                "preset": {"type": "string", "enum": ["quad", "split_vertical", "split_horizontal"]},
                "query": {"type": "string", "maxLength": 120},
                "primitive": {"type": "string", "enum": ["box", "sphere", "cylinder", "cone", "torus"]},
                "color": {"type": "string", "description": "Optional #RGB or #RRGGBB material color."},
            },
            "required": ["action"],
        },
    },
}]

HANDLERS = {"control_hud": control_hud}
