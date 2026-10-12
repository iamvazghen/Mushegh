"""26.R5 — no video frame leaves the house (D-66).

Charter: *detections stay local. No video frame leaves the house — never to a vision model, never
to a logger, never to a crash report. Only event metadata (zone, label, count, timestamp) may cross
to the brain.*

**Read this before reading the results.** There is no detector in this repository: a search for
`frigate`, `reolink` or `coral` under `src/mushegh/` returns nothing, there is no RTSP client, and no
camera has ever been connected. So this gate cannot prove that a local accelerator produces correct
events, and it does not pretend to. What it proves is the part that is code rather than hardware:

  * **the detector's output channel cannot carry a frame.** `mushegh.brain.detector.accept()` is the
    only function that turns a detector result into something the brain holds, and it refuses any
    payload with a key outside `{zone, label, count, at, camera}` and any value that looks like
    frame bytes, a data URI, an image path or a bare base64 blob. The key allowlist alone is not
    enough — `{"label": "data:image/jpeg;base64,…"}` is schema-valid and still a frame — which is
    why the values are checked too.
  * **with egress blocked, events still arrive.** The socket layer and httpx are replaced with
    tripwires that raise, then a stub local detector produces metadata-only events and every one of
    them reaches `perception`. A detection channel that only works while the network is up would be a
    detection channel that works exactly when the house is empty and unobserved.
  * **a frame cannot reach a remote model.** Not by policy — by tripwire: `LLMClient.see`,
    `camera.look_around` and `camera._camera_capture_local` are replaced with functions that record a
    call and raise, the whole accept-and-publish path is run, and the tripwires are asserted never to
    have fired. That is a claim about the *path*, which an import check cannot make and a lazy
    import inside an untaken branch would defeat.
  * **`see()` is not reachable from the detector's output channel** — the same tripwire, plus an AST
    check on the module, because a tripwire only proves the branch this test happened to take.
  * **a frame cannot reach a log or a crash report.** `shared.redact` withholds data URIs and base64
    media fields, and both sinks that write owner data are asserted end to end: the error journal and
    the audit trail. Neither could see a frame before this — both were *credential* scrubbers, and
    base64 is not a credential. The 600-character message clip in the error journal used to store the
    first 600 characters of a JPEG beside the stack trace, by the crash path.

Hermetic: temp state root and temp audit dir set before import, tripwires instead of a network, no
model, no camera, no accelerator.

    uv run python bench/test_no_frame_egress.py
"""

from __future__ import annotations

import ast
import os
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_TMP = tempfile.mkdtemp(prefix="mushegh-frame-egress-")
os.environ["MUSHEGH_STATE_DIR"] = str(Path(_TMP) / "state")
os.environ["MUSHEGH_AUDIT_LOG_DIR"] = str(Path(_TMP) / "audit")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "src"))

passed = failed = 0

#: Not a real frame. A marker long enough and shaped like one, so "is the base64 gone?" is a
#: string search rather than a judgement call. 96 chars, well past the 40-char detection floor.
B64 = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVphYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5ejAxMjM0NTY3ODk"
DATA_URI = f"data:image/jpeg;base64,{B64}"

