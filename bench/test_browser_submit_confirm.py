"""05.R1 — a browser op that could commit a form confirms; reading a page does not.

D-07 says reading is a read-only query and submitting is not. The code did not say either:
`browser` sat in `proactive.CONFIRM_TIER` with no dynamic rule, so `confirm_required` fell
through to its final `return True` and **every** browser action confirmed — `read`, `open`
and `screenshot` included.

That is worth stating precisely, because the subsystem doc had the defect pointing the other
way (`docs/subsystems/05-browser-control.md`: "today a spend or a send can be one voice command
away"). Both readings describe a real problem and they are not the same problem:

  * a gate that never fires lets a purchase through;
  * a gate that fires on every page read trains the owner to say yes without reading it, and
    then the one that mattered is waved through with the rest. `ha_call`'s own comment in
    `proactive.py` names this failure for lamps, and it applies here with more at stake,
    because this browser carries his logged-in sessions.

So the rule is: navigation and reading flow; `fill`/`type` flow, because the data is still
sitting in the page; and `click`/`press` confirm whenever they could commit — which is when
something has been typed, when Enter is pressed, or when the thing being clicked names a
commit ("Buy now", "Send", "Delete account"). Anything unrecognised confirms.

05.R1's threshold is "0 money-sending or data-sending submits without a confirmation". This
asserts it by covering every path that can commit, rather than by guessing which destination
costs money — a URL allowlist would be a list that is wrong the first time a checkout moves.

Hermetic: imports the policy function and the tool's own gate. No browser, no network.

    uv run python bench/test_browser_submit_confirm.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  <- {detail}" if detail else ""))


def main() -> int:
    from mushegh.brain.proactive import CONFIRM_TIER, confirm_required
    from mushegh.brain.tools import browser as B

    print("[1] the tool is still in the confirm tier at all")
    check("browser is in CONFIRM_TIER", "browser" in CONFIRM_TIER)
    check("the dynamic rule is reachable from the policy layer",
          hasattr(B, "submit_needs_confirm"))

    print("\n[2] reading and navigating never confirm — the anti-nag half")
    B.reset_commit_state()
    for action in ("open", "read", "screenshot", "back", "new_tab", "tabs",
                   "switch_tab", "close_tab", "close_all_other_tabs", "close"):
        check(f"{action} flows without a confirmation",
              not confirm_required("browser", {"action": action}))

    print("\n[3] typing does not confirm, because nothing has left the page")
    B.reset_commit_state()
    check("fill flows", not confirm_required("browser", {"action": "fill",
                                                         "selector": "#email",
                                                         "value": "a@b.c"}))
    check("type flows", not confirm_required("browser", {"action": "type", "value": "hello"}))
    check("...and neither armed the gate by being ASKED about",
          not B.commit_armed(),
          "confirm_required must stay pure; only a dispatched op arms it")

    print("\n[4] a click after typing is a submit, and confirms")
    B.reset_commit_state()
    B._note_action("fill")          # what `browser()` records once the op has actually run
    check("the gate is armed after a fill", B.commit_armed())
    check("a plain click now confirms",
          confirm_required("browser", {"action": "click", "text": "Continue"}))
    check("...and so does any key press",
          confirm_required("browser", {"action": "press", "key": "Tab"}))

    print("\n[5] navigating away abandons the form and disarms")
    B._note_action("open")
    check("the gate is disarmed after a navigation", not B.commit_armed())
    check("a click on an ordinary link flows again",
          not confirm_required("browser", {"action": "click", "text": "Next page"}))

    print("\n[6] Enter is a submit whether or not we saw the typing")
    B.reset_commit_state()
    for key in ("Enter", "enter", "Return", "NumpadEnter"):
        check(f"press {key!r} confirms with an empty gate",
              confirm_required("browser", {"action": "press", "key": key}))
    check("a non-Enter key on a clean page flows",
          not confirm_required("browser", {"action": "press", "key": "ArrowDown"}))

    print("\n[7] one-click commits confirm with no typing at all")
    B.reset_commit_state()
    for target in ("Buy now", "Pay £40", "Place order", "Checkout", "Subscribe",
                   "Send message", "Confirm booking", "Delete account", "Transfer funds",
                   "I agree", "Submit"):
        check(f"click {target!r} confirms", confirm_required("browser",
                                                             {"action": "click", "text": target}))
    check("a commit word in the SELECTOR counts too",
          confirm_required("browser", {"action": "click", "selector": "button#submit-order"}))
    check("...and an innocent link still flows",
          not confirm_required("browser", {"action": "click", "text": "About us"}))

    print("\n[8] an unknown verb confirms — this tool is not one to guess on")
    B.reset_commit_state()
    check("an unrecognised action confirms",
          confirm_required("browser", {"action": "upload_file"}))
    check("a missing action confirms", confirm_required("browser", {}))
    check("a None args confirms", confirm_required("browser", None))

    print("\n[9] the gate cannot be argued out of")
    B.reset_commit_state()
    B._note_action("fill")
    check("a 'confirmed' flag in the args does not unlock it",
          confirm_required("browser", {"action": "click", "text": "Pay",
                                       "confirmed": True, "approved": True}),
          "D-09: a confirmation is never carried by an argument")
    check("a secret-typed password still arms rather than exempts",
          confirm_required("browser", {"action": "click", "text": "Log in", "secret": True}))

    print("\n[10] 05.R1's threshold, stated as the test it is")
    B.reset_commit_state()
    spends = [
        {"action": "click", "text": "Buy now"},
        {"action": "click", "text": "Confirm payment"},
        {"action": "press", "key": "Enter"},
    ]
    check("0 of the money-sending paths run unconfirmed",
          all(confirm_required("browser", a) for a in spends))
    B.reset_commit_state()
    B._note_action("type")
    check("0 of the data-sending paths run unconfirmed after input",
          confirm_required("browser", {"action": "click", "text": "Continue"})
          and confirm_required("browser", {"action": "press", "key": "Enter"}))

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
