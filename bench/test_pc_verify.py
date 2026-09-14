"""C5 hermetic test — PC-agent see→act→VERIFY loop (no network, temp files only).

Asserts that after a PC op runs, the executor confirms the effect actually landed (file exists/gone)
and flags a mismatch when it didn't — the "verify" step that turns blind execution into see→act→verify.
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import afon.edge.pc_agent as pc  # noqa: E402
from afon.edge.pc_agent import _run_op, _verify_effect  # noqa: E402

_ok = _fail = 0


def check(cond, label):
    global _ok, _fail
    if cond:
        _ok += 1
    else:
        _fail += 1
        print(f"  FAIL: {label}")


tmp = Path(tempfile.mkdtemp())
f = tmp / "made.txt"

# 1) pure verify: reflects real filesystem state
f.write_text("hi")
check(_verify_effect("file_op", {"action": "create_file", "path": str(f)}) == "verified — it exists now",
      "create verify: existing file confirmed")
f.unlink()
check(_verify_effect("file_op", {"action": "create_file", "path": str(f)}).startswith("WARNING"),
      "create verify: missing file flagged")
check(_verify_effect("file_op", {"action": "delete_file", "path": str(f)}) == "verified — it's gone",
      "delete verify: absent file confirmed")
check(_verify_effect("open_url", {"url": "x"}) is None, "non-verifiable op -> no note")

# 2) see→act→verify through _run_op: the handler ACTS, then _run_op VERIFIES the effect
order: list[str] = []


async def fake_create(args):
    order.append("act")
    Path(args["path"]).write_text("made")
    return "Created the file, sir."


async def fake_create_noop(args):
    order.append("act")   # claims success but does nothing -> verify must catch it
    return "Created the file, sir."


async def run():
    pc.LOCAL_HANDLERS["file_op"] = fake_create
    ok, out = await _run_op("file_op", {"action": "create_file", "path": str(f)})
    check(ok and "verified — it exists now" in out, f"act then verify: success confirmed (got {out!r})")
    check(order == ["act"], "handler (act) ran before the verify step")

    f.unlink()
    pc.LOCAL_HANDLERS["file_op"] = fake_create_noop
    ok2, out2 = await _run_op("file_op", {"action": "create_file", "path": str(f)})
    check(ok2 and "WARNING" in out2, f"a handler that lied about creating is caught by verify (got {out2!r})")


asyncio.run(run())


# ---- 04.F4: a dead link is unreachable within one turn, never a success and never a long wait --
# The executor can verify what it did. What it could not do is notice it was never asked. A laptop
# that closes its lid leaves the websocket open for over a minute, so every device command was
# accepted, waited the full ninety-second result window, and only then failed — several turns after
# the owner asked, having said nothing in the turn where he did.
async def run_linkdown():
    import time as _t

    from afon.brain.pc_link import STALE_AFTER_S, PcLink

    class DeadWS:
        """A socket whose peer is gone: the send succeeds, the ping is never answered."""

        def __init__(self):
            self.sent = []

        async def send(self, data):
            self.sent.append(data)

        def ping(self):
            return asyncio.get_event_loop().create_future()   # never resolves

    class LiveWS(DeadWS):
        def ping(self):
            fut = asyncio.get_event_loop().create_future()
            fut.set_result(b"")
            return fut

    link = PcLink()
    check(link.active is False, "with nothing registered, the link is not active")
    raised = ""
    try:
        await link.forward("file_op", {})
    except Exception as e:
        raised = type(e).__name__
    check(raised == "ConnectionError", f"an unregistered link refuses immediately (got {raised!r})")

    dead = DeadWS()
    link.register(dead, "laptop")
    check(link.active is True, "a registered socket reads as active")
    started = _t.monotonic()
    raised = ""
    try:
        await link.forward("file_op", {}, timeout=90.0)
    except Exception as e:
        raised = type(e).__name__
    took = _t.monotonic() - started
    check(raised == "ConnectionError", f"a dead peer is reported as unreachable (got {raised!r})")
    check(took < 10.0, f"...within one turn, not the 90s result window (took {took:.1f}s)")
    check(not dead.sent, "and the command was never sent into the void")

    live = LiveWS()
    link.register(live, "laptop")
    check(await link.reachable() is True, "a live peer answers the ping")
    # A ping that comes back is proof of life, so the staleness clock resets on it.
    link._seen = _t.monotonic() - (STALE_AFTER_S + 60)
    check(link.stale is True, "a long-silent link reads as stale")
    await link.reachable()
    check(link.stale is False, "...and a successful ping clears that")

    # Health used to call `PC_LINK.active()` — a property, so it raised TypeError, was swallowed,
    # and the laptop was reported down with a made-up reason even while it was connected.
    from afon.brain import health

    from afon.brain import pc_link as pl

    real = pl.PC_LINK
    pl.PC_LINK = link
    try:
        ok, detail = await health._check_pc_link()
        check(ok is True, f"health reports a live laptop as healthy (got {detail!r})")
        check("TypeError" not in detail, "...without a swallowed error standing in for the answer")
        pl.PC_LINK = PcLink()
        pl.PC_LINK.register(DeadWS(), "laptop")
        ok2, detail2 = await health._check_pc_link()
        check(ok2 is False, "a registered-but-silent laptop is NOT reported as connected")
        check("not answering" in detail2, f"...and the reason says so (got {detail2!r})")
    finally:
        pl.PC_LINK = real


asyncio.run(run_linkdown())

def test_launch_and_volume_are_verified() -> None:
    """04.R1 — the two cases `_verify_effect` used to decline, and the answer that was a wish."""
    print("\n[04.R1] a launch is verified by the same probe that verifies a kill")
    from afon.edge.pc_agent import _image_name

    for given, want in [("notepad", "notepad.exe"), ("chrome.exe", "chrome.exe"),
                        ("C:/Program Files/X/code.exe", "code.exe"), ('"notepad"', "notepad.exe")]:
        check(_image_name(given) == want, f"_image_name({given!r}) -> {_image_name(given)!r}")
    check(_image_name("") == "", "an empty app name produces no image name")

    real = pc._proc_running
    try:
        pc._proc_running = lambda _n: True
        check(pc._verify_effect("open_app", {"app": "notepad"}) == "verified — it's running",
              "a launch whose process is found reports verified")
        # The evidence is asymmetric and the wording follows it: finding the image name proves it
        # runs; NOT finding it proves very little ("word" runs as WINWORD.EXE, a store app has no
        # image name, a heavy app is still loading). A false "it didn't start" sends the owner to
        # look at a window that is already open, which is worse than saying nothing.
        pc._proc_running = lambda _n: False
        check(pc._verify_effect("open_app", {"app": "notepad"}) is None,
              "a launch the probe cannot find reports NOTHING, not a warning")
        check(pc._verify_effect("process_op", {"action": "start", "name": "notepad"}) is None,
              "the same rule covers process_op start")
        pc._proc_running = lambda _n: True
        check(pc._verify_effect("process_op", {"action": "start", "name": "notepad"})
              == "verified — it's running", "...and verifies it when the probe does find it")
        # A kill is the opposite shape and must not have changed.
        check(pc._verify_effect("process_op", {"action": "kill", "name": "notepad"})
              == "WARNING: still running after kill",
              "a kill still WARNS when the process survives — absence is the proof there")
        check(pc._verify_effect("open_url", {"url": "http://x"}) is None,
              "a URL open is still unverifiable, and says so by staying silent")
    finally:
        pc._proc_running = real


def test_volume_reports_what_it_measured() -> None:
    print("\n[04.R1] the volume answer is a reading, not the number that was requested")
    import asyncio as _a

    from afon.brain.tools import audioout as A
    from afon.brain.playback import Playing

    real_fwd, real_cur = A._forward, None
    import afon.brain.playback as _pb
    real_cur = _pb.current

    async def _fake_current():
        return Playing(where="desktop", label="something")

    state = {"now": 30}

    def make_forward(settles_at):
        async def _fwd(op, args, _local):
            if args.get("level") is None:
                return {"ok": True, "now": state["now"]}
            state["now"] = settles_at(int(args["level"]))
            return {"ok": True, "now": state["now"]}
        return _fwd

    try:
        _pb.current = _fake_current
        A.current = _fake_current

        # The honest case: it lands where it was asked to.
        state["now"] = 30
        A._forward = make_forward(lambda want: want)
        out = _a.run(A.set_volume({"level": 40}))
        check("40%" in out, f"a volume that lands is reported plainly: {out!r}")

        # The case this exists for: Windows rounds, a device clamps, an endpoint that has gone away
        # accepts the write and changes nothing. Reporting the REQUEST as the result is the
        # media-control version of announcing a send that never left.
        state["now"] = 100
        A._forward = make_forward(lambda _want: 100)
        out = _a.run(A.set_volume({"level": 40}))
        check("100%" in out, f"the answer reports what it MEASURED: {out!r}")
        check("40" in out, f"...and says what it asked for, so the gap is visible: {out!r}")

        # A read-back that fails must not invent a reading.
        state["now"] = 30

        reads = {"n": 0}

        async def _write_ok_read_dead(op, args, _local):
            # The FIRST read works (set_volume needs the current level to compute a target); the
            # read-BACK afterwards is the one that dies. That is the realistic shape: the endpoint
            # goes away between the write and the confirmation.
            if args.get("level") is None:
                reads["n"] += 1
                if reads["n"] == 1:
                    return {"ok": True, "now": 30}
                return {"ok": False, "out": "no endpoint"}
            return {"ok": True}

        A._forward = _write_ok_read_dead
        out = _a.run(A.set_volume({"level": 55}))
        check("55%" in out, f"an unreadable level falls back to the requested one: {out!r}")
    finally:
        A._forward = real_fwd
        _pb.current = real_cur
        A.current = real_cur


test_launch_and_volume_are_verified()
test_volume_reports_what_it_measured()

print(f"=== {_ok}/{_ok + _fail} checks passed ===")
sys.exit(1 if _fail else 0)
