export const CANVASES = [
  { id: 'transcription', title: 'Conversation', label: 'Voice & memory', icon: 'messages', group: 'core', source: 'Transcript stream required', description: 'The live voice transcript and memory search surface. It stays explicit until a transcript endpoint exists.' },
  { id: 'pdf_reader', title: 'Documents', label: 'Document workspace', icon: 'file', group: 'core', source: 'Local PDF', description: 'Open a local PDF, navigate pages, and highlight text without uploading the file.' },
  { id: '3d_engine', title: '3D inspector', label: 'Spatial object lab', icon: 'box', group: 'core', source: 'Mushegh primitives / local GLB', description: 'An initially empty scene that Mushegh can populate with safe primitives or you can load with a local GLB.' },
  { id: 'browser', title: 'Browser', label: 'Research surface', icon: 'globe', group: 'core', source: 'Browser gateway required', description: 'An isolated remote browser view. It remains unavailable until the authenticated streaming gateway exists.' },
  { id: 'diagnostics', title: 'Diagnostics', label: 'System observatory', icon: 'activity', group: 'core', source: '/hud.json', description: 'Measured latency, tool activity, health, loops, provider state, reliability, traces, and unattended work.' },
  { id: 'decisions', title: 'Decisions', label: 'Open questions', icon: 'list', group: 'core', source: '/hud.json', description: 'Deferred objective decisions and requests that currently need your attention.' },
  { id: 'goals', title: 'Objectives', label: 'Mission progress', icon: 'target', group: 'core', source: '/hud.json', description: 'Active objectives and the work Mushegh is currently driving.' },
  { id: 'audio', title: 'Audio', label: 'Focus & sound', icon: 'audio', group: 'core', source: 'Local audio', description: 'Local ambient playback that can continue while its canvas is in the background.' },
  { id: 'approvals', title: 'Approvals', label: 'Operator control', icon: 'shield', group: 'core', source: '/hud.json summaries', description: 'Read-only approval summaries until stable request IDs and the audited action endpoint exist.' },
  { id: 'cameras', title: 'Cameras', label: 'Live presence', icon: 'camera', group: 'core', source: 'Camera gateway required', description: 'Live and historical camera feeds once an authenticated gateway and stream inventory are available.' },
  { id: 'code', title: 'Code workspace', label: 'Editor & execution', icon: 'code', group: 'expansion', source: 'Sandbox service required', description: 'Mushegh-controlled editing, execution, and preview once an isolated code sandbox service is available.' },
  { id: 'agents', title: 'Agent activity', label: 'Delegation activity', icon: 'network', group: 'expansion', source: '/hud.json tasks / loops / unattended', description: 'Real active work, declared background loops, and unattended-run counts without exposing private reasoning.' },
  { id: 'home', title: 'Home & devices', label: 'Spatial floor plan', icon: 'home', group: 'expansion', source: 'Device inventory required', description: 'A spatial device surface once the trusted home inventory and room topology are exposed.' },
  { id: 'memory', title: 'Memory graph', label: 'Connected knowledge', icon: 'network', group: 'expansion', source: 'Memory graph endpoint required', description: 'A navigable relationship graph once a privacy-bounded memory graph endpoint is available.' },
  { id: 'security', title: 'Security', label: 'Operational risk', icon: 'shield', group: 'expansion', source: '/hud.json health / reliability / unattended', description: 'Current operational risk signals. Network threats remain unavailable until a security event feed exists.' },
  { id: 'finance', title: 'Portfolio', label: 'Financial overview', icon: 'chart', group: 'expansion', source: 'Portfolio data required', description: 'Read-only portfolio telemetry once an explicitly configured financial data source is available.' },
  { id: 'calendar', title: 'Calendar', label: 'Time & context', icon: 'calendar', group: 'expansion', source: 'Calendar endpoint required', description: 'Schedule context and predicted preparation windows once a calendar source is connected.' },
  { id: 'spectrum', title: 'Audio spectrum', label: 'Acoustic environment', icon: 'audio', group: 'expansion', source: 'Audio analyser required', description: 'A live local acoustic spectrum once a user-authorized audio analyser stream is available.' },
] as const;
export type CanvasId = typeof CANVASES[number]['id'];
export type SizeMode = '1/4' | '1/2_horizontal' | '1/2_vertical' | 'full' | 'background';
export type Preset = 'quad' | 'split_vertical' | 'split_horizontal';
export interface Tile { id: CanvasId; x: number; y: number; w: number; h: number }
export interface HudState { version: 1; tiles: Tile[]; background: CanvasId[]; hero: CanvasId | null; focused: CanvasId | null; preset: Preset }
export type Command =
  | { type: 'open' | 'focus' | 'background' | 'dismiss'; id: CanvasId }
  | { type: 'hero'; id: CanvasId }
  | { type: 'restore' | 'reset' }
  | { type: 'preset'; preset: Preset }
  | { type: 'swap'; a: CanvasId; b: CanvasId }
  | { type: 'resize'; id: CanvasId; w: number; h: number }
  | { type: 'layout'; tiles: Tile[] };
