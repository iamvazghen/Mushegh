"""M41 — the external-executor contract holds its four invariants (D-79, D-80, D-81, D-85).

Mushegh delegates by domain: daily life and business to the OpenClaw fleet, coding to the corporate
coding CLIs, money to Ruben, reading to the owner's own SDK. One contract carries all of them, and
this is the gate on that contract. Four things it must never allow:

  1. **an undispatchable brief reaching a process** — no acceptance check, a coding brief with no
     repo, or a non-coding brief carrying one;
  2. **a non-zero exit reading as success** — `Result.ok` is derived, never supplied;
  3. **a credential reaching the child** — `_child_env` is an allowlist built from nothing, so a
     secret added to the environment next year is still withheld without anyone editing this;
  4. **an arbitration naming an executor code did not offer** — which is the one failure D-72's
     shape exists to make impossible, here at the executor level instead of the tool level.

Plus the thing that is easy to get wrong and expensive to find later: a brief whose domain has no
configured executor is **refused**, not routed to the nearest thing. The nearest thing is how a
coding brief ends up at a finance agent.

Hermetic: substitutes a real child process with `python -c`, so no executor needs to be installed.
No network. Nothing is committed, applied or sent.

    uv run python bench/test_executor_contract.py
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
    except Exception:  # noqa: BLE001 — the wrong exception type is a failure, not a pass
        return False
    return False


async def main() -> int:
    import mushegh.brain.executors as X
    from mushegh.brain.executors import Brief, BriefRefused, Domain, ExecutorSpec, Result, Tier

    repo = str(Path(__file__).resolve().parents[1])

    print("[1] the table covers the owner's own split of the work")
    served = {d for s in X.SPECS for d in s.domains}
    for d in (Domain.CODING, Domain.DAILY, Domain.BUSINESS, Domain.FINANCE):
        check(f"{d.value} has an executor declared", d in served)
    check("coding is corporate-tier only",
          all(Tier.PERSONAL not in s.tiers for s in X.SPECS if Domain.CODING in s.domains),
          "the owner put coding on the corporate CLIs")
    check("daily life is personal-tier only",
          all(Tier.CORPORATE not in s.tiers for s in X.SPECS if Domain.DAILY in s.domains),
          "personal work runs on free models by his decision")
    check("business is corporate-tier",
          all(Tier.CORPORATE in s.tiers for s in X.SPECS if Domain.BUSINESS in s.domains))
    check("no spec invokes a shell",
          all("sh" not in s.argv[0] and "cmd" not in s.argv[0] and "powershell" not in s.argv[0]
              for s in X.SPECS),
          "D-80: argv form only, never a shell string")
    check("reading has no executor yet, and that is correct (D-86)",
          Domain.READING not in served,
          "the SDK is still being written; a seam for it would be speculative")

    print("\n[2] invariant 1 — an undispatchable brief never reaches a process")
    check("a brief with no acceptance check is refused at construction",
          _raises(lambda: Brief(domain=Domain.DAILY, task="book the dentist", acceptance=""),
                  Exception))
    check("a whitespace acceptance check is refused",
          _raises(lambda: Brief(domain=Domain.DAILY, task="book the dentist",
                                acceptance="   "), Exception))
    coding_no_repo = Brief(domain=Domain.CODING, task="fix the failing test",
                           acceptance="suite green", tier=Tier.CORPORATE)
    check("a coding brief with no repo is refused before dispatch",
          await _refuses(X, coding_no_repo))
    daily_with_repo = Brief(domain=Domain.DAILY, task="book the dentist",
                            acceptance="an appointment exists", repo=repo)
    check("a non-coding brief carrying a repo path is refused",
          await _refuses(X, daily_with_repo))
    check("a relative repo path is refused at construction",
          _raises(lambda: Brief(domain=Domain.CODING, task="fix the test",
                                acceptance="green", repo="./src"), Exception))
    check("a brief always carries a deadline",
          Brief(domain=Domain.DAILY, task="book the dentist",
                acceptance="an appointment exists").timeout_s > 0,
          "an open unit of delegated work is never late")

    print("\n[3] invariant 2 — a non-zero exit never reads as success")
    check("exit 0 with output is ok",
          Result(executor="x", domain=Domain.DAILY, exit_code=0, transcript="done").ok)
    check("exit 1 is not ok even with plausible output",
          not Result(executor="x", domain=Domain.DAILY, exit_code=1,
                     transcript="Looks good to me!").ok)
    check("a timeout with exit 0 is not ok",
          not Result(executor="x", domain=Domain.DAILY, exit_code=0, error="deadline").ok)
    check("ok cannot be supplied by a caller",
          _raises(lambda: Result(executor="x", domain=Domain.DAILY, exit_code=1, ok=True),
                  Exception),
          "extra='forbid' — derived, never passed")

    print("\n[4] invariant 3 — the child gets no credentials")
    os.environ["MUSHEGH_FAKE_SECRET_FOR_TEST"] = "sk-must-not-leak"
    os.environ["ANTHROPIC_API_KEY"] = "allowed-for-claude-only"
    spec_claude = next(s for s in X.SPECS if s.name == "claude-code")
    spec_ruben = next(s for s in X.SPECS if s.name == "ruben")
    env_claude, env_ruben = X._child_env(spec_claude), X._child_env(spec_ruben)
    check("an unrelated secret is withheld from every executor",
          "MUSHEGH_FAKE_SECRET_FOR_TEST" not in env_claude
          and "MUSHEGH_FAKE_SECRET_FOR_TEST" not in env_ruben)
    check("no MUSHEGH_* setting reaches a child at all",
          not any(k.startswith("MUSHEGH_") for k in env_claude),
          "the brief is the interface, not the environment")
    check("an executor's own declared key does reach it",
          env_claude.get("ANTHROPIC_API_KEY") == "allowed-for-claude-only")
    check("...and does not reach a different executor",
          "ANTHROPIC_API_KEY" not in env_ruben,
          "env_allow is per-executor, not global")
    check("the child can still start (PATH is present)", "PATH" in env_claude)
    os.environ.pop("MUSHEGH_FAKE_SECRET_FOR_TEST", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)

    print("\n[4b] the owner's coding pipeline: Claude Code, then mcode, then Mistral Vibe")
    coding = [sp for sp in X.SPECS if Domain.CODING in sp.domains]
    # CORRECTED 2026-10-11: this read {"claude-code", "codex", "mcode"}. Codex was never failing
    # - it simply is not in the owner's pipeline, and three CLIs that can all edit a repo is one
    # more audit shape to diagnose at 2 AM than the brief needs (D-01). The table and the chain
    # are now checked against each other rather than against a literal, so a reorder fails HERE.
    check("the coding rows are exactly the owner's pipeline",
          {sp.name for sp in coding} == set(X.CODING_CHAIN),
          str(sorted(sp.name for sp in coding)))
    check("...Claude Code is the main tool, mcode the first fallback, vibe the second",
          X.CODING_CHAIN == ("claude-code", "mcode", "vibe"), str(X.CODING_CHAIN))
    check("every one of them is corporate tier (the owner's split)",
          all(sp.tiers == (Tier.CORPORATE,) for sp in coding))
    check("every one of them is non-interactive (D-80)",
          all(any(f in sp.argv for f in ("-p", "exec")) for sp in coding),
          str([sp.argv[:2] for sp in coding]))
    check("every one of them emits a machine-readable stream, not prose",
          all(sp.parser in X.PARSERS for sp in coding),
          str([(sp.name, sp.parser) for sp in coding]))
    check("no coding executor is handed a credential belonging to another",
          len({k for sp in coding for k in sp.env_allow})
          == len([k for sp in coding for k in sp.env_allow]))
    check("the one that can enforce a result shape declares it (D-80)",
          {sp.name for sp in coding if sp.structured_output} == {"mcode"},
          "neither `claude -p` nor `vibe -p` has an --output-schema equivalent, so neither "
          "claims one")
    check("a brief sees all three, IN THE OWNER'S ORDER - no caller names one",
          len(X.candidates(Brief(domain=Domain.CODING, task="fix the off-by-one in paging",
                                 acceptance="the paging test passes", tier=Tier.CORPORATE,
                                 repo=os.getcwd()),
                           require_available=False)) == 3)
    check("...and that order is the chain's, not the table's",
          [sp.name for sp in X.candidates(
              Brief(domain=Domain.CODING, task="fix the off-by-one in paging",
                    acceptance="the paging test passes", tier=Tier.CORPORATE, repo=os.getcwd()),
              require_available=False)] == list(X.CODING_CHAIN))
    check("frontend work is refused here and pointed at Open Design, not sent to a coding CLI",
          _raises(lambda: X.resolve(Brief(domain=Domain.FRONTEND, task="rebuild the landing page",
                                          acceptance="it matches the mock")), BriefRefused)
          and "Open Design" in X.FRONTEND_ROUTE)
    check("a coding brief on the PERSONAL tier is refused, naming the fix",
          _raises(lambda: Brief(domain=Domain.CODING, task="fix the paging bug",
                                acceptance="the paging test passes", tier=Tier.PERSONAL,
                                repo=os.getcwd()), Exception),
          "it used to fail later as 'no configured executor serves coding/personal', which reads "
          "as a missing install rather than a contradiction in the brief")

    missing = ExecutorSpec(name="not-installed", domains=(Domain.CODING,),
                           tiers=(Tier.CORPORATE,),
                           argv=("mushegh-no-such-binary-xyz", "exec", "{task}"))
    check("an executor whose binary is absent is not available",
          not X.available(missing), "measured with shutil.which, not asserted")
    check("...and is therefore never a candidate",
          missing not in X.candidates(Brief(domain=Domain.CODING, task="fix the paging bug",
                                            acceptance="the paging test passes",
                                            tier=Tier.CORPORATE, repo=os.getcwd())),
          "a dead executable must read as 'not configured', never as a crash")

    print("\n[5] invariant 4 — arbitration can only narrow what code offered (D-81)")
    fake = ExecutorSpec(name="fake-daily", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
                        argv=(sys.executable, "-c", "print('ok')"))
    original = X.SPECS
    original_chain = X.CODING_CHAIN
    X.SPECS = (fake,)
    try:
        b = Brief(domain=Domain.DAILY, task="book the dentist", acceptance="appointment exists")
        check("a configured executor is a candidate", [s.name for s in X.candidates(b)] == ["fake-daily"])
        check("Jev's verdict is checked against the candidates, not trusted",
              _raises(lambda: X.resolve(b, chosen="ruben"), BriefRefused))
        check("a verdict inside the candidate list resolves",
              X.resolve(b, chosen="fake-daily").name == "fake-daily")
        check("an unavailable executor is not a candidate",
              X.candidates(Brief(domain=Domain.FINANCE, task="value the portfolio",
                                 acceptance="a figure with an as-of time")) == [],
              "so arbitration cannot name one")
        check("a domain with no configured executor is REFUSED, not re-routed",
              _raises(lambda: X.resolve(Brief(domain=Domain.FINANCE,
                                              task="value the portfolio",
                                              acceptance="a figure")), BriefRefused))

        print("\n[6] a real dispatch — one process, no shell, a derived verdict")
        r = await X.dispatch(b)
        check("the executor ran and succeeded", r.ok and r.exit_code == 0, f"{r.exit_code} {r.error}")
        check("the transcript came back", r.transcript == "ok", r.transcript)
        check("it is attributed to the executor that ran", r.executor == "fake-daily")
        check("the elapsed time was measured", r.seconds >= 0.0)
        check("no diff is invented when there is none", r.diff is None)

        print("\n[7] a failing executor degrades; it does not take the brain down")
        boom = ExecutorSpec(name="boom", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
                            argv=(sys.executable, "-c",
                                  "import sys; print('partial work'); sys.exit(3)"))
        X.SPECS = (boom,)
        r = await X.dispatch(b)
        check("a non-zero exit is reported as a failure", not r.ok and r.exit_code == 3)
        check("...and its partial output is kept for the owner to read", "partial work" in r.transcript)
        check("...and an error line is set", bool(r.error))

        missing = ExecutorSpec(name="ghost", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
                               argv=("mushegh-executable-that-does-not-exist",))
        X.SPECS = (missing,)
        check("an uninstalled executable is refused as a candidate, not crashed into",
              _raises(lambda: X.resolve(b), BriefRefused))

        print("\n[8] invariant 4b — a diff is returned and never applied")
        diffy = ExecutorSpec(
            name="differ", domains=(Domain.CODING,), tiers=(Tier.CORPORATE,),
            argv=(sys.executable, "-c",
                  r"print('working...'); print('diff --git a/x.py b/x.py'); print('+changed')"),
        )
        # CODING_CHAIN is patched alongside SPECS: coding candidates are filtered to the
        # owner's named pipeline, so a fake coding executor has to be named in it to be
        # dispatchable at all. That filter IS the "all code work goes down this pipeline"
        # rule, so the test opts into it rather than working around it.
        X.SPECS, X.CODING_CHAIN = (diffy,), ("differ",)
        cb = Brief(domain=Domain.CODING, task="change one line", acceptance="suite green",
                   tier=Tier.CORPORATE, repo=repo)
        r = await X.dispatch(cb)
        check("the diff is extracted", (r.diff or "").startswith("diff --git"), str(r.diff)[:60])
        check("the prose before it is kept too", "working..." in r.transcript)
        src = Path(X.__file__).read_text(encoding="utf-8")
        for forbidden in ("git_commit", "git apply", "subprocess.run", "shell=True", "os.system"):
            check(f"the module cannot land anything: no {forbidden!r}", forbidden not in src)
        check("stdin is closed to every child", "DEVNULL" in src,
              "D-80 draws the line at interactive, so there is nothing to type into")
    finally:
        X.SPECS, X.CODING_CHAIN = original, original_chain

    print("\n[9] availability is measured, not asserted (D-46)")
    # The first version of this check claimed no executor was installed. `claude` is on this
    # machine's PATH, so the claim was false the moment it was written — which is exactly the
    # hazard the registry calls `unverified-import`. What is worth gating is that availability
    # comes from the host rather than from a constant somebody will forget to update.
    import shutil as _sh
    for s in X.SPECS:
        # `unavailable_because` outranks the binary being present, and that is the point of the
        # field: "installed" and "has the interface this row claims" are different facts.
        want = (_sh.which(s.argv[0]) is not None) and not s.unavailable_because
        check(f"{s.name}: availability tracks the host ({'usable' if X.available(s) else 'not usable'})",
              X.available(s) == want)
    blocked = [s for s in X.SPECS if s.unavailable_because]
    check("a row whose interface does not exist is NOT a candidate",
          all(not X.available(s) for s in blocked))
    check("...and every one of them says why, in a sentence that names the fix",
          all(len(s.unavailable_because or "") > 40 for s in blocked),
          str([(s.name, s.unavailable_because) for s in blocked])[:200])
    for s in blocked:
        b = Brief(domain=s.domains[0], task="something real enough to validate",
                  acceptance="a checkable outcome",
                  tier=Tier.CORPORATE if Domain.CODING in s.domains else Tier.PERSONAL)
        try:
            X.resolve(b)
        except BriefRefused as e:
            check(f"{s.name}: the refusal is the REASON, not 'no configured executor'",
                  s.unavailable_because in str(e), str(e)[:120])
        else:
            check(f"{s.name}: the brief is refused", False, "it resolved")
    print("\n[10] a batch shim never re-parses a brief (Windows)")
    # Found by running the real thing: `codex`, `openclaw` and `ruben` all resolve to `.CMD` shims
    # on this machine, and a batch file's arguments are re-parsed by the command interpreter. An
    # `&` inside a task string is then a command separator rather than a character. This module is
    # the safe boundary, so it fails closed.
    shim = Path(__file__).resolve().parent / "_tmp_executor_shim.cmd"
    shim.write_text("@echo off\r\necho shim ran\r\n", encoding="ascii")
    original2 = X.SPECS
    X.SPECS = (ExecutorSpec(name="shim", domains=(Domain.DAILY,), tiers=(Tier.PERSONAL,),
                            argv=(str(shim), "{task}")),)
    try:
        clean = Brief(domain=Domain.DAILY, task="book the dentist for Tuesday",
                      acceptance="an appointment exists")
        r = await X.dispatch(clean)
        check("a clean brief still runs through a batch shim", r.ok, f"{r.exit_code} {r.error}")
        for payload in ("pay rent & shutdown /s", 'say "hi"', "a | b", "x > y", "50%%done"):
            nasty = Brief(domain=Domain.DAILY, task=f"handle this: {payload}",
                          acceptance="it is handled")
            check(f"a brief containing {payload!r} is refused before dispatch",
                  await _refuses(X, nasty))
        check("the guard is scoped to batch shims, not to every executor",
              X._batch_hazard([sys.executable, "a & b"]) == "",
              "a native binary gets its argv through CreateProcess, not through an interpreter")
    finally:
        X.SPECS = original2
        shim.unlink(missing_ok=True)

    print("\n[11] D-83 — a financial position never reaches a store or the audit trail")
    from mushegh.brain import never_store as NS
    check("the finance executor declares a never-store class",
          X.storage_class("ruben") == NS.FINANCIAL_POSITION)
    check("...and no other executor declares one",
          [s.name for s in X.SPECS if s.declares_never_store] == ["ruben"])
    check("the class is declaration-only — there is no detector for it",
          NS.FINANCIAL_POSITION not in NS.DETECTABLE,
          "'EUR 2,400' is a balance, a salary, or the price of a bicycle; prose cannot tell")
    check("a declared finance payload is refused by the write boundary",
          NS.screen("the portfolio is worth 41,280", declared=NS.FINANCIAL_POSITION).refused)
    check("...while the same sentence undeclared is remembered",
          not NS.screen("the portfolio is worth 41,280").refused,
          "the floor must not start refusing ordinary numbers")
    check("storage_class returns None for an executor with nothing to withhold",
          X.storage_class("codex") is None)
    src2 = Path(X.__file__).read_text(encoding="utf-8")
    check("the audit line withholds a declared payload rather than writing it",
          "withheld" in src2 and "never_store.fingerprint" in src2,
          "the first version of _account() wrote every figure into the audit file")

    print("\n[12] D-05/D-80 — a spec cannot name a command interpreter")
    for bad in ("sh", "bash", "cmd", "cmd.exe", "powershell", "pwsh", "/bin/sh",
                r"C:\Windows\System32\cmd.exe", "ssh", "wsl"):
        check(f"{bad!r} is refused at construction",
              _raises(lambda b=bad: ExecutorSpec(name="x", domains=(Domain.DAILY,),
                                                 argv=(b, "-c", "whatever")), Exception))
    check("an empty argv is refused",
          _raises(lambda: ExecutorSpec(name="x", domains=(Domain.DAILY,), argv=()), Exception))
    check("a real executor is still constructible",
          ExecutorSpec(name="ok", domains=(Domain.DAILY,), argv=("claude", "-p", "{task}")).argv[0]
          == "claude")
    check("python -c stays allowed — it is how this gate drives a fake executor, not a shell",
          ExecutorSpec(name="ok", domains=(Domain.DAILY,),
                       argv=(sys.executable, "-c", "pass")).argv[1] == "-c")

    print("\n[14] M44 — each CLI's own stream is parsed, and a reported failure is not spoken "
          "as a result")
    import json as _json
    check("every coding and fleet spec declares a parser",
          all(s.parser for s in X.SPECS
              if Domain.CODING in s.domains or Domain.DAILY in s.domains
              or Domain.BUSINESS in s.domains))
    check("every declared parser exists", all(s.parser in X.PARSERS for s in X.SPECS if s.parser))

    # Claude Code: stream-json, one object per line.
    stream = "\n".join(_json.dumps(o) for o in [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "reading tests"}]}},
        {"type": "result", "result": "one assertion fixed", "is_error": False},
    ])
    text, err = X.parse_stream_json(stream)
    check("stream-json keeps the assistant text and the result", "reading tests" in text
          and "one assertion fixed" in text, text)
    check("...and reports no error on a clean run", err == "", err)
    text, err = X.parse_stream_json(_json.dumps(
        {"type": "result", "is_error": True, "message": "permission denied"}))
    check("an is_error event sets the error", "permission denied" in err, err)

    # Codex: JSONL events. turn.failed is a failure even if the process exits 0.
    jsonl = "\n".join(_json.dumps(o) for o in [
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "item.completed", "text": "ran the suite"},
        {"type": "turn.completed", "summary": "2 files changed"},
    ])
    text, err = X.parse_codex_jsonl(jsonl)
    check("codex events become a readable transcript",
          "ran the suite" in text and "2 files changed" in text, text)
    check("...with no error on a completed turn", err == "", err)
    text, err = X.parse_codex_jsonl(_json.dumps({"type": "turn.failed", "message": "sandbox denied"}))
    check("a turn.failed is an error", "sandbox denied" in err, err)
    text, err = X.parse_codex_jsonl(_json.dumps({"type": "error", "message": "bad schema"}))
    check("an error event is an error", "bad schema" in err, err)

    # OpenClaw: the project's own recorded trap — status ok over a failed tool.
    text, err = X.parse_openclaw_json(_json.dumps(
        {"status": "ok", "error": "tool automations unreachable", "message": "done"}))
    check("an error field beats a cheerful status=ok",
          "unreachable" in err,
          "the fleet's own history: 7 of 14 crons hid a failed tool behind status=ok")

    check("a non-JSON line is kept rather than dropped",
          "note to self" in X.parse_codex_jsonl("note to self\n" + jsonl)[0],
          "these tools print human notes beside their events")
    check("a parser crash falls back to the raw text instead of losing it",
          X._parsed(ExecutorSpec(name="x", domains=(Domain.DAILY,), argv=("claude",),
                                 parser="stream_json"), "\x00not json at all")[0] != "",
          "a parser bug must not swallow the executor's output")

    print("\n[15] a parser verdict can fail a run the exit code passed")
    failing = ExecutorSpec(
        name="liar", domains=(Domain.CODING,), tiers=(Tier.CORPORATE,), parser="codex_jsonl",
        argv=(sys.executable, "-c",
              'print(\'{"type": "turn.failed", "message": "sandbox denied"}\')'),
    )
    original3 = X.SPECS
    X.SPECS, X.CODING_CHAIN = (failing,), (failing.name,)
    try:
        r = await X.dispatch(Brief(domain=Domain.CODING, task="change one line",
                                   acceptance="suite green", tier=Tier.CORPORATE, repo=repo))
        check("the process exited 0", r.exit_code == 0, str(r.exit_code))
        check("...and the run is still NOT ok", not r.ok,
              "this is the failure the parsers exist to prevent")
        check("...and the error says what the executor reported", "sandbox denied" in r.error,
              r.error)
    finally:
        X.SPECS, X.CODING_CHAIN = original3, original_chain

    print("\n[13] D-01 — the 2 AM question is answerable from the running system")
    rows = X.status()
    check("one row per executor", len(rows) == len(X.SPECS))
    check("every row says which domains it serves",
          all(r["domains"] for r in rows))
    check("every row says whether it is installed, and where",
          all(isinstance(r["installed"], bool) for r in rows)
          and all(r["path"] or not r["installed"] for r in rows))
    check("the row for a withholding executor says so",
          next(r for r in rows if r["name"] == "ruben")["withholds"] == NS.FINANCIAL_POSITION)
    check("status() reaches no network and starts no process",
          "status" in src2 and "create_subprocess" in src2.split("def status")[0],
          "the only subprocess call is in dispatch(), above it")

    print(f"\n=== {passed + failed} checks: {passed} passed, {failed} failed ===")
    if not failed:
        print("ALL CHECKS PASSED ===")
    return 1 if failed else 0


async def _refuses(X, brief) -> bool:
    """dispatch() must refuse before any process starts."""
    try:
        await X.dispatch(brief)
    except X.BriefRefused:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
