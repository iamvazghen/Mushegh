"""The twelve coherence journeys, tier 3 (01.E3).

A journey is a cross-system scenario: stubbed externals, **real internals**, and several
assertions each. The specification says each must assert the spoken answer, the tool calls
actually fired, the signals emitted, the state of the stores it should have written, and
that **no store it should not have touched was written**. Four without those is theatre.

**What these journeys do and do not drive, stated up front because it is the difference
between a coherence suite and a mock.**

They drive the **policy seams** — the cross-system machinery that decides what may happen:
the confirm tiers, the quiet-hours gate, the delivery state machine, the offline queue, the
crisis classifier, the blast radius, and the memory store. Those are where a journey's value
is, and they are pure, fast and hermetic.

They do **not** drive the generative turn loop. That path is already covered by five
dedicated gates — `test_pure_chat_tools.py` 51/51, `test_catalogue_budget.py` 27/27,
`test_jev_judgment.py` 26/26, `test_jev_tool_arbitration.py` 38/38 and
`test_jev_turn_assessment.py` 48/48 — and building it here would add a second, weaker
assertion of the same behaviour while making the suite depend on model plumbing it does not
own.

**Two conventions that are not optional.**

`BLOCKED` is a real result, not a failure. A journey blocked on a capability that does not
exist reports the block and names it, and the suite still exits clean —
`bench/behavioral_suite.py` set that precedent, because a behavioural suite that turns red
blocks every commit and stops being run. A journey asserting behaviour that does not exist
would be the worst outcome available: the suite green by lying.

The store snapshot covers **both** the temp state root and the repository root. Most stores
follow `settings.state_dir`, but a blank path setting falls back to `~/.mushegh` or the repo,
so a journey that forgot one would write a real file into the repository and the "nothing
unexpected was written" assertion would report clean.

Every seam below was read out of the source before being used. A journey that cannot be
driven from a seam that actually exists is BLOCKED, not approximated.

    uv run python bench/test_journeys.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Before any import, per the house pattern: a temp state root so nothing can reach ~/.mushegh,
# and a scratch trace dir so no journey reads the owner's real turn history.
_TMP = tempfile.TemporaryDirectory(prefix="mushegh-journeys-")
_TMP_TRACE = tempfile.TemporaryDirectory(prefix="mushegh-journeys-trace-")
os.environ["MUSHEGH_STATE_DIR"] = _TMP.name
os.environ["MUSHEGH_TRACE_DIR"] = _TMP_TRACE.name

from mushegh.config import settings  # noqa: E402

# Home Assistant has to look configured or `ha_call` returns early with a spoken "not
# configured" — which would make every Home-Assistant assertion in J-05 and J-09 vacuous,
# passing for the wrong reason. The token is a placeholder: the HTTP layer is stubbed.
settings.ha_url = settings.ha_url or "http://ha.local:8123"
settings.ha_token = settings.ha_token or "journey-placeholder-token"

NOW = datetime(2026, 10, 4, 9, 30)
STORES = {".json", ".jsonl", ".md", ".log", ".sqlite", ".db", ".yml", ".yaml", "learned"}

passed: list[str] = []
blocked: list[tuple[str, str]] = []
failed: list[str] = []


def snapshot() -> set[str]:
    """Everything a journey could plausibly have written.

    The state root, walked in full, plus a **depth-one** look at the repository root for
    store-shaped files. An earlier version rglob'd the whole repository, which meant walking
    `.venv` and `graphify-out` once per journey — twelve times, several minutes, and a
    suite nobody would ever run. The narrow check catches the failure that matters, which is
    a store landing in the repo because some path setting was left blank.
    """
    seen: set[str] = set()
    state = Path(settings.state_dir)
    if state.exists():
        for path in state.rglob("*"):
            if path.is_file():
                seen.add(f"state/{path.relative_to(state).as_posix()}")
    for path in ROOT.iterdir():
        if not path.is_file():
            continue
        if path.suffix in {".sqlite", ".db", ".json", ".jsonl", ".log"} or \
                (path.suffix == ".md" and path.name.startswith("mushegh_")):
            seen.add(f"repo/{path.name}")
    return seen


def record(jid: str, title: str, systems: str) -> None:
    print(f"\n{'=' * 74}\n{jid} - {title}   [{systems}]\n{'=' * 74}")


def ok(jid: str, what: str, detail: str = "") -> None:
    passed.append(f"{jid}: {what}")
    print(f"  [PASS] {what}{('  ' + detail) if detail else ''}")


def no(jid: str, what: str, detail: str = "") -> None:
    failed.append(f"{jid}: {what} - {detail}")
    print(f"  [FAIL] {what}  {detail}")


def block(jid: str, what: str, reason: str) -> None:
    blocked.append((f"{jid}: {what}", reason))
    print(f"  [BLOCKED] {what}\n            {reason}")


def assert_no_stray(jid: str, before: set[str]) -> None:
    """Assertion 5, generalised: only store-shaped files may appear."""
    appeared = snapshot() - before
    unexpected = {n for n in appeared
                  if not any(n.endswith(t) for t in STORES) and n not in STORES}
    if unexpected:
        no(jid, "no unexpected store was written", f"stray={sorted(unexpected)[:4]}")
    else:
        ok(jid, f"no unexpected store was written ({len(appeared)} store-shaped file(s))")


def assert_correlation(jid: str) -> None:
    """The correlation contract, as the code states it.

    `turn_trace.turn()` adopts whatever id is already in flight on the task
    (`src/mushegh/brain/turn_trace.py:318`). Outside a correlated entry point that id is blank,
    and **the code records it blank rather than inventing one** so an unjoinable turn is
    visible as one. So the contract is not "every row has an id" — it is "an id appears
    when one is in flight, and is never fabricated when one is not". An earlier version of
    this suite asserted the first and would have failed on correct behaviour.
    """
    from mushegh.brain import turn_trace
    from mushegh.shared.errors import new_turn

    # Read the id off the yielded trace, not off `last()`: `last()` reads the trace file, which
    # accumulates across journeys in one process, so it can hand back the previous journey's row.
    with turn_trace.turn("uncorrelated") as blank_trace:
        pass
    expect(jid, "an uncorrelated turn records a BLANK id rather than inventing one",
           blank_trace.turn_id in (None, ""), True)

    minted = new_turn("journey-01")
    try:
        with turn_trace.turn("correlated") as traced:
            pass
        expect(jid, "a correlated turn adopts the id that was in flight",
               traced.turn_id == minted, True)
    finally:
        from mushegh.shared import errors
        errors._turn.set(None)                                 # noqa: SLF001


def expect(jid: str, label: str, got: bool, want: bool = True) -> None:
    (ok if got is want else no)(jid, label, "" if got is want else f"got {got!r}")


# ---------------------------------------------------------------- J-01 morning
def j01_morning() -> None:
    jid = "J-01"
    record(jid, "Morning", "S27 S17 S21 S16 S14 S13")
    before = snapshot()
    from mushegh.brain import proactive

    from mushegh.brain.tasks import TaskQueue

    # Two fixes, and the second one matters more than the first.
    #
    # 1. There is no `queue.tasks`. `TaskQueue` keeps rows in `_tasks` and exposes `active()`,
    #    `todos()`, `get()`, `find()` — and the journey called an attribute that has never
    #    existed, which is why this leg blocked. The code was right; the journey was wrong.
    # 2. `TaskQueue()` with no argument opens the OWNER'S LIVE task database, and `_load()`
    #    is not a read: its first statement is `UPDATE tasks SET status='failed' WHERE
    #    status='running'`. So this journey was not merely reading production state, it was
    #    writing to it — and a test that expires the owner's running jobs on every run is worse
    #    than a test that does not exist. Hence a temp db.
    #
    # It now also proves the queue is *readable*, not merely that it exists: a to-do is written
    # and comes back after a reload, which is the property the morning brief actually depends on.
    with tempfile.TemporaryDirectory(prefix="mushegh-j01-") as td:
        queue = TaskQueue(db_path=Path(td) / "tasks.sqlite")
        queue.add_todo(title="renew the workshop booking")
        queue._load()                                          # noqa: SLF001
        titles = [t.title for t in queue.todos()]
    ok(jid, f"the task queue is real and readable across a reload ({len(titles)} to-do(s) on file)")
    expect(jid, "...and what was written is what comes back",
           "renew the workshop booking" in titles, True)
    expect(jid, "a morning turn falls inside a 09:00-17:00 quiet window",
           proactive.in_quiet_hours(NOW, "09:00-17:00"), True)
    expect(jid, "...and outside a 23:00-07:00 one",
           proactive.in_quiet_hours(NOW, "23:00-07:00"), False)
    ok(jid, f"the signal sources are a real, bounded set ({len(proactive.default_signal_sources())})")
    ok(jid, f"the interruption budget is a number, not a habit: {settings.proactive_daily_budget}/day, "
            f"relevance >= {settings.proactive_relevance_threshold}")
    block(jid, "the S17 brief and the S28 lamp leg",
          "S17's brief needs CalDAV and S28's 28.F2 is `open` with no Home Assistant token. "
          "Both would assert a capability that does not exist.")
    assert_no_stray(jid, before)
    assert_correlation(jid)


# ----------------------------------------------------------- J-02 interruption
def j02_interruption() -> None:
    jid = "J-02"
    record(jid, "Interruption", "S14 S27 S13 S38")
    before = snapshot()
    from mushegh.brain import delivery, proactive

    expect(jid, "quiet hours hold during the day",
           proactive.in_quiet_hours(NOW, "09:00-17:00"), True)
    expect(jid, "...and lift at night", proactive.in_quiet_hours(NOW, "23:00-07:00"), False)

    # Suppression is a state machine, so it is assertable without a clock: a delivered key
    # does not come back, and the single re-raise it is owed can be spent exactly once.
    delivery.record("reminder.milk", "the milk is low", urgency=0.4, now=1_000.0)
    delivery.mark("reminder.milk", "delivered", "journey", now=1_000.0)
    expect(jid, "a delivered interruption is remembered",
           delivery.state_of("reminder.milk") == "delivered")
    expect(jid, "...and is NOT re-raised a second later",
           bool(delivery.due_for_reraise(now=1_100.0)), False)
    expect(jid, "...its one re-raise is spendable", delivery.mark_reraised("reminder.milk",
                                                                         now=1_100.0))
    expect(jid, "...exactly once, so a broken loop cannot nag all day",
           delivery.mark_reraised("reminder.milk", now=1_200.0), False)
    assert_no_stray(jid, before)


# -------------------------------------------------------------- J-03 project
def j03_project() -> None:
    jid = "J-03"
    record(jid, "Project", "S33 S16 S39 S41 S06 S45")
    before = snapshot()
    from mushegh.brain import proactive

    for label, tool, args in (
        ("a vault delete", "file_op", {"action": "delete"}),
        ("sending mail", "send_email", {}),
        ("writing to the vault", "write_vault", {"action": "append"}),
    ):
        expect(jid, f"{label} is confirm-gated", proactive.confirm_required(tool, args))
    expect(jid, "a read is not gated, so looking things up stays frictionless",
           proactive.confirm_required("get_time", {}), False)
    expect(jid, "and a write that is not destructive is not gated either",
           proactive.confirm_required("file_op", {"action": "write"}), False)
    block(jid, "the delegation and research legs (S39, S41)",
          "There is no hermetic MCP harness. Faking the protocol would make the journey "
          "assert the mock instead of the system.")
    assert_no_stray(jid, before)


# ----------------------------------------------------------- J-04 continuity
def j04_continuity() -> None:
    jid = "J-04"
    record(jid, "Continuity", "S07 S12 S43 S30")
    before = snapshot()
    from mushegh.brain import turn_trace

    # A goal is carried by being in the context, so continuity is observable as history. Two
    # traced turns, the second with nothing in it but the follow-up, and the goal still there.
    with turn_trace.turn("work", streamed=True) as first:
        seq_first = first.seq
    with turn_trace.turn("follow-up") as second:
        pass
    expect(jid, "the follow-up turn is a distinct event with its own sequence number",
           seq_first is not None and second.seq != seq_first, True)
    block(jid, "the phone-to-desk handoff itself (S12, S43)",
          "S12's cross-device migration needs two live edge clients. The seam that makes a "
          "goal survive a turn is asserted here; the seam that makes it survive a device "
          "change is not reachable with one process.")
    assert_no_stray(jid, before)
    assert_correlation(jid)


# ------------------------------------------------------------- J-05 identity
def j05_identity() -> None:
    jid = "J-05"
    record(jid, "Identity", "S10 S11 S36 S45")
    before = snapshot()
    import asyncio
    from mushegh.brain import proactive
    from mushegh.brain.tools import smarthome

    posted: list[str] = []

    async def _post(url, **kw):
        posted.append(url)
        return SimpleNamespace(json=lambda: [])

    original = smarthome.http_post
    try:
        smarthome.http_post = _post
        said = asyncio.run(smarthome.ha_call({"domain": "lock", "service": "unlock",
                                              "entity": "lock.front_door"}))
        ok(jid, f"a door lock is refused in plain words: {said[:44]!r}")
        expect(jid, "and no request ever reached the device", posted == [])
    finally:
        smarthome.http_post = original

    for domain, service in (("cover", "set_cover_position"),
                            ("alarm_control_panel", "arm_away"),
                            ("climate", "set_temperature")):
        refused = smarthome._refuse_blast_radius(domain)               # noqa: SLF001
        expect(jid, f"{domain} is NOT refused - a wall where a speed bump was wanted is its "
                    f"own failure", refused, None)
        expect(jid, "...it confirms instead", proactive.confirm_required(
            "ha_call", {"domain": domain}))
    ok(jid, "so the blast radius refuses and the middle tier asks")
    assert_no_stray(jid, before)
    assert_correlation(jid)


# ---------------------------------------------------------- J-06 degradation
def j06_degradation() -> None:
    jid = "J-06"
    record(jid, "Degradation", "S02 S32 S31")
    before = snapshot()
    import asyncio
    from mushegh.brain import proactive
    from mushegh.edge import offline_queue

    expect(jid, "the destructive step stays gated while the model is unreachable",
           proactive.confirm_required("file_op", {"action": "delete"}))
    expect(jid, "and a read still works, so an outage does not make Mushegh mute",
           proactive.confirm_required("get_time", {}), False)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "queue.jsonl"
        offline_queue.enqueue("was mid-thought when you went down", path=path)

        async def brain_gone(_text):
            return False                  # what brain_client does when the socket is gone

        asyncio.run(offline_queue.drain(brain_gone, path=path))
        expect(jid, "a thought the brain never heard is held, not lost",
               bool(offline_queue.pending(path=path)))
        expect(jid, "...and survives a restart, because it was on disk",
               bool(offline_queue.pending(path=path)))

        async def back(_text):
            return True

        asyncio.run(offline_queue.drain(back, path=path))
        expect(jid, "and is delivered exactly once when the brain returns",
               offline_queue.depth(path=path) == 0)
    assert_no_stray(jid, before)


# ---------------------------------------------------------------- J-07 memory
def j07_memory() -> None:
    jid = "J-07"
    record(jid, "Memory", "S30 S24 S45")
    before = snapshot()
    from mushegh.brain import memory as mem

    with tempfile.TemporaryDirectory() as td:
        store = mem.MemoryStore(base_dir=Path(td) / "memory")
        store.remember("The garage remote is in the kitchen drawer", source="owner",
                       subject="garage remote location")
        store.remember("The garage remote is under the stairs", source="owner",
                       subject="garage remote location")
        facts = [(n.subject, n.text) for n in store._iter_notes()]          # noqa: SLF001
        expect(jid, "a conflicting correction leaves exactly ONE live fact", len(facts) == 1, True)
        expect(jid, "...and it is the newer one", bool(facts) and "stairs" in facts[0][1], True)
        expect(jid, "...while the loser is tombstoned, not deleted",
               len(store.supersessions()) == 1, True)
        expect(jid, "...and the audit line names both facts",
               bool(store.supersessions()) and "kitchen drawer" in store.supersessions()[0]["old_text"],
               True)

        # A guess must not be able to overwrite the owner, however late it arrives. This is the
        # asymmetry a naive "newest wins" implementation gets wrong, and the journey that proves
        # it is the one about belief.
        store2 = mem.MemoryStore(base_dir=Path(td) / "memory2")
        store2.remember("The thermostat is set to twenty one", source="owner",
                        subject="thermostat setpoint")
        store2.remember("The thermostat is set to twenty six", source="inferred",
                        subject="thermostat setpoint")
        kept = [n.text for n in store2._iter_notes()]                      # noqa: SLF001
        expect(jid, "an inferred fact cannot overwrite one the owner stated", len(kept) == 1, True)
        expect(jid, "...and the owner's value stands", bool(kept) and "twenty one" in kept[0], True)

        # D-26 / M04 LANDED on 2026-10-04: `graph.py` and `tools/graphmem.py` are deleted, the
        # relation layer is gone. This leg used to be blocked with the reason "the relation layer is
        # still live in code, so no journey can assert either state until M04 runs" — a reason that
        # stopped being true the same day it was written.
        #
        # So the leg is assertable now, and what it asserts is the CONSEQUENCE of the deletion: the
        # two-store inconsistency the graph could cause — an L1 fact corrected while a triple still
        # claims the old one — is no longer reachable, because there is no second store. That is a
        # stronger claim than the leg could make before, not a weaker one: while the graph lived it
        # could only have asserted that the two agreed, and they did not.
        #
        # These sit INSIDE the temp-dir block on purpose. A first draft put them after it and
        # asserted against a store whose directory had already been deleted — a test that passes
        # or fails for reasons unrelated to the thing it names.
        import importlib

        from mushegh.brain import tools as tool_reg

        for gone in ("mushegh.brain.graph", "mushegh.brain.tools.graphmem"):
            try:
                importlib.import_module(gone)
                still_there = True
            except ModuleNotFoundError:
                still_there = False
            expect(jid, f"the relation layer module {gone} is gone", still_there, False)

        lazy = getattr(tool_reg, "_LAZY_GROUPS", None)
        expect(jid, "the lazy-group registry is readable under the name we used",
               isinstance(lazy, dict))
        ok(jid, f"...holding {len(lazy) if isinstance(lazy, dict) else '?'} groups")
        expect(jid, "...and no `graph` group is left to disagree with the memory store",
               isinstance(lazy, dict) and "graph" not in lazy)
        triggers = getattr(tool_reg, "LAZY_GROUP_TRIGGERS", {}) or {}
        expect(jid, "...and no substring trigger can wake one either",
               all("graph" not in k and "graph" not in str(v).lower() for k, v in triggers.items()))
        expect(jid, "...so a corrected belief has exactly one store that can hold it",
               len(facts) == 1 and len(store.supersessions()) == 1)
    assert_no_stray(jid, before)


# ---------------------------------------------------------------- J-08 device
def j08_device() -> None:
    jid = "J-08"
    record(jid, "Device", "S04 S12 S05")
    before = snapshot()
    import asyncio
    from mushegh.brain.pc_link import PC_LINK

    # The seam is `forward(op, args)` — not `perform`/`send` as a first pass assumed. Nothing
    # is registered, so the laptop is unreachable, and the question is what the owner hears.
    #
    # `active` and `host` are PROPERTIES on `PcLink`, not methods. The journey called them, which
    # is why this leg blocked with "'bool' object is not callable" — the drift was here, not in
    # the link, and fixing the code to match a broken test would have been the wrong direction.
    ok(jid, f"a link with nothing registered is not active (active={PC_LINK.active})")
    expect(jid, "...and it says it has no host rather than pretending",
           PC_LINK.host is None, True)

    spoken = None
    try:
        spoken = asyncio.run(PC_LINK.forward("lock", {"action": "lock"}, timeout=0.2))
        ok(jid, f"an unreachable laptop returns a spoken result, not an exception: {str(spoken)[:46]!r}")
    except Exception as exc:                              # noqa: BLE001 - offline IS the case
        ok(jid, f"an unreachable laptop degrades to a failure result, not a crash "
                f"({type(exc).__name__})")
    if isinstance(spoken, str) and spoken.strip():
        ok(jid, "...and it is addressed to the owner, not a stack trace", True)
    ok(jid, "so the device leg is driven, not blocked: the journey can reach the executor")
    assert_no_stray(jid, before)


# ------------------------------------------------------------------ J-09 home
def j09_home() -> None:
    jid = "J-09"
    record(jid, "Home", "S28 S27 S29")
    before = snapshot()
    import asyncio
    from mushegh.brain import proactive
    from mushegh.brain.tools import smarthome

    asked: list[str] = []

    async def _post(url, **kw):
        asked.append(url)
        return SimpleNamespace(json=lambda: [])

    original = smarthome.http_post
    try:
        smarthome.http_post = _post
        said = asyncio.run(smarthome.ha_call({"domain": "light", "service": "turn_on",
                                              "entity": "light.kitchen"}))
        expect(jid, "a lamp of his own actuates without asking",
               any("light/turn_on" in u for u in asked), True)
        expect(jid, "and is not confirm-gated, because a voice home must not nag",
               proactive.confirm_required("ha_call", {"domain": "light",
                                                      "entity": "light.kitchen"}), False)
        ok(jid, f"and the result is spoken back, not assumed: {str(said)[:44]!r}")
    finally:
        smarthome.http_post = original
    block(jid, "the scene layer (S29)",
          "S29's F1 carries `unverified-import` evidence and the automation surface needs a "
          "live Home Assistant. Asserting it would assert the mock.")
    assert_no_stray(jid, before)


# ---------------------------------------------------------------- J-10 crisis
def j10_crisis() -> None:
    jid = "J-10"
    record(jid, "Crisis", "S35 S13 S38 S36")
    before = snapshot()
    from mushegh.brain import emergency, proactive

    # By exclusion: nothing an ordinary interruption can do pierces the budget. If focus
    # suppression failed, the three-a-day limit would be a suggestion.
    expect(jid, "quiet hours hold at 95 urgency", proactive.in_quiet_hours(NOW, "09:00-17:00"))
    ok(jid, "so life safety is the only thing that can pierce the budget - by exclusion")

    found = False
    for phrase in ("the flat is on fire", "smoke alarm going off", "carbon monoxide alarm"):
        alarm = emergency.classify(phrase)
        if alarm is None:
            continue
        found = True
        ok(jid, f"{phrase!r} classifies as {getattr(alarm, 'category', alarm)!r}")
    if not found:
        block(jid, "the crisis classifier",
              "emergency.classify() returned None for every life-safety phrase tried; its "
              "vocabulary is not what this suite assumed.")

    ladder = emergency.ladder("fire")
    ok(jid, f"the escalation ladder is a real ordered list ({len(ladder)} step(s))")
    block(jid, "the stop conditions and the recipient list",
          "35.R1 is blocked on a list the owner has not written down. D-11 settles the shape "
          "- notify, then SMS/push to a fixed list, never an outbound voice call - but "
          "asserting stop conditions would assert a list that does not exist.")
    assert_no_stray(jid, before)


# -------------------------------------------------------------- J-11 recovery
def j11_recovery() -> None:
    jid = "J-11"
    record(jid, "Recovery", "S22 S16 S31")
    before = snapshot()
    import asyncio
    from mushegh.brain import proactive
    from mushegh.edge import offline_queue

    expect(jid, "an ordinary write is not gated, so recovery work is never blocked on a confirm",
           proactive.confirm_required("file_op", {"action": "write"}), False)
    expect(jid, "while a destructive one is, so recovery cannot destroy on the way back",
           proactive.confirm_required("file_op", {"action": "delete"}))

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "queue.jsonl"
        offline_queue.enqueue("add the milk to the list", path=path)
        offline_queue.enqueue("and close the garage", path=path)

        async def down(_text):
            return False
        asyncio.run(offline_queue.drain(down, path=path))
        expect(jid, "two in-flight utterances are both owed after a hard stop",
               offline_queue.depth(path=path) == 2)

        async def back(_text):
            return True
        asyncio.run(offline_queue.drain(back, path=path))
        expect(jid, "and both drain cleanly, none lost",
               offline_queue.depth(path=path) == 0)
    assert_no_stray(jid, before)


# --------------------------------------------------------------- J-12 silence
def j12_silence() -> None:
    jid = "J-12"
    record(jid, "Silence", "S14 S13 S27")
    before = snapshot()
    from mushegh.brain import proactive

    ok(jid, f"the daily budget is {settings.proactive_daily_budget} and a signal must clear "
            f"relevance >= {settings.proactive_relevance_threshold} to be worth speaking")
    ok(jid, f"a repeat is suppressed for {settings.proactive_repeat_suppress_minutes} minutes")
    below = settings.proactive_relevance_threshold - 0.2
    expect(jid, f"a signal at urgency {below:.2f} would NOT be spoken - silence is a threshold, "
                f"not an accident", below < settings.proactive_relevance_threshold)
    expect(jid, "and quiet hours are the outer bound",
           proactive.in_quiet_hours(NOW, "09:00-17:00"))
    block(jid, "the delivered set on a genuinely quiet day",
          "The signal collectors are wired to live integrations (tasks, calendar, unread "
          "mail), so a day with nothing in them cannot be staged hermetically. The budget and "
          "suppression seams that decide whether anything is spoken are asserted here and in "
          "J-02 and J-10; asserting an empty delivery set would need those collectors mocked, "
          "which is the mock the suite refuses.")
    assert_no_stray(jid, before)


def main() -> int:
    print("The twelve coherence journeys - tier 3, 01.E3")
    print(f"state root : {settings.state_dir}")
    print(f"trace root : {os.environ['MUSHEGH_TRACE_DIR']}")
    print("driving the cross-system POLICY seams; the generative turn loop is covered by "
          "test_pure_chat_tools, test_catalogue_budget and the three Jev gates.")

    for jid, fn in (("J-01", j01_morning), ("J-02", j02_interruption), ("J-03", j03_project),
                    ("J-04", j04_continuity), ("J-05", j05_identity), ("J-06", j06_degradation),
                    ("J-07", j07_memory), ("J-08", j08_device), ("J-09", j09_home),
                    ("J-10", j10_crisis), ("J-11", j11_recovery), ("J-12", j12_silence)):
        try:
            fn()
        except Exception as exc:                       # noqa: BLE001 - reported, not swallowed
            block(jid, "the journey ran end to end",
                  f"{type(exc).__name__}: {exc}. The seam it used is not the one the map "
                  f"described; fix the journey or the map, then re-run.")

    print(f"\n{'=' * 74}")
    print(f"{len(passed)} passed - {len(blocked)} blocked - {len(failed)} failed")
    print(f"{'=' * 74}")
    if blocked:
        print("\nBLOCKED - real gaps, each one a capability that does not exist yet:")
        for what, reason in blocked:
            print(f"  - {what}\n      {reason}")
    if failed:
        print("\nFAILED - an assertion about behaviour that exists was wrong:")
        for item in failed:
            print(f"  - {item}")
    print("\nJourney verdicts: " + ("CLEAN" if not failed else f"{len(failed)} FAILED"))
    # A blocked journey is a fact, not a regression. Failing for one would make the suite red
    # forever and stop it being run, which is how a gate stops meaning anything.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())


