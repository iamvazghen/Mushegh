"""28.R4 — D-13: physical door locks refuse. There is no confirmation path that opens one.

The charter puts four things outside the blast radius: physical door locks, main power
breakers, recursive filesystem purges, and external email or messaging dispatch. For the
first of them the code did not agree. `smarthome.py` confirm-gated `lock` and
`garage_door` through `proactive.confirm_required`, which is a second "yes" in a chat
window — and D-13 asks for the owner to be *physically present*, not to have said a word.

That distinction is the whole content of this test. A confirm gate is a speed bump; the
decision was a wall. So the refusal lives inside `ha_call`, before a request is even
built, rather than in the policy layer above it — a refusal that only exists in the gate is
one refactor away from being gone.

What this asserts:

  * `lock` and `garage_door` are refused by policy, and refused *before* any HTTP call;
  * no confirmation flag, argument or second pass unlocks them;
  * the middle tier D-13 does not name — alarm panels, covers, climate, water heater —
    still confirms, because a wall where a speed bump was wanted is its own failure;
  * reading a lock still works: information is not actuation;
  * an ordinary lamp is untouched, because a voice home must not nag to turn on a light.

Hermetic: the HTTP layer is replaced. No Home Assistant, no network, no token needed.

    uv run python bench/test_blast_radius_refusal.py
"""

from __future__ import annotations

import asyncio
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
        print(f"  [FAIL] {name}  {detail}")


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


async def main() -> int:
    from afon.brain.proactive import confirm_required
    from afon.brain.tools import smarthome as sh
    from afon.config import settings

    settings.ha_url = "http://ha.local:8123"
    settings.ha_token = "test-token"

    posted: list[str] = []
    fetched: list[str] = []
    state_reply = {"entity_id": "lock.front_door", "state": "locked",
                   "attributes": {"friendly_name": "Front door"}}

    async def fake_post(url, **kw):
        posted.append(url)
        return _Resp([])

    async def fake_get(url, **kw):
        fetched.append(url)
        return _Resp(state_reply)

    sh.http_post, sh.http_get = fake_post, fake_get

    print("[1] a lock request is refused, and no request is ever built")
    posted.clear()
    out = await sh.ha_call({"domain": "lock", "service": "unlock", "entity": "lock.front_door"})
    check("the refusal is spoken, not an error", "don't" in out.lower() and "sir" in out, out)
    check("...and it never reached Home Assistant", posted == [], str(posted))

    print("\n[2] ...for every service a lock exposes, not just unlock")
    posted.clear()
    for service in ("lock", "unlock", "open", "close"):
        out = await sh.ha_call({"domain": "lock", "service": service, "entity": "lock.front_door"})
        check(f"lock.{service} is refused", "don't" in out.lower() and posted == [], f"{out} / {posted}")

    posted.clear()
    for service in ("open_cover", "close_cover"):
        out = await sh.ha_call({"domain": "garage_door", "service": service,
                                "entity": "cover.garage"})
        check(f"garage_door.{service} is refused", "don't" in out.lower() and posted == [],
              f"{out} / {posted}")

    print("\n[3] no argument, flag or second pass unlocks the refusal")
    for extra in (
        {"confirmed": True},
        {"confirm": True},
        {"force": True},
        {"dry_run": False, "confirmed": True},
    ):
        args = {"domain": "lock", "service": "unlock", "entity": "lock.front_door", **extra}
        posted.clear()
        out = await sh.ha_call(args)
        check(f"{extra} changes nothing", "don't" in out.lower() and posted == [], f"{out} / {posted}")

    print("\n[4] the gate itself still knows these are sensitive")
    check("ha_call on a lock is confirm-gated too (belt and braces)",
          confirm_required("ha_call", {"domain": "lock", "service": "unlock"}))
    check("...and so is the garage door",
          confirm_required("ha_call", {"domain": "garage_door", "service": "open_cover"}))
    check("the refusal is reachable without consulting the gate at all",
          sh._refuse_blast_radius("lock") is not None)
    check("...and returns None for a domain inside the radius",
          sh._refuse_blast_radius("light") is None)

    print("\n[5] the middle tier D-13 does not name still confirms, it does not refuse")
    for domain in ("alarm_control_panel", "cover", "climate", "water_heater"):
        check(f"{domain} is confirm-gated", confirm_required("ha_call", {"domain": domain}))
        check("...and is NOT refused", sh._refuse_blast_radius(domain) is None, domain)

    print("\n[6] reading a lock still works — information is not actuation")
    fetched.clear()
    out = await sh.ha_state({"entity": "lock.front_door"})
    check("ha_state reports the lock state", "Front door" in out and "is locked" in out, out)
    check("...and it was a real read", any("states/lock.front_door" in g for g in fetched), str(fetched))

    print("\n[7] an ordinary lamp is untouched — a voice home must not nag")
    posted.clear()
    out = await sh.ha_call({"domain": "light", "service": "turn_on", "entity": "light.kitchen"})
    check("a light still actuates", any("/api/services/light/turn_on" in u for u in posted), str(posted))
    check("...without a refusal", "don't" not in out.lower(), out)
    check("...and a lamp of his own is not confirm-gated",
          not confirm_required("ha_call", {"domain": "light", "entity": "light.kitchen"}))

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
