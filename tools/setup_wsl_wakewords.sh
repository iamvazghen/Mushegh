#!/usr/bin/env bash
# The Linux wake-word training environment. `.env` has always said these models
# were "trained out-of-repo with openWakeWord's pipeline under WSL" — this is
# that environment, and every line below is there because the obvious one failed.
#
#   wsl -d Ubuntu -- bash /mnt/c/Mushegh/tools/setup_wsl_wakewords.sh
#
# WHY NOT ON WINDOWS. The trainer needs speechbrain's processing stack, which
# eagerly imports its optional integrations; k2 is a native extension with no
# Windows wheel, and `uv pip install k2` resolves a STUB that then fails on a
# missing `_k2`. That is a platform wall, not a bug to shim.
#
# WHY NOT openwakeword[full]. That extra pins tensorflow-cpu==2.8.1, whose wheels
# stop at CPython 3.10. On 3.12 it is unsatisfiable outright; on Windows the
# resolver "solved" it by silently downgrading openwakeword to 0.5.1, which has
# no train.py at all. Install the trainer's real dependencies BY NAME.
#
# WHY PYTHON 3.11. On Linux openwakeword depends on tflite-runtime>=2.8.0, and
# tflite-runtime publishes wheels up to cp311 only. On 3.12 `pip install
# openwakeword` cannot be satisfied. This single pin is the whole reason this
# environment is separate.
set -euo pipefail

VENV="$HOME/.venvs/wakewords"
UV="$HOME/.local/bin/uv"

if ! command -v "$UV" >/dev/null 2>&1 && [ ! -x "$UV" ]; then
  echo "installing uv (no sudo needed)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

"$UV" venv --clear --python 3.11 "$VENV"
export VIRTUAL_ENV="$VENV"
PY="$VENV/bin/python"

echo "--- torch (cpu-only; the GPU is not needed to train a wake word) ---"
"$UV" pip install --python "$PY" torch torchaudio \
  --index-url https://download.pytorch.org/whl/cpu

echo "--- openwakeword, pinned ---"
"$UV" pip install --python "$PY" "openwakeword==0.6.0"

echo "--- the trainer's actual dependencies, by name ---"
"$UV" pip install --python "$PY" \
  torchinfo torchmetrics audiomentations torch-audiomentations \
  mutagen pyyaml requests pronouncing acoustics speechbrain

echo "--- model resources (the package ships code, not the .onnx files) ---"
"$PY" - <<'PY'
import openwakeword.utils as u
try:
    u.download_models([])
except Exception as e:
    print("  download_models:", type(e).__name__, e)
PY

echo
echo "=== verify ==="
"$PY" - <<'PY'
import importlib
for m in ("torch", "torchaudio", "openwakeword", "yaml", "mutagen",
          "torchinfo", "torchmetrics", "audiomentations", "speechbrain"):
    try:
        importlib.import_module(m)
        print(f"  {m:<16} OK")
    except Exception as e:
        print(f"  {m:<16} {type(e).__name__}: {e}")
try:
    import openwakeword.train
    print("  openwakeword.train  OK")
except Exception as e:
    print(f"  openwakeword.train  {type(e).__name__}: {e}")
    print("  (tools/ww_shim.py covers scipy.special.sph_harm and k2_fsa)")
PY