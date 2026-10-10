import { describe, expect, it } from 'vitest';
import {
  AIM_LAG_MS, BONES, GESTURE_HOLD_MS, HandDecision, INDEX_TIP, JOINT_COUNT, PINCH_OFF, PINCH_ON,
  POSE_SETTLE_MS, WRIST, classify, dist, handSpan, isExtended, pinchGap, readFingers,
  type Finger, type Landmark,
} from './handLogic';

/**
 * Synthetic hands in realistic proportions: wrist at the origin, the middle
 * knuckle one span above it, and fingers pointing away from the wrist. Curling
 * a finger brings its tip back toward the palm but never onto its neighbour —
 * a fixture where curled fingertips coincide reports every hand as pinching,
 * which is exactly the mistake this layout exists to avoid.
 */
const SPAN = 100;

/** MCP / PIP / TIP for each finger, laid out as an open hand above the wrist. */
const CHAINS: Record<Finger, { mcp: Landmark; pip: Landmark; open: Landmark; closed: Landmark }> = {
  thumb: { mcp: { x: -60, y: -55 }, pip: { x: -80, y: -85 }, open: { x: -190, y: -55 }, closed: { x: -60, y: -50 } },
  index: { mcp: { x: -45, y: -90 }, pip: { x: -48, y: -140 }, open: { x: -50, y: -200 }, closed: { x: -47, y: -120 } },
  middle: { mcp: { x: 0, y: -100 }, pip: { x: 0, y: -150 }, open: { x: 0, y: -210 }, closed: { x: 0, y: -130 } },
  ring: { mcp: { x: 45, y: -92 }, pip: { x: 48, y: -142 }, open: { x: 50, y: -202 }, closed: { x: 47, y: -122 } },
  pinky: { mcp: { x: 85, y: -78 }, pip: { x: 87, y: -118 }, open: { x: 88, y: -172 }, closed: { x: 86, y: -102 } },
};

const CHAIN_LANDMARKS: Record<Finger, [number, number, number]> = {
  thumb: [1, 2, 4], index: [5, 6, 8], middle: [9, 10, 12], ring: [13, 14, 16], pinky: [17, 18, 20],
};

function hand(extended: Record<Finger, boolean>): Landmark[] {
  const marks: Landmark[] = Array.from({ length: JOINT_COUNT }, () => ({ x: 0, y: 0 }));
  marks[WRIST] = { x: 0, y: 0 };
  for (const [finger, [mcp, pip, tip]] of Object.entries(CHAIN_LANDMARKS) as [Finger, number[]][]) {
    const c = CHAINS[finger];
    marks[mcp] = c.mcp;
    marks[pip] = c.pip;
    marks[tip] = extended[finger] ? c.open : c.closed;
  }
  return marks;
}

/** A hand whose thumb tip has been brought onto the index tip. */
function pinching(extended: Record<Finger, boolean>): Landmark[] {
  const marks = hand(extended);
  marks[4] = { ...marks[8] };
  return marks;
}

const ALL_DOWN: Record<Finger, boolean> = { thumb: false, index: false, middle: false, ring: false, pinky: false };
const withFingers = (up: Finger[]): Record<Finger, boolean> =>
  ({ ...ALL_DOWN, ...Object.fromEntries(up.map(f => [f, true])) });

const cursor = (x: number, y: number) => ({ x, y });

/**
 * Hold one pose long enough to be believed and to clear the settling window.
 *
 * A freshly tracked hand is settling for POSE_SETTLE_MS, and a pose has to hold
 * GESTURE_HOLD_MS before it counts — so no pinch can fire in the first ~220ms of
 * a hand's life. That is deliberate (a hand appearing mid-transition should not
 * fire), and every pinch test below has to account for it rather than work
 * around it by loosening the assertion.
 */
function settle(d: HandDecision, marks: Landmark[], from: number, to: number, at = cursor(500, 500)): void {
  for (let t = from; t <= to; t += 16) d.update(marks, at, t, 'right');
}

describe('anatomy', () => {
  it('covers every joint exactly once across the bone list', () => {
    const seen = new Set<number>();
    for (const [a, b] of BONES) { seen.add(a); seen.add(b); }
    expect([...seen].sort((a, b) => a - b)).toEqual(Array.from({ length: JOINT_COUNT }, (_, i) => i));
  });

  it('builds no bone that points at itself', () => {
    expect(BONES.every(([a, b]) => a !== b)).toBe(true);
  });

  it('puts the index tip where the cursor is meant to come from', () => {
    const m = hand(withFingers(['index']));
    expect(m[INDEX_TIP]).toBeDefined();
    expect(isExtended(m, INDEX_TIP, 6)).toBe(true);
  });
});

