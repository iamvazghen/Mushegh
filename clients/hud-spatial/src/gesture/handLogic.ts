/**
 * Hand decision logic — no DOM, no MediaPipe, no camera.
 *
 * Everything that decides *what the hand means* lives here so it can be tested
 * without a webcam: landmark anatomy, the rotation-invariant finger test, the
 * pose classifier, and the three gates a pinch has to clear before it presses.
 *
 * Ported from adewaskar/jarvis `src/lib/hands.ts` (MIT, © 2026 Aditya
 * Dewaskar). The state that makes these decisions non-obvious — hysteresis,
 * confirmation, a settling window, and the aim trail — is kept per-hand in
 * `HandDecision` rather than in module-level maps, so two hands cannot leak
 * state into each other and a test needs no cleanup.
 */

export type Landmark = { x: number; y: number };
export type Finger = 'thumb' | 'index' | 'middle' | 'ring' | 'pinky';
export type Gesture = 'point' | 'pinch' | 'frame' | 'open' | 'fist' | 'peace' | 'none';
export type Side = 'left' | 'right';
export type Fingers = { thumb: boolean; index: boolean; middle: boolean; ring: boolean; pinky: boolean };

/* ---------------------------------------------------------------- anatomy */

export const WRIST = 0;
const THUMB_MCP = 2;
const THUMB_TIP = 4;
const INDEX_PIP = 6;
export const INDEX_TIP = 8;
const MIDDLE_MCP = 9;
const MIDDLE_PIP = 10;
const MIDDLE_TIP = 12;
const RING_PIP = 14;
const RING_TIP = 16;
const PINKY_PIP = 18;
const PINKY_TIP = 20;
export const JOINT_COUNT = 21;

/**
 * The skeleton, as pairs of landmark indices.
 *
 * Written out rather than taken from HandLandmarker.HAND_CONNECTIONS so the
 * renderer does not depend on a static the library is free to reshape.
 */
export const BONES: readonly [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [9, 10], [10, 11], [11, 12],
  [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  // The arch across the knuckles, which is what makes it read as a hand rather
  // than five separate sticks.
  [5, 9], [9, 13], [13, 17],
];

export const TIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP] as const;

/* ---------------------------------------------------------------- tuning */

/**
 * Pinch thresholds, as a fraction of hand span rather than an absolute.
 *
 * The raw gap between two fingertips is meaningless alone: it halves when you
 * lean back and doubles when you lean in, so a fixed threshold means the
 * interface only works at one distance from the camera. Dividing by the span
 * from wrist to middle knuckle — a length that shrinks with the same
 * perspective — makes it a property of the hand's shape rather than its
 * distance, which is what a pinch actually is.
 *
 * Two thresholds, not one: it takes a tighter pinch to start a press than to
 * keep one, so the press cannot flicker on the boundary.
 */
export const PINCH_ON = 0.40;
export const PINCH_OFF = 0.60;

/** A finger counts as extended when its tip is this much further from the
 *  wrist than its middle joint. Ratio rather than a y-comparison, so it still
 *  works with the hand rotated or upside down. */
export const EXTEND_RATIO = 1.12;

/** The thumb never straightens the way the fingers do, so it is measured
 *  against its own base joint rather than by the same ratio. */
const THUMB_RATIO = 1.35;
const THUMB_SPREAD = 1.1;

/**
 * A gesture must hold for this long before it counts.
 *
 * Fingers pass through other shapes on the way to the one you meant — a fist
 * becomes a point by way of several ambiguous frames — and acting on those
 * intermediate readings is what makes gesture interfaces feel possessed.
 */
export const GESTURE_HOLD_MS = 200;

/**
 * A pinch has to survive this long before it presses.
 *
 * Pinch used to be exempt from any hold, on the reasoning that a press is the
 * one gesture where latency is felt. True, but it made every transition between
 * poses a hazard: going from a framing L to a point takes the fingers through
 * arrangements that momentarily read as a pinch, and each of those fired a
 * press — grabbing something you were not touching.
 */
export const PINCH_CONFIRM_MS = 70;

/**
 * After the finger pose changes, presses are ignored for this long.
 *
 * The confirm window catches a pinch that flickers. This catches the other
 * half: a pose that genuinely settles into something pinch-shaped for a moment
 * while the hand is still rearranging. Both are needed, because they fail in
 * opposite directions.
 */
export const POSE_SETTLE_MS = 220;

/** Below this many pixels of travel, a press was a click rather than a drag. */
export const CLICK_SLOP = 20;

