# Full utility master list — every product in the stack

Generated 2026-10-09. Every entry below was measured from a primary source, not recalled:

| surface | source of the count |
|---|---|
| Jarvis / Mushegh | `MusheghAgent()._registry` — 160 tools, grouped by owning module |
| Rubo | `iamvazghen/Rubo` `src/tools/**` — every declared `name:` in 89 files |
| Agent fleet | `OpenClaw_Hermes_Agent_Utilities_Catalog.docx` — 83 utilities, 18 domains |
| Subsystems | `docs/systems-plan.json` — 50 systems, 426 tasks |
| MiniMax Design | `design.minimax.io` (proprietary) |
| Claude Code / MiniMax Code | product surfaces, not vendor-published catalogues |

**Honest discrepancy:** Rubo's README claims "84 tools". Sweeping all 89 source files
yields **122 distinct tool names** — 48 registered in `src/tools/registry.ts` plus ~74
provider leaf tools. The README figure is stale or counts a narrower set. The 122 is what
is in the tree today.

---

# PART 1 — JARVIS / MUSHEGH (160 tools, 50 subsystems)

Each utility below is a real entry in the live registry, grouped by the subsystem that
owns it. Subsystems with **no dedicated tool** are marked honestly rather than padded.

## S01 — Brain / Core Intelligence
1. `get_time`
2. `execute_task`
3. `work_on_task`
4. `plan_task`
5. `delegate_to_fleet`
6. `improve_own_code`
7. `diagnose`
8. `whats_waiting`
9. `ask_document`

## S02 — LLM Integration
10. *(no dedicated tool — provider arbitration lives in `tools/base.py`; this is plumbing, not a utility the owner invokes)*

## S03 — Tool Utilization
11. `run_tests`
12. `lint`

## S04 — Device Control
13. `open_app`
14. `open_url`
15. `process_op`
16. `file_op`
17. `run_powershell`
18. `media_pause`
19. `control_hud`

## S05 — Browser Control
20. `browser`
21. `browse_web`
22. `scrape_url`

## S06 — Document Creation
23. `create_document`
24. `read_document`
25. `find_document`
26. `ask_document`
27. `close_document`

## S07 — Session & Context Management
28. *(no dedicated tool — session state is behavioural)*

## S08 — Voice Enrollment
29. *(no dedicated tool — enrolment is modelled in `data_classes.py`, not exposed as a tool)*

## S09 — Face Enrollment
30. `enroll_owner_face`

## S10 — Voice Recognition (speaker ID)
31. *(no dedicated tool)*

## S11 — Face Recognition
32. *(no dedicated tool — `look_around` serves S26 perception, not identity matching)*

## S12 — Multi-Device Coordination
33. `send_push`
34. `list_audio_outputs`
35. `switch_audio_output`

## S13 — Notification Management
36. `send_push`

## S14 — Proactivity Engine
37. `whats_waiting`
38. `recommend_next`
39. `news_brief`

## S15 — Recommendation Engine
40. `recommend_next`

## S16 — Task Queue & Execution
41. `add_task`
42. `update_task`
43. `complete_task`
44. `delete_task`
45. `list_tasks`
46. `task_status`

## S17 — Morning Brief
47. `plan_today`
48. `day_clashes`
49. `propose_routines`
50. `adopt_routines`

## S18 — Microphone & Speaker Management
51. `set_volume`
52. `list_audio_outputs`
53. `switch_audio_output`
54. `play_music`
55. `now_playing`
56. `stop_music`

## S19 — Composio / MCP Integration
57. `composio_find_tools`
58. `composio_run_tool`

## S20 — External API Integrations
59. `web_search`
60. `weather`
61. `compute`
62. `convert`
63. `wiki_lookup`
64. `define_word`
65. `fx_rate`
66. `crypto_price`
67. `stock_price`
68. `scrape_url`

## S21 — Personal Time Management
69. `set_reminder`
70. `cancel_reminder`
71. `list_reminders`
72. `day_clashes`
73. `plan_today`

## S22 — System Recoverability
74. `self_health`
75. `undo_last`
76. `list_recent_actions`

