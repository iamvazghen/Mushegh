"""Prove the wake-word TRAINING path runs, end to end, without pretending to train a model.

This is a pipeline test, not a model. It writes synthetic tone/noise WAVs (not
speech) into a temp directory, runs openwakeword.train with a deliberately tiny
`steps`, and asserts that a .onnx comes out. The point is that when the owner
drops real recordings into .wakewords/samples/<word>/, there is nothing left to
debug: the config, the clip layout, the shim and the export are all exercised here
first.

The output is written to a temp dir and never to .wakewords/, so a smoke model
can never be mistaken for a trained one and picked up by MUSHEGH_WAKE_WORDS.

    .venv\\Scripts\\python.exe tools\\smoke_train_wakeword.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]

N_POS = 12
N_NEG = 6
SR = 16000


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def fill(directory: Path, count: int, seed: int, speechy: bool) -> None:
    """Synthetic clips. `speechy` ones are a formant-ish stack so they are at least
    not pure noise; neither class contains the word, because there is no word."""
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    for i in range(count):
        dur = rng.uniform(0.5, 0.9)
        t = np.arange(int(SR * dur)) / SR
        if speechy:
            f0 = rng.uniform(110, 190)
            sig = sum(
                np.sin(2 * np.pi * f0 * k * t) / k
                for k in (1, 2, 3, 5)
            )
            env = np.hanning(len(t))
            sig = sig * env
        else:
            sig = rng.normal(0, 0.2, len(t))
        write_wav(directory / f"{seed}_{i:03d}.wav", sig.astype(np.float32))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ww_smoke_"))
    try:
        model = "smoke_only"
        pos_tr = tmp / model / "positive_train"
        pos_te = tmp / model / "positive_test"
        neg_tr = tmp / model / "negative_train"
        neg_te = tmp / model / "negative_test"
        bg = tmp / "background"
        rir = tmp / "rir"

        fill(pos_tr, N_POS, 1, True)
        fill(pos_te, 3, 2, True)
        fill(neg_tr, N_NEG, 3, False)
        fill(neg_te, 3, 4, False)
        fill(bg, 4, 5, False)
        rir.mkdir(parents=True, exist_ok=True)
        # A degenerate but valid impulse response: one decaying tap.
        decay = np.exp(-np.arange(SR // 20) / 400.0)
        write_wav(rir / "tap.wav", decay.astype(np.float32))

        cfg = {
            "model_name": model,
            # openwakeword.train.Model only builds self.model for these two; anything
            # else falls through both branches and dies at the optimizer with
            # "'Model' object has no attribute 'model'".
            "model_type": "dnn",
            "target_phrase": ["mushegh"],
            "custom_negative_phrases": [],
            "output_dir": str(tmp),
            "n_samples": N_POS,
            "n_samples_val": 3,
            "tts_batch_size": 1,
            "piper_sample_generator_path": str(ROOT / "tools" / "piper_stub"),
            "rir_paths": [str(rir)],
            "background_paths": [str(bg)],
            "background_paths_duplication_rate": [1],
            "false_positive_validation_data_path": str(bg),
            "target_false_positives_per_hour": 1.5,
            "batch_n_per_class": 2,
            "max_negative_weight": 10,
            "layer_size": 32,
            "steps": 20,                          # deliberately tiny
            "augmentation_rounds": 1,
            "augmentation_batch_size": 2,
            "total_length": 32000,
            "feature_data_files": str(tmp / "features"),
        }
        cfg_path = tmp / "config.yaml"
        cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

        print(f"smoke dir : {tmp}")
        print(f"positives : {len(list(pos_tr.glob('*.wav')))}  negatives: {len(list(neg_tr.glob('*.wav')))}")
        print("running the trainer via tools/ww_train_launcher.py ...")
        print()

        launcher = ROOT / "tools" / "ww_train_launcher.py"
        proc = subprocess.run(
            [sys.executable, str(launcher),
             "--train_model", "--training_config", str(cfg_path)],
            capture_output=True, timeout=1800,
        )
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        tail = "\n".join([l for l in out.splitlines() if l.strip()][-14:])
        if tail:
            print(tail)
        if proc.returncode != 0:
            print()
            print("stderr tail:")
            print("\n".join(err.splitlines()[-14:]))

        produced = sorted(tmp.rglob("*.onnx")) + sorted(tmp.rglob("*.tflite"))
        print()
        if produced:
            for p in produced:
                print(f"  PRODUCED {p.relative_to(tmp)}  ({p.stat().st_size:,} bytes)")
            print("\nPIPELINE OK — the trainer runs and exports.")
            print("This is a smoke model on synthetic tones, NOT a wake word. It lives")
            print("in a temp dir and is deleted on exit.")
            return 0
        print(f"PIPELINE FAILED — exit {proc.returncode}, no model produced.")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())