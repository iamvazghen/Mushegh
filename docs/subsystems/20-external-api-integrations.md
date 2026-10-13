# S20 — External API Integrations

> **One line:** Third-party APIs, called with one declared timeout and retry policy, kept inside a four-token credential budget.
> **Status:** dark — code complete, controls nothing; blocked on credentials for the integrations that are not enabled. A recollection, not a record, says the registry's `status` string read "complete for now" until 2026-10-03: `docs/systems-plan.json` is untracked, so no prior string is recoverable and this cannot be checked · **Registry:** S20 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** M07 · **Decisions:** D-62, D-46, D-13

## Purpose

This is the one place an outbound call to somebody else's service happens, and the one place
the policy for such a call is written down. The policy layer is real: every integration's
timeout and retry class is declared in a single table in `src/mushegh/brain/tools/base.py`,
and every integration without credentials returns the typed not-configured sentinel
rather than a sentence describing an outage.

**The system is dark.** The code is complete and it controls nothing, because the API keys
for the integrations that are not enabled were never installed. The registry records this
(`dark: true`, `dark_blocker: "API keys for the integrations that are not enabled."`), and
`docs/subsystems/README.md` marks it dark against M07. Under D-46 dark work is not progress.

The three fates are wire, complete, or delete, in that order (M07). **This one looks like
wire, not delete**: for it, the policy table and the not-configured contract are load-bearing
for S19 and S26 too, and Google OAuth is the only externally verified credential in the
system; against it, every further integration is a fifth credential and D-62 admits exactly
four. So one integration survives and the rest are deleted — an owner decision with a fate
recorded, not an engineering task. What the owner sees today is a working assistant that
declines, in one sentence, anything needing a key that was never installed. That is the
designed failure, and much better than the alternative it prevents: a plausible-sounding
answer about a service that was never reached.

## Structure

All brain-side, all in the always-on process. No second daemon, no distinct security
boundary, so under D-42 this belongs to the S03 belt and the S36 credential story.

| Path | Integration | Credential |
|---|---|---|
| `src/mushegh/brain/tools/base.py` | The policy: `not_configured()`, the error taxonomy, the timeout and retry table, `is_not_configured()` | none |
| `src/mushegh/brain/google.py` | One OAuth app for Gmail and Calendar; `access_token()`, `api_get()`, `api_post()` | `MUSHEGH_GOOGLE_*`, one refresh token |
| `src/mushegh/brain/tools/gmail.py`, `tools/calendar.py` | Mail and calendar handlers on that one token | shared |
| `src/mushegh/brain/tools/maps.py` | `travel_time`, `find_place` — read-only; Google first when keyed (live traffic, ratings), else the open engine | Optional Google Maps key (Routes API + Places API (New)) |
| `src/mushegh/brain/tools/openmaps.py` | The keyless engine: Photon→Nominatim geocoding, OSRM→Valhalla driving, Valhalla walk/bike, Transitous public transport, Overpass→mirror→Photon places. No live traffic, no ratings | None |
| `src/mushegh/brain/tools/web.py` | `web_search` (Tavily), `scrape_url`, `browser` | Tavily key |
| `src/mushegh/brain/tools/wolfram.py` | `compute` — exact numbers, never guessed | Wolfram app id |
| `src/mushegh/brain/tools/notion.py` | Read, write, comment on shared pages | Notion internal integration token |
| `src/mushegh/brain/tools/stock.py`, `src/mushegh/brain/stock.py` | Consumables and quotes | provider key |
| `src/mushegh/brain/mynews.py` | RSS headline signals. Off unless configured, **and no longer collected** — 41.R4 closed the unprompted path under D-34; the module stays for a focused, asked-for session | `MUSHEGH_MYNEWS_URL` |
| `src/mushegh/brain/webhooks.py` | The reverse direction: HMAC-SHA256 verified inbound POSTs | shared secret |
| `src/mushegh/brain/telegram_bridge.py` | Bot API long-poll, so a message works with the laptop off | bot token |
| `src/mushegh/brain/cache.py` | In-process TTL cache for slow-moving reads; the Redis tier was dropped 2026-09-20 | none |

Outbound flow: handler → declared timeout and retry class from `tools/base.py` → HTTP →
result classified into `not_configured` / `auth` / `network` / `rate_limit` /
`unavailable` / `not_found` → speakable text. One attempt plus the declared retries; an
authentication failure is never retried, a 429 is.

`tools/smarthome.py` is the local API and belongs to S28, not here — it is a LAN
integration, not a third party, and it carries one of the four D-62 tokens.

What it stores: nothing per integration. Audit lines under `audit/`, one per call, and the
TTL cache in memory. Credentials live in `.env`, gitignored.

## Goals

1. An integration without credentials says so, typed, in one sentence. Threshold: **100%**
   of unconfigured cases return the sentinel; **0** plausible-sounding failures.
2. One declared timeout and retry policy for every integration. Threshold: **0** tool
   modules opening their own HTTP client; every declared value finite and bounded.
3. A transient failure is retried as declared and then reported, never invented. Threshold:
   **0** answers without a tool call behind them.
4. Slow-moving reads are cached with an explicit TTL. Threshold: **100%** of cached reads
   carry a stated TTL, no cache entry without one.
5. An integration near its quota degrades before it fails. Threshold: **0** quota failures
   that were not preceded by a degradation signal.
