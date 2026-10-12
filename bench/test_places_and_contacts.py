"""Named places and JSON contacts — the two files the owner hand-edits.

The claim: a place said four ways resolves to one address, an ambiguous name
resolves to NOTHING rather than to a guess, and a person said by any channel is
reachable. Everything is offline — no network, no LLM.

    uv run python bench/test_places_and_contacts.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mushegh.brain.locations import LocationBook, Place  # noqa: E402
from mushegh.brain.contacts import ContactBook  # noqa: E402

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


def tmp() -> Path:
    return Path(tempfile.mkdtemp()) / "locations.json"


def seed(path: Path) -> None:
    path.write_text(json.dumps({"version": 1, "locations": {
        "home": {"label": "Home", "address": "12 Lindenweg", "zip": "50667",
                 "city": "Köln", "region": "NRW", "country": "Germany",
                 "aliases": ["the house"]},
        "gym_main": {"label": "The gym", "address": "3 Sportstr", "zip": "50674",
                     "city": "Köln", "region": "NRW", "country": "Germany",
                     "aliases": ["the gym", "workout"]},
        "gym_secondary": {"label": "The second gym", "address": "9 Ringstr", "zip": "50625",
                          "city": "Köln", "region": "NRW", "country": "Germany",
                          "aliases": ["other gym"]},
        "home_armenia": {"label": "Home in Armenia", "address": "", "zip": "",
                         "city": "Yerevan", "region": "", "country": "Armenia",
                         "aliases": ["armenia"]},
    }}), encoding="utf-8")


def main() -> None:
    print("[1] a place said the way a human says it resolves")
    p = tmp(); seed(p); b = LocationBook(p)
    for said, key in [("home", "home"), ("Home", "home"), ("HOME", "home"),
                      ("the gym", "gym_main"), ("the house", "home"),
                      ("gym_main", "gym_main"), ("armenia", "home_armenia")]:
        hits = b.resolve(said)
        check(f"{said!r} -> {key}", [h.key for h in hits] == [key], str([h.key for h in hits]))

    print("[2] accent and punctuation do not change what a place is")
    check("Cologne city centre style input resolves",
          b.resolve("  HOME  ")[0].key == "home")
    check("a hyphen is not a different place", b.resolve("gym-main")[0].key == "gym_main")

    print("[3] an AMBIGUOUS name resolves to nothing rather than to a guess")
    # A genuine collision: two places sharing the SAME alias, with neither label
    # equal to it. Silently picking one gym is a confidently wrong route.
    p2 = tmp(); seed(p2)
    d = json.loads(p2.read_text())
    d["locations"]["gym_main"]["label"] = "Gym North"
    d["locations"]["gym_secondary"]["label"] = "Gym South"
    d["locations"]["gym_secondary"]["aliases"] = ["the gym", "other gym"]
    p2.write_text(json.dumps(d), encoding="utf-8")
    b2 = LocationBook(p2)
    check("both gyms match 'the gym'", len(b2.resolve("the gym")) == 2,
          str([h.key for h in b2.resolve("the gym")]))
    check("and address_for refuses to choose", b2.address_for("the gym") is None)
    check("while an unambiguous name still resolves", b2.address_for("gym north") is not None)

    print("[4] an unfilled place resolves by name but will not route")
    check("an incomplete place is still findable", b.resolve("armenia")[0].key == "home_armenia")
    check("is_complete is False without an address", b.resolve("armenia")[0].is_complete is False)
    check("and address_for declines it", b.address_for("armenia") is None)
    check("a filled one does resolve", b.address_for("home") is not None)

    print("[5] the address is built from the fields, not a hand-written string")
    a = b.address_for("home")
    check("street is present", "12 Lindenweg" in a, a)
    check("postcode is a string with a space", "50667 Köln" in a, a)
    check("country is present", "Germany" in a, a)
    check("no double spaces", "  " not in a, repr(a))

    print("[6] nothing at all is handled without raising")
    empty = LocationBook(tmp() / "does-not-exist.json")
    check("missing file -> no places", empty.all() == [])
    check("missing file -> resolve is empty", empty.resolve("home") == [])
    check("empty query -> empty", b.resolve("") == [])
    check("nonexistent place -> None", b.address_for("the moon") is None)

    print("[7] a save round-trips and keeps the schema uniform")
    p3 = tmp()
    b3 = LocationBook(p3)
    b3.save(Place(key="bookstore", label="The bookstore", address="1 Marktstr",
                  zip="50667", city="Köln", region="NRW", country="Germany",
                  aliases=["book shop"]))
    again = LocationBook(p3)
    check("saved place comes back", again.get("bookstore") is not None)
    check("fields survive", again.get("bookstore").city == "Köln", "city lost")
    check("aliases survive", again.get("bookstore").aliases == ["book shop"], "aliases lost")
    on_disk = json.loads(p3.read_text(encoding="utf-8"))
    check("the file is versioned", on_disk.get("version") == 1)
    check("every entry has the same keys",
          set(on_disk["locations"]["bookstore"]) == {"label", "address", "zip", "city",
                                                     "region", "country", "aliases", "notes"},
          str(sorted(on_disk["locations"]["bookstore"])))

    print("[8] the shipped locations.json is well-formed and has the same schema")
    shipped = Path(__file__).resolve().parents[1] / "locations.json"
    data = json.loads(shipped.read_text(encoding="utf-8"))
    check("it parses", isinstance(data.get("locations"), dict))
    want = {"home", "workplace", "gym_main", "gym_secondary", "college",
            "city_center", "bookstore", "office", "home_ukraine", "home_armenia",
            "best_friend", "airport"}
    have = set(data["locations"])
    check("every place the owner named is present", want <= have, str(sorted(want - have)))
    required = {"label", "address", "zip", "city", "region", "country", "aliases", "notes"}
    check("every entry has the identical schema",
          all(set(v) == required for v in data["locations"].values()),
          str([k for k, v in data["locations"].items() if set(v) != required]))

    print("[9] contacts: JSON is the store, and every channel is reachable")
    jp = Path(tempfile.mkdtemp()) / "contacts.json"
    jp.write_text(json.dumps({"version": 1, "contacts": [
        {"name": "John Smith", "email": "john@example.com", "telegram": "@johnsmith",
         "phone": "+15551234567", "instagram": "johnsmith", "notes": "colleague"},
    ]}), encoding="utf-8")
    book = ContactBook(jp.with_suffix(".md"))
    people = book.all()
    check("one contact loaded", len(people) == 1, str(len(people)))
    c = people[0]
    check("email", c.email == "john@example.com")
    check("telegram", c.telegram == "@johnsmith")
    check("phone", c.phone == "+15551234567")
    check("instagram is a channel too", c.instagram == "johnsmith")
    check("resolved by name", [x.name for x in book.resolve("john")] == ["John Smith"],
          str([x.name for x in book.resolve("john")]))

    print("[10] contacts: an empty or broken file degrades, never raises")
    bad = Path(tempfile.mkdtemp()) / "contacts.json"
    bad.write_text("{not json", encoding="utf-8")
    check("unparseable -> empty", ContactBook(bad.with_suffix(".md")).all() == [])
    none = Path(tempfile.mkdtemp()) / "contacts.json"
    check("absent -> empty", ContactBook(none.with_suffix(".md")).all() == [])
    check("entry with no name is skipped",
          ContactBook(_w(Path(tempfile.mkdtemp()))).all() == [])


def _w(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    f = d / "contacts.json"
    f.write_text(json.dumps({"contacts": [{"email": "orphan@example.com"}]}), encoding="utf-8")
    return f.with_suffix(".md")


if __name__ == "__main__":
    main()
    print(f"\n=== checks passed ===\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)