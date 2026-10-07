# S05 — Browser Control

> **One line:** A real, visible browser on the owner's own screen, driven end to end, with a degrade chain that says when a page could not be read.
> **Status:** complete for now · **Registry:** S05 · 3/3 floor, 1/3 raise in progress, 0/1 elite
> **Milestones:** none assigned in [../ROADMAP.md](../ROADMAP.md) · **Decisions:** D-07, D-34

## Purpose

There are two browsers, deliberately. One is headless and cloud-side, for one-off
extraction: `web.browse_web` over Browserbase. The other is persistent and local — a
real Chromium window on the owner's screen, with a profile that keeps logins between
sessions, which is what "open it and show me" means. This document covers the second.
The distinction is recorded in the module itself, because conflating the two is how a
headless fetch ends up answering as though the owner had been watching his own screen.

The refusal here is about honesty, not capability. A blocked, paywalled or JS-empty page
is reported **as such** (05.F3) and never summarised from the model's own prior
knowledge. The scrape and search degrade chain is typed (05.F2): every falloff — cloud
fetch, local browser, page text, refusal — has a named shape the caller can distinguish.
A summary written from memory is indistinguishable from one written from a page, and the
owner has no way to tell which he got.

D-07 applies throughout: reading a page is a read-only query, but *submitting* is not. A
form that spends money or sends data requires a confirmation, and `05.R1` now enforces that in
code — `submit_needs_confirm()` in `src/afon/brain/tools/browser.py`, called from
`proactive.confirm_required`. It is hermetically green and still owes D-43's seven days. D-34 applies too: a page that merely looked interesting is not a
reason to raise the topic with the owner.

If this is absent, Afon can extract text but cannot show anything, and every answer
about the web is second-hand.

## Structure

```
utterance ──> tools/browser.py   one tool, an `action`, ten ops:
                                  open · click · fill · type · press · read
                                  screenshot · new_tab · back · close
                    │
                    │  forwarded to the laptop whenever it is connected
                    v
   laptop: src/afon/edge/pc_agent.py   the visible Chromium, persistent profile
                    │
                    v
   brain:  src/afon/brain/pc_link.py   (see S04)
   text:   src/afon/brain/tools/web.py  the headless/cloud extraction path, degrade chain
```

| Concern | Where |
|---|---|
| The single `browser` tool and its ten actions | `src/afon/brain/tools/browser.py` |
| Forwarding to the laptop | `src/afon/edge/pc_agent.py`; `test_pc_agent_routing.py` |
| Screenshot transport | `bench/test_screenshot_transport.py` |
| Degrade chain, typed (05.F2) | `src/afon/brain/tools/web.py`; `test_web_fallback.py` |
| Blocked / paywalled / empty body (05.F3) | `tools/web.py`; `test_web_fallback.py` extended with the empty-body case |
| D-07 confirm tier for submits | `src/afon/brain/approvals.py`, `argcheck.py` |

**Process ownership:** edge, when the laptop is connected — the browser has to be visible
on the owner's screen to be worth anything. It runs in-process in the brain only when the
brain itself is on the laptop. **What it stores:** the persistent browser profile
(logins, cookies) lives on the laptop and never leaves it. The brain stores no session
state for the browser today, which is the gap 05.R2 names.

## Goals

1. **The owner can drive a visible browser by voice** — open, click, fill, type, read,
   screenshot, navigate — and see each step happen on their own screen.
2. **Logins persist between sessions** through a local profile that never leaves the
   laptop.
3. **A blocked, paywalled or JS-empty page is reported as unreadable**, never
   summarised from the model's own knowledge (05.F3).
4. **The scrape and search degrade chain is typed**, so every falloff is
   distinguishable at the call site (05.F2).
5. **No form is submitted without a confirmation** when the submit spends money or sends
   data (D-07, 05.R1).
6. **A multi-tab task keeps its tabs and can resume** after an interruption
   (05.R2) — not yet built.
7. **Downloads land in a known directory and are reported by path** (05.R3) — not yet
   built.

## Benchmarks