export const isCanvasId = (id: unknown): id is CanvasId => CANVASES.some(c => c.id === id);
export const initialState: HudState = {
  version: 1, preset: 'quad', hero: null, focused: 'transcription', background: [],
  tiles: [
    { id: 'transcription', x: 0, y: 0, w: 6, h: 6 }, { id: '3d_engine', x: 6, y: 0, w: 6, h: 6 },
    { id: 'goals', x: 0, y: 6, w: 6, h: 6 }, { id: 'diagnostics', x: 6, y: 6, w: 6, h: 6 },
  ],
};
function arrange(ids: CanvasId[], preset: Preset): Tile[] {
  return ids.map((id, i) => preset === 'quad'
    ? { id, x: (i % 2) * 6, y: Math.floor(i / 2) * 6, w: 6, h: 6 }
    : preset === 'split_vertical' ? { id, x: i * 6, y: 0, w: 6, h: 12 }
    : { id, x: 0, y: i * 6, w: 12, h: 6 });
}
export function validTiles(tiles: Tile[]): boolean {
  return tiles.length <= 4 && new Set(tiles.map(t => t.id)).size === tiles.length && tiles.every(t =>
    isCanvasId(t.id) && [t.x, t.y, t.w, t.h].every(Number.isInteger) && t.x >= 0 && t.y >= 0 &&
    [6, 12].includes(t.w) && [6, 12].includes(t.h) && t.x + t.w <= 12 && t.y + t.h <= 12 &&
    !tiles.some(o => o.id !== t.id && t.x < o.x + o.w && t.x + t.w > o.x && t.y < o.y + o.h && t.y + t.h > o.y));
}
export function restoreState(raw: string | null): HudState {
  try {
    const s = JSON.parse(raw || 'null');
    if (!s || s.version !== 1 || !Array.isArray(s.tiles) || !validTiles(s.tiles) || !Array.isArray(s.background) ||
      !s.background.every(isCanvasId) || new Set(s.background).size !== s.background.length ||
      s.background.some((id: CanvasId) => s.tiles.some((t: Tile) => t.id === id)) ||
      !['quad', 'split_vertical', 'split_horizontal'].includes(s.preset) ||
      (s.hero !== null && !s.tiles.some((t: Tile) => t.id === s.hero)) ||
      (s.focused !== null && !s.tiles.some((t: Tile) => t.id === s.focused))) return initialState;
    return s;
  } catch { return initialState; }
}
export function reducer(state: HudState, cmd: Command): HudState {
  if ('id' in cmd && !isCanvasId(cmd.id)) return state;
  switch (cmd.type) {
    case 'reset': return initialState;
    case 'restore': return { ...state, hero: null };
    case 'focus': return state.tiles.some(t => t.id === cmd.id) ? { ...state, focused: cmd.id } : state;
    case 'hero': return state.tiles.some(t => t.id === cmd.id) ? { ...state, hero: state.hero === cmd.id ? null : cmd.id, focused: cmd.id } : state;
    case 'preset': {
      const limit = cmd.preset === 'quad' ? 4 : 2;
      const ids = [...state.tiles.map(t => t.id), ...state.background];
      return { ...state, preset: cmd.preset, hero: null, tiles: arrange(ids.slice(0, limit), cmd.preset), background: ids.slice(limit), focused: ids[0] || null };
    }
    case 'background': case 'dismiss': {
      const tiles = state.tiles.filter(t => t.id !== cmd.id);
      const background = state.background.filter(id => id !== cmd.id);
      if (cmd.type === 'background') background.push(cmd.id);
      return { ...state, tiles, background, hero: state.hero === cmd.id ? null : state.hero, focused: state.focused === cmd.id ? tiles[0]?.id || null : state.focused };
    }
    case 'open': {
      if (state.tiles.some(t => t.id === cmd.id)) return { ...state, focused: cmd.id, hero: state.hero ? cmd.id : null };
      const tiles = [...state.tiles];
      const background = state.background.filter(id => id !== cmd.id);
      const slot = arrange([cmd.id, cmd.id, cmd.id, cmd.id].slice(0, state.preset === 'quad' ? 4 : 2), state.preset)
        .find(t => validTiles([...tiles, t]));
      if (slot) tiles.push(slot);
      else {
        const index = Math.max(0, tiles.findIndex(t => t.id === state.focused));
        const old = tiles[index];
        if (old) { background.push(old.id); tiles[index] = { ...old, id: cmd.id }; }
        else tiles.push(...arrange([cmd.id], state.preset));
      }
      return { ...state, tiles, background, focused: cmd.id, hero: state.hero ? cmd.id : null };
    }
    case 'swap': {
      const a = state.tiles.find(t => t.id === cmd.a), b = state.tiles.find(t => t.id === cmd.b);
      if (!a || !b) return state;
      return { ...state, tiles: state.tiles.map(t => t.id === a.id ? { ...b, id: a.id } : t.id === b.id ? { ...a, id: b.id } : t) };
    }
    case 'resize': {
      const old = state.tiles.find(t => t.id === cmd.id);
      if (!old || ![6, 12].includes(cmd.w) || ![6, 12].includes(cmd.h)) return state;
      if (cmd.w === 12 && cmd.h === 12) return { ...state, hero: old.id, focused: old.id };
      const resized = { ...old, x: cmd.w === 12 ? 0 : old.x, y: cmd.h === 12 ? 0 : old.y, w: cmd.w, h: cmd.h };
      const displaced = state.tiles.filter(t => t.id !== old.id && !validTiles([resized, t]));
      return { ...state, focused: old.id, tiles: state.tiles.filter(t => !displaced.includes(t)).map(t => t.id === old.id ? resized : t), background: [...state.background, ...displaced.map(t => t.id)] };
    }
    case 'layout': return validTiles(cmd.tiles) && cmd.tiles.length === state.tiles.length && cmd.tiles.every(t => state.tiles.some(o => o.id === t.id)) ? { ...state, tiles: cmd.tiles } : state;
  }
}
export function sizeMode(tile: Tile, hero: CanvasId | null): SizeMode {
  if (hero === tile.id || (tile.w === 12 && tile.h === 12)) return 'full';
  if (tile.w === 12) return '1/2_horizontal';
  if (tile.h === 12) return '1/2_vertical';
  return '1/4';
}