describe('span-relative pinch measurement', () => {
  it('reads the same pinch at two different apparent hand sizes', () => {
    const pose = hand(ALL_DOWN);
    const near = pose.map(m => ({ x: m.x * 2, y: m.y * 2 }));
    const far = pose.map(m => ({ x: m.x / 2, y: m.y / 2 }));
    expect(pinchGap(near, handSpan(near))).toBeCloseTo(pinchGap(far, handSpan(far)), 6);
  });

  it('leaves a relaxed hand well outside the threshold band', () => {
    const open = hand(ALL_DOWN);
    expect(pinchGap(open, handSpan(open))).toBeGreaterThan(PINCH_OFF);
  });

  it('reads zero once the fingers actually meet', () => {
    const met = pinching(ALL_DOWN);
    expect(pinchGap(met, handSpan(met))).toBe(0);
  });
});

describe('finger extension is rotation-invariant', () => {
  it('still reads the same after the hand is rotated a quarter turn', () => {
    const m = hand(withFingers(['index', 'middle']));
    const rotate = (pts: Landmark[]): Landmark[] => {
      const c = pts[WRIST];
      return pts.map(p => {
        const dx = p.x - c.x, dy = p.y - c.y;
        return { x: c.x + dy, y: c.y + dx };                // 90 degrees
      });
    };
    const r = rotate(m);
    expect(readFingers(m, handSpan(m))).toEqual(readFingers(r, handSpan(r)));
  });

  it('reads each finger from its own tip, not its middle joint', () => {
    // Regression guard: an off-by-one here reads DIP as the tip and makes a
    // curled ring report as extended.
    const closed = readFingers(hand(ALL_DOWN), SPAN);
    const extended = readFingers(hand(withFingers(['ring'])), SPAN);
    expect(closed.ring).toBe(false);
    expect(extended.ring).toBe(true);
  });
});

describe('pose classifier', () => {
  it('separates aim from sizing, which differ only by the thumb', () => {
    const point = readFingers(hand(withFingers(['index'])), SPAN);
    const frame = readFingers(hand(withFingers(['index', 'thumb'])), SPAN);
    expect(classify(point, false)).toBe('point');
    expect(classify(frame, false)).toBe('frame');
  });

  it('recognises the remaining named poses', () => {
    const f = (up: Finger[]) => readFingers(hand(withFingers(up)), SPAN);
    expect(classify(f(['index', 'middle']), false)).toBe('peace');
    expect(classify(f(['index', 'middle', 'ring', 'pinky']), false)).toBe('open');
    expect(classify(f([]), false)).toBe('fist');
  });

  it('lets a pinch override whatever the fingers say', () => {
    expect(classify(readFingers(hand(ALL_DOWN), SPAN), true)).toBe('pinch');
  });
});

describe('the three pinch gates', () => {
  const START = 400; // past both the pose hold and the settling window

  it('does not press on a pinch that flickers past the confirm window', () => {
    const d = new HandDecision();
    settle(d, hand(ALL_DOWN), 0, START);
    const met = pinching(ALL_DOWN);
    // Four frames of contact — 64ms, just under PINCH_CONFIRM_MS.
    const frames = [0, 16, 32, 48].map(o => d.update(met, cursor(500, 500), START + o, 'right'));
    expect(frames.every(f => !f.pinched)).toBe(true);
  });

  it('presses once a pinch is held past the confirm window', () => {
    const d = new HandDecision();
    settle(d, hand(ALL_DOWN), 0, START);
    const met = pinching(ALL_DOWN);
    const frames = [0, 16, 32, 64, 80, 96].map(o => d.update(met, cursor(500, 500), START + o, 'right'));
    expect(frames.at(-1)!.pinched).toBe(true);
  });

  it('will not press during the settling window after a pose change', () => {
    const d = new HandDecision();
    settle(d, hand(ALL_DOWN), 0, START);
    // A deliberate pose change restarts the settling clock, so a pinch arriving
    // straight afterwards is held back even though it clears the confirm window.
    const open = d.update(hand(withFingers(['index'])), cursor(500, 500), START + 16, 'right');
    expect(open.gesture).toBe('fist');                     // still the held pose
    const met = pinching(ALL_DOWN);
    const during = d.update(met, cursor(500, 500), START + 32, 'right');
    expect(during.pinched).toBe(false);
  });

  it('keeps a press alive across a release through the hysteresis gap', () => {
    const d = new HandDecision();
    settle(d, hand(ALL_DOWN), 0, START);
    const met = pinching(ALL_DOWN);
    for (let o = 0; o <= 80; o += 16) d.update(met, cursor(500, 500), START + o, 'right');
    expect(d.pinched).toBe(true);
    // Thumb parked between the two thresholds: a release in name only.
    const gapped = hand(ALL_DOWN);
    gapped[4] = { x: gapped[8].x + ((PINCH_ON + PINCH_OFF) / 2) * handSpan(gapped), y: gapped[8].y };
    expect(d.update(gapped, cursor(500, 500), START + 96, 'right').pinched).toBe(true);
  });

  it('reports closeness across the threshold band', () => {
    const d = new HandDecision();
    expect(d.update(hand(ALL_DOWN), cursor(0, 0), 0, 'right').closeness).toBe(0);
    expect(d.update(pinching(ALL_DOWN), cursor(0, 0), 16, 'right').closeness).toBe(1);
  });
});