| # | Goal | Tier | Command / drill | Threshold | Last measurement |
|---|---|---|---|---|---|
| 1 | Ten browser actions visible | B1 | `bench/test_pc_agent_routing.py` | 10/10 route when the laptop is connected | not yet measured |
| 2 | Logins persist | B1 | `test_pc_agent_routing.py` + `bench/test_screenshot_transport.py` | profile survives a browser restart; 0 credentials cross the tailnet | not yet measured |
| 3 | Unreadable page reported | B4 | `bench/test_web_fallback.py` extended, empty-body case | 0 summaries produced from model knowledge when the body is empty | not yet measured |
| 4 | Typed degrade chain | B1 | `bench/test_web_fallback.py` | every falloff has a distinct typed outcome; 0 untyped | not yet measured |
| 5 | Confirm before submit | B1 | `bench/test_browser_submit_confirm.py` (05.R1) | 0 money-sending or data-sending submits without a confirmation | **45/45, 2026-10-06** — hermetic only; the seven-day bar is owed |
| 6 | Multi-tab task state | B1 | `bench/test_browser_session.py` — **planned gate, the file does not exist** | a task interrupted and resumed keeps its tabs | not yet measured — nothing built |
| 7 | Downloads by path | B1 | `bench/test_browser_session.py` [downloads] — same planned file | every download reported by absolute path | not yet measured — nothing built |

Goal 3 is the one with teeth: it is a B4 invariant rather than a pass rate, because a
fabricated page summary is not a quality problem, it is a lie the owner cannot detect.
The raise tier is 1 of 3 in progress. Two of the three gates — 05.R2 multi-tab state and
05.R3 downloads — still have no script at all, both waiting on `bench/test_browser_session.py`.
The third, 05.R1, has its own gate as of 2026-10-06: it did **not** end up extending
`bench/test_confirm_tier_documented.py`, because that file asserts the doc and `CONFIRM_TIER`
agree with each other and this is a behavioural claim about when the gate fires — two different
questions, and the doc-consistency one must stay able to fail on its own. 05.E1 (a five-step real web task end to end)
has a planned gate, `test_web_task_e2e.py`, which also does not exist.

## Failure modes

**The page is summarised from memory.** The model was shown a block page, a paywall, or
an empty DOM, and answered anyway from what it already knew. This is the defining
failure of this system: the answer is fluent, plausible, and wrong, and the owner has no
signal. Reproduce with the empty-body case in `test_web_fallback.py`. In the field, the
tell is an answer with no quoted page text in the trace row.

**The browser runs on the wrong machine.** Ops run in-process because the laptop link is
down, so a window opens somewhere the owner cannot see. The forward-or-fallback logic is
in `tools/browser.py`; the honest failure is to say the visible browser is unavailable
rather than to open a window on the VPS.

**An extract silently returns nothing.** A degrade path returns an empty string that
reads as "the page says nothing". The typed chain (05.F2) is what turns this into a
named failure instead of a blank.

**A submit happens without a confirmation — and the opposite, which is what was actually
true.** This doc previously said a spend or a send was one voice command away. It was wrong in
an instructive direction: `browser` sat in `proactive.CONFIRM_TIER` with no dynamic rule, so
`confirm_required` fell through to its final `return True` and **every** action confirmed,
`read` and `open` included. Both are real failures and they are not the same one — a gate that
never fires lets a purchase through, and a gate that fires on every page read teaches the owner
to say yes without reading it, after which the one that mattered is waved through with the rest.
That second failure is the one `ha_call`'s own comment names for lamps, and it matters more here
because this browser carries his logged-in sessions. Reproduce either direction with
`bench/test_browser_submit_confirm.py`.

**A download vanishes.** The file lands somewhere untracked and the owner is told it
worked. 05.R3 is open, so there is no directory contract yet.

## Open questions

1. 05.R1 is answered by `action` plus one bit of state: whether anything has been typed since
   the last navigation. The destination is deliberately **not** consulted — a URL allowlist is
   wrong the first time a checkout moves hosts. The open residue is narrower: the armed flag is
   one boolean for one browser, so two tabs driving forms in parallel would share it and
   over-gate. That is the safe direction, and it stays until tabs actually do that.
2. Multi-tab task state (05.R2) and downloads (05.R3) both gate on
   `test_browser_session.py`, which does not exist. Is that one file or two, and does
   tab state live on the laptop or in the brain?
3. 05.E1 asks for a five-step real web task with recorded fixtures, but no corpus of
   recorded pages exists in the repo. What is the fixture source — a captured set, or a
   live run each time?
