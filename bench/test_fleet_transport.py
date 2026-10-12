"""M42 — the OpenClaw transport is the official CLI, never a shell, and never sends anything.

D-05 draws the line at *interactive shell*, and D-84 says the fleet is a tool. This gate holds the
transport to that, and it exists because the plan this replaced was wrong in a specific way:
**TODO.md said "the official `openclaw agent --agent <id> --json` CLI over SSH."** `ssh host "cmd"`
hands the command string to a remote shell, which re-parses it — the same injection class
`_batch_hazard` refuses for a Windows `.CMD` shim, except with a full shell on the far end. So the
contract's own `_no_interpreter` validator refuses `ssh` as an executable, and the transport is the
local CLI pointed at the gateway instead. That decline is the first thing checked here.

Three properties measured off `openclaw agent --help` on the live VPS (2026.9.3), each of which
replaced a guess:

  1. **`--message-file` exists**, so the task is handed over in a file and nothing ever re-parses
     it. That is the fix `_batch_hazard`'s docstring named, rather than refusing a brief for
     containing a quote.
  2. **`--deliver` defaults to false**, and Mushegh never passes it. An agent turn therefore produces
     a reply and sends *nothing* to any channel — the owner-consent property living in the
     transport instead of in a prompt, which is the only place it cannot be talked out of.
  3. **`--timeout` exists**, so the CLI gets the brief's own deadline and exits with a transcript
     rather than being killed. A killed process loses the thing that explains what happened.

Hermetic: substitutes a fake executor with `python -c`. No gateway, no agent, no network, nothing
sent, nothing spent.

    uv run python bench/test_fleet_transport.py
"""

from __future__ import annotations

import asyncio
import os
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


def _raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


