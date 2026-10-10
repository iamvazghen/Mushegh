/**
 * The tracker — the seam between hand landmarks and the pointer events.
 *
 * Everything upstream of here is a decision (handLogic) and everything downstream
 * is a dispatch (pointerSynth). This module owns the parts in between: which
 * detection belongs to which hand, the per-hand smoothing, and the lifecycle
 * that turns tracking on and off without leaving a press held or a camera light
 * on after the owner has walked away.
 *
 * The landmark source is injected rather than imported, so the whole state
 * machine — identity, lifecycle, release-on-loss — is testable without a webcam,
 * a GPU or a MediaPipe build. Swapping in the real detector later is a wiring
 * change, not a rewrite.
 */

import { holdCamera, releaseCamera } from '../camera';
import { HandDecision, INDEX_TIP, JOINT_COUNT, WRIST, type Landmark, type Side } from './handLogic';
import { OneEuroPoint } from './oneEuro';
import { PointerSynth, patchPointerCapture, type DispatchTarget, type EventFactory } from './pointerSynth';

/** One frame of detections, as a landmark source would produce it. */
export interface Frame {
  landmarks: Landmark[][];
  handedness: Side[];
  /** Milliseconds, monotonic. */
  at: number;
}

export interface HandSource {
  /** Called once per frame with the freshest detections. */
  onFrame(cb: (f: Frame) => void): void;
  /** Stop producing frames. Must be safe to call more than once. */
  close(): void;
}

export interface TrackerEnv {
  source: HandSource;
  hit: { elementFromPoint(x: number, y: number): DispatchTarget | null };
  events: EventFactory;
  viewport(): { w: number; h: number };
  camera?: { hold(): Promise<unknown>; release(): void };
  onStatus?(s: TrackerStatus): void;
}

export interface TrackerStatus {
  running: boolean;
  hands: number;
  lastError: string;
}

/**
 * How far, as a fraction of the screen diagonal, a hand may jump between frames
 * and still be the same hand.
 */
const MAX_JUMP_FRACTION = 0.28;

/** Cursor is filtered harder than the skeleton: aiming is precision work. */
const CURSOR_MIN_CUTOFF = 1.1;
const CURSOR_BETA = 0.012;
const SKELETON_MIN_CUTOFF = 2.4;
const SKELETON_BETA = 0.02;

/** One tracked hand: its identity, its smoothing, its decisions. */
class Tracked {
  readonly decision = new HandDecision();
  readonly cursor: OneEuroPoint;
  readonly joints: OneEuroPoint[];
  readonly points: { x: number; y: number }[] = [];

  constructor(readonly id: number) {
    this.cursor = new OneEuroPoint(CURSOR_MIN_CUTOFF, CURSOR_BETA);
    this.joints = Array.from({ length: JOINT_COUNT }, () => new OneEuroPoint(SKELETON_MIN_CUTOFF, SKELETON_BETA));
  }

  get wrist(): Landmark | undefined { return this.points[WRIST]; }
}

export class HandTracker {
  private hands = new Map<number, Tracked>();
  private pointer: PointerSynth;
  private stop: (() => void) | null = null;
  private _status: TrackerStatus = { running: false, hands: 0, lastError: '' };

  constructor(private env: TrackerEnv) {
    this.pointer = new PointerSynth(env.hit, env.events);
  }

  get status(): TrackerStatus { return { ...this._status, hands: this.hands.size }; }

