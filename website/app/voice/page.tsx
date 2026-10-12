import Link from "next/link";

export default function VoicePipeline() {
  return (
    <>
      <h1>Voice pipeline — the whole path, end to end</h1>
      <p className="lead">
        From the moment sound hits the mic to the moment Mushegh's reply lands in your ear —
        every stage, every config knob, and the trickiest real-world gotchas. This is the deep page
        for anyone tuning the voice loop.
      </p>

      <pre>
        <code>{`MIC  →  MicGain  →  Silero VAD  →  openWakeWord  →  DuplexGate  →  STT  →  SpeakerGate
         (boost)        (speech?)      (wake phrase?)    (half/full)    (→txt)    (you?)

       →  BrainBridge (WS → 24/7 brain or local in-process agent)
       →  TTS  →  TTSLeadInSilence  →  TTFWMeter  →  SPEAKER`}</code>
      </pre>

      <h2>1 · Always-listening wake word</h2>
      <p>
        <code>openWakeWord</code> (CPU, bundled) runs on the mic stream continuously and only forwards
        audio to the (cloud) STT when one of the configured phrases fires. After a wake, a listening
        window opens so the command — and short follow-ups — flow through. The window
        closes on silence, so ambient speech / media is ignored.
      </p>
      <table>
        <thead>
          <tr><th>Setting</th><th>Purpose</th><th>Default</th></tr>
        </thead>
        <tbody>
          <tr><td><code>MUSHEGH_WAKE_WORDS</code></td><td>Comma-list of phrases and/or trained <code>.onnx</code> paths</td><td><code>afon,alfred,robbin,assist,time to work,wake up,six-one-nine</code></td></tr>
          <tr><td><code>MUSHEGH_WAKE_WORD_THRESHOLD</code></td><td>Detection confidence 0…1</td><td><code>0.5</code></td></tr>
          <tr><td><code>MUSHEGH_WAKE_LISTEN_WINDOW_S</code></td><td>How long the mic stays open after a wake</td><td><code>8.0</code></td></tr>
          <tr><td><code>MUSHEGH_WAKE_ACK_PHRASE</code></td><td>Pipe-separated spoken acknowledgements (e.g. <code>Yes, sir?|I'm listening, sir.</code>) so you KNOW it heard you before you say the command</td><td>varied defaults</td></tr>
          <tr><td><code>MUSHEGH_LISTENING_PULSE</code></td><td>One soft ping at startup so you know the edge is live; then silent</td><td><code>true</code></td></tr>
        </tbody>
      </table>

      <h3>Pre-trained openWakeWord phrases</h3>
      <p>
        These ship with openWakeWord and need no API key: <code>afon / hey afon / alexa / hey mycroft /
        hey rhasspy / timer / weather</code>. Anything else goes through one of two paths:
      </p>
      <ul>
        <li><strong>Custom trained <code>.onnx</code></strong> — list the file path in <code>MUSHEGH_WAKE_WORDS</code>; openWakeWord loads it directly. Training happens in a separate WSL workspace (the corpus is tens of gigabytes, so it is deliberately not in the repository); <code>bench/verify_wakeword.py</code> and <code>bench/test_wakeword.py</code> are what check a finished model.</li>
        <li>
          <strong>Porcupine is not supported.</strong> It was evaluated and dropped. For a while the
          two settings it needed stayed in the config being read by nothing — settable in{" "}
          <code>.env</code>, and doing precisely nothing — which is the worst shape a setting can
          have, so they were removed. openWakeWord is the only engine, and a custom{" "}
          <code>.onnx</code> phrase is free.
        </li>
      </ul>
      <div className="callout">
        <span className="k">Phantom &quot;Sir?&quot; loop.</span> The shared watchdog keeps TTS bleed from
        re-firing the wake word every ~10s. The fix lives in the model lifecycle
        (<code>wake_word.py</code>): <code>_needs_reset</code> + <code>self._model.reset()</code> on
        resume. The regression check is in <code>bench/test_wakeword.py</code>.
      </div>

      <h2>2 · STT (ears)</h2>
      <table>
        <thead>
          <tr><th>Engine</th><th>Code</th><th>Languages</th><th>When to use</th></tr>
        </thead>
        <tbody>
          <tr><td>Deepgram nova-3 (cloud, streaming)</td><td><code>deepgram</code></td><td>EN/FR/DE/RU + 5 more (<code>multi</code>)</td><td>Default; lowest latency, best accuracy for the supported languages</td></tr>
          <tr><td>Whisper (local, faster-whisper)</td><td><code>whisper</code></td><td>All six incl. Armenian + Ukrainian (auto-detect)</td><td>Only engine that understands Armenian; offline-capable</td></tr>
          <tr><td>Moonshine (local, ONNX)</td><td><code>moonshine</code></td><td>English-only</td><td>~3&times; faster than whisper on CPU; English-only is fine for it</td></tr>
        </tbody>
      </table>
      <p>
        STT decides only what Mushegh can <em>understand</em>. The reply language is a separate setting
        (<code>MUSHEGH_REPLY_LANGUAGE</code>) and defaults to English regardless of the spoken language.
      </p>

      <h2>3 · TTS (voice)</h2>
      <table>
        <thead>
          <tr><th>Engine</th><th>Code</th><th>Notes</th></tr>
        </thead>
        <tbody>
          <tr><td>ElevenLabs (cloud, streaming)</td><td><code>elevenlabs</code></td><td>The chosen “Mushegh voice”; needs API key + voice id</td></tr>
          <tr><td>Piper (local, CPU)</td><td><code>piper</code></td><td>Offline; model auto-downloads once</td></tr>
          <tr><td>Kokoro (local, CPU)</td><td><code>kokoro</code></td><td>Higher quality than Piper, still CPU-runnable</td></tr>
        </tbody>
      </table>
      <p>
        If the configured cloud provider can't be built (missing key, install issue), it
        <strong>automatically</strong> falls back to the local counterpart so the pipeline always comes up.
        That behaviour is governed by <code>MUSHEGH_VOICE_LOCAL_FALLBACK</code>, with
        <code>MUSHEGH_STT_FALLBACK_PROVIDER</code> / <code>MUSHEGH_TTS_FALLBACK_PROVIDER</code> picking the
        fallback engine.
      </p>

      <h2>4 · VAD, barge-in, and duplex mode</h2>
      <p>
        Silero VAD (CPU, bundled) detects speech start/stop and feeds <code>VADUserStartedSpeakingFrame</code>
        into the pipeline. Barge-in — the ability to <em>interrupt Mushegh mid-sentence</em> —
        requires the mic to NOT re-hear his own TTS, so it only works on a <strong>private</strong> endpoint:
      </p>
      <ul>
        <li><strong>Private endpoint</strong> (headphones, AirPods, earbuds, smart-glasses) — barge-in safe and useful.</li>
        <li><strong>Open speakers</strong> (laptop / desktop) — the mic re-hears Mushegh, so barge-in would interrupt himself. Stay half-duplex.</li>
      </ul>
      <p>
        <code>MUSHEGH_BARGE_IN_MODE=auto</code> (default) classifies the live output device and turns
        barge-in ON only when it's safe — the device can declare a hint
        (<code>MUSHEGH_DEVICE_HINT=headphones|airpods|glasses|phone-headphones|phone-speaker|...</code>)
        and that wins over name-sniffing. <code>on</code>/<code>off</code> force it.
      </p>
      <div className="callout">
        <span className="k">Speakers: no AEC, but still barge-in.</span> openWakeWord is hot through TTS,
        so saying the wake word OVER Mushegh's speech interrupts him mid-sentence at a raised
        threshold (<code>threshold + 0.15</code>) — no acoustic echo canceller needed. VAD barge-in
        remains headphones-only. See <code>edge/wake_word.py::_barge_threshold</code>.
      </div>

      <h2>5 · Speaker biometrics (optional)</h2>
      <p>
        Enroll once, then Mushegh obeys only <em>your</em> voice and ignores the TV or a guest.
      </p>
      <pre><code>{`uv sync --extra identity
uv run python bench/enroll_voice.py --script "to-read-script.md"   # ~3 min
# then in .env:
MUSHEGH_SPEAKER_ID_ENABLED=true`}</code></pre>
      <p>
        Backend is SpeechBrain ECAPA-TDNN (192-dim embedding, CPU-runnable). Fail-open until enrolled
        (so a fresh install can never lock you out). The <code>MUSHEGH_SPEAKER_THRESHOLD</code> knob trades
        false-accept vs false-reject; default <code>0.25</code> sits at the EER point.
      </p>

      <h2>6 · Audio I/O</h2>
      <ul>
        <li>
          <strong>Output device:</strong> <code>MUSHEGH_AUDIO_OUTPUT_DEVICE</code> (alias or name fragment)
          or <code>MUSHEGH_AUDIO_OUTPUT_DEVICE_INDEX</code> (numeric). Bluetooth headsets in HFP mode need
          the index pinned — the auto-route can't always see the raw HFP endpoint. Output sample
          rate (<code>MUSHEGH_AUDIO_OUT_SAMPLE_RATE</code>) must match the device (HFP = 16000).
        </li>
        <li>
          <strong>Input device:</strong> <code>MUSHEGH_AUDIO_INPUT_DEVICE_NAME</code> (e.g. <code>airpods</code>)
          survives Bluetooth reconnects — indices go stale. Falls back to
          <code>MUSHEGH_AUDIO_INPUT_DEVICE_INDEX</code>, then the OS default.
        </li>
        <li>
          <strong>Auto-route to headphones</strong> (<code>MUSHEGH_AUTO_ROUTE_HEADPHONES=true</code>): when
          AirPods/BT headphones are connected, output flows there automatically.
        </li>
        <li>
          <strong>Mic gain</strong> (<code>MUSHEGH_MIC_GAIN</code>): software boost for quiet laptop
          arrays. Best paired with raising the OS mic level and lowering this gain.
        </li>
        <li>
          <strong>Voice command:</strong> <em>“switch to my headphones / speakers”</em> persists
          the preference to <code>~/.mushegh/audio_pref.json</code>; next edge start honors it.
        </li>
      </ul>

      <h2>7 · Latency — TTFW + VAQI</h2>
      <p>
        <strong>TTFW (Time-To-First-Word)</strong> — milliseconds from user-stop to first audible
        word of the reply. <code>bench_metrics.TTFW</code> accumulates it; <code>edge/latency_meter.py</code>
        wires it into the pipeline; <code>bench/benchmarks.py</code> prints the mean / median / p95.
        Target <code>MUSHEGH_TTFW_TARGET_MS=1200</code> on CPU.
      </p>
      <p>
        <strong>VAQI (Voice Assistant Quality Index)</strong> — a 0&ndash;100 score blending latency,
        responsiveness (no missed turns), and smoothness (no false self-interruptions). See
        <code>bench/benchmarks.py</code>.
      </p>

      <h2>8 · Mic-listening pulse</h2>
      <p>
        A <strong>single</strong> soft ping shortly after the edge starts, so you <em>know</em> it's up
        and listening BEFORE the first wake word. Then permanently silent. Pure stdlib (sine WAV via
        <code>wave</code>; <code>winsound</code> on Windows / <code>afplay|aplay|ffplay</code> elsewhere).
        Lives outside the pipecat pipeline so it can't trip the half-duplex gate.
      </p>
      <div className="callout warn">
        <span className="k">No heartbeat after that.</span> The wake acknowledgement covers every
        later turn. A constant pulse would be a nag — one ping is the Mushegh touch.
      </div>

      <h2>9 · Diagnostics — if it stops listening</h2>
      <pre><code>{`# Windows
Get-Content logs/edge.log -Tail 50 -Wait
# macOS / Linux
tail -f logs/edge.log`}</code></pre>
      <table>
        <thead><tr><th>Symptom</th><th>Likely cause</th></tr></thead>
        <tbody>
          <tr><td>No <code>wake … detected</code> in the log</td><td>Two edges are fighting for the mic, or wrong default input device. Confirm one edge, restart.</td></tr>
          <tr><td><code>brain link: connected</code> never appears</td><td>Brain not running, or the tailnet IP / token is wrong. <code>curl http://&lt;brain-tailnet-ip&gt;:8766/healthz</code>.</td></tr>
          <tr><td>TTFW spikes to 5&ndash;15s</td><td>LLM provider cold-start or a hung model. Failover chain + warmup probe should fix this; <code>uv run python bench/efficiency_report.py</code> diagnoses it.</td></tr>
          <tr><td>Barge-in triggers on speakers</td><td>You're in half-duplex; the wake word can still interrupt, but VAD barge-in is intentionally off. Use wake-word barge-in or headphones.</td></tr>
        </tbody>
      </table>

      <p style={{ marginTop: 22 }}>
        See <Link href="/configuration">Configuration</Link> for every <code>MUSHEGH_</code> knob, and{" "}
        <Link href="/devices">Devices</Link> for per-device setup.
      </p>
    </>
  );
}