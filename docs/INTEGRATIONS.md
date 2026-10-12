# INTEGRATIONS — the verified repository inventory

Written 2026-10-07, for **D-93**. A four-slice re-review of all fifty subsystem
documents, against [PRINCIPLES.md](PRINCIPLES.md) §1 and §6.

**Authority: none.** [DECISIONS.md](DECISIONS.md) D-92 to D-94 carry the
decisions this inventory informed. This is the evidence behind them, the way
[EXTERNAL-EXECUTORS.md](EXTERNAL-EXECUTORS.md) is the evidence behind D-79 to
D-87. Nothing here is a proposal that has not already passed the filter.

**Every repository named here was verified live against the GitHub API.** Two
owner names that looked right (`Valetudo/Valetudo`, `Moonraker/Moonraker`)
returned 404 and were dropped and re-found by search rather than reported. A
phantom repo is worse than a blank, because it will be trusted.

**Every `src/mushegh/...` path cited here was verified to exist** before it was
written down, per [subsystems/README.md](subsystems/README.md) rule 1.

---

## 1. The two names this file uses

| Term | Meaning |
|---|---|
| **Base addition** | Small, local, boring, and debuggable with three commands: a protocol client, a parser, a test harness. It makes code that already exists correct. |
| **Significant improvement** | It changes what a system can do. One candidate cleared this bar in the whole review. |

**What the review returned across fifty subsystems:** 11 base additions,
1 significant improvement, 6 already covered by
[EXTERNAL-EXECUTORS.md](EXTERNAL-EXECUTORS.md), and a majority answering
HANDLER, SUBTRACT or WIRE. **Zero** additions went to S46, S47, S48, S49 or
S50, which carry deletion decisions — adding to a system being deleted is the
failure the charter was written to prevent.

---

## 2. Base additions

