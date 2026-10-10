# S01 — status as of 2026-10-10 08:0x CEST

Written at the end of a long working session so the next reader does not have to reconstruct it
from four appended registry notes. **Everything here was measured; nothing is projected.**

The authoritative record stays `docs/systems-plan.json` (S01 tasks) and `docs/DECISIONS.md`.
This file is orientation, not authority.

---

## 1. What state the system is in

| | |
|---|---|
| Registered suite | **252 passed, 0 failed, 0 skipped**, exit 0, on a clean environment |
| Behavioural overall | **not currently quotable** — see §3 |
| Registry | 50 systems, 427 bounded tasks, `systems_plan.py check` green |
| Public-surface scan | clean |
| Doc integrity | 8/0, 95 decisions, no gaps |
| Ruff | clean on every file touched |

01.E1 and 01.E2 both remain **open**. Neither is closed, and neither should be recorded as
progress until it is measured on a chain with more than one reachable provider.

---

## 2. Defects found and fixed this session

Ten, all found by reading a *result* and asking why — never by a failing gate alone.

### The measurement was wrong, repeatedly

This was the dominant theme, and it is worth stating plainly because it cost the most.

1. **The uncertainty classifier docked genuine admissions.** Calibration read 63.5, but reading
   the replies showed *"you know there isn't one. Best depends entirely on the task"*, *"that
   debate is still very live… proponents argue X, opponents point to Y"* and *"I can't check the
   forecast"* were all scored **overconfident**. Root causes were mechanical: the lexicon held
   `"depends on"`, which does not match *"depends **entirely** on"*; and `"still"` sat in
   `_CONTRASTIVE`, so an ordinary adverb split a balanced answer and made the supporting date
   after it read as overconfidence. **Three misses of one shape across two nights is what a
   regex is for** — `_DEPENDS_RE` and `_NEEDS_RE` now cover the pattern, not the instance.
   Gate: `test_uncertainty` 34 → **46/46**, every negative still failing correctly.

2. **The scorer scored a failed tool at 100.0.** `proactivity_list` earned full marks on the
   reply *"I couldn't fetch your reminders, sir."* — a failure — for two independent reasons:
   the expectation check counted a tool as satisfied if it was *invoked*, and the reply
   contained the word "reminder", which is one of the `expect_text` substrings. Corrected to
   require tools that ran **and** returned something `looks_failed` does not recognise.

   **Every behavioural number measured before this fix was optimistic.** Comparisons across it
   are invalid unless both sides used the same scorer.

3. **The intent-classes holdout conflated two axes.** It derived the expected label from
   `expect_tools`, so a two-intent turn whose tools are all reads was expected to be `lookup`
   when `multi` is correct. It only passed by luck: most compound scenarios paired a read with a
   write and fell out of the comparison entirely, so the question was never asked. Fixed using
   the scenario's own category. Holdout went **19/22 → 24/27**.