/**
 * How far back a press aims.
 *
 * A pinch takes about this long from "hand open, pointing at the thing" to
 * "fingers touching", and the fingertip travels several centimetres over that
 * time — so the position at the instant the press fires is not the position you
 * aimed from.
 */
export const AIM_LAG_MS = 190;
/** Nothing older than this is kept; two frames' worth of slack over the lag. */
export const TRAIL_MS = 500;

export const dist = (a: Landmark, b: Landmark): number => Math.hypot(a.x - b.x, a.y - b.y);

/**
 * Is this finger extended?
 *
 * Compared as distance from the wrist rather than by which landmark is higher
 * on screen. The y-comparison is the common recipe and it is wrong the moment
 * the hand is not upright: turn your hand sideways and every finger reads as
 * curled. Distance from the wrist is rotation-invariant, which is the property
 * the question actually needs.
 */
export function isExtended(marks: readonly Landmark[], tip: number, pip: number): boolean {
  const wrist = marks[WRIST];
  return dist(marks[tip], wrist) > dist(marks[pip], wrist) * EXTEND_RATIO;
}

export function readFingers(marks: readonly Landmark[], span: number): Fingers {
  return {
    // The thumb reads as out either by straightening against its own base joint
    // or by standing away from the index — both are thumbs-up to a camera.
    thumb: dist(marks[THUMB_TIP], marks[WRIST]) > dist(marks[THUMB_MCP], marks[WRIST]) * THUMB_RATIO
      || dist(marks[THUMB_TIP], marks[INDEX_PIP]) > span * THUMB_SPREAD,
    index: isExtended(marks, INDEX_TIP, INDEX_PIP),
    middle: isExtended(marks, MIDDLE_TIP, MIDDLE_PIP),
    ring: isExtended(marks, RING_TIP, RING_PIP),
    pinky: isExtended(marks, PINKY_TIP, PINKY_PIP),
  };
}

export function classify(fingers: Fingers, pinched: boolean): Gesture {
  if (pinched) return 'pinch';
  const { thumb, index, middle, ring, pinky } = fingers;
  const up = [thumb, index, middle, ring, pinky].filter(Boolean).length;
  if (index && middle && !ring && !pinky) return 'peace';
  /**
   * The framing pose — index up, thumb out, the rest curled: the corner of a
   * rectangle, the shape people already make when they mime framing a shot.
   *
   * Tested before `point`, and it has to be: a framing hand also has exactly
   * one finger extended, so the point rule would swallow it. The thumb is the
   * whole difference between "I am aiming at that" and "I am sizing this".
   */
  if (thumb && index && !middle && !ring && !pinky) return 'frame';
  if (index && !middle && !ring && !pinky) return 'point';
  if (up >= 4) return 'open';
  if (up === 0) return 'fist';
  return 'none';
}

/** Thumb-to-index gap as a fraction of hand span. See PINCH_ON. */
export function pinchGap(marks: readonly Landmark[], span: number): number {
  return dist(marks[THUMB_TIP], marks[INDEX_TIP]) / span;
}

export function handSpan(marks: readonly Landmark[]): number {
  return dist(marks[WRIST], marks[MIDDLE_MCP]) || 1;
}

/* ------------------------------------------------------------- per hand */

export interface Decision {
  gesture: Gesture;
  pinched: boolean;
  closeness: number;
  fingers: Fingers;
  span: number;
  /** Where the cursor sits — the index fingertip, filtered by the caller. */
  x: number;
  y: number;
  /** Where a press is aimed: the cursor as it was AIM_LAG_MS ago. */
  aimX: number;
  aimY: number;
}

/**
 * One hand's decision state.
 *
 * Holds the hysteresis, the confirmation window, the settling window, the aim
 * trail and the pose vote. `update` is a pure function of its arguments and
 * prior state — no DOM, no globals — which is what makes all of the timing
 * rules above testable with a synthetic clock.
 */
export class HandDecision {
  private pinchSince: number | null = null;
  private poseChangedAt = 0;
  private settling: { raw: Gesture; since: number; held: Gesture } | null = null;
  private trail: { x: number; y: number; at: number }[] = [];
  private sideVote = 0;

  private _pinched = false;
  private _gesture: Gesture = 'none';
  private aimX = 0;
  private aimY = 0;

  get pinched(): boolean { return this._pinched; }
  get gesture(): Gesture { return this._gesture; }

