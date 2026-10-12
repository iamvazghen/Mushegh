"""Named places — "home", "the gym", "city centre" as things you can route to.

One home address is not a life. The owner has a second gym, a college, a
bookstore he drives to on Saturdays, a flat in Ukraine and a house in Armenia,
and the question that actually gets asked is never the full street address —
it is *"how do I get from home to city centre"* and *"what time do I need to
leave for the airport"*.

So places are named, aliased, and resolved. A tool hands this the string the
owner said; it gets back the full address. The point is that the *caller* never
has to know an address, and a request phrased the way a human phrases it lands
on the right door without the owner ever saying a post code.

Storage is one JSON file, same schema for every entry, so a place is added by
appending an object rather than by remembering which field this one wanted. An
inconsistent schema is how a list of places becomes a list that is half
addressable.

**Resolution is deliberately forgiving and deliberately narrow.** An alias that
matches exactly one place resolves. An alias that matches several does NOT pick
the closest or the first — it reports the candidates and lets the owner choose,
because silently routing to the wrong gym is worse than asking which gym.

Nothing here decides a route or calls a network. It is the dictionary the
routing tools read, and it is offline and testable.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Every place is this shape. `zip` is a string because German and UK postcodes
#: contain letters and leading zeros, and an int would eat both.
FIELDS = ("address", "zip", "city", "region", "country")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _path() -> Path:
    return _repo_root() / "locations.json"


def _norm(s: str) -> str:
    """Lowercase, strip accents, collapse punctuation to single spaces.

    "City Centre", "city centre", "city-centre" and "citycenter" are the same
    place said four ways, and the owner will use whichever his mood produced.
    Diacritics go because they arrive inconsistently typed on a phone keyboard.
    """
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


@dataclass
class Place:
    key: str
    label: str
    address: str = ""
    zip: str = ""          # noqa: A003 — the field is a postcode, and renaming it breaks the file
    city: str = ""
    region: str = ""
    country: str = ""
    aliases: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, key: str, raw: dict) -> "Place":
        return cls(
            key=key,
            label=str(raw.get("label") or key.replace("_", " ").title()),
            address=str(raw.get("address") or "").strip(),
            zip=str(raw.get("zip") or "").strip(),
            city=str(raw.get("city") or "").strip(),
            region=str(raw.get("region") or "").strip(),
            country=str(raw.get("country") or "").strip(),
            aliases=[str(a) for a in (raw.get("aliases") or [])],
            notes=str(raw.get("notes") or "").strip(),
        )

    def to_dict(self) -> dict:
        return {"label": self.label, "address": self.address, "zip": self.zip,
                "city": self.city, "region": self.region, "country": self.country,
                "aliases": self.aliases, "notes": self.notes}

    @property
    def one_line(self) -> str:
        """The form a routing API wants, and the form to read aloud.

        Built from the structured fields rather than from a hand-written address
        string, because a hand-written one drifts from the fields it was written
        beside the first time a post code is corrected.
        """
        return ", ".join(p for p in (self.address, f"{self.zip} {self.city}".strip(),
                                     self.region, self.country) if p) or self.label

    @property
    def is_complete(self) -> bool:
        """Has the owner actually filled this place in yet?"""
        return bool(self.address and self.city and self.country)


class LocationBook:
    """The named places, loaded once per process and read by the routing tools."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _path()
        self._loaded: dict[str, Place] | None = None

    def _load(self) -> dict[str, Place]:
        if self._loaded is not None:
            return self._loaded
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # No file, or a file mid-edit, is a normal state for a personal store
            # the owner hand-edits. An empty book degrades every caller to "I
            # don't know that place" rather than taking the brain down.
            self._loaded = {}
            return self._loaded
        places = raw.get("locations") if isinstance(raw, dict) else {}
        out: dict[str, Place] = {}
        if isinstance(places, dict):
            for key, value in places.items():
                if isinstance(value, dict):
                    out[str(key).strip().lower()] = Place.from_dict(str(key).strip().lower(), value)
        self._loaded = out
        return out

    def all(self) -> list[Place]:
        return list(self._load().values())

    def get(self, key: str) -> Place | None:
        return self._load().get(_norm(key).replace(" ", "_"))

    def resolve(self, query: str) -> list[Place]:
        """Every place `query` could mean, narrowest match first.

        Four passes, so a precise word never widens into an ambiguity: exact key,
        exact alias, key starting with the query, alias starting with it. The
        caller decides what to do with more than one; this function never picks.
        """
        q = _norm(query)
        if not q:
            return []
        places = list(self._load().values())
        # Compared normalised on BOTH sides: the key holds an underscore and the
        # owner's mouth produces a space, so "gym_main" and "gym main" are one
        # query to a human and two strings to a naive ==.
        nk = {_norm(p.key): p for p in places}
        if q in nk:
            return [nk[q]]
        exact = [p for p in places if _norm(p.label) == q]
        if exact:
            return exact
        alias = [p for p in places for a in p.aliases if _norm(a) == q]
        if alias:
            return alias
        prefix = [p for p in places if _norm(p.key).startswith(q) or _norm(p.label).startswith(q)]
        if prefix:
            return prefix
        return [p for p in places for a in p.aliases if _norm(a).startswith(q)]

    def address_for(self, query: str) -> str | None:
        """The one-line address for `query`, or None.

        None is a deliberate third answer, distinct from "": an empty string would
        let a caller silently route to nowhere, and a guessed pick would route to
        the wrong place with total confidence.

        An UNFILLED place also returns None, even though `one_line` will happily
        fall back to its label for display. A label is not an address, and handing
        "Home in Armenia" to a routing API produces a confident answer about a
        place nobody has written down yet.
        """
        hits = self.resolve(query)
        if len(hits) != 1:
            return None
        return hits[0].one_line if hits[0].is_complete else None

    def save(self, place: Place) -> None:
        data: dict[str, Any] = {"version": 1, "locations": {}}
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("locations"), dict):
                    data = {"version": loaded.get("version", 1), "locations": dict(loaded["locations"])}
            except ValueError:
                pass  # overwrite an unparseable file rather than refuse to save
        data["locations"][place.key] = place.to_dict()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._loaded = None


BOOK = LocationBook()