#: The detector is a stub. There is no Frigate here and no accelerator, and inventing a fake one
#: would be a measurement of the fake. This produces the events a metadata-only detector produces,
#: which is the only half of the claim that is code.
STUB_EVENTS = [
    {"zone": "front_door", "label": "person", "count": 1, "camera": "cam1"},
    {"zone": "garden", "label": "car", "count": 1, "camera": "cam3"},
    {"zone": "outbuilding", "label": "motion", "count": 3, "camera": "cam3"},
]


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def main() -> int:
    from mushegh.brain import detector
    from mushegh.brain.detector import DetectionEvent, FrameEgressRefused, accept, accept_all, publish
    from mushegh.shared.redact import withhold_media

    print("\n--- the channel carries metadata and declares nothing else ---")
    check("the allowed keys are exactly zone, label, count, at, camera",
          detector.ALLOWED == frozenset({"zone", "label", "count", "at", "camera"}),
          str(sorted(detector.ALLOWED)))
    check("zone and label are required; count, at and camera are not",
          detector.REQUIRED == ("zone", "label"))
    ev = accept(STUB_EVENTS[0])
    check("a metadata-only event is accepted", isinstance(ev, DetectionEvent))
    check("its record has exactly the five metadata fields",
          set(ev.as_record()) == {"zone", "label", "count", "at", "camera"},
          str(sorted(ev.as_record())))
    check("every value in the record is a short scalar",
          all(isinstance(v, (str, int)) and len(str(v)) <= 120 for v in ev.as_record().values()))

    print("\n--- a frame cannot enter through the channel ---")
    hostile = [
        ("an image key", {"zone": "garden", "label": "person", "image": DATA_URI}),
        ("a frame key", {"zone": "garden", "label": "person", "frame": B64}),
        ("a snapshot key", {"zone": "garden", "label": "person", "snapshot": "/tmp/f.jpg"}),
        ("a data URI in a metadata value",
         {"zone": "garden", "label": f"person {DATA_URI}"}),
        ("a bare base64 blob as the label", {"zone": "garden", "label": B64}),
        ("a path to a frame as the zone", {"zone": "/var/lib/frigate/front.jpg", "label": "person"}),
        ("a windows frame path as the zone", {"zone": r"C:\\frigate\\front.jpg", "label": "person"}),
        ("bytes as a count", {"zone": "garden", "label": "person", "count": B64.encode()}),
        ("a nested payload", {"zone": "garden", "label": "person", "crop": {"b64": B64}}),
    ]
    for why, payload in hostile:
        try:
            accept(payload)
            check(f"refuses {why}", False, "it was accepted")
        except FrameEgressRefused as e:
            check(f"refuses {why}", True, "")
            if B64 in str(e):
                check(f"  ...and the refusal itself quotes no frame bytes ({why})", False, str(e)[:80])
    check("no refusal message in the batch quoted frame bytes",
          all(B64 not in str(e) for e in _messages(hostile)))

    print("\n--- the refusals are legible, not silent ---")
    try:
        accept({"zone": "garden", "label": "person", "image": DATA_URI})
    except FrameEgressRefused as e:
        check("the refusal names the rejected key", e.key == "image", e.key)
        check("the refusal names the rule", "D-66" in str(e), str(e))
    try:
        accept({"zone": "garden"})
    except FrameEgressRefused as e:
        check("a missing required field is refused by name", e.key == "label", e.key)
    try:
        accept({"zone": "garden", "label": "person", "count": "two"})
    except FrameEgressRefused as e:
        check("a non-numeric count is refused rather than coerced", e.key == "count", e.key)
    check("a batch refuses wholesale rather than skipping the frame-bearing event",
          _batch_refuses())

    print("\n--- with egress blocked, the detector still produces events ---")
    egress_blocked, tripwires = _block_egress()
    check("the socket layer is genuinely blocked", egress_blocked)
    from mushegh.brain import perception

    perception.reset_visual()
    try:
        events = accept_all(STUB_EVENTS)
        published = [publish(e) for e in events]
    except Exception as e:  # noqa: BLE001
        check("events are accepted with the network down", False, f"{type(e).__name__}: {e}")
        published = []
    check("every event was accepted with egress blocked", len(published) == len(STUB_EVENTS),
          f"{len(published)} of {len(STUB_EVENTS)}")
    check("no egress tripwire fired while producing them", not tripwires["fired"],
          f"fired: {tripwires['which']}")
    fact = perception.perceive()
    # `perception` keeps ONE visual fact (the most recent) and hands it back as a `Fact`, so the
    # assertion is that whichever event landed is a metadata string and not a frame — not that all
    # three are simultaneously readable. `perception.visual` is the Fact; its `.value` is the text.
    check("the brain holds the detection as a fact", fact.visual is not None, repr(fact)[:120])
    expected = [e["zone"] + ": " + e["label"] + f" x{e['count']}" for e in STUB_EVENTS]
    value = str(getattr(fact.visual, "value", fact.visual))
    check("the fact is one of the detector's metadata lines, and no frame bytes",
          value in expected and B64 not in value, f"{value!r} not in {expected}")
    check("the fact is attributed to the detector, not to a camera tool",
          str(getattr(fact.visual, "source", "")).startswith("detector"),
          repr(getattr(fact.visual, "source", "")))
    check("the fact carries a freshness stamp (S26 goal 2: a detection cannot pretend to be current)",
          bool(getattr(fact.visual, "at", 0)), repr(fact.visual)[:120])

    print("\n--- a frame cannot reach a remote model, and see() is not on this path ---")
    seen = _install_vision_tripwires()
    perception.reset_visual()
    try:
        for payload in STUB_EVENTS:
            publish(accept(payload))
        for bad in hostile:
            try:
                accept(bad[1])
            except FrameEgressRefused:
                pass
    except Exception as e:  # noqa: BLE001
        check("the whole path runs without touching vision", False, f"{type(e).__name__}: {e}")
    check("LLMClient.see was never called", not seen["see"], "see() was called")
    check("look_around was never called", not seen["look_around"], "look_around was called")
    check("the camera capture op was never called", not seen["capture"], "camera_capture was called")
    _restore_vision_tripwires()

    src = (ROOT / "src" / "mushegh" / "brain" / "detector.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {"mushegh.brain.llm", "mushegh.brain.tools.camera", "mushegh.brain.tools.multimodal",
                 "mushegh.brain.tools", "mushegh.config", "httpx", "socket", "urllib", "requests"}
    check("the module imports nothing that can reach a model or a socket",
          not (imported & forbidden), f"imports {sorted(imported & forbidden)}")
    for attr in ("see(", "look_around", "_dispatch", "chat.completions", "httpx", "urlopen"):
        check(f"the module's source contains no {attr!r}", attr not in src)

    print("\n--- a frame cannot reach a log ---")
    from mushegh.brain import audit
    from mushegh.shared.paths import audit_dir

    audit.record("look_around", {"prompt": "describe the room"},
                 f"Through the camera, sir: {DATA_URI}", ok=True)
    audit.record("pc_op", {"op": "camera_capture", "detail": f'{{"b64": "{B64}"}}'}, "ok", ok=True)
    raw = "".join(f.read_text(encoding="utf-8") for f in sorted(audit_dir().glob("*.jsonl")))
    check("THE AUDIT TRAIL HELD NO FRAME BYTES", B64 not in raw)
    check("...and says it withheld one", "<withheld>" in raw, raw[-200:])
    check("the tool and its prompt are still recorded, so the line is useful",
          "look_around" in raw and "describe the room" in raw)
    check("the ordinary result text was not mangled",
          "Through the camera, sir:" in raw)

    print("\n--- a frame cannot reach a crash report ---")
    from mushegh.shared import errors

    check("_scrub withholds a data URI", B64 not in errors._scrub(f"failed: {DATA_URI}"))
    check("_scrub withholds a b64 field",
          B64 not in errors._scrub('pc op returned {"b64": "' + B64 + '"}'))
    check("_scrub still redacts a credential (unchanged behaviour)",
          "abcdef123456" not in errors._scrub("api_key=abcdef123456"))
    check("withhold_media leaves ordinary text alone",
          withhold_media("the front door opened at 3am") == "the front door opened at 3am")

    with tempfile.TemporaryDirectory(prefix="mushegh-frame-errs-") as td:
        journal = Path(td) / "errors.jsonl"
        original = errors.JOURNAL
        errors.JOURNAL = journal
        try:
            errors.record(level="error", subsystem="brain/llm", error_type="VisionError",
                          message=f"vision chain exhausted; last body {DATA_URI}",
                          where="mushegh.brain.llm.see", context={"frame": B64}, ship=False)
        finally:
            errors.JOURNAL = original
        written = journal.read_text(encoding="utf-8") if journal.exists() else ""
        check("the error journal was written", bool(written.strip()))
        check("THE CRASH REPORT HELD NO FRAME BYTES", B64 not in written, written[:200])
        check("...and the error itself is still recorded, so the crash is diagnosable",
              "VisionError" in written and "vision chain exhausted" in written)
        check("...and the withheld token is in there", "<withheld>" in written)

    print("\n--- what this gate does NOT claim ---")
    # Checked as IMPORTS, not as text. A grep for the vendor names is self-defeating here: this
    # very module's docstring names them in order to record that they are absent, and so does
    # `detector.py`. What would change the claim is a client library being imported, so that is what
    # is asserted.
    #
    # `cv2` is deliberately NOT on this list. OpenCV is imported today and legitimately: it is the
    # local face counter in `tools/camera.py`, reading a USB device index. It is a local device
    # library, not a networked detector, and pretending otherwise would make this gate fail for a
    # correct system.
    detector_pkgs = {"frigate", "pyfrigate", "reolink", "pyreolink", "coral", "tflite_runtime",
                     "pycoral", "tflite_support", "pyrealsense2", "rtsp", "rtsplib", "pydarknet"}
    imported_anywhere: set[str] = set()
    video_capture_args: list[ast.AST] = []
    rtsp_literals: list[str] = []
    for path in (ROOT / "src" / "mushegh").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "rtsp://" in text.lower():
            rtsp_literals.append(path.name)
        try:
            t = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(t):
            if isinstance(node, ast.Import):
                imported_anywhere.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported_anywhere.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("VideoCapture", "VideoCaptureAsync"):
                video_capture_args.extend(node.args)
    check("no vendor detector client is imported anywhere in src/",
          not (imported_anywhere & detector_pkgs),
          f"imports {sorted(imported_anywhere & detector_pkgs)} — the hardware half of 26.R5 is now "
          f"real, or newly stale, and this gate's scope has to grow")
    check("no RTSP URL appears anywhere in src/", not rtsp_literals, str(rtsp_literals))
    check("every VideoCapture call opens a DEVICE INDEX, never a URL",
          bool(video_capture_args) and all(isinstance(a, ast.Name) for a in video_capture_args),
          f"{len(video_capture_args)} call(s), "
          f"{[type(a).__name__ for a in video_capture_args]}")
    check("...which is what keeps the existing camera path local (a URL would not be)",
          all(isinstance(a, ast.Name) and a.id in ("index", "idx", "camera_index", "i")
              for a in video_capture_args),
          f"argument names: {[getattr(a, 'id', '?') for a in video_capture_args]}")

    print(f"\n{'=' * 60}")
    print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