  /**
   * @param marks smoothed, already-mirrored landmarks in viewport pixels.
   * @param cursor the filtered index fingertip, which is the cursor.
   * @param saw   the handedness label for this frame, display only.
   */
  update(marks: readonly Landmark[], cursor: Landmark, now: number, saw: Side): Decision {
    const span = handSpan(marks);
    const gap = pinchGap(marks, span);

    /**
     * Hysteresis, then confirmation, then a settling window.
     *
     * Three filters rather than one because they catch different things. The
     * hysteresis stops a held pinch flickering on the boundary. The
     * confirmation stops a pinch that lasts a frame or two on the way between
     * poses. The settling window stops one that arrives while the hand is still
     * rearranging after a deliberate change of gesture. A press has to get past
     * all three, and an intentional pinch does so without noticing they exist.
     */
    const wantsPinch = this._pinched ? gap < PINCH_OFF : gap < PINCH_ON;
    if (wantsPinch && !this._pinched) this.pinchSince = this.pinchSince ?? now;
    else if (!wantsPinch) this.pinchSince = null;
    const held = this.pinchSince;
    const settledLongEnough = now - this.poseChangedAt > POSE_SETTLE_MS;
    const pinched = this._pinched
      ? wantsPinch
      : wantsPinch && held !== null && now - held >= PINCH_CONFIRM_MS && settledLongEnough;

    /**
     * A trail has no cliff: it always records, and the press simply reads back
     * AIM_LAG_MS, which is the distance a fingertip covers on its way to meeting
     * the thumb. (An earlier version latched the aim only while the pinch was
     * "open", which demanded the fingers be further apart than anyone holds a
     * hand they are pointing with — so the aim froze at first sight and every
     * press landed somewhere stale.)
     */
    this.trail.push({ x: cursor.x, y: cursor.y, at: now });
    while (this.trail.length > 1 && now - this.trail[0].at > TRAIL_MS) this.trail.shift();
    if (!pinched) {
      const want = now - AIM_LAG_MS;
      let pick = this.trail[0];
      for (const p of this.trail) if (p.at <= want) pick = p;
      this.aimX = pick.x;
      this.aimY = pick.y;
    }

    const fingers = readFingers(marks, span);
    const wasGesture = this._gesture;
    this._gesture = this.stabilise(classify(fingers, pinched), now);
    // A change of pose starts the settling window. Pinch is not counted: it is
    // the thing being protected, not a transition to recover from.
    if (this._gesture !== wasGesture && this._gesture !== 'pinch' && wasGesture !== 'pinch') {
      this.poseChangedAt = now;
    }

    this._pinched = pinched;
    this.vote(saw);

    return {
      gesture: this._gesture,
      pinched,
      closeness: Math.max(0, Math.min(1, 1 - (gap - PINCH_ON) / (PINCH_OFF - PINCH_ON))),
      fingers,
      span,
      x: cursor.x,
      y: cursor.y,
      aimX: this.aimX,
      aimY: this.aimY,
    };
  }

  /**
   * Only report a finger pose once it has held.
   *
   * A pinch is deliberately exempt: it carries its own hysteresis, and it is
   * the one gesture where the delay would be felt directly — as a press that
   * lands late.
   */
  private stabilise(raw: Gesture, now: number): Gesture {
    if (raw === 'pinch') {
      this.settling = { raw, since: now, held: raw };
      return raw;
    }
    const s = this.settling;
    if (!s || s.raw !== raw) {
      const held: Gesture = s?.held === 'pinch' ? 'none' : (s?.held ?? 'none');
      this.settling = { raw, since: now, held };
      return held;
    }
    if (now - s.since >= GESTURE_HOLD_MS) s.held = raw;
    return s.held;
  }

  /**
   * A running vote on which hand this is.
   *
   * Handedness decides thumb geometry and the label on screen, and a single bad
   * frame renaming a hand is visible even when nothing else is wrong. A vote
   * that decays settles within a few frames and then stays put.
   */
  private vote(saw: Side): void {
    // Clamped so a long run of one label cannot make the other take a second to
    // win once the hand genuinely changes.
    this.sideVote = Math.max(-6, Math.min(6, this.sideVote + (saw === 'right' ? 1 : -1)));
  }

  get handedness(): Side { return this.sideVote >= 0 ? 'right' : 'left'; }

  reset(): void {
    this.pinchSince = null;
    this.poseChangedAt = 0;
    this.settling = null;
    this.trail = [];
    this.sideVote = 0;
    this._pinched = false;
    this._gesture = 'none';
  }
}