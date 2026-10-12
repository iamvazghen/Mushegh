"""22.R1 — a bad config change is detected and reverted automatically, inside one brain restart.

What counts as a bad start: `.env` is missing, `mushegh.config` refuses to load it (a value of the
wrong type, an unknown provider), or it carries no MUSHEGH_ setting at all (a file overwritten with
something else). That is checked in a SUBPROCESS, because `mushegh.config` builds its settings at
import time — a broken file raises before any code here could run, so the check must not share this
process's import of it. MUSHEGH_* variables are stripped from that subprocess for the same reason:
systemd's EnvironmentFile has already exported the broken values, and they would mask the file.

The good copy is the `.env` the brain last STARTED with (`remember_good`, called once the brain is
serving), kept at `<state>/env.last-good` mode 600; the setup wizard's `.env.bak-<stamp>` files are
the fallback. A rollback keeps the broken file as `.env.broken-<stamp>` (nothing is deleted) and
writes one audit line. It never edits `.env` to test itself — the drill is `bench/test_setup_wizard.py`
against a scratch directory.

Run before the brain starts (systemd ExecStartPre):  python -m mushegh.shared.config_guard
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


_SRC = str(Path(__file__).resolve().parents[2])


def _state() -> Path:
    # Not mushegh.shared.paths: that imports mushegh.config, which is exactly what may be broken.
    return Path(os.environ.get("MUSHEGH_STATE_DIR") or Path.home() / ".mushegh").expanduser()


def problem(env: Path) -> str | None:
    """Why `env` cannot start the brain, or None if it can."""
    if not env.is_file():
        return "no .env"
    text = env.read_text(encoding="utf-8-sig", errors="replace")
    if not any(line.lstrip().startswith("MUSHEGH_") for line in text.splitlines()):
        return "no MUSHEGH_ setting in .env"
    clean = {k: v for k, v in os.environ.items() if not k.startswith("MUSHEGH_")}
    # Import THIS package whatever directory the file sits in (the trial copy lives outside the repo).
    clean["PYTHONPATH"] = os.pathsep.join(filter(None, [_SRC, clean.get("PYTHONPATH")]))
    r = subprocess.run([sys.executable, "-c", "import mushegh.config"], cwd=env.parent, env=clean,
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        lines = (r.stderr or "").strip().splitlines()
        return (lines[-1] if lines else f"exit {r.returncode}")[:300]
    return None


def remember_good(env: Path, state: Path | None = None) -> None:
    """The brain is serving with this .env — keep it as the rollback target."""
    target = (state or _state()) / "env.last-good"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(env, target)
    os.chmod(target, 0o600)


def ensure(env: Path, state: Path | None = None) -> dict:
    """Leave a good .env alone; replace a bad one with the newest good candidate. Returns what happened."""
    state = state or _state()
    why = problem(env)
    if why is None:
        return {"rolled_back": False}
    candidates = [state / "env.last-good"] + sorted(env.parent.glob(".env.bak-*"), reverse=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for cand in candidates:
        if not cand.is_file():
            continue
        trial = state / "env.trial" / ".env"
        trial.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cand, trial)
        os.chmod(trial, 0o600)
        ok = problem(trial) is None
        trial.unlink()
        if not ok:
            continue
        kept = None
        if env.is_file():
            kept = env.with_name(f".env.broken-{stamp}")
            env.replace(kept)
        shutil.copyfile(cand, env)
        os.chmod(env, 0o600)
        event = {"at": stamp, "rolled_back": True, "reason": why, "restored_from": str(cand),
                 "broken_kept_as": str(kept) if kept else None}
        _audit(state, event)
        return event
    event = {"at": stamp, "rolled_back": False, "reason": why, "error": "no good config to restore"}
    _audit(state, event)
    return event


def _audit(state: Path, event: dict) -> None:
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "config_rollbacks.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    result = ensure(Path.cwd() / ".env")
    print(json.dumps(result))
    # Never block the start: a brain on a restored config, or on the broken one with its error
    # logged, beats a unit that refuses to start at all.
    sys.exit(0)
