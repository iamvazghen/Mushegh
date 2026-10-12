import { describe, expect, it } from 'vitest';
import { HandTracker, type Frame, type HandSource, type TrackerStatus } from './tracker';
import type { DispatchTarget } from './pointerSynth';
import { JOINT_COUNT, WRIST, type Landmark, type Side } from './handLogic';

/** Records what a synthetic world dispatches, per element. */
class El implements DispatchTarget {
  readonly seen: string[] = [];
  constructor(readonly name: string) {}
  dispatchEvent(e: Event): boolean {
    this.seen.push((e as unknown as { type: string }).type);
    return true;
  }
}

class FakePointerEvent {
  readonly type: string;
  constructor(type: string) { this.type = type; }
}
class FakeMouseEvent {
  readonly type: string;
  constructor(type: string) { this.type = type; }
}

/** A hand source a test drives by hand, with no camera behind it. */
class ManualSource implements HandSource {
  private cb: ((f: Frame) => void) | null = null;
  closed = 0;
  onFrame(cb: (f: Frame) => void): void { this.cb = cb; }
  close(): void { this.closed++; this.cb = null; }
  emit(f: Frame): void { this.cb?.(f); }
}

/**
 * One hand in normalised landmark space. `x`/`y` place the wrist; the rest are
 * laid out so a pinch reads as a pinch.
 */
function hand(wristX: number, wristY: number, opts: { pinch?: boolean; side?: Side } = {}): Landmark[] {
  const marks: Landmark[] = Array.from({ length: JOINT_COUNT }, () => ({ x: 0, y: 0 }));
  marks[WRIST] = { x: wristX, y: wristY };
  marks[9] = { x: wristX, y: wristY - 0.1 };               // MIDDLE_MCP
  marks[8] = { x: wristX - 0.05, y: wristY - 0.2 };         // INDEX_TIP
  marks[4] = opts.pinch ? marks[8] : { x: wristX - 0.15, y: wristY + 0.05 };
  return marks;
}

function world() {
  const left = new El('left');
  const right = new El('right');
  return {
    left, right,
    hit: { elementFromPoint: (x: number) => (x < 400 ? left : right) },
  };
}

function tracker(over: { viewport?: () => { w: number; h: number } } = {}) {
  return makeEnv(over);
}

function makeEnv(over: { viewport?: () => { w: number; h: number } } = {}) {
  const w = world();
  const source = new ManualSource();
  const statuses: TrackerStatus[] = [];
  const t = new HandTracker({
    source,
    hit: w.hit,
    events: {
      PointerEvent: FakePointerEvent as unknown as new (a: string, b: Record<string, unknown>) => Event,
      MouseEvent: FakeMouseEvent as unknown as new (a: string, b: Record<string, unknown>) => Event,
    },
    viewport: over.viewport ?? (() => ({ w: 1000, h: 1000 })),
    camera: { hold: async () => undefined, release: () => undefined },
    onStatus: (s) => statuses.push(s),
  });
  return { t, w, source, statuses };
}

/** Drive a hand until the pinch gates have all passed. */
function frames(from: number, count: number, step = 16): number[] {
  return Array.from({ length: count }, (_, i) => from + i * step);
}

describe('tracker identity', () => {
  it('keeps one hand in one slot while its handedness label flips', () => {
    // The bug this guards: a single mislabelled frame moved the hand to the other
    // slot, dropped the old one, fired pointercancel and ended the drag.
    const { t } = tracker();
    t.ingest({ landmarks: [hand(0.2, 0.5, { side: 'right' })], handedness: ['right'], at: 0 });
    const before = t.status.hands;
    for (const at of frames(16, 12)) {
      t.ingest({ landmarks: [hand(0.2, 0.5, { side: 'right' })], handedness: ['right'], at });
    }
    expect(before).toBe(1);
    // One bad frame naming it left-handed must not create a second hand.
    t.ingest({ landmarks: [hand(0.2, 0.5, { side: 'left' })], handedness: ['left'], at: 240 });
    expect(t.status.hands).toBe(1);
  });

  it('follows a hand that moves across the screen without losing it', () => {
    const { t } = tracker();
    for (const [i, at] of frames(0, 20).entries()) {
      t.ingest({ landmarks: [hand(0.2 + i * 0.01, 0.5)], handedness: ['right'], at });
    }
    expect(t.status.hands).toBe(1);
  });

  it('tracks two hands as two hands', () => {
    const { t } = tracker();
    t.ingest({ landmarks: [hand(0.2, 0.5, { side: 'right' }), hand(0.8, 0.5, { side: 'left' })], handedness: ['right', 'left'], at: 0 });
    expect(t.status.hands).toBe(2);
  });

  it('forgets a hand that leaves the picture', () => {
    const { t } = tracker();
    t.ingest({ landmarks: [hand(0.2, 0.5)], handedness: ['right'], at: 0 });
    expect(t.status.hands).toBe(1);
    t.ingest({ landmarks: [], handedness: [], at: 16 });
    expect(t.status.hands).toBe(0);
  });

  it('ignores a malformed detection rather than crashing the loop', () => {
    const { t } = tracker();
    t.ingest({ landmarks: [[{ x: 0, y: 0 }]], handedness: ['right'], at: 0 });
    expect(t.status.hands).toBe(0);
  });
});

