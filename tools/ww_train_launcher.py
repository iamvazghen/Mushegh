"""Run openwakeword.train WITH the SciPy shim applied.

    .venv\\Scripts\\python.exe tools\\ww_train_launcher.py --train_model \\
        --training_config <path.yaml>

`openwakeword.train` must run in a subprocess when driven from a tool, and the
shim in tools/ww_shim.py only patches the process it is imported into. Calling
`python -m openwakeword.train` directly therefore dies on `import acoustics`
again — which is exactly what the first smoke run did. This launcher applies the
shim first and then hands control to the trainer with the same argv, so the
patch is in the process that actually does the work.

This is the entry point tools/train_wakeword.py and tools/smoke_train_wakeword.py
both call.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ww_shim import apply  # noqa: E402

note = apply()
if note:
    print(f"[ww_shim] {note}", file=sys.stderr)

sys.argv = ["openwakeword.train", *sys.argv[1:]]
runpy.run_module("openwakeword.train", run_name="__main__", alter_sys=True)