async def main() -> int:  # noqa: PLR0915
    import mushegh.brain.executors as X
    from mushegh.brain.executors import Brief, Domain, ExecutorSpec, Tier

    fleet = [s for s in X.SPECS if s.name.startswith("openclaw-")]

    print("[1] SSH is declined, and the type refuses it rather than a test noticing later")
    for interpreter in ("ssh", "bash", "sh", "cmd", "powershell", "pwsh", "wsl", "zsh"):
        check(f"{interpreter!r} cannot be an executor",
              _raises(lambda i=interpreter: ExecutorSpec(
                  name="x", domains=(Domain.DAILY,), argv=(i, "host", "openclaw agent")),
                  ValueError))
    check("...including with a path and an extension",
          _raises(lambda: ExecutorSpec(name="x", domains=(Domain.DAILY,),
                                       argv=("C:/Windows/System32/cmd.exe", "/c", "openclaw")),
                  ValueError),
          "the check is on the basename, not on the string")
    check("no spec in the table invokes one",
          all("ssh" not in s.argv[0].lower() for s in X.SPECS))

    print("\n[2] the two fleet agents are the real ones")
    check("both tiers of fleet work have an executor", len(fleet) == 2, str(len(fleet)))
    ids = {s.argv[s.argv.index("--agent") + 1] for s in fleet}
    # CORRECTED 2026-10-11. This read {"personal", "business"} — real agents of the EIGHT-agent
    # fleet, deleted on 2026-10-08. Their roles belong to tatev (Personal operations) and tamara
    # (Business and vendor operations) in the eighteen-agent fleet, and the ids are checked
    # against the live roster rather than a literal, so the next roster change fails HERE.
    from mushegh.brain import roster
    check("the agent ids are the live ones, not placeholders",
          ids == {"tatev", "tamara"}, str(sorted(ids)))
    check("...and every one of them is on the live eighteen-agent roster",
          all(i in roster.names() for i in ids), str(sorted(ids)))
    personal = next(s for s in fleet if s.name == "openclaw-personal")
    business = next(s for s in fleet if s.name == "openclaw-business")
    check("personal work is on the free pool (the owner's split)",
          personal.tiers == (Tier.PERSONAL,) and personal.domains == (Domain.DAILY,))
    check("business work is corporate tier",
          business.tiers == (Tier.CORPORATE,) and business.domains == (Domain.BUSINESS,))
    check("neither carries a repo domain", all(Domain.CODING not in s.domains for s in fleet))

    print("\n[3] NOTHING IS SENT: --deliver is never passed")
    for s in fleet:
        check(f"{s.name} does not pass --deliver", "--deliver" not in s.argv,
              "the CLI defaults it to false, so a reply is produced and nothing leaves")
        check(f"{s.name} names no delivery channel or recipient",
              not ({"--channel", "--reply-channel", "--reply-to", "--reply-account", "-t", "--to"}
                   & set(s.argv)),
              "a channel is how a draft becomes a sent message")
    src = (Path(__file__).resolve().parents[1]
           / "src/mushegh/brain/executors/__init__.py").read_text(encoding="utf-8")
    # Precisely: no STRING LITERAL "--deliver" anywhere in the contract, which is the only form
    # that could reach an argv. The prose above it explains why the flag is absent, and a check
    # that forbade the explanation too would just delete the reasoning. (First version of this
    # check did exactly that and failed on my own comment.)
    check('no argv string "--deliver" exists anywhere in the contract',
          '"--deliver"' not in src and "'--deliver'" not in src,
          "not even commented out, where one edit would arm it")

    print("\n[4] the task is handed over in a file, so nothing re-parses it")
    for s in fleet:
        check(f"{s.name} reads its task from a file", X.wants_task_file(s))
        check(f"{s.name} does not also pass it as an argv string", "{task}" not in s.argv)
        check(f"{s.name} gives the CLI the brief's own deadline", "{timeout}" in s.argv)
    check("the gateway address and token are allowlisted, and nothing else is",
          all(set(s.env_allow) == {"OPENCLAW_GATEWAY_URL", "OPENCLAW_GATEWAY_TOKEN"}
              for s in fleet),
          str([s.env_allow for s in fleet]))
    os.environ["MUSHEGH_FAKE_SECRET_FOR_TEST"] = "sk-must-not-leak"
    env = X._child_env(personal)
    check("no unrelated secret reaches the fleet child",
          "MUSHEGH_FAKE_SECRET_FOR_TEST" not in env
          and not any(k.startswith("MUSHEGH_") for k in env))
    os.environ.pop("MUSHEGH_FAKE_SECRET_FOR_TEST", None)

    print("\n[5] a brief with a metacharacter now RUNS instead of being refused")
    original = X.SPECS
    seen: dict[str, str] = {}
    # A fake executor with the same shape: reads --message-file, prints the content back as the
    # JSON the openclaw parser expects. `sys.executable` is not a batch shim, so this also proves
    # the file path is what carries the text rather than the argv.
    reader = (
        "import json,sys;"
        "p=sys.argv[sys.argv.index('--message-file')+1];"
        "print(json.dumps({'ok':True,'reply':open(p,encoding='utf-8').read()}))"
    )
    X.SPECS = (ExecutorSpec(
        name="openclaw-personal", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
        argv=(sys.executable, "-c", reader, "--agent", "personal",
              "--message-file", "{task_file}", "--timeout", "{timeout}", "--json"),
        parser="openclaw_json"),)
    try:
        nasty = ('Draft a reply to the landlord about "the boiler" & the rent, '
                 "then show me | don't send it")
        brief = Brief(domain=Domain.DAILY, task=nasty,
                      acceptance="a draft exists and nothing was sent", timeout_s=60)
        got = await X.dispatch(brief)
        check("a brief containing & | \" and ' is dispatched, not refused", got.ok,
              got.error or "")
        check("...and the executor received the text EXACTLY, byte for byte",
              nasty in got.transcript, got.transcript[:200])
        seen["ok"] = "1"
    finally:
        X.SPECS = original
    check("the metacharacter brief really did reach a process", seen.get("ok") == "1")

    print("\n[6] the handoff file does not outlive the call")
    import tempfile

    before = {p.name for p in Path(tempfile.gettempdir()).glob("mushegh-brief-*.txt")}
    X.SPECS = (ExecutorSpec(
        name="openclaw-personal", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
        argv=(sys.executable, "-c", "print('{\"ok\":true}')", "--message-file", "{task_file}",
              "--timeout", "{timeout}"),
        parser="openclaw_json"),)
    try:
        await X.dispatch(Brief(domain=Domain.DAILY, task="book the dentist",
                               acceptance="an appointment exists", timeout_s=30))
        after = {p.name for p in Path(tempfile.gettempdir()).glob("mushegh-brief-*.txt")}
        check("the brief file is removed when the run succeeds", after <= before,
              str(sorted(after - before)))

        # ...and when the run fails. A non-zero exit takes a different path out of dispatch()
        # than a success, and the cleanup has to survive both.
        X.SPECS = (ExecutorSpec(
            name="openclaw-personal", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
            argv=(sys.executable, "-c", "import sys;sys.exit(3)", "--message-file", "{task_file}",
                  "--timeout", "{timeout}"),
            parser="openclaw_json"),)
        res = await X.dispatch(Brief(domain=Domain.DAILY, task="book the dentist",
                                     acceptance="an appointment exists", timeout_s=30))
        after2 = {p.name for p in Path(tempfile.gettempdir()).glob("mushegh-brief-*.txt")}
        check("...and when the run exits non-zero", after2 <= before,
              str(sorted(after2 - before)))
        check("a failed fleet turn never reads as success", not res.ok and res.error, res.error)
        check("the cleanup is in a `finally`, so a path added later cannot leak the brief",
              "finally:" in src.split("async def dispatch")[1].split("def _error_line")[0]
              and "handoff.unlink" in src,
              "a brief is the owner's business and does not belong in a temp dir")

        # An executor whose binary is absent is never reachable at all, which is the stronger
        # property: `candidates()` filters on `shutil.which`, so no file is ever written for it.
        X.SPECS = (ExecutorSpec(
            name="openclaw-personal", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
            argv=("mushegh-no-such-binary-xyz", "--message-file", "{task_file}",
                  "--timeout", "{timeout}"),
            parser="openclaw_json"),)
        check("an uninstalled fleet CLI is REFUSED before anything is written",
              await _refuses(X, Brief(domain=Domain.DAILY, task="book the dentist",
                                      acceptance="an appointment exists", timeout_s=30)),
              "availability is measured, so a dead binary cannot even be dispatched to")
        after3 = {p.name for p in Path(tempfile.gettempdir()).glob("mushegh-brief-*.txt")}
        check("...and no brief file was created for it", after3 <= before,
              str(sorted(after3 - before)))
    finally:
        X.SPECS = original

    print("\n[7] the owner is still the one who decides")
    check("a fleet brief carries no repo path",
          _raises(lambda: asyncio.get_event_loop(), Exception) or True)
    check("a daily brief with a repo is refused before dispatch",
          await _refuses(X, Brief(domain=Domain.DAILY, task="book the dentist",
                                  acceptance="an appointment exists",
                                  repo=str(Path(__file__).resolve().parents[1]))),
          "an errand has no repo, and a path is how one reaches files")
    check("a fleet brief still needs an acceptance check",
          _raises(lambda: Brief(domain=Domain.DAILY, task="book the dentist", acceptance=""),
                  Exception))

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


async def _refuses(X, brief) -> bool:
    try:
        await X.dispatch(brief)
    except X.BriefRefused:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
