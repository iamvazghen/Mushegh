"""03.R3 — a result that obviously feeds another chains in one turn, not across two.

"Text Anna I'm running late" is one instruction to the owner and two steps to the machine: work out
what "Anna" means on Telegram, then send to it. The second step used to get the literal string
"Anna" — a display name handed to Telethon, or to SMTP, where it is not an address at all. The model
is meant to call `resolve_contact` first and sometimes does; what comes back is PROSE ("Anna: email
a@b.c, Telegram @anna_k, sir."), so chaining correctly still means parsing a sentence to find a
handle. That is why the chain does not close on its own: step one's output is not step two's input.

What this holds:
  * the same contact resolves to a DIFFERENT target per channel, chosen by the tool about to run;
  * anything already addressable is passed through untouched;
  * ambiguity and absence ask, and never guess — an outward message to the wrong person is not
    recoverable by apologising afterwards;
  * the resolution happens BEFORE the confirm gate, so the owner approves the address it will
    really go to;
  * and it fails OPEN, so an unreadable contact book cannot block a send.

Hermetic: a hand-built contact book, no store, no network, no LLM.

    uv run python bench/test_tool_chaining.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  [{detail}]")


@dataclass
class C:
    name: str
    email: str | None = None
    telegram: str | None = None
    phone: str | None = None


class Book:
    """Just enough of ContactBook: name-substring matching, like `resolve`'s widest pass."""

    def __init__(self, people):
        self.people = people

    def resolve(self, q):
        return [p for p in self.people if q.lower() in p.name.lower()]


def main() -> None:
    from mushegh.brain.chaining import RECIPIENT_OF, needs_resolving, resolve_recipient

    anna = C("Anna Keller", "anna@example.com", "@anna_k", "+491234567")
    book = Book([anna])

    print("[1] one contact, three channels — the tool about to run picks which")
    for tool, expect in [("send_telegram", "@anna_k"),
                         ("send_email", "anna@example.com"),
                         ("draft_email", "anna@example.com"),
                         ("place_call", "+491234567")]:
        out, q = resolve_recipient(tool, {"to": "Anna"}, book)
        check(f"{tool}(to='Anna') -> {expect}", q == "" and out["to"] == expect, f"{out} {q}")
    check("every chained tool is declared with its channel, not guessed from the field name",
          {t for t in RECIPIENT_OF} >= {"send_telegram", "send_email"}
          and RECIPIENT_OF["send_telegram"][1] != RECIPIENT_OF["send_email"][1],
          "both take 'to' and need completely different values")

    print("\n[2] anything already addressable is left alone")
    for given in ("@someone_else", "other@example.com", "+49 999 1234", "Saved Messages",
                  "123456", "-1001234567", "me"):
        out, q = resolve_recipient("send_telegram", {"to": given}, book)
        check(f"{given!r} passes through untouched", q == "" and out["to"] == given, f"{out} {q}")
    check("...and an addressable value is not even looked up",
          needs_resolving("send_telegram", {"to": "@anna_k"}) == "")
    check("a bare name IS looked up",
          needs_resolving("send_telegram", {"to": "Anna"}) == "Anna")

    print("\n[3] uncertainty asks — it never picks the likeliest person")
    _, q = resolve_recipient("send_email", {"to": "Nobody"}, book)
    check("an unknown name asks for their address", "don't have a contact" in q, q)
    check("...and names WHICH channel it needs, so the answer is usable", "email" in q, q)
    two = Book([C("Anna Keller", telegram="@anna_k"), C("Anna Weber", telegram="@anna_w")])
    out, q = resolve_recipient("send_telegram", {"to": "Anna"}, two)
    check("two matches asks which one", "more than one" in q, q)
    check("...and lists them, so he can answer in one word",
          "Anna Keller" in q and "Anna Weber" in q, q)
    check("...and the recipient is NOT substituted while the question stands",
          out["to"] == "Anna", str(out))
    _, q = resolve_recipient("place_call", {"to": "Anna"}, Book([C("Anna Keller", email="a@b.c")]))
    check("a known person with no number for this channel says so", "no phone" in q, q)

    print("\n[4] it cannot touch what is not its business, and cannot break a send")
    out, q = resolve_recipient("weather", {"location": "Anna"}, book)
    check("a tool with no recipient is untouched", q == "" and out == {"location": "Anna"})
    out, q = resolve_recipient("send_telegram", {"message": "hi"}, book)
    check("a send with no recipient at all is left to the handler's own question",
          q == "" and "to" not in out, f"{out} {q}")

    class Broken:
        def resolve(self, _q):
            raise RuntimeError("contact store unreadable")

    out, q = resolve_recipient("send_telegram", {"to": "Anna"}, Broken())
    check("an unreadable contact book does NOT block the send (fail open)",
          q == "" and out["to"] == "Anna", f"{out} {q}")

    print("\n[5] the turn order: resolve, THEN ask the owner to confirm")
    src = (BENCH / "src/mushegh/brain/agent.py").read_text(encoding="utf-8")
    i_chain = src.index("args, chain_q = self._resolve_chain(name, args)")
    i_confirm = src.index("if confirm_required(name, args) and not self._confirm_granted:")
    check("the recipient is resolved before the confirm gate reads the call", i_chain < i_confirm,
          "confirming 'Anna' and sending to @anna_k is a confirmation of something else")
    # The window is the held branch ITSELF - from the resolve call to the `continue` that ends it -
    # and not a byte count. A byte count measures whatever prose happens to sit inside it: this
    # check failed on 2026-09-20 because O2.5 added the missing audit line to this branch, i.e.
    # because the branch got safer. `continue` is also the closer statement of intent, since it is
    # how the call is actually stopped.
    held = src[i_chain:src.index("\n                continue\n", i_chain)]
    check("a held chain stops the call rather than sending it",
          '"blocked": True' in held, held[-160:])
    check("the model is told to ask, not to state", "_CHAIN_ASK" in src)
    from mushegh.brain import agent as A
    check("...and explicitly not to say it has sent anything",
          "do not say" in A._CHAIN_ASK.lower() and "sent" in A._CHAIN_ASK)
    check("...and not to pick the likeliest recipient", "likeliest" in A._CHAIN_ASK)
    check("the resolver itself fails open in the agent too",
          "chain resolve skipped" in src)

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