describe('aim trail', () => {
  it('aims a press at where the cursor was, not where the fingers closed', () => {
    const d = new HandDecision();
    const marks = hand(ALL_DOWN);
    // Walk the cursor right at 1px per millisecond, so AIM_LAG_MS of history is
    // exactly AIM_LAG_MS pixels behind.
    for (let t = 0; t <= 400; t += 16) d.update(marks, cursor(100 + t, 500), t, 'right');
    const open = d.update(marks, cursor(500, 500), 416, 'right');
    // The trail is sampled at 16ms, so the aim is one frame either side of the
    // nominal lag; anything near AIM_LAG_MS proves the press is aimed backwards,
    // and anything near 0 would mean it is aimed at the closed fingertips.
    expect(500 - open.aimX).toBeGreaterThan(AIM_LAG_MS - 32);
    expect(500 - open.aimX).toBeLessThan(AIM_LAG_MS + 16);
  });

  it('holds the aim still while pinched so a press cannot drift', () => {
    const d = new HandDecision();
    const met = pinching(ALL_DOWN);
    for (let t = 0; t <= 400; t += 16) d.update(met, cursor(300, 300), t, 'right');
    const first = d.update(met, cursor(900, 900), 416, 'right');
    const second = d.update(met, cursor(1200, 1200), 432, 'right');
    expect(second.aimX).toBe(first.aimX);
    expect(second.aimY).toBe(first.aimY);
  });
});

describe('handedness vote', () => {
  it('does not flip on a single disagreeing frame', () => {
    const d = new HandDecision();
    const marks = hand(ALL_DOWN);
    for (let t = 0; t <= 300; t += 16) d.update(marks, cursor(0, 0), t, 'right');
    d.update(marks, cursor(0, 0), 316, 'left');
    expect(d.handedness).toBe('right');
  });

  it('follows a genuine change once the vote turns', () => {
    const d = new HandDecision();
    const marks = hand(ALL_DOWN);
    let t = 0;
    for (; t <= 300; t += 16) d.update(marks, cursor(0, 0), t, 'right');
    for (; t <= 700; t += 16) d.update(marks, cursor(0, 0), t, 'left');
    expect(d.handedness).toBe('left');
  });
});

describe('isolation between hands', () => {
  it('keeps two hands in separate states', () => {
    const a = new HandDecision();
    const b = new HandDecision();
    settle(a, hand(ALL_DOWN), 0, 400);
    const met = pinching(ALL_DOWN);
    for (let t = 416; t <= 496; t += 16) a.update(met, cursor(0, 0), t, 'right');
    expect(b.update(hand(ALL_DOWN), cursor(0, 0), 512, 'right').pinched).toBe(false);
    expect(a.pinched).toBe(true);
  });

  it('will not fire a pinch before the pose it interrupts has been believed', () => {
    // The three gates compound: a fresh hand spends GESTURE_HOLD_MS before its
    // pose counts, and only then does the settling window start. A pinch held
    // from the first frame therefore cannot press until past both — which is
    // why a hand appearing mid-transition cannot grab something.
    const d = new HandDecision();
    const met = pinching(ALL_DOWN);
    const boundary = GESTURE_HOLD_MS + POSE_SETTLE_MS;
    for (let t = 0; t <= boundary; t += 16) {
      expect(d.update(met, cursor(0, 0), t, 'right').pinched).toBe(false);
    }
    // The settling test is strictly "more than", so the first frame past the
    // boundary is the one that presses.
    expect(d.update(met, cursor(0, 0), boundary + 16, 'right').pinched).toBe(true);
  });

  it('returns to a clean slate on reset', () => {
    const d = new HandDecision();
    const met = pinching(ALL_DOWN);
    for (let t = 0; t <= 400; t += 16) d.update(met, cursor(0, 0), t, 'right');
    d.reset();
    expect(d.pinched).toBe(false);
    expect(d.gesture).toBe('none');
    expect(d.update(hand(ALL_DOWN), cursor(0, 0), 500, 'left').pinched).toBe(false);
  });
});

describe('measurement sanity', () => {
  it('never reports a zero span, which would divide every threshold', () => {
    const degenerate = Array.from({ length: JOINT_COUNT }, () => ({ x: 5, y: 5 }));
    expect(handSpan(degenerate)).toBeGreaterThan(0);
  });

  it('measures distance the ordinary way', () => {
    expect(dist({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5);
  });
});