"""Regenerate the docs site's generated tool manifest.

`bench/dump_tools.py --json` writes UTF-8 text to stdout. Redirecting it with
PowerShell `>` writes UTF-16LE and a BOM, which `import`/`read_text` then either
mangles or chokes on -- so the bytes are captured and written from Python instead.

Run:  .venv\\Scripts\\python.exe tools\\regen_tool_manifest.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DUMP = ROOT / "bench" / "dump_tools.py"
TARGET = ROOT / "website" / "app" / "tools" / "tools.generated.json"


def main() -> int:
    proc = subprocess.run(
        [str(PYTHON), str(DUMP), "--json"],
        capture_output=True,
        timeout=180,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))
        return proc.returncode

    before = TARGET.read_bytes() if TARGET.exists() else b""
    after = proc.stdout
    # Normalise to LF; git warns about CRLF churn on these generated files.
    after = after.replace(b"\r\n", b"\n")
    TARGET.write_bytes(after)

    import json

    data = json.loads(after.decode("utf-8"))
    changed = "unchanged" if before == after else "CHANGED"
    print(f"tools.generated.json {changed}: {data['count']} tools, {len(after)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())