6. One source for credentials, and it is not `.env`. Threshold: **1** source, **0** keys
   duplicated between `.env` and anything else.
7. The credential set stays at four. Threshold: **4** tokens, and any addition is on the
   record as beating that list (D-62).

### 7.1 Proposed addition — name the store goal 6 is about (D-93)

Goal 6 says "one source, and it is not `.env`", and this document's own open
questions admit the store has no name. The re-review named one.

**[getsops/sops](https://github.com/getsops/sops) (MPL-2.0) with
[FiloSottile/age](https://github.com/FiloSottile/age) (BSD-3)**, as a
**subprocess adapter**: `sops -e` / `sops -d` driven by
`src/mushegh/setup_wizard.py` and `bench/check_config.py`. No daemon, so it
structurally cannot become the second failure domain that open question 1 is
testing for.

**This is a base addition, not a capability.** It replaces a hand-rolled scheme
for a file that already exists; it makes no goal reachable that is not already
listed. What it does buy is the honest version of goal 6: rotating a leaked key
becomes one command instead of a hunt, no key sits in a pasteable plaintext
file, and the result is still legible to a text editor in 2036 (D-54).

**The limit, stated before anyone discovers it:** it does not protect against
someone holding the VPS filesystem, because unattended decrypt needs the key on
the host. A compromised host still wins.

**Gate:** `bench/check_config.py`'s single-source case, which does not exist yet.
PRINCIPLES §1 three commands, in order:

```
sops filestatus .env
journalctl -u openmushegh-brain -n 200 --no-pager | grep -i "not configured"
grep -c "_KEY\|_TOKEN" .env
```

**Not proposed:** trufflehog, which has better detector breadth and the wrong
shape — a second binary, an AGPL dependency, and live credential *verification*
is not what belongs beside a write-boundary screen. See
[INTEGRATIONS.md](../INTEGRATIONS.md) §2 and §6.

## Benchmarks

- **G1** · B1 · `bench/test_no_result_sentinels.py`, `bench/test_phase11_integrations.py`.
  Threshold 100% sentinel returns across the unconfigured set. Last: **not yet measured**.
- **G2** · B1 · `bench/test_api_policy.py`. Threshold 0 self-declared HTTP clients; every
  timeout and retry value finite and bounded. Last: **not yet measured**.
- **G3** · B1 · `bench/test_new_integrations.py` for the failure-classification half. The
  no-fabrication property is B4: a turn returning content with no successful tool call behind
  it is a hard failure. Threshold: **0**. Last: **not yet measured**.
- **G4** · B1 · `bench/test_phase9b_cache.py` extended for the TTL case. Threshold 100% of
  cached reads carry a stated TTL. Last: **not yet measured**. 20.R1 is open.
- **G5** · B1 · `bench/test_api_policy.py` [quota] — the named case does not exist yet.
  Threshold 0 quota failures without a preceding degradation signal. Last: **not yet
  measured**.
- **G6** · B1 · `bench/check_config.py` extended for the single-source case — the named case
  does not exist yet. Threshold 1 credential source. Last: **not yet measured**. 20.R3 is
  open, and which store it means is an open question below.
- **G7** · B4 · invariant, not a test. Threshold: **4** credentials in `.env` at most, plus
  any a decision has named. No counting script exists. Last: **not yet measured**.
- **20.E1** · B3 · zero fabricated answers from an unconfigured or failing integration
  across a week of real use — the D-43 bar. Threshold: **0** fabricated answers over **7**
  days. Last: **not yet measured**.

## Failure modes

- **A key is missing.** The turn ends in the not-configured note. Correct, and the owner
  sees a decline. Diagnose: `journalctl -u mushegh-brain -n 200 --no-pager | grep -i "not
  configured"`, then check the key is present in `.env` without printing it.
- **A service is down or slow.** Retries fire as declared, then the turn reports the
  failure. The owner hears about an outage that a single dropped packet caused — the exact
  sentence 20.F3 was written to remove. Diagnose: the audit lines under `audit/` for that
  tool, and the error class the policy table assigned.
- **A 401 is treated as retryable.** Quota is spent to be told "no" again, and the turn
  takes three times as long. Diagnose: `bench/test_api_policy.py` for the table, then the
  audit line's error class.
- **Credentials drift.** Two sources disagree and the wrong one wins. Diagnose:
  `grep -c "_KEY\|_TOKEN" .env` for the count, never the values.
- **The system stays dark and nobody decides.** The floor tasks read `done`, the dashboard
  reads "complete for now", and the actual state is that no key was ever installed. This is
  the failure the M07 decision exists to end. Diagnose: the `dark` and `dark_blocker`
  fields in `docs/systems-plan.json`, and M07 in `docs/ROADMAP.md`.

## Open questions

1. 20.R3 moves credentials out of `.env` into "the password store". D-01 rejected HashiCorp
   Vault, so that phrase needs naming — what is the one store, and does it run on the
   always-on host without becoming a second failure domain?
2. D-62 lists CalDAV. The code's calendar path is a Google OAuth refresh token covering
   Gmail and Calendar on one app. Which one is the calendar credential, and does the
   Calendar half of the Google grant count against the same four?
3. M07 wants a recorded fate. Wire, complete, or delete — and if wire, is the survivor the
   one weather/transit token D-62 already names?
