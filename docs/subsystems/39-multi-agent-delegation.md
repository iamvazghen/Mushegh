# S39 — Multi-Agent Delegation

> **One line:** other agents are tools Afon calls, never the voice the owner is talking
> to.
> **Status:** built, thin · **Registry:** S39 · 3/3 floor, 0/3 raise, 0/1 elite
> **Milestones:** none assigned · **Decisions:** D-05, D-08

## Purpose

D-05 is one sentence long and entirely about this system: the external agent fleet is a
tool, never the assistant. The charter is specific about why the line erodes — "the
moment an agent is handed an unconstrained interactive shell with root or network
access" — which is the honest failure mode, not a hypothetical one. The mitigation is
named in the same decision: sandboxed, AST/diff verified, never a shell.

So the capability here is narrow. Afon delegates a bounded brief, gets an answer back,
checks the answer, and reports it in his own voice. What is refused: an agent output
applied to the system without a verification gate, and any arrangement in which the
agent's output is delivered to the owner as if it were Afon's judgement.

The registry calls this "built, thin" and that is accurate rather than diplomatic.
Reachability, tracking and result verification all exist. The thing that makes delegation
*safe* — knowing which work goes to which agent, and proving an answer before acting on
it — is thin to the point of absent, and 39.R1 is the task that would fix it.

If it were absent, two things happen, both bad: Afon does everything himself and the
delegation path goes dark (D-46 gives dark code three fates, none of them "keep it for
later"), or the assistant identity leaks outward and the owner is talking to something
whose incentives he cannot inspect.

## Structure

| Path | Process | Role |
|---|---|---|
| `src/afon/brain/fleet.py` | brain | The fleet as one tool in Afon's brain, never his identity; transport is the gateway WebSocket |
| `src/afon/brain/delegation.py` | brain | 39.F2/F3 — a delegation is a tracked unit with a deadline, and its answer is checked before it is reported |
| `src/afon/brain/coordination.py` | brain | One row per unit of delegated work, claimed before it is worked and written only by the holder |
| `src/afon/brain/tasks.py` | brain | The task record the deadline and the result check hang on |
| `src/afon/brain/worker.py` | brain | The bounded autonomous loop — Afon doing focused work himself, which is the alternative to delegating |
| `src/afon/brain/code_improve.py` | brain | The shape D-05 asks for, already built for self-edits: branch-only, test-gated, reversible |
| `src/afon/brain/audit.py` | brain | Where a delegation, its verification and its outcome are recorded |

**Data flow.** Afon composes a brief, hands it to the fleet over the gateway
WebSocket, and `delegation.py` opens a tracked row with a deadline. The answer comes
back as text, is checked (39.F3), and only then may it be reported as fact. A
self-edit is the special case where the "check" is a diff plus a green suite on a
dedicated branch, which is the D-08 contract and the most concrete form of D-05's
"AST/diff verified" in the repo today.

**The honest gap.** The routing policy is thin and undeclared. `fleet.py` names a
transport, not a policy: there is no file, table or schema that says which kinds of work
go to which agent, so the choice is made per call by whatever the model does that turn.
The second gap is that D-05's verification requirement is implemented for self-edits
(diff, suite, branch) and only approximated for fleet answers (a result check, which is
not the same thing). Neither gap is dangerous today because the failure requires an
agent to be given access, and it has not been.

## Goals

1. The fleet is reachable as one tool among many, and never becomes the assistant
   (39.F1, D-05).
2. Every delegation is a tracked unit with a deadline and a result check — nothing is
   fire-and-forget (39.F2).
3. A delegated result is verified before it is reported as fact (39.F3).
4. No agent ever holds an unconstrained interactive shell, and no agent output is applied
   without a sandboxed, AST/diff verification gate (D-05).
5. A declared, testable routing policy exists: which kinds of work go to which agent
   (39.R1).
6. A delegation that stalls returns to Afon rather than hanging (39.R2).
7. Cost and value are accounted per delegation, so a route that never earns its keep is
   visible (39.R3).

## Benchmarks

| Goal | Tier | Command or drill | Threshold | Last measurement |
|---|---|---|---|---|
| 1 | B1 | fleet live check: `delegate_to_fleet` a read-only brief over the gateway WebSocket | 1 result returned; the acting identity on the reply is `brain`; 0 turns answered by an agent | not yet measured |
| 2 | B1 | `uv run python bench/test_delegation_tracking.py` | every delegation has a row, a deadline and a result check; 0 untracked; 0 without a deadline | registry records 39.F2 done; run not reproduced here — not yet measured |
| 3 | B1 | `uv run python bench/test_delegation_tracking.py` [verification] | a wrong or fabricated result is caught before it is reported; 0 unverified results reported as fact | registry records 39.F3 done; run not reproduced here — not yet measured |
| 4 | B4 | `grep -nE 'shell|os\.system|sudo|root' src/afon/brain/fleet.py src/afon/brain/delegation.py` | 0 interactive-shell grants; 0 root or network credentials passed to an agent | not yet measured — D-05 has no dedicated test, and the pattern is a tripwire, not proof |
| 5 | B1 | `uv run python bench/test_delegation_tracking.py` [routing] | every work item matches exactly one declared route; 0 unrouted; the policy is readable data | not yet measured (39.R1 open — there is no policy to test) |
| 6 | B1 | `uv run python bench/test_delegation_tracking.py` [timeout] | a stalled delegation is taken back at its deadline and returned to the task; 0 lost | not yet measured (39.R2 open) |
| 7 | B1 | `uv run python bench/test_metrics.py` [delegation] | each delegation records time, tokens and whether the result was used; 0 unattributed | not yet measured (39.R3 open) |

Goal 4 is deliberately a B4 rather than a B1: the property that must hold is structural,
and a grep cannot prove it. It is recorded because the decision names it and because the
day someone hands an agent a shell, this line is where it will show up first.

## Failure modes

**The fleet starts answering.** An agent is given a long-running turn and the owner's next
utterance is answered by it, in another voice, with another disposition. The system still
looks healthy; only the identity on the reply is wrong. Diagnose:
`journalctl -u openafon-brain -n 300 | grep -i fleet`, then read the acting identity on
those lines.

**A result is reported as fact.** An agent says a file was changed or a test passed, and
neither claim was checked. 39.F3 records this as fixed, so the appearance of it is a
regression rather than a known-open state. Diagnose: the delegation rows, then verify
independently — `git status --short` and `git log --oneline -3` answer the filesystem
half in one line.

**A delegation stalls and is never taken back.** The task waits indefinitely, the owner's
belief that work is progressing is false, and the deadline is a decoration. Diagnose:
`journalctl -u openafon-brain -n 200 | grep -iE 'delegat|timeout'`, then the task rows for
any deadline already past.

**A self-edit lands outside D-08.** The fleet's answer is applied without all four
conditions — dedicated branch, green suite, no migrations, explicit owner approval of the
diff — and the code base changes under a rule that was supposed to be unbendable.
Diagnose: `git branch --show-current` (never `main`), then `git log --oneline -5` for
commits the owner did not read.

## Open questions

1. For fleet output that is not a self-edit, what is the D-05 verification gate: a diff
   against a working tree, an AST check on proposed code, or a result check? D-05 names
   all three and 39.F3 implements only the last.
2. Does a stalled delegation return to `worker.py`, where Afon does the work himself, or
   to the owner's task list as a failure? 39.R2 asks the question without answering it.
3. Where does the routing policy live — a file beside the code, a table in the database,
   or the tool schema? 39.R1's gate is a test, which means the policy has to be readable
   data rather than model judgement.
