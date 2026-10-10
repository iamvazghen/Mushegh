/**
 * The 1€ filter — Casiez, Roussel & Vogel, CHI 2012.
 *
 * Pointer smoothing has two problems pulling in opposite directions. A hand at
 * rest is not still: landmarks jitter by several pixels a frame, and a cursor
 * that shivers cannot be aimed at a 6-unit tile. A moving hand needs the
 * opposite treatment: smoothing strong enough to kill that jitter also adds lag,
 * and a cursor that trails your finger feels broken in a way jitter does not.
 *
 * A fixed low-pass filter has to pick one of those to be bad at. This picks
 * neither — it estimates the speed of the signal and adapts its own cutoff to
 * it: smooth hard when the hand is nearly still, barely smooth at all when it is
 * moving fast. Jitter is a problem at low speed and lag is a problem at high
 * speed, and this is the filter that knows which one it is currently facing.
 *
 * Two parameters are the entire tuning surface:
 *   minCutoff — the floor. Lower is smoother when still, slower to respond.
 *               Raise it if the cursor feels sluggish; lower it if it shivers.
 *   beta      — how aggressively the cutoff opens up with speed.
 *
 * Ported from adewaskar/jarvis `src/lib/oneEuro.ts` (MIT, © 2026 Aditya
 * Dewaskar). Rewritten to explicit fields because this client compiles with
 * `erasableSyntaxOnly`, which forbids parameter properties.
 */

const TAU = 2 * Math.PI;

function alphaFor(cutoff: number, dt: number): number {
  const tau = 1 / (TAU * cutoff);
  return 1 / (1 + tau / dt);
}

class LowPass {
  private value: number | null = null;

  filter(x: number, alpha: number): number {
    this.value = this.value === null ? x : alpha * x + (1 - alpha) * this.value;
    return this.value;
  }

  get last(): number | null {
    return this.value;
  }

  reset(): void {
    this.value = null;
  }
}

export class OneEuro {
  private x = new LowPass();
  private dx = new LowPass();
  private lastAt: number | null = null;

  private minCutoff: number;
  private beta: number;
  /** Cutoff for the speed estimate itself, which is noisier than the signal. */
  private dCutoff: number;

  constructor(minCutoff = 1.0, beta = 0.0, dCutoff = 1.0) {
    this.minCutoff = minCutoff;
    this.beta = beta;
    this.dCutoff = dCutoff;
  }

  /** @param at timestamp in seconds. */
  filter(x: number, at: number): number {
    if (this.lastAt === null) {
      this.lastAt = at;
      this.dx.filter(0, alphaFor(this.dCutoff, 1 / 60));
      return this.x.filter(x, 1);
    }

    // Guard the sample period. A backgrounded tab returns with a dt of several
    // seconds, which drives alpha to ~1 and lets one stale frame snap the filter
    // to it; a dt of zero divides by nothing at all.
    const dt = Math.min(Math.max(at - this.lastAt, 1 / 240), 1 / 5);
    this.lastAt = at;

    const prev = this.x.last;
    const speed = prev === null ? 0 : (x - prev) / dt;
    const edx = this.dx.filter(speed, alphaFor(this.dCutoff, dt));

    // The whole idea, in one line: the faster the signal moves, the higher the
    // cutoff, and the less it is smoothed.
    const cutoff = this.minCutoff + this.beta * Math.abs(edx);
    return this.x.filter(x, alphaFor(cutoff, dt));
  }

  reset(): void {
    this.x.reset();
    this.dx.reset();
    this.lastAt = null;
  }
}

/** A 1€ filter per axis, for filtering a point. */
export class OneEuroPoint {
  private fx: OneEuro;
  private fy: OneEuro;

  constructor(minCutoff: number, beta: number, dCutoff = 1.0) {
    this.fx = new OneEuro(minCutoff, beta, dCutoff);
    this.fy = new OneEuro(minCutoff, beta, dCutoff);
  }

  filter(x: number, y: number, at: number): { x: number; y: number } {
    return { x: this.fx.filter(x, at), y: this.fy.filter(y, at) };
  }

  reset(): void {
    this.fx.reset();
    this.fy.reset();
  }
}