  /**
   * Which tracked hand a detection belongs to.
   *
   * Handedness alone is not enough, and using it that way causes the worst bug
   * this class can have. The classifier is confident but not stable: it
   * mislabels a hand for a frame or two fairly often, especially while the hand
   * is rotating. Keyed purely on the label, that single frame moves the hand into
   * the other slot — which drops the old slot, fires pointercancel, and silently
   * ends whatever was being dragged. The symptom is a drag that works once and
   * then refuses to start again.
   *
   * So identity comes from continuity first: a detection belongs to whichever
   * tracked hand was nearest last frame. Your hand cannot teleport across the
   * screen between frames, but its label can flip, so position is the more
   * trustworthy signal by a wide margin. Handedness decides only where a hand
   * that is genuinely new goes.
   */
  private slotFor(side: Side, wrist: Landmark, taken: Set<number>, reach: number): number {
    let best = -1;
    let bestDist = Infinity;
    for (const h of this.hands.values()) {
      if (taken.has(h.id) || !h.wrist) continue;
      const d = Math.hypot(h.wrist.x - wrist.x, h.wrist.y - wrist.y);
      if (d < bestDist) {
        bestDist = d;
        best = h.id;
      }
    }
    if (best !== -1 && bestDist < reach * MAX_JUMP_FRACTION) return best;

    const want = side === 'right' ? 1 : 0;
    if (!taken.has(want)) return want;
    return want === 1 ? 0 : 1;
  }

  private dropHand(id: number): void {
    const h = this.hands.get(id);
    if (!h) return;
    // Release before removing: a press that outlives its hand leaves whatever was
    // being dragged stuck to a cursor that no longer exists.
    this.pointer.release(id, h.wrist ?? { x: 0, y: 0 });
    h.decision.reset();
    this.hands.delete(id);
  }

  /** Process one frame of detections. Exposed so tests need no camera. */
  ingest(f: Frame): void {
    const { w, h } = this.env.viewport();
    const reach = Math.hypot(w, h);
    const seen = new Set<number>();
    const at = f.at / 1000;

    for (let k = 0; k < f.landmarks.length && k < 2; k++) {
      const marks = f.landmarks[k];
      if (!marks || marks.length < JOINT_COUNT) continue;

      // Mirrored, because the camera faces you: moving your hand right should
      // move the cursor right, not left.
      const wristPx: Landmark = { x: (1 - marks[WRIST].x) * w, y: marks[WRIST].y * h };
      const side = f.handedness[k] ?? 'right';
      const id = this.slotFor(side, wristPx, seen, reach);
      seen.add(id);

      let t = this.hands.get(id);
      if (!t) {
        t = new Tracked(id);
        this.hands.set(id, t);
      }
      t.points.length = 0;
      for (let j = 0; j < JOINT_COUNT; j++) {
        t.points.push(t.joints[j].filter((1 - marks[j].x) * w, marks[j].y * h, at));
      }

      const tip = t.points[INDEX_TIP];
      const aimed = t.cursor.filter(tip.x, tip.y, at);
      const decision = t.decision.update(t.points, aimed, f.at, side);
      this.pointer.emit(decision, id);
    }

    // Anything not seen this frame has left the picture.
    for (const id of [...this.hands.keys()]) if (!seen.has(id)) this.dropHand(id);
    this.env.onStatus?.(this.status);
  }

  /** Start tracking. Safe to call when already running. */
  async start(): Promise<void> {
    if (this.stop) return;
    this._status = { ...this._status, running: true, lastError: '' };
    try {
      await (this.env.camera?.hold() ?? holdCamera());
      patchPointerCapture();
    } catch (err) {
      this._status = { ...this._status, running: false, lastError: String((err as Error)?.message ?? err) };
      this.env.onStatus?.(this.status);
      return;
    }
    const source = this.env.source;
    source.onFrame((f) => {
      if (!this._status.running) return;
      try {
        this.ingest(f);
      } catch (err) {
        this._status = { ...this._status, lastError: String((err as Error)?.message ?? err) };
        this.env.onStatus?.(this.status);
      }
    });
    this.stop = () => source.close();
    this.env.onStatus?.(this.status);
  }

  /** Stop tracking and hand back everything it holds. Safe to call twice. */
  stop_(): void {
    if (!this.stop) return;
    this.stop();
    this.stop = null;
    for (const id of [...this.hands.keys()]) this.dropHand(id);
    this.hands.clear();
    this.pointer.reset();
    try {
      (this.env.camera?.release() ?? releaseCamera());
    } catch {
      /* a camera that is already gone is not an error worth reporting */
    }
    this._status = { ...this._status, running: false, hands: 0 };
    this.env.onStatus?.(this.status);
  }
}