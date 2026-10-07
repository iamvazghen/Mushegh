# OpenWatari spatial HUD — architecture review and first implementation

> **Status 2026-10-03.** This record is current and detailed, and it remains the
> authority for the HUD client. Two things it does not cover, now answered elsewhere:
> the project's current intent is [`DECISIONS.md`](DECISIONS.md), and the planning surface
> is [`ROADMAP.md`](ROADMAP.md). Note that **the HUD is optional** — the system is
> complete without a visible surface, which is why no milestone in the roadmap depends on
> it, and why the spatial work is sequenced behind voice quality rather than ahead of it.

Date: 2026-09-21; implementation record updated 2026-10-03. Owner request: a React spatial Jarvis-style HUD with 10 core canvases, 8 expansion concepts, quarter/half/full/background tiling, dynamic transitions, selected dependencies installed, a single voice-addressable command/search surface, and a visible localhost preview.

The checkout remains named Afon/OpenAfon internally. OpenWatari is the new HUD's presentation name; no repository-wide rename is performed. This record distinguishes implemented frontend behavior, available backend data, and future integration work.

## Documentation inventory

| Source | HUD relevance and current interpretation |
| --- | --- |
| `TODO.md` Part O, especially O7 | Previous Jev assessment: use existing browser/API boundary, control room and belief inspection; defer visible surface until real usage. Owner now explicitly requests the surface. |
| `TODO.md` Part P (starts at line 3868 in the inspected tree) | Full 35-capability inventory, source ownership, hardware and data blockers, the previously omitted observability fields, local workspace persistence, and the single panel-dispatch proposal. P1.1/P1.2 already repaired the old client; preserve those changes. |
| `TODO.md` Part R (starts at line 4307) | Earlier five-mode plan: OPS, AMBIENT, TRACE, BELIEF, CONTROL; vendored anime/Motion/uPlot, local fonts, queued operator intent, SSE, render coverage, reduced-motion gates. It explicitly forbade React/npm/3D. This newer owner request supersedes those UI technology restrictions. |
| `docs/systems-plan.json` | Authoritative task registry. Relevant tasks: 45.F4 unattended review; 45.R4 control actions; 45.R5 belief inspector; 45.R6 shell; 45.R7 ambient; 45.R8 trace; 45.R9 panel dispatcher; 26.R5 event stream; 06.R4 voice-to-content. The verified 2026-10-03 batch completes only 45.R6 under the owner's newer spatial direction. |
| `docs/SYSTEMS.md` | Generated registry overview. Do not hand-edit to claim completion. |
| `docs/SYSTEMS-DETAILS.md` | Governing projection model; S31 diagnostics and performance budgets; S45 explainability/control; queued intent versus mutating an in-flight turn; S06 document and S26 perception ownership. |
| `docs/JEV-REPORT.md`, “The visible surface” | Earlier model preference for an interactive control room and belief visibility, preserving existing HTTP/WS boundary. Its low-confidence first-screen preference is not a design requirement. |
| `docs/MASTER-PLAN.md` | Explicitly superseded historical snapshot. Not used as a current implementation authority. |
| `src/afon/brain/hud.py` | Actual read-only snapshot producer; 16 current top-level fields, including identity metadata, observability, and the presentation-only HUD command stream. |
| `src/afon/brain/server.py` | Existing authenticated HUD/review routes, static `clients/` handler, trusted-client token injection for the old HUD only. Default HTTP port 8766. |
| `clients/hud/index.html` | Existing functioning client with uncommitted user improvements. Left intact. |
| `bench/test_hud.py`, `bench/test_hud_render.py` | Snapshot and rendering regressions; previously invisible data must remain discoverable. |

The Obsidian memory pointer in `CLAUDE.md` was checked but its target file does not exist at the recorded path. No assumptions were taken from that missing note.

## Evaluation of the proposed architecture

The hybrid architecture is a sound fit: one spatial coordinator, a registry of canvas adapters, and purpose-specific rendering engines. Installing an engine does not create its data source. Keep interaction and visualization separate from brain authority.