| Repo | Licence | For | Subsystem | Door | 2 AM, first command |
|---|---|---|---|---|---|
| [restic/restic](https://github.com/restic/restic) | BSD-2 | verified, deduplicated, incremental backup | S22 | subprocess | `restic snapshots` |
| [getsops/sops](https://github.com/getsops/sops) + [FiloSottile/age](https://github.com/FiloSottile/age) | MPL-2.0 / BSD-3 | credentials encrypted at rest in the env file | S20 | subprocess | `sops filestatus .env` |
| [wenet-e2e/wespeaker](https://github.com/wenet-e2e/wespeaker) | Apache-2.0 | PLDA scoring and EER measurement | S08, S10 | in-repo, **bench only** | `uv run python bench/test_phase5_identity_bench.py` |
| [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets) | Apache-2.0 | the five-language credential gap | S37 | subprocess sweep, **behind** `src/mushegh/brain/never_store.py` | `detect-secrets scan audit_log/` |
| [adbar/trafilatura](https://github.com/adbar/trafilatura) | Apache-2.0 | real article text instead of nav chrome | S41 | in-repo + its CLI | `trafilatura --url <url> --output-format json` |
| [polyvertex/fitdecode](https://github.com/polyvertex/fitdecode) | MIT | FIT binary to the vitals schema | S34 | in-repo | `python -m mushegh.brain.vitals` |
| [jgm/pandoc](https://github.com/jgm/pandoc) | GPL-2.0 | document format conversion | S06 | subprocess | `pandoc --version` |
| [beancount/beancount](https://github.com/beancount/beancount) | GPL-2.0 | parses the one ledger the owner may read | S40 | in-repo | `bean-check ledger.beancount` |
| [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis) | MPL-2.0 | generates the conflict pairs M26 must enumerate | S44 | in-repo, **bench only** | `uv run python bench/test_refusal_grades.py` |
| [openai/tiktoken](https://github.com/openai/tiktoken) | MIT | exact tokens for the catalogue budget | S03 | in-repo | `python -c "import tiktoken…"` |
| [Hypfer/Valetudo](https://github.com/Hypfer/Valetudo) | Apache-2.0 | cloud-free vacuum control | S42 | subprocess; it runs **on the device**, so it dodges D-42 | `curl -s <vacuum>/api/v1/status \| jq` |

**Two licence obligations to record rather than inherit.** `pandoc` and
`beancount` are GPL-2.0, and `wespeaker`, `hypothesis` and `sops` are not the
permissive licences their popularity suggests. All are acceptable for a private,
never-distributed install. Each becomes a real obligation the day Mushegh is
shared (D-57, D-60), and `THIRD_PARTY_NOTICES.md` is where that belongs.

**Two are bench-only on purpose.** `wespeaker` and `hypothesis` change *how the
bar is measured*, never the hot path. `speaker_gate.py` must stay exactly as
inspectable as it is now; the harness is where a better model belongs.

---

## 3. The one significant improvement

**[browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast)** and
**[Ying-Kai-Liao/jev-browser](https://github.com/Ying-Kai-Liao/jev-browser)**,
for S05. Already held in [EXTERNAL-EXECUTORS.md](EXTERNAL-EXECUTORS.md) §2, and
this review did not re-open it.

It earns the label because it changes the loop rather than filling a gap: one
typed JEv decision per browser step, over Chrome DevTools Protocol, with the
page observed as a numbered table. Published numbers are a demonstration rather
than a reliability benchmark — three runs per task on one profile.

**The blocker is a question, not a missing repository:** **M49** — can that MCP
server drive the browser the owner is looking at, with his profile? Yes buys
`05.R1` and `05.R2` as a config line. No, and we keep
`src/mushegh/brain/tools/browser.py` and port only the decision loop.

**What must not be traded away:** S05 exists for a *visible* Chromium with a
persistent profile. A headless agent driving its own browser somewhere he cannot
see is the cloud path already in `src/mushegh/brain/tools/web.py`, and the doc is
explicit that conflating the two is how a headless fetch ends up answering as
though he had been watching his screen.

---

## 4. Already covered — not re-litigated

[EXTERNAL-EXECUTORS.md](EXTERNAL-EXECUTORS.md) carries these; this review
confirmed the gaps and did not re-propose the libraries. Marked **ALREADY-COVERED**
in the subsystem documents: `mcode` and uv (build and coding), `aioesphomeapi`,
the Wyoming protocol, `zigpy`, `python-matter-server`, Frigate (hardware), the
Claude Agent SDK and Codex CLI (coding), the OpenClaw CLI over SSH (fleet),
Rubo (finance, read side only), `bookroom-sdk` (books, §6 above),
`src/mushegh/brain/mcp_client.py` (the MCP door, and it stays).

---

## 5. Wire, not add — the highest-value items cost zero dependencies

This is the finding, not a shortfall. Each of these unblocks more than any
repository in §2.

1. **Install the Home Assistant token (`28.F1`).** Four hours, one credential
   already inside the D-62 budget, and every IoT item in the roadmap is
   downstream of it. `src/mushegh/brain/tools/smarthome.py` is already the adapter.
2. **Write `emergency.md` by hand and delete `call` from `ACTIONS`.** The
   highest-stakes gap in thirteen subsystems is owner content, not a package.
3. **Add the ArcFace enrolment driver** behind `src/mushegh/brain/tools/camera.py`.
   The backend is already installed; the gap is a driver and a person standing
   in front of a camera.
4. **Set `MUSHEGH_WHISPER_LANGUAGE`.** Unset today, which leaves
   `src/mushegh/edge/stt.py` pinned to `en`, so a Ukrainian turn during a cloud
   outage is answered in English. One setting.
5. ~~**Make the delegation routing policy readable data** beside
   `src/mushegh/brain/fleet.py`.~~ **Already done, 2026-10-06/07 — this row was stale
   when written.** The policy is `SPECS` in `src/mushegh/brain/executors/__init__.py`:
   a frozen table of domain, tier, argv and parser per executor, with
   `candidates()` producing the ballot and `pick()` restricting Jev to it, so the
   choice is **not** made per call by the model — a verdict naming anything off the
   ballot is refused by `resolve()`. Gated by `test_executor_contract.py` (109) and
   `test_executor_arbitration.py` (43). Registry `39.R1`, `39.R5`. Two sessions were
   editing this repo on 2026-10-07 and this is the one row where they disagreed;
   corrected here rather than left, because a stale note is trusted.
6. **Run `32.E1`.** One hour of measured downtime instead of an architecture
   debate about a second brain host.

---

## 6. Evaluated and declined

Naming these is the point: each is the obvious answer to a question somebody
will ask again.

| Candidate | Why declined |
|---|---|
| **[666ghj/MiroFish](https://github.com/666ghj/MiroFish)** (AGPL-3.0, 76k★) | Fails PRINCIPLES §1 **at the install line**: Node 18 **+** Python 3.11–3.12 **+** uv **+** a frontend on :3000 **+** an API on :5001 **+** `ZEP_API_KEY`, a hosted commercial graph store. It is also a resurrection of S46, cancelled by D-28. Jev scored it **0.00 at confidence 1.00** — the most decisive answer in the set. It is good software and not an improvement to Mushegh. |
| **LangGraph and relatives** | D-77 already declined it as the cortex. |
| **A second MCP client library** | `src/mushegh/brain/mcp_client.py` is ~200 working lines of newline-delimited JSON-RPC that already does `initialize`, `tools/list` and `tools/call`. |
| **Temporal, APScheduler, huey, taskiq, any broker** | D-01. The queue is already a SQLite table and a bounded worker. |
| **Postgres, pgvector, `sqlite-vec`, litestream** | D-02. `sqlite-vec` was verified (Apache-2.0) and is still declined: pre-v1, it keeps the network embedding call, and it improves a recall p95 nobody has measured. |
| **mopidy** | A music *server* — a new daemon, refused by D-42. |
| **python-fido2** | There is nothing to override today, so D-14's override hardware would be a dark feature under D-46. |
| **Fuzzy relative-date parsers** | Inferring "next week" is the opposite of D-56's conservative branch, and it writes into a `KEEP_FOREVER` row. |
| **Uptime SaaS** | A fifth credential under D-62, and it moves the alarm onto infrastructure the owner does not control. |
| **trufflehog** | Better detector breadth than `detect-secrets`, wrong shape: a second binary, AGPL, and live credential *verification* is not what belongs beside a write-boundary screen. |
| **LiteLLM proxy router** | Declined by S02's own text: a second failure domain with its own config file. |
| **A scene classifier (YAMNet, PANNs, CLAP)** | Adds torch to a CPU already 1.7× over the STT budget, for work §C already defers. |
| **deepinsight/insightface, SYSTRAN/faster-whisper** | **Already installed.** Recommending them would have been a phantom add. |
| **bootandy/dust** | A sound tool, for code belonging to a system M06 deletes. |
| **promptfoo, Langfuse and observability layers** | Each is debugged through its own dashboard, which §1 treats as the tell of a non-boring dependency. |

---

## 7. What a proposal has to carry to appear in this file

1. A **verified URL**, checked this session, plus the licence.
2. The **door** it enters through: MCP server, subprocess adapter, or in-repo.
3. **Three commands** for 2 AM. No three, no row.
4. Whether it needs a **daemon**, a **new security boundary**, or a
   **third-party cloud account** — the three things that disqualify it.
5. **Base addition or significant improvement**, using §1's definitions.
6. The **decision it serves**, cited as a `D-nn`.

A library that is merely a library does not enter through the executor contract
at all — that rule is
[EXTERNAL-EXECUTORS.md](EXTERNAL-EXECUTORS.md) §6's, and it is the reason
`bookroom-sdk` was wired in-process rather than dispatched.

## Sources

- [restic/restic](https://github.com/restic/restic) · [getsops/sops](https://github.com/getsops/sops) ·
  [FiloSottile/age](https://github.com/FiloSottile/age) · [wenet-e2e/wespeaker](https://github.com/wenet-e2e/wespeaker) ·
  [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets) · [adbar/trafilatura](https://github.com/adbar/trafilatura) ·
  [polyvertex/fitdecode](https://github.com/polyvertex/fitdecode) · [jgm/pandoc](https://github.com/jgm/pandoc) ·
  [beancount/beancount](https://github.com/beancount/beancount) · [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis) ·
  [openai/tiktoken](https://github.com/openai/tiktoken) · [Hypfer/Valetudo](https://github.com/Hypfer/Valetudo)
- [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) · [Ying-Kai-Liao/jev-browser](https://github.com/Ying-Kai-Liao/jev-browser)
- [666ghj/MiroFish](https://github.com/666ghj/MiroFish) · [asg017/sqlite-vec](https://github.com/asg017/sqlite-vec) ·
  [benbjohnson/litestream](https://github.com/benbjohnson/litestream) · [mopidy/mopidy](https://github.com/mopidy/mopidy) ·
  [Yubico/python-fido2](https://github.com/Yubico/python-fido2) · [trufflesecurity/trufflehog](https://github.com/trufflesecurity/trufflehog) ·
  [bootandy/dust](https://github.com/bootandy/dust) · [Arksine/moonraker](https://github.com/Arksine/moonraker)
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/) · [AirGradient integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/airgradient)
