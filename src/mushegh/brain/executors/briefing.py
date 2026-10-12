"""M46 — the prompting layer is Mushegh's, not the executor's (D-79, D-80).

The owner called this "professional prompting", and the thing that makes it professional is not
the wording: it is that **a brief is assembled by code from a record, never improvised per call.**
An improvised prompt is one whose constraints depend on which turn it was written in. A brief whose
constraints come from a table in this module is one a reviewer can read once and know what every
delegation was told.

**Three things every brief carries, and the reason each is non-negotiable:**

* **The acceptance check.** `Brief` already refuses an empty one, so this module's job is to refuse
  the *useless* ones — an acceptance that restates the task tells Mushegh nothing he did not already
  know, and an un-checkable brief is not a small brief, it is an unverifiable one.
* **The constraint set.** Declared per domain, in code. A model cannot widen it by being asked
  nicely, and a caller cannot forget it, because the caller does not write it.
* **The repo**, for coding only — and the one it gets is the throwaway worktree `landing.py`
  creates, never the owner's checkout.

**What the constraints are actually for.** They are not politeness. `landing.py` will *reject* a
diff that adds a schema migration (D-08 condition 3) and will never push, so telling the executor
both up front is the difference between a wasted paid run and a usable one. The same logic applies
outward: an OpenClaw agent that sends an email before the owner saw it has done something no later
check can undo, so "report what you would send, do not send it" belongs in the brief rather than in
a hope.

**The tier is derived, not declared twice.** "Coding goes to the corporate CLIs, personal work runs
on free models" is the owner's split, and it is already expressed in `SPECS`. Reading it back out
of the table means there is exactly one place for it to drift from.

ponytail: a table and two functions. No template engine, no per-executor prompt variants — the
constraint that differs by executor rather than by domain has not appeared yet, and inventing the
seam before it does is how prompts end up spread across five files.

    uv run python bench/test_brief_assembly.py
"""

from __future__ import annotations

from mushegh.brain.executors import SPECS, Brief, BriefRefused, Domain, Tier

__all__ = ["COMMON_CONSTRAINTS", "CONSTRAINTS", "assemble", "constraints_for", "from_task",
           "render", "tier_for"]

#: Every brief, whatever the domain. Each line is here because of a failure it prevents, not
#: because it sounds careful.
COMMON_CONSTRAINTS: tuple[str, ...] = (
    # The process has no stdin (D-80). An executor that waits for an answer waits until its
    # deadline and then reports nothing, which reads as a hang rather than as a missing detail.
    "You are running non-interactively. Do not ask follow-up questions; if a detail is missing, "
    "state the assumption you made and continue.",
    # The 2026-09-20 lesson in its general form: a confident summary of unverified work is worse
    # than an admission, because only one of the two can be checked.
    "Say plainly what you could not verify. An unverifiable claim is worse than an admission.",
    # D-24 and D-80's "no credential path". The allowlisted environment already withholds them;
    # this is the instruction that matches the enforcement, so a refusal is not a surprise.
    "Do not read or copy credentials, .env files, tokens, keys or personal archives. You were not "
    "given them and you do not need them.",
    "Work only inside the directory you were started in. Nothing outside it is yours.",
    "If you cannot do this, say so and stop. A plausible answer to a task you did not complete is "
    "the one outcome with no recovery.",
)

#: Per domain, in code. A sixth domain is an edit here, which is the point.
CONSTRAINTS: dict[Domain, tuple[str, ...]] = {
    Domain.CODING: (
        # D-08. `landing.py` will reject a migration and will never push, so saying both up front
        # is the difference between a wasted paid run and a usable diff.
        "Do not commit, push, tag, or open a pull request. Leave your work in the working tree; "
        "the owner reviews the diff and it is landed for you.",
        "Introduce no schema migration and no new database table or column. A change that does "
        "will be refused before it reaches the owner.",
        "Add no new dependency without naming it in your final message and saying why nothing "
        "already installed would do.",
        "Make the smallest change that satisfies the acceptance check. Leave unrelated code, "
        "formatting and comments alone.",
        "Run the test suite before you finish, and report the result honestly even when it is red.",
    ),
    Domain.DAILY: (
        # The owner-consent gate, in the brief rather than only in the gateway.
        "Send nothing and buy nothing. Draft it, show it, and say who it would go to.",
        "Do not create, cancel or move anything in a calendar, inbox or account without being "
        "told to in this brief.",
        "If this needs a decision only the owner can make, stop and say which decision.",
    ),
    Domain.BUSINESS: (
        "Send nothing outward - no email, message, filing or submission. Produce the draft and "
        "say exactly where it would be sent.",
        "Name every figure's source. An unsourced number in a business document is a liability.",
        "Where a document has a legally required form, say which parts you are not qualified to "
        "settle rather than guessing at them.",
    ),
    Domain.FINANCE: (
        # 40.F2 and D-83: the ledger is read, never written, and a figure without an as-of time is
        # a figure about an unknown moment.
        "Move no money, place no order, and change no holding. This is analysis only.",
        "Give every figure an as-of time, and say what it leaves out.",
        "Do not estimate a price you could not fetch. 'I could not price that' is an answer; an "
        "invented quote is not.",
    ),
}