4. **Two route exemptions were falsified by measurement.** `list_skills` ("listing is answering
   a question") and `read_journal` ("journal reads are prompted by the owner") both assumed a
   question needs no tool. Both were asked directly and both produced **fabrication** — a
   journal entry that had never been read, and a skills list recited from memory.

### Real bugs in the system

5. **Two UTC-day bugs.** The daily audit file was named by UTC, so between 00:00 and 02:00 local
   everything filed into *yesterday's* file. Worse, `review.unattended_runs()` read UTC days
   too — so the unattended-review surface reported **nothing** for two hours every night, which
   is the single failure that surface exists to prevent. One rule now, `audit._owner_day()`,
   consumed by the writer, the reviewer and four gates; pinned by six assertions.

6. **`define_word` was completely broken.** The dictionary API returns 403 for every word from
   this host; `http_get` raises on a non-2xx, so the handler's graceful branch was unreachable.
   The owner heard a raw `HTTPStatusError`.

7. **`tool_error` handed the model a traceback class name to read aloud**, in third person, to
   the owner. The class name stays in the log; the owner gets words.

8. **402 was classified `bad_args`**, so a service wanting payment was reported as a malformed
   call — and a caller retrying on `bad_args` would retry forever.

9. **A memory correction produced a clarifying question.** `memory_update` scored 48.0 because
   *"Actually it's Petrova — can you fix that one?"* routed to nothing, and JEv asked *"what
   exactly should I do with it?"* **instead of acting**. Two causes: a proper noun in
   *substitution* position was counted as a competing antecedent (*"change that to Dr Petrov"*
   refused to resolve because Petrov competed with itself), and the copula guard vetoed
   *"it IS Petrova"*. `memory_update` → **96.5**, Memory → **~84.8**.

10. **A `.gitignore` bug of my own.** Twelve artifact patterns written with backslashes, which
    gitignore does not accept, so **none matched** — `git add -A` would have published eleven
    run transcripts. Replaced with one `bench/_*.txt` wildcard.

---

## 3. Why the behavioural number is not quotable

Three consecutive runs gave **82.2, 77.8 and 59.1**. That is not variance.

Probing each chain entry individually at 08:0x:

```
LIVE   minimax:MiniMax-Text-01
DEAD   groq:llama-3.3-70b-versatile   404 — that model id does not exist
DEAD   groq:llama-3.1-8b-instant      404 — that model id does not exist
DEAD   gemini-3.5-flash                unreachable
DEAD   mistral-small-latest           unreachable
DEAD   groq/compound                  unreachable
DEAD   vercel:deepseek/deepseek-v3.2  402 — out of credit
DEAD   vercel:alibaba/qwen3.5-flash   402 — out of credit

1 of 8 entries can answer
```

The 59.1 is the Vercel gateway running out of credit mid-run. **That is not a quality
regression**, and reading it as one would be the wrong lesson.

**One reachable provider is a primary, not a fallback.** With only MiniMax answering, any
category score is a measurement of MiniMax rather than of Afon.

### This invalidated an earlier recommendation of mine

I had advised reordering the chain to put Vercel first, on the grounds that the shipped primary
was dead. I had already flagged that this violated the four `test_finetune` invariants. It is
also operationally wrong: following it would leave a chain whose only reachable provider is out
of credit. The correct statement is narrower — **the dead entries cost latency, and the fix is to
repair or remove them, never to promote the gateway above a working primary.**

`tools/check_providers.py` now checks liveness, which `test_finetune` structurally cannot: it
pins the chain's *shape* and stayed green throughout. It is deliberately **not** a registered
gate — a red suite caused by a billing state is a fact about the account, not a code defect.

---

## 4. Blocked, and by whom

| blocker | owner |
|---|---|
| Vercel gateway out of credit — no fallback exists | **owner** |
| Both groq model ids 404; current ids would give the free tier `test_finetune` asks for | **owner** |
| Jina returns 402 on every URL, so `scrape_url` is capped | **owner** |
| What counts as a calibration *outcome*, before `brain/calibration.py` can be wired | **owner** |
| Fleet category — explicitly reserved, not touched | **owner** |
| 7 `behavioral-suite-temp` rows in the real Notion board, 307 rows in `afon_tasks.sqlite` | **owner** |
| Infisical workspace, and reading its NOASSERTION licence | **owner** |
| REA MCP registration — the installer refuses without Ghidra/IDA | **owner** |
| Ratify `test_missing_arg` strengthening; scorer bands; `clause_completion` repair | **owner** |
| D-08 end-to-end diff approval, D-43 seven-day run | **owner** |

---

## 5. State of work delivered earlier in the session

Green, gated, and separate from the provider question:

- **Skills suite** — 26 playbooks including `integration-utilization`, `prompting`,
  `sessions-and-context`, `secrets-and-access`, `owner-model`. Gated by `test_skill_suite`
  (123/123) for truncation and phantom tool names, and published on the docs site.
- **`afon/shared/secrets.py`** — environment wins → Infisical → `age` floor, wired before
  `Settings()`. Graceful degradation **proven live**: an unreachable endpoint logs a class name,
  boots in 3.56 s, raises nothing, and the report object has no field that can hold a value.
  Gate 52/52.
- **`afon/brain/calibration.py`** — ECE, Brier, reliability bins and a *signed* overconfidence
  index. Returns `None`, never `0.0`, when there is nothing to measure. Gate 49/49. **Not
  wired** — it needs the outcome definition.
- **`tools/verify_repos.py` / `check_repo_exists.py`** — 105 candidate repos proposed by five
  research agents; 61 verified, 31 exist, **13 did not exist at all**, 7 more cited under the
  wrong owner. Recorded in `docs/INTEGRATION-MATRIX.md` §0.

---

## 6. The next step

Not another category score. The sequence is:

1. **Owner restores a second provider.** Everything else is unmeasurable until then.
2. Run `python tools/check_providers.py` and confirm **≥2 live**.
3. **Re-baseline** the behavioural suite once, on the repaired chain.
4. Only then work categories — and work the ones that are low **and** stable across two runs,
   because several moved 15–18 points between runs and chasing a noisy number is wasted effort.

01.E1 is expected to clear on a repaired chain: it measured **94.4** on a healthy two-model
chain against **83.4** on the shipped one, same code and same scenarios. 01.E2 needs eight
categories above 90 and is a much larger piece of work.