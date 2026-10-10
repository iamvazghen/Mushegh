/**
 * Camera, shared safely, and the contact sheet built from it.
 *
 * Two things live here because they must agree: a single refcounted capture
 * stream, and the contact-sheet compositor that turns a clip into one image.
 *
 * The contact sheet exists because a model sees images, not video. Handing a
 * vision model a ten-second clip means either many round trips or an unplayable
 * blob; handing it one grid of timestamped frames costs one request and is
 * legible in a single pass.
 *
 * Ported from adewaskar/jarvis `src/lib/camera.ts` (MIT, © 2026 Aditya
 * Dewaskar). The layout arithmetic is separated from the canvas drawing so it
 * can be tested without a GPU or a webcam.
 */

export interface ContactSheetOptions {
  cols: number;
  rows: number;
  cellWidth: number;
  cellHeight: number;
  /** Frames sampled per second into the rolling window. */
  fps: number;
  /** How much history the window keeps. */
  windowMs: number;
}

export const DEFAULT_SHEET: ContactSheetOptions = {
  cols: 6, rows: 10, cellWidth: 426, cellHeight: 240, fps: 6, windowMs: 10_000,
};

/** The cell grid a set of options describes, plus how many frames fit in it. */
export interface SheetLayout {
  cols: number;
  rows: number;
  cellWidth: number;
  cellHeight: number;
  width: number;
  height: number;
  /** Frames the grid can hold. */
  capacity: number;
}

export function sheetLayout(o: ContactSheetOptions): SheetLayout {
  return {
    cols: o.cols, rows: o.rows, cellWidth: o.cellWidth, cellHeight: o.cellHeight,
    width: o.cols * o.cellWidth, height: o.rows * o.cellHeight,
    // The grid is the limit, not the window: a sheet with 60 cells should not
    // silently drop to 59 because the timing maths rounded down.
    capacity: o.cols * o.rows,
  };
}

/** A frame offered to the sheet. */
export interface SheetFrame { at: number }

/** Where one frame belongs in the grid, and how stale it is. */
export interface SheetSlot<F extends SheetFrame = SheetFrame> { frame: F; row: number; col: number; ageMs: number }

/**
 * Choose which frames go in the grid, oldest first, and where each lands.
 *
 * Frames newer than the window are dropped, so the grid always shows the last
 * `windowMs` of history rather than drifting. A frame older than the window is
 * discarded outright rather than clamped to the first cell: silently
 * redisplaying a stale frame as if it were current is worse than a gap.
 *
 * Generic in the frame type so a caller keeps whatever it hung on each frame —
 * the drawing path relies on it and would otherwise have to cast.
 */
export function sheetPlan<F extends SheetFrame>(frames: readonly F[], now: number, o: ContactSheetOptions = DEFAULT_SHEET): SheetSlot<F>[] {
  const { capacity } = sheetLayout(o);
  const live = frames.filter(f => now - f.at <= o.windowMs).sort((a, b) => a.at - b.at);
  const kept = live.slice(-capacity);
  // Right-aligned, so the newest frame is always the last cell and history runs
  // left from it. A half-filled sheet that packed from the top-left would move
  // "now" around every time the sample rate wobbled, which makes the grid
  // unreadable at exactly the moment you are scanning it.
  const start = capacity - kept.length;
  return kept.map((frame, i) => ({
    frame,
    row: Math.floor((start + i) / o.cols),
    col: (start + i) % o.cols,
    ageMs: now - frame.at,
  }));
}

/** A frame that knows how to draw itself into a cell. */
export type DrawableFrame = SheetFrame & { draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void };

/**
 * Draw the grid. Needs a 2D context and something to draw per frame; the caller
 * owns both, which is what keeps this file free of DOM assumptions.
 */
export function drawContactSheet(
  ctx: CanvasRenderingContext2D,
  frames: readonly DrawableFrame[],
  now: number,
  o: ContactSheetOptions = DEFAULT_SHEET,
): number {
  const layout = sheetLayout(o);
  const plan = sheetPlan(frames, now, o);
  for (const slot of plan) {
    const x = slot.col * o.cellWidth;
    const y = slot.row * o.cellHeight;
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, o.cellWidth, o.cellHeight);
    ctx.clip();
    slot.frame.draw(ctx, o.cellWidth, o.cellHeight);
    ctx.restore();
    ctx.strokeStyle = 'rgba(0,0,0,0.35)';
    ctx.strokeRect(x + 0.5, y + 0.5, o.cellWidth - 1, o.cellHeight - 1);
    stampAge(ctx, slot.ageMs, x + 8, y + o.cellHeight - 10);
  }
  return plan.length;
}

/**
 * Label a cell with how long ago it was captured.
 *
 * The stamp is the point of the sheet. Without it the grid is ten seconds of
 * unordered pictures and the model has to guess which one is "the moment the
 * glass fell", which is the only question anyone asks of a clip.
 */
function stampAge(ctx: CanvasRenderingContext2D, ageMs: number, x: number, y: number): void {
  const seconds = Math.max(0, ageMs) / 1000;
  ctx.font = '600 16px ui-monospace, monospace';
  ctx.textBaseline = 'bottom';
  ctx.lineWidth = 4;
  ctx.strokeStyle = 'rgba(0,0,0,0.75)';
  const label = `−${seconds.toFixed(1)}s`;
  ctx.strokeText(label, x, y);
  ctx.fillStyle = '#ffffff';
  ctx.fillText(label, x, y);
}

/* ------------------------------------------------------------- capture */

/**
 * One capture stream, refcounted.
 *
 * A second getUserMedia call on a camera already in use makes Chrome drop the
 * first: hand tracking and a contact sheet both want frames, and asking twice
 * is how you end up with neither. Holders take a reference and the last release
 * stops the tracks.
 */
let stream: MediaStream | null = null;
let refs = 0;

export function cameraRefCount(): number {
  return refs;
}

export async function holdCamera(constraints: MediaStreamConstraints = { video: { width: 640, height: 480 } }): Promise<MediaStream> {
  refs += 1;
  if (stream) return stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia(constraints);
    return stream;
  } catch (err) {
    refs -= 1;
    throw err;
  }
}

export function releaseCamera(): void {
  refs = Math.max(0, refs - 1);
  if (refs > 0) return;
  for (const track of stream?.getTracks() ?? []) track.stop();
  stream = null;
}

/** Test hook: drop the shared stream without touching the counter. */
export function resetCameraForTest(): void {
  refs = 0;
  stream = null;
}