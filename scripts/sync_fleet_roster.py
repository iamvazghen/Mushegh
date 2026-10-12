"""Regenerate ``src/mushegh/brain/fleet18.json`` from the vault's canonical roster.

The fleet's definition — which of the eighteen agents owns which of the eighty-three
domains — lives in the vault at ``20-Agents/fleet18.json``, because the agents themselves
read it there. Mushegh needs the same table at runtime on a laptop that may have no vault
mounted, so this copies it into the package with its provenance recorded.

It is a *generated* file. Do not edit the copy: edit the vault's and run

    uv run python scripts/sync_fleet_roster.py

``roster.py`` compares the two when both are readable and says so when they disagree, which
is the rule a stale copy would otherwise break silently.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "mushegh" / "brain" / "fleet18.json"


def vault_roster() -> Path:
    """Where the canonical roster lives. ``MUSHEGH_VAULT_PATH`` wins; the replica is the fallback."""
    root = os.environ.get("MUSHEGH_VAULT_PATH") or str(
        Path.home() / "Documents" / "Obsidian Vault"
    )
    return Path(root) / "20-Agents" / "fleet18.json"


def main() -> int:
    src = vault_roster()
    if not src.is_file():
        print(f"canonical roster not found at {src}", file=sys.stderr)
        return 1
    agents = json.loads(src.read_text(encoding="utf-8"))
    if len(agents) != 18:
        print(f"refusing: {src} holds {len(agents)} agents, not 18", file=sys.stderr)
        return 1
    payload = {
        "_source": "vault 20-Agents/fleet18.json",
        "_generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_regenerate": "uv run python scripts/sync_fleet_roster.py",
        "agents": agents,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(agents)} agents, "
          f"{sum(len(a.get('utilities', [])) for a in agents.values())} domains)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