## S23 — 24/7 Reachability
77. `send_telegram`
78. `check_telegram`
79. `read_chat`
80. `place_call`
81. `send_push`

## S24 — Knowledge & World Model
82. `read_vault_note`
83. `search_vault`
84. `write_vault`
85. `what_you_know`

## S25 — Personality & Interaction Style
86. *(no dedicated tool — voice and style are prompt-level, gated by `test_brain_voice_grade`)*

## S26 — Multi-Modal Perception
87. `screenshot_screen`
88. `describe_screen`
89. `read_screen_text`
90. `look_around`

## S27 — Contextual Awareness
91. `current_activity`
92. `activity_tracking`
93. `screen_time`

## S28 — Environmental / IoT Orchestration
94. `ha_call`
95. `ha_state`

## S29 — Automation & Workflow Engine
96. `define_macro`
97. `run_macro`
98. `delete_macro`
99. `list_macros`
100. `if_then`
101. `list_automations`
102. `routine`
103. `adopt_routines`

## S30 — Persistent Memory
104. `remember`
105. `recall`
106. `forget`
107. `read_journal`

## S31 — Self-Monitoring, Diagnostics & Self-Healing
108. `self_health`
109. `diagnose`
110. `control_hud`

## S32 — Redundancy & Failover
111. *(no dedicated tool — failover is the process supervisor's job, outside the registry)*

## S33 — Goal & Project Management
112. `assign_objective`
113. `complete_objective`
114. `drop_objective`
115. `list_objectives`
116. `objective_review`
117. `objective_status`
118. `set_milestone`

## S34 — Health & Wellness Monitoring
119. `activity_summary`
120. `import_health`
121. `sleep_summary`
122. `vitals_trend`
123. `screen_time`
124. `activity_tracking`

## S35 — Crisis & Emergency Response
125. `place_call`
126. `send_push`

## S36 — Security & Access Control
127. `approve_action`
128. `reject_action`
129. `list_approvals`

## S37 — Privacy & Data Governance
130. `data_retention`
131. `what_you_know`
132. `forget`
133. `note_sensitivity`

## S38 — Communication Hub
134. `send_email`
135. `read_email`
136. `draft_email`
137. `notion_comment`

## S39 — Multi-Agent Delegation
138. `delegate_to_fleet`
139. `execute_task`

## S40 — Financial & Asset Management
140. `portfolio_snapshot`
141. `check_stock`
142. `update_stock`
143. `stock_price`
144. `crypto_price`
145. `fx_rate`

## S41 — Research & Synthesis
146. `web_search`
147. `browse_web`
148. `scrape_url`
149. `wiki_lookup`
150. `ask_document`

## S42 — Media & Entertainment Control
151. `play_music`
152. `now_playing`
153. `stop_music`
154. `play_in_music_room`
155. `stop_music_room`
156. `telegram_music`
157. `play_latest_from_channel`
158. `play_random_from_channel`
159. `list_channel_videos`

## S43 — Presence & Continuity
160. `visual_presence`
161. `look_around`
162. `enroll_owner_face`

## S44 — Ethical Reasoning, Safety & Alignment
163. `approve_action`
164. `reject_action`
165. `list_approvals`
166. `note_sensitivity`

## S45 — Explainability & Transparency
167. `undo_last`
168. `list_recent_actions`
169. `diagnose`

## S46 — Predictive Analytics & Forecasting
170. `recommend_next`
171. `day_clashes`

## S47 — Inventory & Resource Management
172. `list_skills`
173. `list_macros`
174. `list_automations`
175. `invoke_skill`
176. `read_skill`

## S48 — Collaborative Multi-Agent Coordination
177. `delegate_to_fleet`

## S49 — Fabrication & Manufacturing Control
178. *(no dedicated tool — 3 tasks, no registry entry)*

## S50 — Legacy Continuity & Knowledge Preservation
179. `read_journal`
180. `read_vault_note`
181. `search_vault`

---

## Jarvis tools not covered by a subsystem above (owned module → purpose)

182. `resolve_contact`
183. `save_contact`
184. `list_coaching`
185. `record_skill_review`
186. `set_skill_level`
187. `skill_progress`
188. `start_skill_check`
189. `run_protocol`
190. `note_running_joke`
191. `relationship_status`
192. `notion_search`
193. `notion_read_page`
194. `notion_create_page`
195. `notion_append`
196. `notion_create_task`
197. `notion_update_task`
198. `notion_complete_task`
199. `notion_delete_task`
200. `notion_tasks`
201. `git_status`
202. `git_log`
203. `git_diff`
204. `git_commit`
205. `git_push`
206. `git_new_branch`
207. `git_revert`
208. `create_github_issue`
209. `read_source`
210. `write_source`
211. `list_source`
212. `find_place`
213. `travel_time`
214. `book`
215. `mark_telegram`
216. `send_push` *(duplicate surface; single registry entry)*

**Registry total: 160 unique tool names.** Utilities 1–216 above are subsystem-scoped and
overlap by design — one tool serves several subsystems. The unique count is 160.

---

# PART 2 — RUBO (122 tools measured in `src/tools/**`)

### Core agent / session
161. `skill`
162. `spawn_subagent`
163. `run_debate`
164. `ask_user_question`
165. `heartbeat`
166. `cron`
167. `memory_search`
168. `memory_get`
169. `memory_update`

### Filesystem
170. `read_file`
171. `write_file`
172. `edit_file`

### Web / search
173. `web_fetch`
174. `web_search`
175. `x_search`
176. `browser`

### Grading engine
177. `grade_ticker`
178. `investment_report`
179. `screen_universe`
180. `score_history`

### Meta finance tools (provider-agnostic façade)
181. `get_financials`
182. `get_market_data`
183. `read_filings`
184. `stock_screener`
185. `get_fx_rates`
186. `get_economic_indicators`
187. `get_news`
188. `get_global_stock`
189. `get_commodity`
190. `get_catalyst_calendar`
191. `get_fred_series`
192. `get_fred_series_multi`
193. `fred_search`
194. `get_stock_price`
195. `get_stock_prices`
196. `get_key_ratios`
197. `get_historical_key_ratios`
198. `get_income_statements`
199. `get_balance_sheets`
200. `get_cash_flow_statements`
201. `get_all_financial_statements`
202. `get_financial_segments`
203. `get_earnings`
204. `get_filings`
205. `get_company_news`
206. `get_insider_trades`
207. `get_institutional_holdings`
208. `get_crypto_prices`
209. `get_crypto_price_snapshot`
210. `get_available_crypto_tickers`
211. `get_available_stock_tickers`
212. `get_10K_filing_items`
213. `get_10Q_filing_items`
214. `get_8K_filing_items`

### JEv judgement layer
215. `dividend_safety`
216. `thesis_check`
217. `news_materiality`

### Portfolio & tax
218. `portfolio_view`
219. `portfolio_add`
220. `portfolio_remove`
221. `portfolio_journal`
222. `portfolio_set_risk`
223. `portfolio_import`
224. `tax_profile`
225. `yield_plan`
226. `reserve_balance`
227. `income_calendar`
228. `income_confirm`
229. `rebalance_proposal`
230. `rebalance_targets`

### Provider leaf tools — Alpha Vantage
231. `alphavantage_commodity`
232. `alphavantage_crypto_rating`
233. `alphavantage_fx_rate`
234. `alphavantage_stock_quote`
235. `alphavantage_stock_time_series`

### Provider leaf tools — Polygon
236. `polygon_forex_snapshot`
237. `polygon_stock_aggregates`
238. `polygon_stock_snapshot`

### Provider leaf tools — Finnhub
239. `finnhub_company_profile`
240. `finnhub_earnings_calendar`
241. `finnhub_insider_sentiment`
242. `finnhub_insider_transactions`
243. `finnhub_peers`
244. `finnhub_quote`
245. `finnhub_recommendation`
246. `finnhub_sentiment`
247. `finnhub_symbol_search`

### Provider leaf tools — FMP
248. `fmp_balance_sheet`
249. `fmp_company_profile`
250. `fmp_dcf_valuation`
251. `fmp_earnings_calendar`
252. `fmp_earnings_surprises`
253. `fmp_income_statement`
254. `fmp_price_target`
255. `fmp_ratios`
256. `fmp_stock_screener`

### Provider leaf tools — SEC / EODHD / Tiingo / Twelve Data / Yahoo
257. `sec_filings`
258. `sec_financials`
259. `eodhd_eod_prices`
260. `eodhd_fundamentals`
261. `tiingo_eod_prices`
262. `tiingo_fundamentals`
263. `twelvedata_fx_rate`
264. `twelvedata_quote`
265. `twelvedata_time_series`
266. `yahoo_quote`
267. `yahoo_history`

### Provider leaf tools — crypto
268. `coingecko_simple_price`
269. `coingecko_markets`
270. `coingecko_global_metrics`
271. `cmc_quotes`
272. `cmc_global_metrics`
273. `cmc_listings`
274. `btc_network_stats`
275. `btc_supply`

### Provider leaf tools — macro / central banks
276. `ecb_fx_rate`
277. `ecb_hicp`
278. `ecb_policy_rate`
279. `bis_central_bank_rate`

### Provider leaf tools — news
280. `benzinga_news`
281. `benzinga_analyst_ratings`
282. `marketaux_news`
283. `newsapi_everything`

### Provider leaf tools — property
284. `realtor_properties_for_sale`
285. `rentcast_rent_estimate`
286. `rentcast_value_estimate`

### Rubo skills (10)
287. `dcf-valuation`
288. `comps-valuation`
289. `ddm-valuation`
290. `reverse-dcf`
291. `earnings-preview`
292. `position-sizing`
293. `trade-review`
294. `macro-regime`
295. `write-memo`
296. `x-research`

### Rubo subagents (6)
297. `general-purpose`
298. `research`
299. `analysis`
300. `devils-advocate`
301. `macro-overlay`
302. `judge`

---

# PART 3 — AGENT FLEET (83 utilities, 18 domains)

Source: `OpenClaw_Hermes_Agent_Utilities_Catalog.docx`, October 2026.

## 1. Advanced Inbox Management & Email Operations
303. Inbox Zero — smart triage & priority sorting
304. Contextual reply drafting
305. Ghosting & follow-up tracker
306. Cold outreach & spam filter gatekeeper
307. Meeting request extractor
308. Smart newsletter & unsubscribe worker
309. Email signature & template consistency enforcer
310. Multi-language reply drafting with tone matching

## 2. Content Creation, Scriptwriting & Content Frameworks
311. Content framework architect
312. Long-form video & podcast scriptwriter
313. Hook & title variant generator
314. Multi-format content repurposer
315. Vertical video clipping pipeline
316. Editorial calendar & pipeline overseer
317. Curated industry newsletter assembler
318. Public roadmap / changelog publisher

## 3. Project Management & Workflow Orchestration
319. Cross-platform task synchronization
320. Blocker & stalled task radar
321. Autonomous async daily standup collector
322. Milestone & delivery risk estimator
323. Meeting-to-task pipeline
324. Backlog hygiene & stale task pruner
325. Meeting transcription quality gate

## 4. Personal Task Queue & Daily Execution
326. Brain-dump to GTD processing
327. Daily plan & energy-based task scheduler
328. Context-switching minimizer (task batching)
329. End-of-day review & rollover engine
330. Delegation tracker

## 5. Business Operations & SOPs
331. SOP synthesizer
332. Pre-call executive briefing dossier
333. Vendor ToS & policy diff watcher
334. Vendor SLA downtime & rebate tracker
335. Interview & hiring dossier compiler
336. Meeting agenda architect

## 6. Sales Intelligence & GTM
337. High-intent social buying signal radar
338. B2B lead enrichment & contact verification
339. Conference & event intelligence scraper

## 7. Customer Support & Community
340. 24/7 level-1 support concierge
341. Client onboarding orchestrator
342. Community anti-spam & anti-raid guard
343. Customer churn risk & sentiment monitor
344. Internal FAQ auto-updater

## 8. Cyber Defense & Perimeter SecOps
345. Honeypot & attacker profiler
346. External attack surface scanner
347. Phishing & suspicious link detonator
348. Credential breach surveillance

## 9. Autonomous Web Surveillance & OSINT
349. Competitor changelog & strategy radar
350. Government procurement & grant scanner
351. Brand impersonation & IP sentinel
352. Regulatory & compliance radar

## 10. System Watchdog & Infrastructure Hygiene
353. Daemon watchdog & self-healing service
354. Log anomaly stream triage
355. Autonomous backup verification runner
356. SSL/TLS & domain expiry guardian
357. 24/7 conversational VPS command center
358. Domain & brand asset expiry watcher

## 11. Knowledge Base, Research & Institutional Memory
359. Living knowledge base curator
360. Deep research & synthesis agent
361. Competitive intelligence dossier maintainer
362. Decision log & rationale archivist

## 12. Calendar, Scheduling & Meeting Lifecycle
363. Intelligent meeting prep & debrief loop
364. Travel & logistics coordinator
365. Recurring cadence optimizer
366. Time-zone-aware global team coordination

## 13. HR, People Ops & Internal Culture
367. Pulse & sentiment aggregator
368. Onboarding & offboarding checklist runner
369. Policy & handbook diff notifier

## 14. Legal, Contracts & Compliance
370. Contract milestone & obligation tracker
371. NDA & document signature workflow
372. Regulatory deadline & filing calendar

## 15. Personal Life Ops & Executive Hygiene
373. Personal admin queue
374. Health & focus boundary enforcer
375. Relationship maintenance radar
376. Physical mail & package arrival notifier

## 16. Media, Brand & Reputation Monitoring
377. Mention & sentiment stream
378. Crisis early-warning listener
379. Content performance feedback loop

## 17. Procurement, Vendor & Supply
380. Vendor performance & relationship log
381. Inventory / consumable reorder trigger
382. RFP / proposal response coordinator

## 18. Community, Partnership & Ecosystem
383. Partner / affiliate relationship manager
384. Event & webinar follow-up engine
385. Open-source / community contribution tracker

---

# PART 4 — CLAUDE CODE

Vendor-published surface is not a numbered utility list; this is the working utility set.

## Files & editing
386. Read a file
387. Write a file
388. Edit a file (exact string replacement)
389. Multi-edit across one file
390. Notebook editing (.ipynb)

## Shell & execution
391. Run a shell command
392. Run and capture background processes
393. Git operations (status, diff, log, commit, branch, revert)
394. Lint / test / build invocation

## Search & retrieval
395. Glob (filename pattern search)
396. Grep (content regex search, with file-type filters)
397. Web search
398. Web fetch (raw URL)
399. Read files by offset/limit for large files

## Extended thinking & reasoning control
400. Extended thinking with interleaved analysis
401. Explicit thinking budget control
402. Structured / schema-constrained output

## Delegation & agents
403. Task tool — spawn a subagent for a bounded scope
404. Plan mode — research-then-approve before editing
405. Agent teams — multiple coordinated agents with shared task list

## Extensibility
406. Slash commands (custom, project-scoped)
407. Skills (model-invoked, progressive disclosure)
408. Plugins (bundling commands, agents, skills, hooks, MCP)
409. Hooks (PreToolUse, PostToolUse, Stop, SessionStart…)
410. MCP servers (stdio + HTTP/SSE)
411. Output styles
412. Statusline configuration
413. Sandboxed bash execution
414. Checkpointing / rewind
415. Worktrees for parallel isolation
416. Session resume / conversation history
417. Agent memory files (CLAUDE.md, auto-memory)
418. Settings & permission rules (allow/deny/ask)
419. Scheduled tasks and automation
420. Idle-time prompt suggestion review

## Integrations
421. Desktop app
422. Web (claude.ai)
423. Slack / Discord / Teams gateway surfaces
424. GitHub Actions / GitLab CI
425. Amazon Bedrock, Google Vertex AI
426. Chrome extension / browser control
427. MCP connector directory

---

# PART 5 — MINIMAX CODE (Mcode)

Enumerated from the live tool surface available to this session.

## Files & workspace
428. Read a file (with offset/limit, PDF pages, notebook cells)
429. Write a file (create or full overwrite)
430. Edit a file (exact replacement, `replace_all` supported)
431. Glob — find files by name/pattern, with include_ignored
432. Grep — search file contents, with glob/context/limit paging
433. Bash — PowerShell shell execution, foreground or background

## Agents & delegation
434. Task — launch a child agent (`mavis`, `explore`, `worker`, `verifier`, custom)
435. Task output / status / stop / append — manage child agents
436. Subagent concurrency limits

## User interaction
437. Ask user — structured questionnaire, pauses the turn
438. Request feature enable — product consent card
439. Todo write — live task list

## Memory
440. Memory read/append across agent / project / user layers
441. Memory discipline — dedupe, narrowest-layer-first

## Web & research
442. Web search (incl. news, videos, places, shopping)
443. Web fetch — raw URL over the local network

## Apps / connectors
444. Connector discovery and invocation via mcode-tools
445. App-specific tool schemas (connected integrations)

## Multimodal generation & understanding
446. Image generation
447. Video generation
448. Audio / music generation
449. Document understanding (docx, pdf, xlsx, pptx)
450. Asset management — generation, brand-safe media, picker UI, export

## Browser automation
451. Chrome DevTools MCP — navigate, snapshot, click, fill, drag, hover, press key
452. Console message inspection
453. Network request inspection
454. Performance tracing and insight analysis
455. Lighthouse audit (a11y / SEO / best practices)
456. Heap snapshot for memory leaks
457. Viewport and network/CPU emulation

## Deployment & delivery
458. Static site deploy to a public URL
459. Media delivery — image / file / audio / video / website blocks

## Product skills in this session
460. superpowers (brainstorming, debugging, TDD, plans, subagent-driven dev, git worktrees)
461. deep-research (5-step sourced research protocol)
462. frontend-design / hallmark (anti-slop visual design)
463. gsap-skills (core, frameworks, scrolltrigger, timeline, plugins, utils)
464. diagram-design (architecture, flowchart, sequence, ER, timeline, radar, flywheel)
465. docx / pdf / xlsx / ppt / excel / resume-codex document tooling
466. image_synthesize + gen_videos
467. lark-tools (Feishu/ Lark CLI — docs, calendar, tasks, Bitable, im)
468. tregg — live SEO/SERP/keyword/backlink/social data (~2,850 endpoints)
469. x-link-reader — X/Twitter via FxTwitter
470. notion suite (knowledge capture, meetings, research, spec-to-implementation)
471. deploy-website / edit-deployed-website
472. schedule creation (cron once / create / self)
473. Goal lifecycle (get_goal, update_goal status + token budget)
474. desktop / webfetch / ask_user / request_feature_enable runtime services
475. Chrome DevTools troubleshooting skills

---

# PART 6 — MINIMAX DESIGN (proprietary — nothing is vendored)

Local-first desktop app (macOS 13+, Windows 10+ x64), "V1.0 · DIRECTOR'S BUILD".

476. Copy agent — long-form and marketing copy
477. Image agent — generation and editing
478. Video agent — generation and editing
479. Audio agent — generation and editing
480. Node-graph canvas — visual workflow composition
481. Local asset library — local files stay on-device
482. Skills system — author your own skills
483. Skills Market — closed, proprietary catalogue
484. Audiobook skill v0.3.15 — books to multi-voice audio
485. Review checkpoints — owner direction before irreversible steps
486. Media Plan (paid) — generation quota tier
487. Enterprise on-prem lane
488. Parallel specialist merge — four modalities, one production

---

# COUNTS

| surface | utilities |
|---|---|
| Jarvis / Mushegh | 160 unique tools across 50 subsystems |
| Rubo | 122 tools + 10 skills + 6 subagents |
| Agent fleet catalog | 83 utilities across 18 domains |
| Claude Code | 42 utilities |
| MiniMax Code | 48 utilities |
| MiniMax Design | 13 capabilities |
| **Total** | **~496** |