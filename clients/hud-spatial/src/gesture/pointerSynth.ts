/**
 * Turning a hand into ordinary pointer events.
 *
 * The architectural decision is that nothing here knows what a canvas is. No
 * hit-testing of tiles, no calls to focus or resize, no knowledge of the header
 * you drag by. A hand becomes a position and a press, and the events are
 * dispatched as `PointerEvent`s â€” so every interaction the mouse already has in
 * this client works with a hand for free, and anything added later works without
 * being taught that hands exist.
 *
 * Ported from adewaskar/jarvis `src/lib/hands.ts` (MIT, Â© 2026 Aditya
 * Dewaskar). The DOM is injected rather than reached for, which is what makes
 * the press state machine â€” aim latching, drag-vs-click, orphan release â€”
 * testable without a browser.
 */

import { CLICK_SLOP, type Decision } from './handLogic';

/**
 * The subset of `Element` this module needs â€” just enough to dispatch at.
 * Narrower than `EventTarget` so the press machine can be driven by a test
 * double without implementing the full DOM listener surface.
 */
export interface DispatchTarget {
  dispatchEvent(event: Event): boolean;
}

/** The subset of `document` this module needs. */
export interface HitTest {
  elementFromPoint(x: number, y: number): DispatchTarget | null;
}

export interface EventFactory {
  PointerEvent: new (type: string, init: Record<string, unknown>) => Event;
  MouseEvent: new (type: string, init: Record<string, unknown>) => Event;
}

/** Well clear of any id the browser might issue for a real pointer. */
const POINTER_ID_BASE = 9000;

type Press = {
  /** What took the press, so the release and any click agree on their target. */
  captured: DispatchTarget | null;
  wasPinched: boolean;
  /** Where the press began â€” for telling a click from a drag. */
  downX: number;
  downY: number;
};

export class PointerSynth {
  private presses = new Map<number, Press>();

  constructor(
    private hit: HitTest,
    private events: EventFactory,
  ) {}

  private fire(el: DispatchTarget | null, type: string, id: number, pressed: boolean, at: { x: number; y: number }): void {
    if (!el) return;
    el.dispatchEvent(new this.events.PointerEvent(type, {
      bubbles: true,
      cancelable: true,
      composed: true,
      clientX: at.x,
      clientY: at.y,
      pointerId: POINTER_ID_BASE + id,
      pointerType: 'touch',
      isPrimary: id === 0,
      button: 0,
      buttons: pressed ? 1 : 0,
      width: 1,
      height: 1,
      pressure: pressed ? 0.5 : 0,
    }));
  }

  /** Drive one hand's pointer state for a frame. */
  emit(d: Decision, id: number): void {
    let p = this.presses.get(id);
    if (!p) {
      p = { captured: null, wasPinched: false, downX: d.x, downY: d.y };
      this.presses.set(id, p);
    }

    const over = this.hit.elementFromPoint(d.x, d.y);

    if (d.pinched && !p.wasPinched) {
      /**
       * Press, aimed from where the hand was before the fingers closed.
       *
       * The fingertip travels several centimetres on its way to meeting the
       * thumb â€” that is what a pinch is â€” so the position at the instant the
       * press fires is not the position you were aiming from. Hit-testing the
       * live point made a press land below whatever you had pointed at.
       */
      const aim = { x: d.aimX, y: d.aimY };
      const target = this.hit.elementFromPoint(aim.x, aim.y) ?? over;
      p.captured = target;
      p.downX = aim.x;
      p.downY = aim.y;
      this.fire(target, 'pointerdown', id, true, aim);
    } else if (!d.pinched && p.wasPinched) {
      const target = p.captured ?? over;
      this.fire(target, 'pointerup', id, false, { x: d.x, y: d.y });
      // Only a press that ends roughly where it began is a click. One that
      // travelled was a drag, and a drag that also clicked would activate the
      // very control it had just finished moving.
      const travelled = Math.hypot(d.x - p.downX, d.y - p.downY);
      if (target && travelled < CLICK_SLOP && target === over) {
        target.dispatchEvent(new this.events.MouseEvent('click', {
          bubbles: true,
          cancelable: true,
          composed: true,
          clientX: d.x,
          clientY: d.y,
        }));
      }
      p.captured = null;
    } else {
      // While pressed, moves go to whatever took the press, so a drag survives
      // the cursor sliding off the header it grabbed.
      this.fire(d.pinched ? (p.captured ?? over) : over, 'pointermove', id, d.pinched, { x: d.x, y: d.y });
    }

    p.wasPinched = d.pinched;
  }

  /**
   * Let go of anything still held.
   *
   * A press that outlives its hand leaves whatever was being dragged stuck to a
   * cursor that no longer exists â€” which is the symptom of the identity bug
   * this module's caller has to avoid, so the cleanup has to be unconditional.
   */
  release(id: number, at: { x: number; y: number }): boolean {
    const p = this.presses.get(id);
    if (!p?.wasPinched) return false;
    this.fire(p.captured, 'pointerup', id, false, at);
    this.fire(p.captured, 'pointercancel', id, false, at);
    p.wasPinched = false;
    p.captured = null;
    return true;
  }

  /** True while a hand is holding something. */
  holding(id: number): boolean {
    return this.presses.get(id)?.wasPinched === true;
  }

  reset(): void {
    this.presses.clear();
  }
}

/**
 * setPointerCapture, made safe for pointers that do not exist.
 *
 * A synthetic PointerEvent carries a pointerId the browser has never issued, so
 * any element that calls setPointerCapture with it throws NotFoundError and the
 * interaction dies at its first move. That call is made by react-grid-layout's
 * drag and by resize grips, both of which we very much want a hand to be able
 * to use.
 *
 * Capture is an optimisation, not a requirement: it exists so a drag keeps
 * receiving events after the cursor leaves the element. These events are aimed
 * by hit-testing every frame and routed to the element that took the press, so
 * they land correctly whether or not capture was granted.
 */
export function patchPointerCapture(): boolean {
  const scope = globalThis as unknown as { Element?: { prototype: Record<string, unknown> } };
  if (!scope.Element?.prototype) return false;
  const p = scope.Element.prototype;
  if (p.__handSafe) return true;
  const capture = p.setPointerCapture as ((this: unknown, id: number) => void) | undefined;
  const release = p.releasePointerCapture as ((this: unknown, id: number) => void) | undefined;
  if (typeof capture !== 'function' || typeof release !== 'function') return false;
  p.setPointerCapture = function (id: number) {
    try { return capture.call(this, id); } catch { /* a synthetic pointer */ }
  };
  p.releasePointerCapture = function (id: number) {
    try { return release.call(this, id); } catch { /* as above */ }
  };
  p.__handSafe = true;
  return true;
}