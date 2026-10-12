"""The `mushegh` command — one entry point, subcommands underneath.

Previously the project shipped a single `mushegh-setup` binary that only knew
how to do one thing. An installer that can only install is fine on day one and
annoying forever after: updating means remembering a second command, checking
whether it changed means reading release notes, and "what does this thing
support" means grepping the source.

So there is one command and it answers the questions a person actually has:

    mushegh wizard     run (or resume) setup
    mushegh doctor     what is configured, what is missing, what is broken
    mushegh update     pull a newer release
    mushegh help       this text

Every subcommand is safe to run without arguments and safe to run twice. None of
them delete anything.
"""

from __future__ import annotations

import argparse
import sys

from mushegh import __version__ as _version

BANNER = r"""
   __  __  __    ___ _____ _   _ __   __
  |  \/  | \ \  / /|_   _| | | |  \ |  |
  | |\/| |  \ \/ /   | | | |_| | .  |  |
  | |  | |   \  /    | |  _  | |\  |  |
  |_|  |_|    \_/     |_| |_| |_| \_|  |

  Modular Universal Synthetic Hyper Engine General Hub
"""


def _print_banner() -> None:
    # Written to stderr deliberately: `mushegh help | less` should give the help,
    # not eight lines of ASCII art, and stdout stays machine-readable everywhere else.
    print(BANNER, file=sys.stderr)


# ------------------------------------------------------------------ commands

def cmd_wizard(args: argparse.Namespace) -> int:
    from mushegh.setup_wizard import main as wizard_main
    if args.reset:
        from mushegh import wizard_state
        wizard_state.reset()
        print("Setup progress cleared. Starting from the beginning.", file=sys.stderr)
    _print_banner()
    wizard_main()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from mushegh import wizard_state
    data = wizard_state.load()
    done = data.get("completed") or []
    from mushegh.config import settings

    print(f"Mushegh {_version}")
    print(f"  state dir        : {settings.state_dir or '(default) ~/.mushegh'}")
    print(f"  llm backend      : {settings.llm_backend.value}")
    print(f"  assistant name   : {settings.assistant_name}")
    print(f"  wake words       : {'enabled' if settings.wake_word_enabled else 'disabled'}")
    if data.get("started_at"):
        print(f"  wizard started   : {data['started_at']}")
        print(f"  steps completed  : {len(done)}  -> {', '.join(done) if done else '(none)'}")
        print("\n  Finish setup with:  mushegh wizard")
    else:
        print("\n  Setup has not been run yet:  mushegh wizard")

    # The subsystem ledger. "Which of my fifty subsystems are dark, and why?" is
    # the question an owner actually has; counting set variables is not it.
    if getattr(args, "systems", False):
        from mushegh import subsystems
        marks = {"ready": "ok  ", "dark": "DARK", "builtin": "n/a "}
        counts = subsystems.summary()
        total = sum(counts.values())
        print(f"\nSubsystems ({counts.get('ready', 0)} ready / {counts.get('dark', 0)} dark / "
              f"{counts.get('builtin', 0)} built-in / {counts.get('unmapped', 0)} unmapped of {total})")
        for view in subsystems.system_views():
            print(f"  [{marks.get(view.state, '?')}] {view.id} {view.title[:40]}"
                  + (f"  — {view.detail}" if view.detail else ""))
    elif counts_hint():
        from mushegh import subsystems
        c = subsystems.summary()
        if c.get("dark"):
            print(f"\n  {c['dark']} subsystem(s) built but dark. Run `mushegh doctor --systems` for the list.")
    return 0


def counts_hint() -> bool:
    """True when at least one mapped subsystem is dark. Cheap and failure-tolerant."""
    try:
        from mushegh import subsystems
        return bool(subsystems.summary().get("dark"))
    except Exception:  # noqa: BLE001 — a hint must never break the real report
        return False


def cmd_update(args: argparse.Namespace) -> int:
    """Pull a newer release from the fork's own repository."""
    import subprocess
    _print_banner()
    repo = "https://github.com/iamvazghen/MUSHEGH.git"
    print(f"Updating Mushegh from {repo}", file=sys.stderr)
    for argv in (["git", "fetch", "--all", "--tags"], ["git", "pull", "--ff-only"]):
        try:
            done = subprocess.run(argv, cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
                                  capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"  could not run {' '.join(argv)}: {exc}", file=sys.stderr)
            return 1
        if done.returncode != 0:
            print(done.stderr.strip() or f"  {' '.join(argv)} failed", file=sys.stderr)
            return done.returncode
    print("Updated. Run `mushegh doctor` to check your setup still resolves.", file=sys.stderr)
    return 0


def cmd_help(args: argparse.Namespace) -> int:
    print(BANNER)
    print("""usage: mushegh <command>

  wizard     Run setup, or resume where you left off
  doctor     Show what is configured and what is still missing
  update     Pull a newer release of Mushegh
  help       This message

Run `mushegh wizard --reset` to start setup over from the beginning.
""")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    print(_version)
    return 0


# --------------------------------------------------------------------- entry

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mushegh", add_help=False,
                                     description="Mushegh — Modular Universal Synthetic Hyper Engine General Hub")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    parser.add_argument("-V", "--version", action="store_true", dest="show_version")
    sub = parser.add_subparsers(dest="command")

    wiz = sub.add_parser("wizard", help="run or resume setup")
    wiz.add_argument("--reset", action="store_true", help="forget progress and start over")
    wiz.set_defaults(func=cmd_wizard)

    doc = sub.add_parser("doctor", help="show setup status")
    doc.add_argument("--systems", action="store_true",
                     help="list all 50 subsystems and which are dark")
    doc.set_defaults(func=cmd_doctor)
    sub.add_parser("update", help="pull a newer release").set_defaults(func=cmd_update)
    sub.add_parser("help", help="show this message").set_defaults(func=cmd_help)
    sub.add_parser("version", help="print the version").set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "show_help", False) or not args.command:
        return cmd_help(args)
    if getattr(args, "show_version", False):
        return cmd_version(args)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())