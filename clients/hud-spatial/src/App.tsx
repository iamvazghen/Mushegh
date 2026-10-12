import { lazy, Suspense, useEffect, useReducer, useRef, useState } from 'react';
import GridLayout, { noCompactor, useContainerWidth, type Layout, type LayoutItem } from 'react-grid-layout';
import { LayoutGroup, motion, MotionConfig, useReducedMotion } from 'motion/react';
import { ArrowDownToLine, Box, Command as CommandIcon, Expand, Grip, Maximize2, Minimize2, Search, Send, X } from 'lucide-react';
import { CANVASES, initialState, isCanvasId, reducer, restoreState, type CanvasId, type Command } from './state';
import { useSnapshot, type HudControlCommand } from './api';
import { CanvasBoundary, CanvasIcon, CanvasLoader, Empty } from './components';
import { Agents, Conversation, Decisions, Diagnostics, Goals, Security } from './canvases/DataCanvases';
import type { PrimitiveSpec } from './canvases/ModelCanvas';

const ModelCanvas = lazy(() => import('./canvases/ModelCanvas'));
const PdfCanvas = lazy(() => import('./canvases/PdfCanvas'));
const AudioCanvas = lazy(() => import('./canvases/AudioCanvas'));
const STORAGE = 'openwatari.hud.layout.v1';
const CONTROL_CURSOR = 'openwatari.hud.control.v1';

type ControlCursor = { streamId: string; sequence: number };

function canvasForText(text: string) {
  const normalized = text.replace(/[_-]/g, ' ');
  return CANVASES.find(canvas => {
    const id = canvas.id.replace(/[_-]/g, ' ');
    return normalized.includes(id) || normalized.includes(canvas.title.toLowerCase()) || normalized === canvas.label.toLowerCase();
  });
}

function canvasState(id: CanvasId, visible: CanvasId[], background: CanvasId[]) {
  if (visible.includes(id)) return 'VISIBLE';
  if (background.includes(id)) return 'BACKGROUND';
  return 'CLOSED';
}

