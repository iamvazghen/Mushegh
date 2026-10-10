import { describe, expect, it } from 'vitest';
import { PointerSynth } from './pointerSynth';
import type { Decision } from './handLogic';

/** A stand-in element that records what was dispatched at it. */
class FakeElement {
  readonly seen: string[] = [];
  constructor(readonly name: string) {}
  dispatchEvent(e: Event): boolean {
    this.seen.push((e as unknown as { type: string }).type);
    return true;
  }
}

class FakePointerEvent {
  readonly type: string;
  readonly x: number;
  readonly y: number;
  readonly pointerId: number;
  readonly buttons: number;
  readonly pressure: number;
  constructor(type: string, init: Record<string, unknown>) {
    this.type = type;
    this.x = init.clientX as number;
    this.y = init.clientY as number;
    this.pointerId = init.pointerId as number;
    this.buttons = init.buttons as number;
    this.pressure = init.pressure as number;
  }
}
class FakeMouseEvent {
  readonly type: string;
  constructor(type: string) {
    this.type = type;
  }
}

/** Two named regions of the screen, so hit-testing is meaningful. */
function world() {
  const header = new FakeElement('header');
  const body = new FakeElement('body');
  const anywhere = new FakeElement('anywhere');
  const at = (x: number, y: number): FakeElement => (y < 100 ? header : y > 400 ? anywhere : body);
  return { header, body, anywhere, at };
}

function synth(w: ReturnType<typeof world>) {
  return new PointerSynth({ elementFromPoint: (x, y) => w.at(x, y) }, {
    PointerEvent: FakePointerEvent as unknown as new (t: string, i: Record<string, unknown>) => Event,
    MouseEvent: FakeMouseEvent as unknown as new (t: string, i: Record<string, unknown>) => Event,
  });
}

const frame = (over: Partial<Decision> & Pick<Decision, 'x' | 'y' | 'pinched'>): Decision => ({
  gesture: over.pinched ? 'pinch' : 'point',
  closeness: 0,
  fingers: { thumb: false, index: true, middle: false, ring: false, pinky: false },
  span: 100,
  aimX: over.x,
  aimY: over.y,
  ...over,
});

describe('pointer synthesis', () => {
  it('moves the pointer over whatever is under the cursor without pressing', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 200, pinched: false }), 0);
    expect(w.body.seen).toEqual(['pointermove']);
    expect(p.holding(0)).toBe(false);
  });

  it('presses and releases the element that took it', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: true }), 0);
    expect(w.header.seen).toEqual(['pointerdown']);
    expect(p.holding(0)).toBe(true);
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: false }), 0);
    expect(w.header.seen).toEqual(['pointerdown', 'pointerup', 'click']);
  });

  it('aims the press from before the fingers closed, not from the closed position', () => {
    // The regression this exists for: hit-testing the live point put the press
    // below the thing you were pointing at, because a pinch travels.
    const w = world();
    const p = synth(w);
    // Cursor at the header when the fingers start closing, but by the time the
    // pinch confirms the smoothed cursor has drifted well down the page.
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: true }), 0);
    expect(w.header.seen).toEqual(['pointerdown']);
    expect(w.body.seen).toEqual([]);
  });

  it('keeps dragging on the captured element after the cursor slides off it', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: true }), 0);
    p.emit(frame({ x: 50, y: 200, pinched: true }), 0);       // now over the body
    expect(w.header.seen).toEqual(['pointerdown', 'pointermove']);
    expect(w.body.seen).toEqual([]);
  });

  it('treats a press that travelled as a drag and does not also click', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: true }), 0);
    p.emit(frame({ x: 50, y: 300, pinched: true }), 0);
    p.emit(frame({ x: 50, y: 300, pinched: false }), 0);
    // A click here would activate the very control the drag just moved.
    expect(w.header.seen).toEqual(['pointerdown', 'pointermove', 'pointerup']);
    expect(w.header.seen).not.toContain('click');
  });

  it('does not click when the release lands on a different element', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: true }), 0);
    p.emit(frame({ x: 50, y: 300, pinched: false }), 0);      // under the slop, but elsewhere
    expect(w.header.seen).toEqual(['pointerdown', 'pointerup']);
  });

  it('releases an orphan press instead of leaving a control stuck', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: true }), 0);
    expect(p.release(0, { x: 50, y: 50 })).toBe(true);
    expect(w.header.seen).toEqual(['pointerdown', 'pointerup', 'pointercancel']);
    expect(p.holding(0)).toBe(false);
  });

  it('reports nothing to release when no press was held', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 200, pinched: false }), 0);
    expect(p.release(0, { x: 50, y: 200 })).toBe(false);
  });

  it('keeps two hands entirely independent', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 50, y: 50, aimX: 50, aimY: 50, pinched: true }), 0);
    p.emit(frame({ x: 400, y: 500, pinched: false }), 1);
    expect(p.holding(0)).toBe(true);
    expect(p.holding(1)).toBe(false);
    p.release(0, { x: 50, y: 50 });
    expect(p.holding(1)).toBe(false);
  });
});

describe('synthetic pointer ids', () => {
  it('marks only the first hand as the primary pointer and gives each a distinct id', () => {
    const captured: Record<string, unknown>[] = [];
    class Recording extends FakePointerEvent {
      constructor(type: string, init: Record<string, unknown>) {
        super(type, init);
        captured.push({ type, isPrimary: init.isPrimary, pointerId: init.pointerId });
      }
    }
    const w = world();
    const p = new PointerSynth({ elementFromPoint: (x, y) => w.at(x, y) }, {
      PointerEvent: Recording as unknown as new (t: string, i: Record<string, unknown>) => Event,
      MouseEvent: FakeMouseEvent as unknown as new (t: string, i: Record<string, unknown>) => Event,
    });
    p.emit(frame({ x: 10, y: 200, pinched: false }), 0);
    p.emit(frame({ x: 20, y: 200, pinched: false }), 1);
    expect(captured.map(c => c.isPrimary)).toEqual([true, false]);
    expect(captured.map(c => c.pointerId)).toEqual([9000, 9001]);
  });

  it('reports pressure only while a press is actually held', () => {
    const w = world();
    const p = synth(w);
    p.emit(frame({ x: 10, y: 200, pinched: false }), 0);
    p.emit(frame({ x: 10, y: 50, aimX: 10, aimY: 50, pinched: true }), 0);
    p.emit(frame({ x: 10, y: 50, pinched: false }), 0);
    const header = w.header.seen;
    expect(header).toEqual(['pointerdown', 'pointerup', 'click']);
  });
});