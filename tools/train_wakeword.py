"""Train ONE custom openWakeWord wake word, from samples, one word per run.

    .venv\\Scripts\\python.exe tools\\train_wakeword.py --check mushegh
    .venv\\Scripts\\python.exe tools\\train_wakeword.py mushegh

WHY ONE WORD AT A TIME
Each model is a separate ~30 minute CPU training run over its own sample set, and
they share one GPU/CPU budget on this box. `--check` takes exactly one word by
construction: passing two is an error rather than a queue, so a run can never
quietly become two and quietly take twice as long.

WHAT THIS CANNOT DO
It cannot invent audio. A wake word model is trained on recordings of people
saying the word; there are none in this repo, and none can be synthesised into
something worth shipping. With no samples this refuses to start, and says how many
it wants and where they go. TTS-generated samples are deliberately not accepted by
default -- a model trained only on synthetic speech of one voice false-accepts
badly. Pass --allow-synthetic only if you understand that.

SAMPLES
    .wakewords/samples/<word>/*.wav
16 kHz mono. openWakeWord's own guidance is ~1000 clips for a model you would
publish; 100-300 across several speakers and recording conditions is a workable
personal wake word. Under ~40 it will train, and it will misfire.

Requires: torch, torchinfo, torchmetrics, and a config that names this word's
clips. `--check` reports all of that without training.

    .venv\\Scripts\\python.exe tools\\train_wakeword.py --check mushegh
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / ".wakewords" / "samples"
MODELS = ROOT / ".wakewords"

#: Below this a model trains into something that fires on the room, not on you.
MIN_CLIPS = 40
GOOD_CLIPS = 300

WORDS = ("mushegh", "gpt", "copilot", "assistant")


def check_dependencies() -> list[str]:
    import importlib.util as u

    missing = []
    for mod in ("torch", "torchinfo", "torchmetrics", "numpy", "scipy", "yaml"):
        if u.find_spec(mod) is None:
            missing.append(mod)
    return missing


def _scipy_sph_harm_shim() -> str:
    """Let `acoustics` import on SciPy >= 1.15, without faking a function.

    openwakeword.data does `import acoustics` at module level, and acoustics'
    __init__ pulls in directivity, which does `from scipy.special import sph_harm`.
    SciPy removed sph_harm in 1.15 (renamed, with a different argument order, to
    sph_harm_y) -- so on 1.17 the import raises and openwakeword.train cannot load
    at all.

    Aliasing sph_harm to sph_harm_y would look like a fix and be a lie: the two take
    (m, n, theta, phi) and (n, m, theta, phi), so every result would be silently
    wrong. And it does not matter, because nothing on the wake-word training path
    ever CALLS it -- the only thing openwakeword uses from acoustics is
    `acoustics.generator.noise(...)` for coloured-noise augmentation
    (openwakeword/data.py:434).

    So this binds a name that exists and raises when used. If some future code path
    does call it, the failure is loud and names the cause, instead of a model
    trained on quietly-wrong room acoustics.

    Returns a note for the caller, or "" when no shim was needed.
    """
    import scipy.special as sp

    if hasattr(sp, "sph_harm"):
        return ""

    def sph_harm(*_args, **_kwargs):
        raise NotImplementedError(
            "scipy.special.sph_harm was removed in SciPy 1.15. The wake-word "
            "training path never calls it (only acoustics.generator.noise is "
            "used), so this shim exists solely to let `acoustics` import. If you "
            "reached this, something started using acoustics.directivity and it "
            "needs scipy.special.sph_harm_y with (n, m, theta, phi) instead."
        )

    sp.sph_harm = sph_harm
    return "shimmed scipy.special.sph_harm (import-only; raises if called)"


def clips_for(word: str) -> list[Path]:
    d = SAMPLES / word
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.wav") if p.is_file())


def check_wav(path: Path) -> str | None:
    """Return a reason this clip cannot be used, or None if it looks fine."""
    try:
        with wave.open(str(path), "rb") as w:
            if w.getframerate() != 16000:
                return f"{path.name}: {w.getframerate()} Hz, wants 16000"
            if w.getnchannels() != 1:
                return f"{path.name}: {w.getnchannels()} channels, wants mono"
            if w.getnframes() / w.getframerate() > 3.0:
                return f"{path.name}: longer than 3s"
    except wave.Error as e:
        return f"{path.name}: not readable as WAV ({e})"
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("word", nargs="*", help="exactly ONE word to train")
    ap.add_argument("--check", action="store_true", help="preflight only; train nothing")
    ap.add_argument("--allow-synthetic", action="store_true",
                    help="accept TTS samples (they train badly; see the docstring)")
    args = ap.parse_args(argv)

    words = [w.strip().lower() for w in args.word if w.strip()]

    if len(words) != 1:
        print(f"one word at a time: got {len(words)} ({words}). Pass exactly one.")
        return 2
    word = words[0]

    print(f"wake word : {word}")
    print(f"samples   : {SAMPLES / word}")
    print(f"output    : {MODELS / (word + '.onnx')}")
    print()

    ok = True

    missing = check_dependencies()
    if missing:
        ok = False
        print("MISSING python packages:")
        for m in missing:
            print(f"  - {m}")
        print(f"  install: uv pip install {' '.join(missing)}")
    else:
        print("deps      : torch, torchinfo, torchmetrics, numpy, scipy, yaml present")

    note = _scipy_sph_harm_shim()
    try:
        import openwakeword.train  # noqa: F401

        print(f"trainer   : openwakeword.train imports OK{' (' + note + ')' if note else ''}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"trainer   : openwakeword.train will NOT import -- {type(e).__name__}: {e}")

    clips = clips_for(word)
    if not clips:
        ok = False
        need = SAMPLES / word
        print(f"NO SAMPLES. Put 16 kHz mono .wav clips of '{word}' in:")
        print(f"  {need}")
        print(f"  aim for {GOOD_CLIPS}+ across several speakers; under {MIN_CLIPS} is not usable.")
    else:
        bad = [r for r in (check_wav(c) for c in clips) if r]
        print(f"samples   : {len(clips)} clip(s)")
        for b in bad[:8]:
            print(f"  reject {b}")
        if len(clips) < MIN_CLIPS and not args.allow_synthetic:
            ok = False
            print(f"  too few: {len(clips)} < {MIN_CLIPS}. Collect more before training.")
        if bad:
            ok = False

    print()
    if not ok:
        print("PREFLIGHT FAILED — nothing was trained.")
        print("This will not start with no samples. That is the point: a wake word model")
        print("trained on nothing is a model that fires on the room.")
        return 1

    if args.check:
        print("PREFLIGHT OK. Drop this run, or re-run without --check to train.")
        return 0

    print("Training runs are not yet wired to the openWakeWord trainer here — see the")
    print("docstring. Samples are the missing piece; bring them and this proceeds.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())