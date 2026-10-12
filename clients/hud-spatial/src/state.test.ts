import { describe, expect, it } from 'vitest';
import { CANVASES, initialState, reducer, restoreState, validTiles } from './state';
import { DATA_COVERAGE, parseSnapshot } from './api';
import { readFileSync } from 'node:fs';
describe('Spatial state invariants', () => {
  it('restores the exact pre-focus grid', () => { const s = reducer(initialState, { type: 'hero', id: '3d_engine' }); expect(s.hero).toBe('3d_engine'); expect(reducer(s, { type: 'restore' }).tiles).toEqual(initialState.tiles); });
  it('replaces focused canvas and retains displaced state in the dock', () => { const s = reducer(initialState, { type: 'open', id: 'pdf_reader' }); expect(s.background).toEqual(['transcription']); expect(s.tiles[0].id).toBe('pdf_reader'); expect(s.tiles.length).toBe(4); expect(validTiles(s.tiles)).toBe(true); });
  it('fills an empty slot before displacing a canvas', () => { const s = reducer(reducer(initialState, { type: 'background', id: 'goals' }), { type: 'open', id: 'pdf_reader' }); expect(s.tiles.find(t => t.id === 'pdf_reader')).toMatchObject({ x: 0, y: 6 }); expect(s.background).toEqual(['goals']); });
  it('split and quad preserve every open canvas without duplicates', () => { const s = reducer(initialState, { type: 'preset', preset: 'split_vertical' }); expect(s.tiles).toHaveLength(2); expect(s.background).toHaveLength(2); const restored = reducer(s, { type: 'preset', preset: 'quad' }); expect(restored.tiles.map(t => t.id)).toEqual(initialState.tiles.map(t => t.id)); expect(restored.background).toEqual([]); });
  it('dismiss removes both visibility and retained entry', () => { const s = reducer(initialState, { type: 'dismiss', id: 'transcription' }); expect([...s.tiles.map(t => t.id), ...s.background]).not.toContain('transcription'); });
  it('rejects invalid, overlapping and out-of-bounds persisted geometry', () => { for (const patch of [{ version: 2 }, { tiles: [{ id: 'goals', x: 10, y: 0, w: 6, h: 6 }] }, { background: ['fake'] }, { tiles: [initialState.tiles[0], { ...initialState.tiles[0], id: 'goals' }] }, { focused: 'unknown' }, { background: ['goals'] }]) expect(restoreState(JSON.stringify({ ...initialState, ...patch }))).toEqual(initialState); expect(restoreState('{bad')).toEqual(initialState); });
  it('rejects invalid resize without losing previous layout', () => { expect(reducer(initialState, { type: 'layout', tiles: initialState.tiles.map(t => ({ ...t, w: 12 })) })).toBe(initialState); });
  it('resizing to a half tile backgrounds only covered peers', () => { const s = reducer(initialState, { type: 'resize', id: 'transcription', w: 12, h: 6 }); expect(s.tiles.find(t => t.id === 'transcription')).toMatchObject({ x: 0, y: 0, w: 12, h: 6 }); expect(s.background).toEqual(['3d_engine']); expect(s.tiles).toHaveLength(3); expect(validTiles(s.tiles)).toBe(true); });
  it('full resize uses locked hero mode and restores the exact previous grid', () => { const s = reducer(initialState, { type: 'resize', id: 'diagnostics', w: 12, h: 12 }); expect(s.hero).toBe('diagnostics'); expect(reducer(s, { type: 'restore' }).tiles).toEqual(initialState.tiles); });
  it('exercises every canvas through focus, background and restore', () => { let s = initialState; for (const c of CANVASES) { s = reducer(s, { type: 'open', id: c.id }); s = reducer(s, { type: 'hero', id: c.id }); s = reducer(s, { type: 'background', id: c.id }); s = reducer(s, { type: 'open', id: c.id }); expect(validTiles(s.tiles)).toBe(true); expect(new Set([...s.tiles.map(t => t.id), ...s.background]).size).toBe(s.tiles.length + s.background.length); } });
});
describe('Brain contract', () => {
  it('maps every real producer top-level field to a named surface', () => {
    const source = readFileSync(new URL('../../../src/mushegh/brain/hud.py', import.meta.url), 'utf8');
    const body = source.slice(source.indexOf('    return {', source.indexOf('def hud_snapshot(')), source.indexOf('\ndef _unattended'));
    const keys = [...body.matchAll(/^        "([a-z_]+)":/gm)].map(m => m[1]);
    expect([...new Set(Object.values(DATA_COVERAGE).flat())].sort()).toEqual(keys.sort());
  });
  it('rejects malformed snapshots instead of displaying false live data', () => { expect(() => parseSnapshot({ generated: 'not-a-date' })).toThrow(); });
});
