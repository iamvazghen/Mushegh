"""Stub for Piper's `generate_samples`, for training from clips you already have.

openwakeword/train.py does this UNCONDITIONALLY when `--train_model` is used
(train.py:637-639):

    sys.path.insert(0, os.path.abspath(config["piper_sample_generator_path"]))
    from generate_samples import generate_samples

...and then only actually CALLS it when a class has fewer clips than
`n_samples` — "Skipping generation of positive clips for training, as ~N already
exist". So supplying your own recordings means Piper's repo is never used, but the
import still has to resolve.

Rather than vendoring a Piper checkout (voices, models, licences) for a function
this path will not call, point `piper_sample_generator_path` at THIS directory.
If the trainer does reach for it, that means the sample count came up short of
`n_samples`, and it says so instead of quietly synthesising speech from one voice.

    config["piper_sample_generator_path"] = r"C:\\Mushegh\\tools\\piper_stub"
"""


def generate_samples(*_args, **_kwargs):
    raise RuntimeError(
        "Piper sample generation is not available: this run is configured to "
        "train from clips you already supplied, and the trainer wanted to "
        "synthesise more. Either drop `n_samples` to the number of .wav files "
        "you actually have, or install Piper's sample generator and point "
        "`piper_sample_generator_path` at it. Synthesised wake-word samples "
        "false-accept badly, which is why this refuses rather than quietly "
        "generating them."
    )