1. A Vite build is a development toolchain, not a required production service. Compile React to static files and continue serving them through the existing Python HTTP/static boundary. The localhost Vite server is for development. The earlier plan conflated a build dependency with an always-on runtime.
2. Use a fixed **12 by 12 usable workspace** below a single command/search field. There is no status bar, navigation rail, footer, toolbar, or background dock. An “infinite plane” and a bounded 12x12 screen are different coordinate systems; this implementation uses the bounded screen. Add a separate camera/pan transform only if a future workspace needs an infinite plane.
3. React Grid Layout alone owns tile drag/resize geometry. A second react-dnd engine is unnecessary. Motion acts on nested panels, avoiding two engines writing the same transform. Preset/focus/background transitions use `layout`/`layoutId`; during direct dragging, spatial layout animation is disabled. Narrow screens stack rather than squeezing four panels into unreadable quarters.
4. Persist serializable layout only: stable IDs, slot geometry, focus and background order. Keep callbacks, files, WebGL instances, media objects and authorization outside that record. Validate storage before restoring it. Pointer, keyboard, local text commands, and Afon's bounded remote commands all use the same typed reducer. A stream ID plus monotonic sequence cursor makes snapshot polling idempotent; commands from an unfamiliar stream are applied only while fresh.
5. Backgrounding preserves component session state; the one search surface is the restore path, so a separate dock is unnecessary. Hidden PDF/WebGL views stop rendering. Local audio is an explicit exception and continues until paused or dismissed. Dismiss releases resources. Unlimited retained heavyweight renderers would exhaust memory, so future imported-document/model caches need an LRU budget.
6. Full focus remembers the prior grid. Critical approval UI must be orthogonal to layout: closing an approval overlay should restore the previous state, not always force quad. The current preview does not invent an approval state machine or bypass the brain gate.
7. Never display fake VRAM allocation, weights, percent-complete or initialization logs. Use actual fetch/parse/render phases and unknown progress when no denominator exists. Conversation animation must follow actual token events; a typewriter package cannot synchronize speech on its own.
8. A general website cannot reliably be embedded. Frame restrictions involve CSP `frame-ancestors` and `X-Frame-Options`; CORS mainly governs script access/fetch. A Playwright-controlled browser needs a separate capture/input/stream gateway. rrweb is replay instrumentation, not a universal browser stream. This preview creates no iframe that pretends to bypass those restrictions.
9. Browser HLS players do not receive raw RTSP. Cameras need an RTSP-to-WebRTC/HLS gateway, authorization, stream lifecycle, and a recording/time-index API for history. Those sources are not configured here.
10. Keep the owner's cyan/dark-glass palette, use local fonts, keyboard alternatives, high-contrast readable text, no fake listening waveform, and zero CSS transition duration with reduced motion. The Hallmark/UI-UX guidance informed these controls and the responsive checks; its marketing-page themes and anti-glass defaults were overridden by the explicit brief.

## Dependency decisions by canvas

Versions are resolved in `clients/hud-spatial/package-lock.json`. React is pinned to the 19.2 minor line because installed R3F 9.7.0 declares `>=19 <19.3`; the initial attempt to select React 19.3 was rejected normally, without `--force` or `--legacy-peer-deps`.

| Canvas | Selected engine / alternative | Installation and implementation status |
| --- | --- | --- |
| Spatial shell | React 19.2, TypeScript, Vite, Tailwind 4, RGL 2, Motion and Lucide | Installed; working search-plus-grid client, local fonts, typed reducer, and idempotent Afon presentation command stream. No modal library or XState runtime is needed for this shell. |
| 1 Conversation/memory | Native streamed React text + TanStack Virtual | Virtualizer installed for the future stream. Current conversation view honestly reports no transcript source. No typewriter package or fabricated history. |
| 2 Documents/PDF | react-pdf with its matched PDF.js and locally bundled worker | Installed and implemented for local PDFs: page jump, previous/next, current-page text highlighting. No private `PDFFindController` coupling. Whole-document search, speech coordinates and library-backed document retrieval remain future adapters. |
| 3 3D inspector | Three.js + R3F + Drei; official Three GLTFLoader | Installed and implemented: initially empty scene, Afon-authored safe primitives, orbit/zoom, local self-contained GLB, and mesh/vertex inspection. No fabricated specimen, separate three-stdlib dependency, OBJ ingestion, or AI mesh endpoint. |
| 4 Browser | Existing browser tool + future capture/input gateway | Connection placeholder. Reuse the existing Python browser ownership; do not install a second Puppeteer service solely for the UI. No rrweb until replay is a named requirement. |
| 5 Diagnostics | Recharts | Installed; actual snapshot values and sampled latency chart, raw detailed health/loops/providers/reliability/trace/unattended sections. No Tremor duplication or unmeasured circular gauges. CPU/GPU/VRAM/network collector absent. |
| 6 Decisions | Semantic React list and native controls | Existing deferred objective decisions and approval summaries render. TanStack Table and shadcn generation would add no value to this small list. |
| 7 Goals | Semantic progress list now; React Flow for actual dependency graphs | React Flow installed as a foundation; current snapshot contains linear objectives, not edges or completion denominators. No invented percentages or dependency arrows. |
| 8 Audio | Howler directly, native range controls | Installed; local audio, play/pause/volume, background playback. No React-Howler wrapper required. Focus timers and music-service adapters remain future work. |
| 9 Approval/voice | Native accessible controls; existing brain approval gate | Summaries render; action buttons disabled. Payload has no stable approval IDs and no HUD action endpoint. No microphone, modal dependency, or fake live waveform. Use native Web Audio only after the actual input lifecycle exists; defer wavesurfer. |
| 10 Cameras | hls.js plus native video; future WebRTC path | hls.js installed; camera gateway and recording timeline absent. No video.js duplication; native range suffices for a future basic scrubber. |
| 11 Code sandbox | Monaco + xterm; isolated execution service | Deferred installation until code/execution transport is implemented. Sandpack only for an actual web preview use case, not as a general secure execution boundary. |
| 12 Agent monitor | Current semantic view; React Flow reserved for real edges | Real `working_on`, `loops`, and `unattended` snapshot data render now without exposing private model reasoning. A node graph waits for an actual event/edge contract. |
| 13 Home/IoT | R3F for a surveyed 3D plan; SVG for 2D | 3D foundation installed; HA connection, device inventory, room geometry and telemetry required. D3 unnecessary before a real heatmap. |
| 14 Knowledge graph | 2D force graph first; WebGL when measured scale needs it | Deferred; requires real memory entities, edges, provenance and selection query. Do not promise thousands of nodes at 60fps without measuring. |
| 15 Security | Existing health/reliability/unattended evidence first; time series with Recharts | Real operational-risk evidence renders with an explicit warning that it is not a firewall feed. Network events remain absent; defer Deck.gl and Visx until a real geospatial or dense custom rendering need exists. |
| 16 Portfolio | Lightweight Charts + existing Recharts for KPIs | Deferred; no portfolio/market-data contract. Trading is a separate authorized action flow and is not implemented by displaying prices. |
| 17 Calendar | FullCalendar standard React plugins | Deferred; calendar data/mutation adapter absent. Premium timeline plugins need a separate licensing decision; ordinary grid views do not imply predictive scheduling. |
| 18 Spectrum | Native AudioContext/AnalyserNode + existing R3F | Engines available from browser/installed stack; deferred microphone/audio analyser integration. No extra visualization wrapper required. |

