# OpenWatari spatial HUD

React 19.2 / TypeScript / Vite / Tailwind 4 browser client for the existing Mushegh brain. Production output is static; it does not replace the Python brain or the existing `clients/hud` client.

```powershell
cd C:\Mushegh\clients\hud-spatial
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The dev server binds only to loopback. `npm run build` typechecks and builds `dist/`; `npm run preview` serves that build at http://127.0.0.1:5174.

## Controls

- Drag a canvas by its header; use the bottom-right corner to resize in quarter/half/full increments. Occupied equal-sized slots swap; expanding sends covered canvases to the background.
- Expand / F focuses a canvas; Escape or the focus-mode control restores the exact previous grid.
- Background retains the canvas session without a separate dock. Ctrl+K / Cmd+K focuses the single command/search field; a backgrounded canvas is restored from its search result. Dismiss releases it from the workspace.
- Commands include `open documents`, `expand 3D inspector`, `background audio`, `dismiss browser`, `explain diagnostics`, `inspect goals`, `render sphere`, `quad`, `split vertical`, `split horizontal`, `restore grid`, and `reset`.
- A layout is saved in browser localStorage, with validation on reload. Local documents, models and audio are session-only and never uploaded by this client.

The field is also the only persistent HUD chrome: there is no navbar, sidebar, footer, toolbar, or background dock. It is a deterministic local controller and canvas finder. Voice control arrives through Mushegh's `control_hud` tool and the authenticated snapshot; the page itself does not claim microphone access.

## Brain connection

The development and preview servers proxy only GET `/api/hud.json` and `/api/review.json` to the existing brain on `http://127.0.0.1:8766`. They load `MUSHEGH_API_AUTH_TOKEN` and `MUSHEGH_CLIENT_HTTP_PORT` from the repository root `.env` on the server side. `HUD_BRAIN_ORIGIN` can override the target. No root credentials are emitted into the Vite frontend environment. Restart Vite after changing these settings.

No brain process is started by this client. Without a running brain, the interface explicitly displays offline state while layout, PDF, 3D and audio controls continue to work. Last data remains visible after a disconnect and is marked as an old snapshot.

Deployment: `dist/` may be served by the existing static handler at `/hud-spatial/dist/`. Its API reads use same-origin `/hud.json` and `/review.json`; an authenticated deployment needs a trusted bootstrap that supplies the existing `window.MUSHEGH_TOKEN`, or an authenticated reverse proxy. This change does not modify the existing handler to inject tokens into the new client. Do not expose Vite to the public network or use a `VITE_` variable for any secret.

## Current capability boundary

Implemented: search-plus-grid spatial shell; session-preserving background state; focus restoration; responsive stack; reduced motion; shared truthful loading states; local PDF page selection and in-page highlighting; an initially empty 3D scene populated by an Mushegh box/sphere/cylinder/cone/torus command or a self-contained local GLB; local audio playback; real goals, decisions, diagnostics, agent activity, and operational-risk evidence from the existing snapshot; unattended review fetch; and bounded Mushegh presentation commands with an idempotent browser cursor. All current snapshot fields have a named render surface. Low-level observability records are inspectable JSON until richer views are implemented.

Not implemented: streamed conversations, memory search, AI model generation, remote browser gateway, hardware metrics collector, live microphone, actionable approval endpoint, camera gateway/history, and the eight expansion integrations. Those canvases show their missing data source explicitly. Installed engines are not evidence that those integrations work.

Local PDF and GLB files are limited to 50 MB. GLB external asset references are refused. PDF annotations/links are disabled; text is escaped before highlights are inserted. WebGL renders on demand and unmounts while hidden. Audio intentionally continues in the background and stops on dismiss. There is no default 3D specimen or fabricated model.

## Verification

```powershell
npm test
npm run test:browser
npm run build
npm audit
.venv\Scripts\python.exe bench\test_hud_modes.py
```

Browser tests use installed Microsoft Edge, mock the brain endpoint with clearly synthetic fixtures, and never start the brain. The unit contract gate reads the real Python snapshot producer and checks its top-level keys against `DATA_COVERAGE`. Tests and screenshots prove frontend behavior, not live voice, camera, or autonomous action integration.

Architecture decisions, the full eighteen-canvas dependency matrix, documentation inventory, Jev assessment, and remaining integration work are recorded in [HUD-SPATIAL.md](../../docs/HUD-SPATIAL.md).
