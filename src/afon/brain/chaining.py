"""03.R3 — resolve the step a request obviously implies, in the same turn that asked for it.

"Text Anna I'm running late" is one instruction to the owner and two steps to the machine: find
out what "Anna" means on Telegram, then send to it. Today the second step gets the literal string
"Anna" — `send_telegram(to="Anna")` hands a display name to Telethon and `send_email(to="Anna")`
hands it to SMTP, which is not an address at all. The model is supposed to call `resolve_contact`
first, and sometimes does; when it does, what comes back is **prose** — "Anna: email a@b.c,
Telegram @anna_k, sir." — so chaining correctly still means parsing a sentence to find the handle.
That is the real reason the chain does not close: the first step's output is not usable as the
second step's input.

So this closes it in code rather than asking the model to try harder. Before an outward tool is
dispatched, a recipient that is plainly a person's NAME is replaced with the stored target for
THAT channel — Telegram gets the handle, email gets the address, a call gets the number. One
contact, three answers, and the right one depends on which tool is about to run.

Three rules keep it from doing harm:

* **Only a bare name is touched.** Anything already addressable — `@handle`, an email address, a
  phone number, a numeric chat id, "Saved Messages" — is passed through untouched. The owner who
  types an address means that address.
* **Ambiguity is never guessed.** Two Annas, or nobody by that name, returns a question instead of
  a substitution, and 01.R2 already owns what happens to a question.
* **It resolves BEFORE the confirm gate**, so what the owner is asked to approve names the address
  it will actually go to. Resolving afterwards would mean confirming "Anna" and sending to
  @anna_k — a confirmation of something other than the act.

    uv run python -m afon.brain.chaining
"""
from __future__ import annotations

import re

#: tool -> (the argument holding the recipient, the contact channel that tool needs).
#: A table rather than a guess from the argument name: `send_telegram` and `send_email` both take
#: "to" and need completely different values out of the same contact.
RECIPIENT_OF: dict[str, tuple[str, str]] = {
    "send_telegram": ("to", "telegram"),
    "send_email": ("to", "email"),
    "draft_email": ("to", "email"),
    "place_call": ("to", "phone"),
}

#: Already addressable — leave it alone. A handle, an address, a number, an id, or Telegram's own
#: special destination.
_ADDRESSABLE = re.compile(
    r"^\s*(?:@[\w.]+"                      # @handle
    r"|[^@\s]+@[^@\s]+\.[^@\s]+"            # an email address
    r"|[+]?[\d][\d\s()\-]{4,}"               # a phone number or chat id
    r"|-?\d+"                              # a bare numeric chat id
    r"|saved(?:\s+messages)?"               # Telegram's note-to-self
    r"|me|myself)\s*$",
    re.I,
)


def needs_resolving(tool: str, args: dict) -> str:
    """The bare name this call would send to, or "" when there is nothing to resolve."""
    field = RECIPIENT_OF.get(tool, ("", ""))[0]
    if not field:
        return ""
    value = str((args or {}).get(field) or "").strip()
    if not value or _ADDRESSABLE.match(value):
        return ""
    return value


def resolve_recipient(tool: str, args: dict, book=None) -> tuple[dict, str]:
    """``(args, question)``. `question` is "" when the call is ready to dispatch.

    On success the recipient field carries the channel-correct target and the call goes out in the
    same turn the owner asked for it. On anything less than certainty it carries a question, which
    is the honest outcome: an outward message to the wrong person is not recoverable by apologising.
    """
    name = needs_resolving(tool, args)
    if not name:
        return args, ""
    field, channel = RECIPIENT_OF[tool]
    try:
        if book is None:
            from afon.brain import contacts as _c

            book = _c.BOOK
        matches = book.resolve(name)
    except Exception:                                        # noqa: BLE001
        return args, ""          # no contact book is not a reason to block a send

    if not matches:
        return args, (f"I don't have a contact for '{name}', sir — what's their "
                      f"{'Telegram' if channel == 'telegram' else channel}?")
    if len(matches) > 1:
        who = "; ".join(c.name for c in matches[:6])
        return args, f"I have more than one '{name}', sir: {who}. Which one?"

    person = matches[0]
    target = getattr(person, channel, None)
    if not target:
        return args, (f"I have {person.name}, sir, but no "
                      f"{'Telegram' if channel == 'telegram' else channel} for them.")
    out = dict(args)
    out[field] = target
    return out, ""


def _selfcheck() -> None:
    """ponytail: the one runnable check — the same contact, three channels, three answers."""
    from dataclasses import dataclass

    @dataclass
    class C:
        name: str
        email: str | None = None
        telegram: str | None = None
        phone: str | None = None

    class Book:
        def __init__(self, people):
            self.people = people

        def resolve(self, q):
            return [p for p in self.people if q.lower() in p.name.lower()]

    anna = C("Anna Keller", "anna@example.com", "@anna_k", "+491234567")
    book = Book([anna])

    for tool, expect in [("send_telegram", "@anna_k"), ("send_email", "anna@example.com"),
                         ("place_call", "+491234567")]:
        out, q = resolve_recipient(tool, {"to": "Anna"}, book)
        assert q == "", q
        assert out["to"] == expect, (tool, out)

    # Already addressable: untouched, whatever the book says.
    for given in ("@someone_else", "other@example.com", "+49999", "Saved Messages", "123456"):
        out, q = resolve_recipient("send_telegram", {"to": given}, book)
        assert q == "" and out["to"] == given, (given, out, q)

    # Unknown and ambiguous both ask rather than guess.
    _, q = resolve_recipient("send_email", {"to": "Nobody"}, book)
    assert "don't have a contact" in q, q
    two = Book([C("Anna Keller", telegram="@anna_k"), C("Anna Weber", telegram="@anna_w")])
    _, q = resolve_recipient("send_telegram", {"to": "Anna"}, two)
    assert "more than one" in q, q
    # Known person, wrong channel: say so instead of sending to a blank.
    _, q = resolve_recipient("place_call", {"to": "Anna"}, Book([C("Anna Keller", email="a@b.c")]))
    assert "no phone" in q, q
    # A tool that takes no recipient is not this module's business.
    out, q = resolve_recipient("weather", {"location": "Anna"}, book)
    assert q == "" and out == {"location": "Anna"}

    print(f"selfcheck ok — {len(RECIPIENT_OF)} outward tools chained to the contact book")


if __name__ == "__main__":
    _selfcheck()