All 18 canvases have registry entries and can be opened. Connection placeholders are explicitly labelled; they are not claimed as implemented backend integrations.

## Jev review

One request to official `https://api.typesafe.ai/v1/systemone`, authenticated with `TYPESAFE_API_KEY` read locally from the root `.env`. The key was neither printed nor included in the evaluation state. Model returned: `jev-1.13.0`. Usage: 1,299 input tokens, 191 output tokens.

The supplied context included the owner's new requirements; existing Python/static architecture; dirty worktree; all 15 snapshot keys; missing action IDs and integrations; explicit override of earlier no-React/no-3D planning; proposed dependency choices; serializable state; offline behavior; renderer lifecycle; and the rule against starting the live brain solely for a preview. It did not include unrelated repository data, root .env contents, conversations or biometrics.

| Question | Returned answer |
| --- | --- |
| Add static React client / replace brain / reject React | Add static React client: probability 1.00, confidence 1.00 |
| Core plus first canvas engines / all alternatives / shell only | Core plus first canvas engines: probability 1.00, confidence 1.00 |
| Keep approvals unavailable until IDs and existing gate route exist? | Yes probability 0.96 |
| Separate RGL outer transform ownership from Motion? | Yes probability 0.92 |
| Keep callbacks out of serialized state? | Yes probability 0.92 |
| Grounded local/live-capable preview / invented live data / wait for all integrations | Grounded preview: probability 1.00, confidence 1.00 |

No answer in this bounded review fell in the ambiguous range, so no clarification call was needed. These are model preferences within the supplied options, not empirical proof or an independent safety approval. Installation compatibility, code inspection and browser tests decide whether the implementation works.

The 2026-10-03 raise batch asked Jev again because the canonical `45.R6` wording still described the superseded five-mode/no-React shell. The request used the same root-secret discipline and model `jev-1.13.0`. With the owner's later spatial requirements and the remaining authority gates included in context, Jev selected the spatial React direction over the legacy presentation plan (1.00/confidence 1.00), selected a shell/control batch rather than prematurely building every integration (1.00/confidence 1.00), supported a bounded brain-side presentation command bus consumed by the existing typed reducer (0.93), and supported leaving missing data integrations explicitly open (0.96). No result was ambiguous enough to require a follow-up.

## Data and authority

`DATA_COVERAGE` declares shell identity/presence/system/control fields, goals/tasks, decisions/approvals, agents, operational risk, and diagnostics' full observability set. A unit test reads the real Python producer to guard against newly emitted fields being forgotten. Browser fixtures exercise actual visible output and details.

The development proxy only permits GET of HUD and review JSON; rejects other routes/methods; sets no-store; applies request timeouts; disables redirect following; uses the configured server-side bearer token. No browser action endpoint was added. The lazy `control_hud` tool publishes only bounded presentation intents to a process-local ring; it cannot approve, invoke another tool, mutate an in-flight turn, or touch the operating system. No root `.env` is copied into the client, no secret is placed in a `VITE_` variable, and no independent brain/autonomy process is started.

