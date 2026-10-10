import { describe, expect, it } from 'vitest';
import { DEFAULT_SHEET, sheetLayout, sheetPlan } from './camera';

const NOW = 10_000;

/** One frame every `step` ms, ending at `now`. */
function burst(count: number, step: number, now = NOW) {
  return Array.from({ length: count }, (_, i) => ({ at: now - (count - 1 - i) * step }));
}

describe('sheet layout', () => {
  it('multiplies the grid out to a single image', () => {
    const l = sheetLayout(DEFAULT_SHEET);
    expect(l.width).toBe(6 * 426);
    expect(l.height).toBe(10 * 240);
    expect(l.capacity).toBe(60);
  });

  it('never holds fewer frames than the window allows', () => {
    // windowMs/fps is exactly 60 here; a floor() would silently drop one.
    expect(DEFAULT_SHEET.windowMs / 1000 * DEFAULT_SHEET.fps).toBe(60);
    expect(sheetLayout(DEFAULT_SHEET).capacity).toBe(60);
  });
});

describe('sheet planning', () => {
  it('puts frames in time order regardless of the order they arrived', () => {
    const plan = sheetPlan([{ at: 9_900 }, { at: 9_800 }, { at: 9_700 }], NOW);
    expect(plan.map(s => s.frame.at)).toEqual([9_700, 9_800, 9_900]);
  });

  it('drops anything older than the window instead of clamping it forward', () => {
    const far = 500_000;
    const plan = sheetPlan([{ at: 1_000 }, { at: far - 200 }], far);
    expect(plan.map(s => s.frame.at)).toEqual([far - 200]);
  });

  it('keeps a frame sitting exactly on the window edge', () => {
    const plan = sheetPlan([{ at: NOW - DEFAULT_SHEET.windowMs }], NOW);
    expect(plan).toHaveLength(1);
  });

  it('keeps at most a full grid and discards the oldest first', () => {
    const plan = sheetPlan(burst(80, 100), NOW);
    expect(plan).toHaveLength(60);
    expect(plan[0].frame.at).toBe(NOW - 59 * 100);
    expect(plan.at(-1)!.frame.at).toBe(NOW);
  });

  it('never overwrites a cell', () => {
    const plan = sheetPlan(burst(40, 100), NOW);
    expect(new Set(plan.map(s => `${s.row},${s.col}`)).size).toBe(plan.length);
  });

  it('keeps every cell inside the grid', () => {
    for (const s of sheetPlan(burst(60, 100), NOW)) {
      expect(s.row).toBeGreaterThanOrEqual(0);
      expect(s.col).toBeGreaterThanOrEqual(0);
      expect(s.row).toBeLessThan(DEFAULT_SHEET.rows);
      expect(s.col).toBeLessThan(DEFAULT_SHEET.cols);
    }
  });

  it('reports each frame as a duration old, never negative', () => {
    const plan = sheetPlan(burst(3, 200), NOW);
    expect(plan.map(s => s.ageMs)).toEqual([400, 200, 0]);
    expect(plan.every(s => s.ageMs >= 0)).toBe(true);
  });

  it('right-aligns the window so the newest frame always sits in the last cell', () => {
    // Consistency beats compactness: the cell holding "now" must not move when
    // the sample rate wobbles.
    expect([sheetPlan([{ at: NOW }], NOW)[0].row, sheetPlan([{ at: NOW }], NOW)[0].col])
      .toEqual([DEFAULT_SHEET.rows - 1, DEFAULT_SHEET.cols - 1]);
    const partial = sheetPlan(burst(7, 100), NOW);
    expect(partial[0].row * DEFAULT_SHEET.cols + partial[0].col).toBe(60 - 7);
    expect(partial.at(-1)!.row).toBe(DEFAULT_SHEET.rows - 1);
    expect(partial.at(-1)!.col).toBe(DEFAULT_SHEET.cols - 1);
  });

  it('fills a full grid from the very first cell', () => {
    const full = sheetPlan(burst(60, 100), NOW);
    expect([full[0].row, full[0].col]).toEqual([0, 0]);
  });

  it('yields nothing rather than a blank grid for an empty window', () => {
    expect(sheetPlan([], NOW)).toEqual([]);
  });
});