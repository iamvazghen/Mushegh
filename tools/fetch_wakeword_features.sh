#!/usr/bin/env bash
# Fetch openWakeWord's precomputed background FEATURES (not audio).
#
# From davidscripka/openwakeword_features on HuggingFace. CC-BY-NC-SA-4.0.
#
#   validation_set_features.npy                                176 MB  <- fetched here
#   openwakeword_features_ACAV100M_2000_hrs_16bit.npy        16.1 GB  <- deliberately NOT
#
# The 16 GB training corpus is left for the owner to decide on: it is a long
# download, and CC-BY-NC-SA-4.0 is a NON-COMMERCIAL licence on data the trained
# model is derived from -- which is worth a decision rather than a background
# transfer.
set -euo pipefail
DEST="$HOME/.cache/openwakeword_features"
URL="https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main"
mkdir -p "$DEST"

if [ -s "$DEST/validation_set_features.npy" ]; then
  echo "already present: validation_set_features.npy"
else
  echo "downloading validation_set_features.npy (176 MB)..."
  curl -L --fail --silent --show-error -o "$DEST/validation_set_features.npy" \
    "$URL/validation_set_features.npy"
fi

ls -la "$DEST"
"$HOME/.venvs/wakewords/bin/python" - <<PY
import numpy as np
a = np.load("$DEST/validation_set_features.npy", mmap_mode="r")
print("validation features:", a.shape, a.dtype)
PY