The spatial client lives under `clients/hud-spatial/`; the bounded command bus and lazy tool live under `src/afon/brain/`. The original HUD HTML remains intact. The canonical system registry now records 45.R6 as verified while leaving the five later HUD raises open. Changes are uncommitted and unpushed.

## Remaining work in a concrete order

1. Integrate the static build and trusted auth bootstrap into the existing brain deployment flow, then verify the command stream against a deliberately started brain. The development preview stays honest while the brain is parked.
2. Continue the remaining raises as separate systems: 45.R7 ambient, 26.R5 event stream, 45.R8 trace, 45.R4 audited control actions, 45.R5 belief inspection/correction, then 45.R9 panel dispatch. Presentation control completed here does not satisfy any action gate.
3. Add real transcription, document lookup, browser output and now-playing adapters through the existing boundary. Keep per-source stale/error states.
4. Add camera/device sources when configured; do not infer live surveillance from an installed player. Build recording timelines against real timestamps.
5. Add expansion adapters and their selected engines as concrete tasks. Measure graph scale, memory use and rendering budgets before adding more WebGL contexts.
6. Profile and split the remaining large lazy renderer chunks if measured startup or memory evidence warrants it.

## Primary references checked

- [React Grid Layout v2 API and hooks](https://github.com/react-grid-layout/react-grid-layout)
- [Motion layout animations](https://motion.dev/docs/react-layout-animations)
- [React-PDF setup and PDF.js worker](https://github.com/wojtekmaj/react-pdf)
- [R3F on-demand rendering](https://r3f.docs.pmnd.rs/advanced/scaling-performance)
- [hls.js supported playback](https://github.com/video-dev/hls.js)
- [TypeSafe official API contract](https://docs.typesafe.ai/api)

## Verification record

Measured on 2026-10-03 for the 45.R6 raise batch:

- `npm run build`: TypeScript and the production build pass. Fonts and the PDF worker remain local. Vite reports the known >500 KB advisory for the Three/PDF/main chunks; this is documented work, not a false performance claim.
- `npm test`: 12/12 pass, including layout invariants, malformed storage rejection, focus restoration, resize displacement, every canvas lifecycle, and exact coverage of the Python snapshot producer.
- `npm run test:browser`: 12/12 pass in headless Microsoft Edge. The suite covers the search-only shell, absence of header/nav/footer/rail/dock, pointer drag and resize, focus/restore, background state retention, local PDF state, initially empty 3D plus command rendering, fresh remote-command consumption exactly once, real snapshot fields, truthful loaders, reduced motion, keyboard focus, and 320/375/768/1024/1440px geometry.
- `bench/test_hud_modes.py`: 24/24 pass. It verifies the bounded sequence stream, safe command enums/colors, all 18 IDs, fail-quiet snapshot projection, lazy tool discovery/handler registration, initial empty 3D state, search-plus-grid DOM contract, loader/reduced-motion contract, and local assets.
- Existing `bench/test_hud.py`: 28/28 pass. Focused Ruff and Python compilation checks pass for the new/changed backend modules and gate.
- Legacy `bench/test_hud_render.py`: **21/21 green on 2026-10-03**. The reproduced 8/18 regression was repaired in the separate `clients/hud/index.html`: dynamic identity, loop state, turn trace, provider health, unattended work and the compact `hud_control` sequence render again. A headless Edge file load produced all eight cards with zero page-JavaScript errors. P1.1/P1.2 are marked done again in `TODO.md`.
- The live tool catalog now includes all **153/153** registered tools, including `control_hud` (`test_website_claims.py` 10/10). Graphify was rebuilt after the new module; the regenerated routing manifest resolves all **219/219** routes and its gate passes 22/22, so both `tool:control_hud` and `group:hud` reach real graph nodes.
- The VPS transfer and content verifier now exclude `node_modules` symmetrically; the spatial HUD build artifacts remain deployable without shipping 22,753 developer-dependency files. The cross-platform, stubbed deploy-prune drill passes **23/23** and cannot resolve a configured real SSH target.
- Desktop 1440px and mobile 320px screenshots were visually inspected after the browser checks. The rounded workbench remains legible and contained at both sizes.
- Localhost root is live at `http://127.0.0.1:5173/`; the Vite server is loopback-only. The configured brain read remains unavailable while the deliberately parked brain is not started. The preview does not launch it.

Frontend fixtures cannot establish real voice capture, camera feeds, approval authority or production backend availability. The brain-side tool-to-snapshot command seam is covered hermetically, but an end-to-end voice turn requires the brain to be deliberately unparked under its separate operating gate. No production deployment, commit or push was performed.