#: Domains whose work is done by a *library* rather than by an agent, so no brief is assembled for
#: them. D-86's book summarizer is the case: it is imported and called, and a brief would be a
#: prompt sent to something that does not take prompts.
NOT_DELEGATED: dict[Domain, str] = {
    Domain.READING: ("the book summarizer is a library Mushegh calls directly (D-86), not an agent "
                     "that takes a brief"),
}


def constraints_for(domain: Domain) -> tuple[str, ...]:
    """Everything an executor working on this domain is told, in order. Common lines come first."""
    if domain in NOT_DELEGATED:
        raise BriefRefused(NOT_DELEGATED[domain])
    if domain not in CONSTRAINTS:
        raise BriefRefused(f"no constraint set is declared for {domain.value}")
    return COMMON_CONSTRAINTS + CONSTRAINTS[domain]


def tier_for(domain: Domain) -> Tier:
    """Which model pool pays for this domain, read back out of ``SPECS``.

    Derived rather than declared again: the owner's split already lives in the executor table, and
    a second copy of it here would be a second thing to keep true. When a domain's executors serve
    both tiers, the free pool wins - his decision was that personal work runs on free models, and
    the cheaper default is the one that fails safe.
    """
    served = {t for s in SPECS if domain in s.domains for t in s.tiers}
    if not served:
        raise BriefRefused(f"no configured executor serves {domain.value}")
    return Tier.CORPORATE if served == {Tier.CORPORATE} else Tier.PERSONAL


def render(task: str, acceptance: str, domain: Domain) -> str:
    """The full text the executor receives: the work, the constraints, then the acceptance check.

    The acceptance check goes **last** deliberately. It is the thing the executor is measured on,
    and the last line of a prompt is the one a model is most likely to still be holding when it
    decides it is finished.
    """
    lines = [task.strip(), "", "Constraints:"]
    lines += [f"- {c}" for c in constraints_for(domain)]
    lines += ["", f"Done when: {acceptance.strip()}"]
    return "\n".join(lines)


def assemble(
    *,
    domain: Domain,
    task: str,
    acceptance: str,
    repo: str | None = None,
    timeout_s: int | None = None,
) -> Brief:
    """Build one dispatchable brief. Refuses rather than guessing at anything missing.

    The two refusals that are this function's whole reason to exist:

    * **an acceptance check that restates the task** - it reads like diligence and carries no
      information, so a run that "met" it has been verified against nothing;
    * **a coding brief with no repo**, which `dispatch()` also refuses, but by then the owner has
      already been told his work was delegated.
    """
    task, acceptance = (task or "").strip(), (acceptance or "").strip()
    if not task:
        raise BriefRefused("a brief with no task is not a brief")
    if not acceptance:
        raise BriefRefused(
            f"what would tell you this was done? {domain.value} work needs an acceptance check"
        )
    if _same(task, acceptance):
        raise BriefRefused(
            "the acceptance check just restates the task, so it checks nothing - say what would "
            "be observably true afterwards"
        )
    if domain is Domain.CODING and not repo:
        raise BriefRefused("a coding brief must name the repo it may work in")
    if domain is not Domain.CODING and repo:
        raise BriefRefused(f"a {domain.value} brief must not carry a repo path")

    return Brief(
        domain=domain,
        task=render(task, acceptance, domain),
        acceptance=acceptance,
        tier=tier_for(domain),
        repo=repo,
        **({"timeout_s": timeout_s} if timeout_s else {}),
    )


def from_task(record: object, *, repo: str | None = None, domain: Domain | None = None) -> Brief:
    """Assemble a brief from a `tasks.Task`. The task record is the source, not a fresh sentence.

    `Task.meta["acceptance"]` is where the check lives, and its absence is a **refusal**, not a
    default: a generated acceptance check would be Mushegh marking his own homework. The record's
    `description` is used as the acceptance only when it is clearly a different statement from the
    title, which `assemble()` then re-checks.
    """
    title = str(getattr(record, "title", "") or "")
    meta = getattr(record, "meta", None) or {}
    acceptance = str(meta.get("acceptance") or "").strip()
    if not acceptance:
        desc = str(getattr(record, "description", "") or "").strip()
        acceptance = desc if desc and not _same(title, desc) else ""
    if not acceptance:
        raise BriefRefused(
            f"the task {title[:60]!r} has no acceptance check recorded, so there is nothing to "
            "verify a delegation against - add one to the task before delegating it"
        )
    if domain is None:
        kind = str(getattr(record, "kind", "") or "").lower()
        domain = Domain.CODING if kind == "coding" else Domain.DAILY
    return assemble(domain=domain, task=title, acceptance=acceptance, repo=repo)


def _same(a: str, b: str) -> bool:
    """Whether two statements say the same thing, as far as text can tell.

    Deliberately shallow - punctuation and case folded, nothing else. A fuzzy ratio here would
    start refusing legitimately similar pairs, and the failure this catches is the copy-paste one.
    """
    def norm(x: str) -> str:
        return "".join(c for c in x.casefold() if c.isalnum() or c == " ").strip()

    return norm(a) == norm(b)
