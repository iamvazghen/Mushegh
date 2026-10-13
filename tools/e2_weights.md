---

## 01.J29 — 2026-10-13: 01.E2 is not gated on Calibration. The weights say it cannot be.

01.E2 is "overall behavioural >=95, no category <90". Its own evidence note says
"01.E2 IS ALMOST ENTIRELY GATED ON ONE CATEGORY" and names Calibration, which
carries 24 of 50 scored scenarios. That is a claim about arithmetic, so it was
checked rather than repeated.

From `bench/behavioral_suite.py scenarios()`, 75 scenarios, total weight 89.0:

| category | n | weight | share |
|---|---|---|---|
| **Calibration** | **26** | **32.0** | **36.0%** |
| Combination | 5 | 7.5 | 8.4% |
| Safety / Autonomy | 3 each | 4.5 each | 5.1% each |
| the other 13 categories | 2-4 each | 2.0-4.0 each | 2.2-4.5% each |

Calibration is 36.0%, not 40.0% — the suite has grown since the note was written.
But the share is the smaller half of the problem. The two clauses of 01.E2 pull
against each other, and the ceiling that follows is not obvious:

    other 16 categories at their 90 floor -> Calibration must reach 103.9  IMPOSSIBLE
    other categories at 92              -> Calibration must reach 100.3  IMPOSSIBLE
    other categories at 95              -> Calibration must reach  95.0  reachable
    other categories perfect           -> Calibration must reach  86.1  reachable

**Best overall achievable with Calibration perfect (100) and every other
category sitting exactly at its permitted 90 floor: 93.6.** That is below the bar.

So `>=95` is **not reachable on Calibration alone at all.** It requires the rest
of the brain above 90 as well: for Calibration to reach 95 on its own, the other
sixteen categories must average 95 too, and for Calibration to merely hit 100 the
others must average 92.2. The evidence frames 01.E2 as one category's problem and
the weights say it is sixteen.

Last recorded overall is **89.1** (2026-10-10, median-3, healthy chain), so the
gap is 5.9 points — and the cheapest 5.9 points are NOT in the category everyone
has been working on.

**What this changes.** Reaching 01.E2 means lifting the long tail, not tuning the
head. Fourteen categories sit at 2-5% each; moving all of them from 90 to 95 is
worth about 2.2 points of overall on its own, which is more than half the gap.

**And what it does not decide.** Whether a weighted mean over scenarios is the
right measure of "behavioural readiness" at all is a judgement with consequences
— a category with 26 scenarios outvotes one with 2 — and that is the owner's
call, not something to quietly re-weight. Recording the ceiling is not the same
as lowering the bar.

Re-run this with `python tools/_e2_weights.py` (it needs no model and no
credentials; `rollup()` is pure for exactly this reason).