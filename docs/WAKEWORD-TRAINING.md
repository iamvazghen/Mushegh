# Wake words: what is configured, and what training actually needs

    .venv\Scripts\python.exe tools\train_wakeword.py --check mushegh
    .venv\Scripts\python.exe tools\train_wakeword.py mushegh

## What an entry in MUSHEGH_WAKE_WORDS means

`src/mushegh/edge/wake_word.py` splits the list in two:

| Entry | Becomes | Wakes you? |
|---|---|---|
| `mushegh`, `hey mushegh` | pretrained **hey_jarvis** | Yes — but the words you *say* are "hey jarvis". Aliases to someone else's model. |
| a path ending `.onnx` / `.tflite` | that file, if it exists | Yes, once trained. |
| anything else | **pending** | **No.** |

Pending is not an error. The edge logs it by name at startup
(`wake words pending custom engine (Porcupine/training): [...]`). It is also a
trap: a list of names matching nothing looks configured and wakes nothing.

Verified on the current `.env`:

    loads    3 : hey_jarvis  .wakewords/afon.onnx  .wakewords/hey_afon.onnx
    pending  4 : mushegh.onnx  gpt.onnx  copilot.onnx  assistant.onnx

## Training: the real requirements, from upstream

An earlier version of this file said "record 100–300 clips, never use TTS". That
was my opinion and it **contradicts openWakeWord's own documentation**. The
authoritative source is `examples/custom_model.yml` in the upstream repo, and its
shape is:

| | |
|---|---|
| `n_samples` | 10000 (`n_samples_val` 2000) — *"minimum of 20,000 recommended, often 100,000+ is best"* |
| `piper_sample_generator_path` | a fork of `dscripka/piper-sample-generator` — **the positives are TTS-generated** |
| `feature_data_files` | a **dict** of precomputed background features, e.g. `"ACAV100M_sample": "...ACAV100M_2000_hrs_16bit.npy"` |
| `false_positive_validation_data_path` | `validation_set_features.npy` |
| `rir_paths`, `background_paths` | room impulse responses and background audio |
| `steps` | 50000 |
| `model_type` | `"dnn"` (or `"rnn"`) |

Both background-feature files come from
`https://huggingface.co/datasets/davidscripka/openwakeword_features`.

So upstream's documented path is **generated speech plus a large real background
corpus**, and a 50 000-step run — hours, not minutes. My earlier "TTS trains
badly" claim was not wrong about the risk (a model trained only on one
synthesiser's voice false-accepts) but it was wrong to present hand-recording as
the supported route when the supported route is Piper.

`batch_n_per_class` keys must match `feature_data_files`, plus `positive` and
`adversarial_negative`, which the trainer adds itself.

## Where it has to run

**Not on Windows, and not on Python 3.12.** Three packaging walls, all confirmed:

* `k2` has no Windows wheel — `uv pip install k2` resolves a stub that then fails
  on a missing `_k2`. speechbrain's processing stack imports it eagerly.
* `openwakeword[full]` pins `tensorflow-cpu==2.8.1`, wheels for CPython ≤ 3.10.
  On Windows the resolver "solved" it by downgrading openwakeword to 0.5.1, which
  has no `train.py`.
* on Linux, openwakeword needs `tflite-runtime>=2.8.0`, and tflite-runtime ships
  wheels up to **cp311 only**.

So: `tools/setup_wsl_wakewords.sh` builds it under WSL on Python 3.11, installing
the trainer's dependencies **by name** rather than through the broken extra.
`tools/ww_shim.py` covers two import-only gaps on that venv
(`scipy.special.sph_harm`, `speechbrain.integrations.k2_fsa`); both refuse loudly
if anything ever actually calls them.

## The background-feature corpus

Training needs precomputed *features* (not audio) from
`davidscripka/openwakeword_features` on HuggingFace — **CC-BY-NC-SA-4.0**.

| File | Size | Fetched |
|---|---|---|
| `validation_set_features.npy` | 176 MB | yes — verified `(481345, 96) float32` |
| `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` | **16.1 GB** | **not** — left as a decision |

`tools/fetch_wakeword_features.sh` fetches the small one into
`~/.cache/openwakeword_features/` and deliberately skips the large one.

Two reasons that 16 GB is a decision rather than a background transfer:
it is a long download, and **CC-BY-NC-SA-4.0 is non-commercial** on data the
trained model is derived from. This repo is MIT and invites commercial forks,
so training against an NC corpus puts a constraint on what the resulting model
can be used for. Worth deciding deliberately rather than discovering later.

## Samples

`.wakewords/samples/<word>/*.wav` — **16 kHz, mono, under 3 s** — is the
hand-recording route, for when you want speaker variety that a synthesiser cannot
give. It is gitignored: those recordings are the owner's own voice, which is
biometric data. `tools/train_wakeword.py --check <word>` validates format and
count without training.

`--allow-synthetic` exists and defaults to refusing. That default was written
before reading `custom_model.yml`; revisit it when you decide which route you
want.

## Verified so far

Environment built and the run reaches `openwakeword/train.py:845`
(`mmap_batch_generator`). It is **not** a passing training run: the smoke test
still needs a correct config plus real data.