describe('tracker lifecycle', () => {
  it('reports running and stops cleanly', async () => {
    const { t, source } = tracker();
    await t.start();
    expect(t.status.running).toBe(true);
    t.stop_();
    expect(t.status.running).toBe(false);
    expect(source.closed).toBe(1);
  });

  it('is safe to stop twice and safe to start twice', async () => {
    const { t, source } = tracker();
    await t.start();
    await t.start();
    t.stop_();
    t.stop_();
    expect(source.closed).toBe(1);
  });

  it('releases a held press when the hand disappears', async () => {
    const { t, w } = tracker();
    await t.start();
    // wristX 0.2 mirrors to ~800px, so the press lands on the right-hand element.
    // Pinch down and hold long enough to pass every gate.
    for (const at of frames(0, 30)) {
      t.ingest({ landmarks: [hand(0.2, 0.5, { pinch: true })], handedness: ['right'], at });
    }
    expect(w.right.seen).toContain('pointerdown');
    t.ingest({ landmarks: [], handedness: [], at: 500 });
    // Otherwise the control stays stuck to a cursor that no longer exists.
    expect(w.right.seen).toContain('pointercancel');
  });

  it('stops processing frames after stop', async () => {
    const { t, source } = tracker();
    await t.start();
    t.stop_();
    // A source that keeps emitting after close must not resurrect the tracker.
    const emit = (source as unknown as { emit(f: Frame): void }).emit;
    emit.call(source, { landmarks: [hand(0.5, 0.5)], handedness: ['right'], at: 900 });
    expect(t.status.hands).toBe(0);
  });

  it('reports a camera failure instead of pretending to track', async () => {
    const { t, statuses } = tracker();
    const failing = new HandTracker({
      source: new ManualSource(),
      hit: { elementFromPoint: () => null },
      events: {
        PointerEvent: FakePointerEvent as unknown as new (a: string, b: Record<string, unknown>) => Event,
        MouseEvent: FakeMouseEvent as unknown as new (a: string, b: Record<string, unknown>) => Event,
      },
      viewport: () => ({ w: 1000, h: 1000 }),
      camera: { hold: async () => { throw new Error('Permission denied'); }, release: () => undefined },
      onStatus: (s) => statuses.push(s),
    });
    await failing.start();
    expect(failing.status.running).toBe(false);
    expect(failing.status.lastError).toContain('Permission denied');
    expect(t.status.running).toBe(false);
  });

  it('mirrors the cursor so moving right moves the pointer right', async () => {
    const w = world();
    const source = new ManualSource();
    const t = new HandTracker({
      source,
      hit: w.hit,
      events: {
        PointerEvent: FakePointerEvent as unknown as new (a: string, b: Record<string, unknown>) => Event,
        MouseEvent: FakeMouseEvent as unknown as new (a: string, b: Record<string, unknown>) => Event,
      },
      viewport: () => ({ w: 1000, h: 1000 }),
      camera: { hold: async () => undefined, release: () => undefined },
    });
    await t.start();
    // wristX 0.2 mirrors to 800px — the right-hand element, not the left.
    t.ingest({ landmarks: [hand(0.2, 0.5)], handedness: ['right'], at: 0 });
    expect(w.right.seen.length).toBeGreaterThan(0);
    expect(w.left.seen).toEqual([]);
  });
});