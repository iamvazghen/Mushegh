"""Every core-advertised tool must be routed, or exempt with a stated reason.

Written because this class of defect was found by hand twice in one session, and both
times the failure was worse than a score:

  * `routine` shipped, sat in the core surface every turn, and no route reached it - so
    every mode change depended on the model happening to volunteer it. "You can drop focus
    mode now" was answered "I have deactivated focus mode" while `MODES.focus_active()`
    stayed True.
  * the day-planning tools shipped, were advertised, and no route reached them, so a fully
    specified planning request was answered with 1005 characters of invented schedule.

A tool the model can see but no route can reach is a capability whose correctness depends
on the model guessing. The router exists to make that a decision rather than a coincidence,
so an unrouted core tool is a defect even when nothing is currently failing.

Not every unrouted tool is a bug: some exist for the owner to NAME ("delete_task",
"run_powershell"), where inferring them would be wrong. Those are exempt below, each with
its reason - which is the point. A silent gap and a considered exception should not look
the same, and the second version of this file is the one worth having.

Usage:
    uv run python bench/test_tool_reachability.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

#: Core-advertised tools that are deliberately NOT routed, and why that is correct.
#: Adding a tool here is a decision, not a cleanup.
EXEMPT: dict[str, str] = {
    "get_time": "answered inline and faster than a tool round-trip; forcing it was "
                "declined as gaming the scorer",
    # -- named directly by the owner; inferring them would be wrong --
    "delete_task": "the owner says 'delete'; inferring a destructive act from context "
                   "is exactly what the confirm-gate exists to prevent",
    "update_task": "needs fields the owner supplies; nothing implies it on its own",
    "complete_task": "completion is a consequential act the owner must ask for by name",
    "file_op": "filesystem access must be named, never inferred",
    "run_powershell": "shell execution must be named, never inferred",
    "process_op": "process control must be named, never inferred",
    "diagnose": "an owner asking for a diagnosis is asking for an ANSWER, not a runbook",
    "browse_web": "interactive browsing; a URL the owner names goes through the "
                  "scrape_url route, which is the reachable path for 'open this page'",
    "browser": "paired with browse_web",
    "open_app": "the owner names the app; inferring one would be a guess",
    "open_url": "the owner names the URL",
    "execute_task": "runs a plan that must already exist; reached through plan_task",
    "invoke_skill": "skill selection is its own decision, not a router guess",
    "run_protocol": "password-gated and consequential; never inferred",
    "send_push": "pushing to a device is a side effect the owner asks for by name",
    "mark_telegram": "an owner marking their own message read is named, not inferred",
    "save_contact": "saving a person is a write the owner asks for",
    "resolve_contact": "paired with save_contact",
    "set_home_location": "location is set once, deliberately, by name",
    "media_pause": "the owner says pause; there is no inference that implies it",
    "telegram_music": "paired with play_music",
    "convert": "arithmetic is answered inline; a unit conversion needs no tool round-trip",
    "fx_rate": "a rate lookup, but paired with crypto_price in the same route family",
    "self_health": "a diagnostic the owner requests explicitly",
    "news_brief": "S41 declared the unprompted feed a D-34 breach; it must be asked for",
    "list_tasks": "read back, not inferred from 'what should I do'",
    "work_on_task": "reached through the autonomy route, not on the name alone",
    "delegate_to_fleet": "reached when the fleet route matches",
    "play_music": "paired with stop_music and now_playing",
    "stop_music": "paired with play_music",
    "now_playing": "paired with play_music",
    "read_chat": "the owner names the chat; the router does not guess which",
    # `read_journal` and `list_skills` used to be here, and both exemptions were FALSIFIED by
    # measurement on 2026-10-09 (01.E1, median-5, Combination 70.2):
    #   - read_journal: "journal reads are prompted by the owner, not inferred". It WAS prompted
    #     by the owner, and the reply returned a journal entry that did not exist — a fabricated
    #     history from a model that was never handed the journal.
    #   - list_skills: "listing is answering a question, not executing a request". It is, and the
    #     model answered it from memory rather than reading the 26 playbooks actually on disk,
    #     listing capabilities that may not exist.
    # The premise of both was that a question needs no tool. The measurement says the opposite:
    # asked about its own state, this model invents it. Both are routed in intent_router now, and
    # this comment is here so neither is re-exempted on the same reasoning.
    "wiki_lookup": "an explicit lookup the owner asks to perform",
    "add_task": "needs a title and context the owner supplies; nothing implies it alone",
}


def main() -> int:
    from mushegh.brain.agent import MusheghAgent
    from mushegh.brain.intent_router import _CLAUSE_ONLY_ROUTES, _ROUTES

    agent = MusheghAgent()
    core = sorted(t["function"]["name"] for t in (agent._core_tools or []))

    routed: set[str] = set()
    for _, names in _ROUTES:
        routed.update(names)
    for _, names in _CLAUSE_ONLY_ROUTES:
        routed.update(names)

    unrouted = [t for t in core if t not in routed and t not in EXEMPT]
    covered = [t for t in core if t in routed]
    exempted = [t for t in core if t in EXEMPT]

    print(f"[1] core-advertised tools: {len(core)}")
    print(f"    routed                 : {len(covered)}")
    print(f"    exempt with a reason   : {len(exempted)}")
    print(f"    ROUTED BY NOTHING      : {len(unrouted)}")

    ok = True
    for name in unrouted:
        print(f"    FAIL  {name} is advertised every turn and no route can reach it")
    if unrouted:
        ok = False
        print("       Either add a route, or add it to EXEMPT with the reason it is correct")
        print("       for it to be unrouted. A silent gap and a considered exception must")
        print("       not look the same.")

    print("\n[2] the exempt set is honest")
    stale = sorted(t for t in EXEMPT if t not in core)
    for name in stale:
        print(f"    WARN  {name} is exempted but is no longer core-advertised; drop it")
    missing_reason = [t for t in EXEMPT if not EXEMPT[t].strip()]
    for name in missing_reason:
        print(f"    FAIL  {name} is exempted with no reason")
    if missing_reason:
        ok = False

    print("\n[3] the two defects that motivated this gate stay closed")
    from mushegh.brain.intent_router import forced_tools
    plan = forced_tools("Plan my day for me — deep work at 9am, admin at 4pm.")
    mode_off = forced_tools("You can drop focus mode now.")
    mode_on = forced_tools("Put yourself in focus mode for thirty minutes.")
    print(f"    day planning routes        : {plan}")
    print(f"    leaving a mode routes      : {mode_off}")
    print(f"    entering a mode routes     : {mode_on}")
    if "plan_today" not in plan:
        print("    FAIL  day planning is unrouted again")
        ok = False
    if "routine" not in mode_off:
        print("    FAIL  leaving a mode is unrouted again - Mushegh can claim a mode changed")
        print("          without it changing")
        ok = False
    if "routine" not in mode_on:
        print("    FAIL  entering a mode is unrouted")
        ok = False

    print("\n[4] no route names a tool the registry does not have")
    registry = set(agent._registry)
    phantom = sorted(n for n in routed if n not in registry)
    for name in phantom:
        print(f"    FAIL  {name} is routed but not registered")
    if phantom:
        ok = False

    print("\nALL CHECKS PASSED" if ok else "\nCHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())