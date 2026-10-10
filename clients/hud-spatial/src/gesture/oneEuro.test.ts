import { describe, expect, it } from 'vitest';
import { OneEuro, OneEuroPoint } from './oneEuro';

const FRAME = 1 / 60;

/** Deterministic pseudo-noise — a fixed-seed jitter signal beats Math.random for a contract test.
 *  xorshift32, kept in 32 bits with |0 / >>>0 so it does not leave the integer range. */
function jitter(centre: number, amplitude: number, frames: number): number[] {
  let seed = 0x9e3779b9;
  const next = (): number => {
    seed ^= seed << 13; seed >>>= 0;
    seed ^= seed >>> 17;
    seed ^= seed << 5; seed >>>= 0;
    return seed / 0x100000000;
  };
  return Array.from({ length: frames }, () => centre + (next() * 2 - 1) * amplitude);
}

const spread = (xs: number[]): number => Math.max(...xs) - Math.min(...xs);

describe('OneEuro', () => {
  it('passes the first sample through untouched', () => {
    expect(new OneEuro().filter(42, 0)).toBe(42);
  });

  it('collapses jitter on a resting signal', () => {
    // beta=0 pins the cutoff, which is the fixed-low-pass configuration: the
    // aggressive case, and the yardstick the adaptive case is measured against.
    // Measured at 4.0x suppression for this signal.
    const input = jitter(300, 4, 240);
    const f = new OneEuro(1.1, 0);
    const out = input.map((v, i) => f.filter(v, i * FRAME));
    expect(spread(input) / spread(out.slice(60))).toBeGreaterThan(3.5);
  });

  it('keeps a still signal at rest — smoothing must not drift the centre', () => {
    const f = new OneEuro(1.1, 0);
    const out = jitter(300, 4, 240).map((v, i) => f.filter(v, i * FRAME));
    expect(Math.abs(out[out.length - 1] - 300)).toBeLessThan(0.5);
  });

  it('spends some jitter suppression to buy responsiveness, and that is the trade', () => {
    // Raising beta opens the cutoff with speed, so a resting hand is smoothed
    // slightly less (4.0x -> 3.2x here). That is the cost side of the same
    // mechanism the next test shows the benefit of; both numbers are asserted so
    // a future tuning change cannot quietly make this one-sided.
    const input = jitter(300, 4, 240);
    const ratio = (beta: number): number => {
      const f = new OneEuro(1.1, beta);
      const out = input.map((v, i) => f.filter(v, i * FRAME));
      return spread(input) / spread(out.slice(60));
    };
    expect(ratio(0)).toBeGreaterThan(ratio(0.012));
    expect(ratio(0.012)).toBeGreaterThan(3);
  });

  it('opens the cutoff with speed, so a fast ramp is tracked rather than trailed', () => {
    // The property that distinguishes a 1€ filter from the fixed low-pass above:
    // same minCutoff, and the adaptive one must close most of the remaining gap.
    const target = 290;
    const ramp = (beta: number): number => {
      const f = new OneEuro(1.1, beta);
      let out = 0;
      for (let i = 0; i < 30; i++) out = f.filter(i * 10, i * FRAME);
      return out;
    };
    const fixedError = Math.abs(target - ramp(0));
    const adaptiveError = Math.abs(target - ramp(0.012));
    // Measured: 206.9 vs 282.8 after 30 frames, so 83.1 of error becomes 7.2.
    expect(adaptiveError).toBeLessThan(fixedError / 5);
  });

  it('refuses to snap to a stale frame after a long hidden gap', () => {
    const f = new OneEuro(1.0, 0.0);
    const first = f.filter(0, 0);
    const afterGap = f.filter(100, 10);
    expect(first).toBe(0);
    // dt is clamped to 1/5s, so alpha stays well under 1 and one stale frame
    // cannot become the whole truth.
    expect(afterGap).toBeLessThan(100);
    expect(afterGap).toBeGreaterThan(0);
  });

  it('survives a non-advancing timestamp instead of dividing by zero', () => {
    const f = new OneEuro();
    f.filter(10, 1);
    const out = f.filter(10, 1);
    expect(Number.isFinite(out)).toBe(true);
  });

  it('forgets everything on reset', () => {
    const f = new OneEuro();
    f.filter(500, 0);
    f.reset();
    expect(f.filter(1, 1)).toBe(1);
  });
});

describe('OneEuroPoint', () => {
  it('filters each axis independently', () => {
    const p = new OneEuroPoint(1.1, 0.012);
    p.filter(0, 0, 0);
    const out = p.filter(100, 0, FRAME);
    expect(out.x).toBeGreaterThan(0);
    expect(out.y).toBe(0);
  });

  it('resets both axes together', () => {
    const p = new OneEuroPoint(1.1, 0.012);
    p.filter(10, 10, 0);
    p.reset();
    expect(p.filter(3, 4, 1)).toEqual({ x: 3, y: 4 });
  });
});