def _messages(hostile) -> list[Exception]:
    out = []
    for _why, payload in hostile:
        try:
            from mushegh.brain.detector import accept as _accept
            _accept(payload)
        except Exception as e:  # noqa: BLE001
            out.append(e)
    return out


def _batch_refuses() -> bool:
    from mushegh.brain.detector import FrameEgressRefused, accept_all
    try:
        accept_all([{"zone": "garden", "label": "person"},
                    {"zone": "garden", "label": "person", "image": "x"}])
    except FrameEgressRefused:
        return True
    return False


def _block_egress():
    """Replace the socket layer and httpx with tripwires. Returns (blocked, recorder).

    httpx is imported FIRST, deliberately. `ssl` defines `class SSLSocket(socket)` at import time,
    so replacing `socket.socket` before anything has imported it breaks the interpreter rather than
    the network — a tripwire that fires on a class definition is not a network block, it is a
    broken test that happens to look strict.
    """
    state = {"fired": False, "which": []}
    try:
        import httpx
    except ImportError:
        httpx = None

    def _no_socket(*_a, **_k):
        state["fired"] = True
        state["which"].append("socket.socket")
        raise AssertionError("egress: socket.socket was created")

    socket.socket = _no_socket  # type: ignore[assignment]
    if httpx is not None:
        def _no_request(*_a, **_k):
            state["fired"] = True
            state["which"].append("httpx")
            raise AssertionError("egress: an HTTP request was attempted")

        httpx.Client.request = _no_request  # type: ignore[assignment]
        httpx.AsyncClient.request = _no_request  # type: ignore[assignment]
    return True, state


def _install_vision_tripwires() -> dict:
    from mushegh.brain import llm
    from mushegh.brain.tools import camera

    seen = {"see": False, "look_around": False, "capture": False}

    async def _no_see(*_a, **_k):
        seen["see"] = True
        raise AssertionError("D-66: LLMClient.see was reached from the detector channel")

    async def _no_look(*_a, **_k):
        seen["look_around"] = True
        raise AssertionError("D-66: look_around was reached from the detector channel")

    async def _no_capture(*_a, **_k):
        seen["capture"] = True
        raise AssertionError("D-66: the camera capture op was reached from the detector channel")

    llm.LLMClient.see = _no_see  # type: ignore[method-assign]
    camera.look_around = _no_look  # type: ignore[assignment]
    camera._camera_capture_local = _no_capture  # type: ignore[assignment]
    return seen


def _restore_vision_tripwires() -> None:
    from mushegh.brain import llm
    from mushegh.brain.tools import camera

    for mod, name in ((llm.LLMClient, "see"), (camera, "look_around"),
                      (camera, "_camera_capture_local")):
        if hasattr(mod, name):
            delattr(mod, name)
    import importlib
    importlib.reload(llm)
    importlib.reload(camera)


if __name__ == "__main__":
    raise SystemExit(main())