export function App() {
  const [state, dispatch] = useReducer(reducer, initialState, () => {
    try { return restoreState(localStorage.getItem(STORAGE)); } catch { return initialState; }
  });
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const [persistError, setPersistError] = useState(false);
  const [pageVisible, setPageVisible] = useState(!document.hidden);
  const [interacting, setInteracting] = useState(false);
  const [modelSpec, setModelSpec] = useState<PrimitiveSpec | null>(null);
  const reduced = !!useReducedMotion();
  const { snapshot, status, history, reconnect } = useSnapshot();
  const { width, containerRef, mounted } = useContainerWidth();
  const [height, setHeight] = useState(700);
  const mobile = width < 640;
  const activeIds = state.tiles.filter(tile => !state.hero || state.hero === tile.id).map(tile => tile.id);
  const opened = [...state.tiles.map(tile => tile.id), ...state.background];
  const searchInput = useRef<HTMLInputElement>(null);
  const cursor = useRef<ControlCursor | null>(null);

  const results = CANVASES.filter(canvas => {
    const needle = query.trim().toLowerCase();
    return !needle || `${canvas.title} ${canvas.label} ${canvas.id} ${canvas.source}`.toLowerCase().includes(needle);
  });

  useEffect(() => {
    try { localStorage.setItem(STORAGE, JSON.stringify(state)); setPersistError(false); }
    catch { setPersistError(true); }
  }, [state]);
  useEffect(() => {
    try { cursor.current = JSON.parse(localStorage.getItem(CONTROL_CURSOR) || 'null'); }
    catch { cursor.current = null; }
  }, []);
  useEffect(() => {
    const change = () => setPageVisible(!document.hidden);
    document.addEventListener('visibilitychange', change);
    return () => document.removeEventListener('visibilitychange', change);
  }, []);
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setHeight(entry.contentRect.height));
    observer.observe(element);
    return () => observer.disconnect();
  }, [containerRef]);
  useEffect(() => {
    function key(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); setSearchOpen(true); searchInput.current?.focus(); return;
      }
      if (target.closest('input,textarea,select,[contenteditable=true]')) {
        if (event.key === 'Escape') { setSearchOpen(false); searchInput.current?.blur(); }
        return;
      }
      if (event.key === 'Escape') dispatch({ type: 'restore' });
      if (event.key.toLowerCase() === 'f' && state.focused) dispatch({ type: 'hero', id: state.focused });
    }
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [state.focused]);

  function send(command: Command) { dispatch(command); }
  function applyControl(command: HudControlCommand, remote = false) {
    const id = isCanvasId(command.canvas) ? command.canvas : null;
    const canvas = id ? CANVASES.find(item => item.id === id)! : null;
    if (command.action === 'open' || command.action === 'focus') { if (id) send({ type: 'open', id }); }
    else if (command.action === 'toggle' && id) send(activeIds.includes(id) ? { type: 'background', id } : { type: 'open', id });
    else if (command.action === 'background' && id) send({ type: 'background', id });
    else if (command.action === 'dismiss' && id) send({ type: 'dismiss', id });
    else if ((command.action === 'inspect' || command.action === 'explain') && id) {
      send({ type: 'open', id });
      if (command.action === 'inspect' && !state.hero) send({ type: 'hero', id });
      if (command.action === 'explain') setNotice(`${canvas!.title}: ${canvas!.description}`);
    } else if (command.action === 'restore') send({ type: 'restore' });
    else if (command.action === 'reset') send({ type: 'reset' });
    else if (command.action === 'preset' && ['quad', 'split_vertical', 'split_horizontal'].includes(command.preset || '')) send({ type: 'preset', preset: command.preset as 'quad' | 'split_vertical' | 'split_horizontal' });
    else if (command.action === 'search' && command.query) { setQuery(command.query); setSearchOpen(true); searchInput.current?.focus(); }
    else if (command.action === 'resize' && id) {
      if (command.size === 'full') { send({ type: 'open', id }); if (!state.hero) send({ type: 'hero', id }); }
      else if (command.size === 'quarter') send({ type: 'resize', id, w: 6, h: 6 });
      else if (command.size === 'half_horizontal') send({ type: 'resize', id, w: 12, h: 6 });
      else if (command.size === 'half_vertical') send({ type: 'resize', id, w: 6, h: 12 });
    } else if (command.action === 'render_3d' && ['box', 'sphere', 'cylinder', 'cone', 'torus'].includes(command.primitive || '')) {
      setModelSpec({ primitive: command.primitive as PrimitiveSpec['primitive'], color: command.color });
      send({ type: 'open', id: '3d_engine' });
      if (!state.hero) send({ type: 'hero', id: '3d_engine' });
    } else return false;
    if (remote && command.action !== 'explain') setNotice(`Mushegh applied: ${command.action.replace('_', ' ')}`);
    return true;
  }

  useEffect(() => {
    const control = snapshot?.hud_control;
    if (!control?.stream_id) return;
    const previous = cursor.current;
    const sameStream = previous?.streamId === control.stream_id;
    let last = sameStream ? previous.sequence : 0;
    const now = Date.now();
    for (const command of [...control.commands].sort((a, b) => a.sequence - b.sequence)) {
      if (command.sequence <= last) continue;
      const age = now - Date.parse(command.issued_at);
      if (sameStream || (Number.isFinite(age) && age >= 0 && age <= 60_000)) applyControl(command, true);
      last = command.sequence;
    }
    const next = { streamId: control.stream_id, sequence: Math.max(last, control.sequence) };
    cursor.current = next;
    try { localStorage.setItem(CONTROL_CURSOR, JSON.stringify(next)); } catch { /* Layout remains usable without storage. */ }
  }, [snapshot?.hud_control]);

  function submitCommand(event: React.FormEvent) {
    event.preventDefault();
    const text = query.toLowerCase().replace(/^(jarvis|mushegh|watari)[, ]*/g, '').trim();
    const canvas = canvasForText(text);
    const primitive = ['box', 'sphere', 'cylinder', 'cone', 'torus'].find(item => new RegExp(`\\b${item}\\b`).test(text));
    let applied = false;
    if (primitive && /(render|create|show|make|display)/.test(text)) {
      applied = applyControl({ sequence: 0, issued_at: new Date().toISOString(), action: 'render_3d', primitive });
    } else if (/^(quad|tile quad|restore grid|restore|split vertical|split horizontal|reset)$/.test(text)) {
      if (text === 'restore' || text === 'restore grid') send({ type: 'restore' });
      else if (text === 'reset') send({ type: 'reset' });
      else send({ type: 'preset', preset: text.includes('vertical') ? 'split_vertical' : text.includes('horizontal') ? 'split_horizontal' : 'quad' });
      applied = true;
    } else if (canvas) {
      const id = canvas.id;
      if (/dismiss|close/.test(text)) send({ type: 'dismiss', id });
      else if (/background|minimi[sz]e/.test(text)) send({ type: 'background', id });
      else if (/explain/.test(text)) applyControl({ sequence: 0, issued_at: new Date().toISOString(), action: 'explain', canvas: id });
      else if (/inspect|see/.test(text)) applyControl({ sequence: 0, issued_at: new Date().toISOString(), action: 'inspect', canvas: id });
      else { send({ type: 'open', id }); if (/full|expand|focus/.test(text)) send({ type: 'hero', id }); }
      applied = true;
    }
    if (applied) { setNotice(`Applied: ${text}`); setQuery(''); setSearchOpen(false); }
    else { setSearchOpen(true); setNotice(results.length ? 'Choose a canvas below, or use an action such as open, expand, background, explain, or render.' : 'No matching canvas or command.'); }
  }

  const layout: Layout = opened.map((id, index) => {
    const tile = state.tiles.find(item => item.id === id);
    const base = tile ? state.hero ? { x: 0, y: 0, w: 12, h: 12 } : mobile ? { x: 0, y: activeIds.indexOf(id) * 6, w: 12, h: 6 } : tile : { x: 0, y: 120 + index * 12, w: 6, h: 6 };
    return { ...base, i: id, static: !tile || !!state.hero || mobile, minW: 6, minH: 6, maxW: 12, maxH: 12 };
  });
  const rowHeight = mobile ? 56 : Math.max(12, (height - 11 * 12) / 12);
  function commitLayout(next: Layout, oldItem: LayoutItem | null, newItem: LayoutItem | null) {
    setInteracting(false);
    if (mobile || state.hero) return;
    if (oldItem && newItem) {
      const target = state.tiles.find(tile => tile.id !== newItem.i && tile.x === Math.round(newItem.x / 6) * 6 && tile.y === Math.round(newItem.y / 6) * 6 && tile.w === oldItem.w && tile.h === oldItem.h);
      if (target) { send({ type: 'swap', a: newItem.i as CanvasId, b: target.id }); return; }
    }
    send({ type: 'layout', tiles: next.filter(item => state.tiles.some(tile => tile.id === item.i)).map(item => ({ id: item.i as CanvasId, x: Math.round(item.x / 6) * 6, y: Math.round(item.y / 6) * 6, w: Math.round(item.w / 6) * 6, h: Math.round(item.h / 6) * 6 })) });
  }
  function commitResize(_layout: Layout, _old: LayoutItem | null, item: LayoutItem | null) {
    setInteracting(false);
    if (item) send({ type: 'resize', id: item.i as CanvasId, w: Math.round(item.w / 6) * 6, h: Math.round(item.h / 6) * 6 });
  }
  function body(id: CanvasId, visible: boolean) {
    const needsBrain = ['goals', 'diagnostics', 'decisions', 'approvals', 'agents', 'security'].includes(id);
    if (needsBrain && status === 'connecting' && !snapshot) return <CanvasLoader label="Connecting to Mushegh" detail="Waiting for the authenticated HUD snapshot"/>;
    if (id === 'transcription') return <Conversation/>;
    if (id === 'goals') return <Goals data={snapshot}/>;
    if (id === 'diagnostics') return <Diagnostics data={snapshot} history={history} reduced={reduced} refresh={reconnect}/>;
    if (id === 'decisions' || id === 'approvals') return <Decisions data={snapshot} approvals={id === 'approvals'}/>;
    if (id === 'agents') return <Agents data={snapshot}/>;
    if (id === 'security') return <Security data={snapshot}/>;
    if (id === '3d_engine') return <ModelCanvas active={visible && pageVisible} reduced={reduced} instruction={modelSpec}/>;
    if (id === 'pdf_reader') return <PdfCanvas active={visible && pageVisible}/>;
    if (id === 'audio') return <AudioCanvas/>;
    const canvas = CANVASES.find(item => item.id === id)!;
    const message = id === 'browser' ? 'Connect the isolated browser streaming gateway before Mushegh can navigate or explain a page here.' : id === 'cameras' ? 'Connect an authenticated camera gateway before live or recorded feeds can appear.' : `This canvas is addressable by Mushegh, but ${canvas.source.toLowerCase()} before it can show real information.`;
    return <Empty title={`${canvas.title} source unavailable`} icon={canvas.icon}><p>{message}</p></Empty>;
  }

  return <MotionConfig reducedMotion={reduced ? 'always' : 'user'} transition={reduced ? { duration: 0 } : { type: 'spring', stiffness: 300, damping: 30, mass: 0.8 }}>
    <div className="hud-shell">
      <div className="command-surface">
        <form className="command-form" onSubmit={submitCommand} role="search">
          <span className={`brain-indicator ${status}`} title={`Mushegh brain: ${status}`} aria-label={`Mushegh brain ${status}`}/>
          <CommandIcon size={17} aria-hidden="true"/>
          <label className="sr-only" htmlFor="hud-command">Mushegh command or canvas search</label>
          <input ref={searchInput} id="hud-command" value={query} onFocus={() => setSearchOpen(true)} onChange={event => { setQuery(event.target.value); setSearchOpen(true); setNotice(''); }} placeholder="Ask Mushegh to open, move, explain, inspect, or render…" autoComplete="off"/>
          {query && <button type="button" className="clear-command" aria-label="Clear command" onClick={() => { setQuery(''); setNotice(''); searchInput.current?.focus(); }}><X size={15}/></button>}
          <button type="submit" className="run-command" aria-label="Run HUD command" disabled={!query.trim()}><Send size={16}/></button>
          <kbd>Ctrl K</kbd>
        </form>
        {(notice || persistError) && <div className="command-notice" role="status">{persistError ? 'Layout storage is unavailable; changes last for this session.' : notice}</div>}
        {searchOpen && <div className="search-results" aria-label="Canvas search results">
          <div className="search-summary"><span>{results.length} canvases</span><button onClick={() => { setSearchOpen(false); searchInput.current?.blur(); }}>Close</button></div>
          <div className="search-list">{results.map(canvas => <button key={canvas.id} aria-label={`Open ${canvas.title}`} onClick={() => { send({ type: 'open', id: canvas.id }); setQuery(''); setSearchOpen(false); setNotice(`${canvas.title} brought into view.`); }}><CanvasIcon name={canvas.icon}/><span><strong>{canvas.title}</strong><small>{canvas.description}</small></span><span className="result-state">{canvasState(canvas.id, activeIds, state.background)}</span></button>)}</div>
        </div>}
      </div>

      <main className="grid-viewport" ref={containerRef} data-testid="workspace-grid">
        <LayoutGroup id="hud">{mounted && <GridLayout width={width} layout={layout} autoSize={false} gridConfig={{ cols: 12, rowHeight, margin: [12, 12], containerPadding: [0, 0], maxRows: mobile ? Infinity : 12 }} dragConfig={{ enabled: !mobile && !state.hero, handle: '.drag-handle', cancel: 'button,input,a,label', bounded: true }} resizeConfig={{ enabled: !mobile && !state.hero, handles: ['se'] }} compactor={noCompactor} onDragStart={() => setInteracting(true)} onResizeStart={() => setInteracting(true)} onDragStop={commitLayout} onResizeStop={commitResize} style={{ height: mobile ? activeIds.length * 6 * (rowHeight + 12) : '100%' }}>
          {opened.map(id => {
            const canvas = CANVASES.find(item => item.id === id)!;
            const visible = activeIds.includes(id);
            return <div key={id} className={`tile-slot ${visible ? '' : 'is-background'}`} data-canvas={id} data-visible={visible} aria-hidden={!visible} inert={!visible} style={{ zIndex: state.hero === id ? 50 : state.focused === id ? 2 : 1 }}>
              <motion.section layout={!interacting && !reduced && !mobile} layoutId={mobile ? undefined : `canvas-${id}`} className="hud-glass-panel" data-focused={state.focused === id} aria-label={`${canvas.title} canvas`} onPointerDown={() => { if (visible) send({ type: 'focus', id }); }} initial={reduced ? false : { opacity: 0, scale: 0.96, filter: 'blur(8px)' }} animate={{ opacity: visible ? 1 : 0, scale: visible ? 1 : 0.95, filter: visible ? 'blur(0px)' : 'blur(6px)' }} transition={reduced ? { duration: 0 } : undefined}>
                <div className="canvas-header"><div className="drag-handle" title="Drag canvas"><Grip size={14}/><span className={`status-dot ${status === 'live' && ['goals', 'diagnostics', 'decisions', 'approvals', 'agents', 'security'].includes(id) ? 'good' : ''}`}/><h2>{canvas.title}</h2></div><div className="canvas-actions"><button aria-label={`Background ${canvas.title}`} title="Send to background" onClick={() => send({ type: 'background', id })}><ArrowDownToLine size={14}/></button><button aria-label={`Expand ${canvas.title}`} title="Toggle full screen" onClick={() => send({ type: 'hero', id })}>{state.hero === id ? <Minimize2 size={14}/> : <Maximize2 size={14}/>}</button><button aria-label={`Dismiss ${canvas.title}`} title="Dismiss" onClick={() => send({ type: 'dismiss', id })}><X size={14}/></button></div></div>
                <div className="canvas-content"><CanvasBoundary><Suspense fallback={<CanvasLoader label={`Loading ${canvas.title.toLowerCase()}`} detail="Initializing the canvas renderer"/>}>{body(id, visible)}</Suspense></CanvasBoundary></div>
              </motion.section>
            </div>;
          })}
        </GridLayout>}</LayoutGroup>
        {!state.tiles.length && <div className="empty-workspace"><Search size={26}/><h2>No canvases in view</h2><p>Use the command field to restore the grid or open a canvas.</p></div>}
        {state.hero && <button className="restore-focus" aria-label="Restore grid" onClick={() => send({ type: 'restore' })}><Expand size={14}/>Restore grid</button>}
        {modelSpec && state.tiles.some(tile => tile.id === '3d_engine') && <button className="clear-model" aria-label="Clear 3D scene" onClick={() => setModelSpec(null)}><Box size={14}/>Clear scene</button>}
      </main>
    </div>
  </MotionConfig>;
}
