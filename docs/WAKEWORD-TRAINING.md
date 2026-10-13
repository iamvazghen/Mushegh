Wake words: what is configured, and what is actually listening

    .venv\Scripts\python.exe tools\train_wakeword.py --check mushegh
    .venv\Scripts\python.exe tools\train_wakeword.py mushegh

## What an entry in MUSHEGH_WAKE_WORDS actually means

`src/mushegh/edge/wake_word.py` splits the configured list in two, and the split is
the whole thing to understand:

| Entry | Becomes | Wakes you? |
|---|---|---|
| `mushegh`, `hey mushegh` | the pretrained **hey_jarvis** model | Yes — but the words you *say* are "hey jarvis". These are aliases to someone else's model, not a Mushegh model. |
| a path ending `.onnx` / `.tflite` | that file, if it exists | Yes, once trained. |
| anything else | **pending** | **No.** |

Pending is not an error. The edge logs it by name at startup —
`wake words pending custom engine (Porcupine/training): [...]` — and then runs with
whatever did resolve. That is a deliberate design, and it is also a trap: a list of
names that match nothing looks configured and wakes nothing.

Verified on the current `.env`:

    loads    3 : hey_jarvis  .wakewords/afon.onnx  .wakewords/hey_afon.onnx
    pending  4 : mushegh.onnx  gpt.onnx  copilot.onnx  assistant.onnx

## Why .env.example changed

It shipped `mushegh,alfred,robbin,assist,time to work,wake up,six-one-nine`.
Resolved against the registry: **1 loads, 6 pending.** Six entries that read as
settings and could never wake anyone. The default is now `mushegh,hey mushegh`,
which resolves cleanly, and the comment says why.

Only `hey_jarvis` is loaded from the pretrained set. `alexa`, `hey_mycroft` and
`hey_rhasspy` were false-firing every ~8 seconds on silence, which made the gate
flap open and closed and chopped real speech.

## Training a new word

One word per run — `tools/train_wakeword.py` takes exactly one word and errors on
two, so a run can never quietly become two.

Samples go in `.wakewords/samples/<word>/*.wav` — **16 kHz, mono, under 3 s.**
That directory is gitignored: the recordings are the owner's own voice, which is
biometric data, and there are hundreds of them. `*.onnx` already covered the trained
models; it would not have covered the audio.

Under 40 clips trains a model that fires on the room. 100–300 across several
speakers and rooms is a workable personal wake word. Include 20–50 **negative**
clips — ordinary speech without the word — or it will wake on the television.

Output lands at `.wakewords/<word>.onnx`, which `MUSHEGH_WAKE_WORDS` already points
at, so a trained model is picked up on the next brain start.

## Not TTS

`--allow-synthetic` exists; the default refuses. A model trained on synthetic speech
of one synthesiser's voice false-accepts badly.

## Blocked, and it is not a sample problem

`openwakeword[full]` requires `acoustics==0.2.6`, which calls
`scipy.special.sph_harm`. SciPy **removed that function in 1.15**; this venv is on
**1.17.1**. `openwakeword.train` therefore does not import.

Everything else the training stack needs is installed and verified: `torch`,
`torchinfo`, `torchmetrics`, `audiomentations`, `torch-audiomentations`, `mutagen`.

Clearing it needs one of: SciPy pinned below 1.15 across the whole project venv
(blast radius is the entire assistant, not just wake words); `acoustics` patched; or
`acoustics` dropped from the training path. That is an owner's call, not a
drive-by downgrade.