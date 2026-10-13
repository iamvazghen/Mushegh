"""20 — the open maps engine: every service and every fallback, offline.

Nominatim -> Photon geocoding (spaced, cached), OSRM -> Valhalla driving, Valhalla walking/cycling,
Transitous public transport, Nominatim-in-a-box -> Overpass -> Photon place search. Fakes stand in for the network;
the reply shapes were captured from the live services on 2026-10-13.

    uv run python bench/test_openmaps.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


PHOTON_ALEX = {"features": [{"properties": {"name": "Alexanderplatz", "city": "Berlin"},
                             "geometry": {"coordinates": [13.4136, 52.5220]}}]}
PHOTON_BER = {"features": [{"properties": {"name": "Flughafen BER"},
                            "geometry": {"coordinates": [13.5082, 52.3643]}}]}
OSRM_OK = {"code": "Ok", "routes": [{"duration": 1834.7, "distance": 24458.9}]}
VALHALLA_OK = {"trip": {"summary": {"time": 675.3, "length": 3.245}}}
TRANSIT_OK = {"itineraries": [{
    "duration": 2100, "startTime": "2026-10-13T17:09:00Z", "endTime": "2026-10-13T17:44:00Z",
    "legs": [
        {"mode": "WALK", "duration": 240, "to": {"name": "S+U Alexanderplatz Bhf (Berlin)"}},
        {"mode": "METRO", "routeShortName": "S3", "duration": 480, "startTime": "2026-10-13T17:13:00Z",
         "to": {"name": "S Ostkreuz Bhf (Berlin)"}},
        {"mode": "WALK", "duration": 120, "to": {"name": "S Ostkreuz Bhf (Berlin)"}},
        {"mode": "REGIONAL_RAIL", "routeShortName": "RB24", "duration": 1020,
         "startTime": "2026-10-13T17:23:00Z", "to": {"name": "Flughafen BER"}},
        {"mode": "WALK", "duration": 240, "to": {"name": "END"}}]}]}
OVERPASS_OK = {"elements": [
    {"lat": 52.5341, "lon": 13.4100, "tags": {"name": "Hangi Sushi", "cuisine": "asian"}},
    {"lat": 52.5272, "lon": 13.3990, "tags": {"name": "Kuchi", "cuisine": "sushi",
                                              "addr:street": "Gipsstraße", "addr:housenumber": "3",
                                              "opening_hours": "Mo-Sa 12:00-23:00"}},
    {"center": {"lat": 52.5225, "lon": 13.4140}, "tags": {"name": "Sushi Circle"}},
    {"lat": 52.5226, "lon": 13.4141, "tags": {"cuisine": "sushi"}},          # unnamed: dropped
]}


def main() -> None:
    from mushegh.brain.cache import CACHE
    from mushegh.brain.tools import openmaps as om
    from mushegh.config import settings

    calls: list[tuple[str, str, dict]] = []
    down: set[str] = set()             # hosts that raise
    reply: dict[str, object] = {}      # host -> json

    def host(url: str) -> str:
        return httpx.URL(url).host

    async def fake(method: str, url: str, **kw) -> httpx.Response:
        h = host(url)
        calls.append((method, url, kw))
        if h in down:
            raise httpx.ConnectError(f"{h} down")
        body = reply.get(h, {})
        if callable(body):
            body = body(url, kw)
        return httpx.Response(200, json=body, request=httpx.Request(method, url))

    async def fake_get(url, **kw):
        return await fake("GET", url, **kw)

    async def fake_post(url, **kw):
        return await fake("POST", url, **kw)

    def photon(url, kw):
        q = (kw.get("params") or {}).get("q", "").lower()
        return PHOTON_BER if "ber" in q and "alex" not in q else PHOTON_ALEX

    near_reply: list = []

    def nominatim(url, kw):
        q = kw["params"]
        if q.get("bounded") or q.get("limit") == 3:      # box search, or the plain name search
            return near_reply
        if "nowhere" in q["q"].lower():
            return []
        f = photon(url, kw)["features"][0]
        lon, lat = f["geometry"]["coordinates"]
        return [{"name": f["properties"]["name"], "lat": str(lat), "lon": str(lon)}]

    real = om.http_get, om.http_post, settings.user_tz, om.NOMINATIM_GAP
    om.http_get, om.http_post, settings.user_tz = fake_get, fake_post, "Europe/Berlin"
    om.NOMINATIM_GAP = 0.0

    def run(coro_fn, args):
        CACHE.clear()
        calls.clear()
        return asyncio.run(coro_fn(args))

    def hosts() -> list[str]:
        return [host(u) for _, u, _ in calls]

    try:
        print("[1] geocoding: Nominatim first, Photon when Nominatim misses or fails; cached")
        reply.update({"photon.komoot.io": photon, "nominatim.openstreetmap.org": nominatim,
                      "router.project-osrm.org": OSRM_OK})
        out = run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER"})
        check("Nominatim answered, Photon never asked", "photon.komoot.io" not in hosts()
              and hosts().count("nominatim.openstreetmap.org") == 2, str(hosts()))
        calls.clear()
        asyncio.run(om.travel_time({"origin": "Alexanderplatz", "destination": "BER", "mode": "bike"}))
        check("a second question reuses both geocodes (cached a week)",
              "nominatim.openstreetmap.org" not in hosts(), str(hosts()))
        down.add("nominatim.openstreetmap.org")
        out = run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER"})
        check("Nominatim down -> Photon", hosts().count("photon.komoot.io") == 2, out)
        down.discard("nominatim.openstreetmap.org")
        reply["photon.komoot.io"] = {"features": []}
        out = run(om.travel_time, {"origin": "Nowhere-on-earth", "destination": "BER"})
        check("nobody knows the place -> said plainly", "couldn't find 'Nowhere-on-earth'" in out, out)
        reply["photon.komoot.io"] = photon
        om.NOMINATIM_GAP = 0.3
        t0 = time.monotonic()
        run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER"})
        check("Nominatim calls are spaced (usage policy)", time.monotonic() - t0 >= 0.3)
        om.NOMINATIM_GAP = 0.0

        print("\n[2] driving: OSRM, falling back to Valhalla; no traffic is admitted")
        out = run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER", "mode": "car"})
        check("OSRM gives the car time", "31 minutes by car" in out and "24 km" in out, out)
        check("free-flow time says so", "without live traffic" in out, out)
        down.add("router.project-osrm.org")
        reply["valhalla1.openstreetmap.de"] = VALHALLA_OK
        out = run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER"})
        valhalla = [kw for _, u, kw in calls if "valhalla" in u]
        check("OSRM down -> Valhalla auto", valhalla and valhalla[0]["json"]["costing"] == "auto", out)
        down.discard("router.project-osrm.org")

        print("\n[3] walking and cycling go to Valhalla (the OSRM demo only routes cars)")
        out = run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER", "mode": "walk"})
        check("walk never touches OSRM", "router.project-osrm.org" not in hosts(), str(hosts()))
        check("walk -> pedestrian costing", calls[-1][2]["json"]["costing"] == "pedestrian")
        check("walk answer", "11 minutes on foot" in out and "3 km" in out
              and "traffic" not in out, out)
        out = run(om.travel_time, {"origin": "a Alexanderplatz", "destination": "BER", "mode": "bike"})
        check("bike -> bicycle costing", calls[-1][2]["json"]["costing"] == "bicycle", out)

        print("\n[4] public transport via Transitous, read out in the owner's time zone")
        reply["api.transitous.org"] = TRANSIT_OK
        out = run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER", "mode": "transit"})
        p = calls[-1][2]["params"]
        check("asks Transitous by coordinates", p["fromPlace"] == "52.522,13.4136"
              and p["toPlace"] == "52.3643,13.5082", str(p))
        check("lines and departure times, local time", "S3 at 19:13" in out and "RB24 at 19:23" in out,
              out)
        check("leave and arrive times", "leave at 19:09, arrive 19:44" in out and "35 minutes" in out, out)
        check("a short platform change is not read out", out.count("walk ") == 2, out)
        reply["api.transitous.org"] = {"itineraries": []}
        out = run(om.travel_time, {"origin": "Alexanderplatz", "destination": "BER", "mode": "train"})
        check("no connection -> said plainly", "couldn't find a public transport" in out, out)

        print("\n[5] places: 'X near Y' is Nominatim in a box around Y, nearest first")
        check("split near", om._split("sushi near Alexanderplatz") == ("sushi", "Alexanderplatz"))
        check("split in", om._split("pharmacy in Mitte Berlin") == ("pharmacy", "Mitte Berlin"))
        check("no anchor", om._split("Berghain") == ("Berghain", ""))
        near_reply[:] = [
            {"name": "Far Pharmacy", "lat": "52.5300", "lon": "13.4136", "address": {}},
            {"name": "Alexa Apotheke", "lat": "52.5215", "lon": "13.4140",
             "address": {"road": "Grunerstraße", "house_number": "20"},
             "extratags": {"opening_hours": "Mo-Sa 10:00-20:00"}}]
        out = run(om.find_place, {"query": "pharmacy near Alexanderplatz"})
        box = [kw["params"] for _, u, kw in calls if kw.get("params", {}).get("bounded")]
        check("Nominatim box search, Overpass never asked", box and "overpass-api.de" not in hosts(),
              str(hosts()))
        check("the box surrounds the anchor", box and (lambda v: v[0] < 13.4136 < v[2]
              and v[3] < 52.522 < v[1])([float(x) for x in box[0]["viewbox"].split(",")]), str(box))
        check("nearest first, with address and hours",
              out.index("Alexa Apotheke, Grunerstraße 20, open Mo-Sa 10:00-20:00") < out.index("Far"), out)
        run(om.find_place, {"query": "coffee near Alexanderplatz"})
        box = [kw["params"] for _, u, kw in calls if kw.get("params", {}).get("bounded")]
        check("spoken word -> OSM word for Nominatim (coffee -> cafe)", box[0]["q"] == "cafe", str(box))

        print("\n[6] Nominatim finds nothing (gyms) -> Overpass around the anchor")
        near_reply[:] = []
        reply["overpass-api.de"] = OVERPASS_OK
        out = run(om.find_place, {"query": "sushi near Alexanderplatz"})
        check("nearest first, unnamed dropped", out.index("Sushi Circle") < out.index("Kuchi")
              < out.index("Hangi Sushi"), out)
        check("address and opening hours read out", "Gipsstraße 3" in out
              and "open Mo-Sa 12:00-23:00" in out, out)
        q = calls[-1][2]["data"]["data"]
        check("query is around the anchor", "around:1500,52.522,13.4136" in q, q)
        check("synonym: gym -> fitness_centre", "fitness_centre" in om._overpass_query("gym", 1, 2, 3))
        check("spoken text cannot break the query",
              '"' not in om._overpass_query('su"shi);out;(', 1, 2, 3).split("[name~")[1].split(",i]")[0][1:-1])
        down.add("overpass-api.de")
        reply["photon.komoot.io"] = lambda url, kw: (
            {"features": [{"properties": {"name": "Sushi Ya", "street": "Karl-Marx-Allee",
                                          "housenumber": "1", "city": "Berlin"},
                           "geometry": {"coordinates": [13.42, 52.52]}}]}
            if "sushi" in kw["params"]["q"].lower() else PHOTON_ALEX)
        out = run(om.find_place, {"query": "sushi near Alexanderplatz"})
        check("Overpass busy -> Photon, biased to the anchor",
              "Sushi Ya, Karl-Marx-Allee 1, Berlin" in out and calls[-1][2]["params"].get("lat") == 52.522,
              out)
        down.discard("overpass-api.de")
        check("empty query asks", "look for" in run(om.find_place, {}).lower())

        print("\n[7] no 'near': around home, then the region; no home: a plain name search")
        from mushegh.brain import prefs
        real_home = prefs.home_location
        try:
            prefs.home_location = lambda: None
            near_reply[:] = [{"name": "Berghain", "lat": "52.511", "lon": "13.443",
                              "address": {"road": "Am Wriezener Bahnhof", "city": "Berlin"}}]
            out = run(om.find_place, {"query": "Berghain"})
            plain = [kw["params"] for _, u, kw in calls if "nominatim" in u]
            check("no home -> one plain Nominatim name search", len(plain) == 1
                  and "bounded" not in plain[0] and "Berghain, Am Wriezener Bahnhof, Berlin" in out, out)
            prefs.home_location = lambda: "Alexanderplatz"
            boxes: list[float] = []

            def by_radius(url, kw):
                q = kw["params"]
                if not q.get("bounded"):
                    return nominatim(url, kw)
                v = [float(x) for x in q["viewbox"].split(",")]
                boxes.append(v[1] - v[3])
                return near_reply if v[1] - v[3] > 0.1 else []      # only the wide box finds it
            reply["nominatim.openstreetmap.org"] = by_radius
            near_reply.append(dict(near_reply[0]))                  # mapped twice in OSM
            out = run(om.find_place, {"query": "Berghain"})
            check("home: walkable box first, then the region", len(boxes) == 2 and boxes[0] < boxes[1],
                  str(boxes))
            check("found across town, said in km", "Berghain, Am Wriezener Bahnhof (2.3 km)" in out, out)
            check("a place mapped twice is said once", out.count("Berghain") == 1, out)
            reply["nominatim.openstreetmap.org"] = lambda url, kw: (
                [] if kw["params"].get("bounded") else near_reply)          # in another city
            reply["overpass-api.de"] = {"elements": []}
            out = run(om.find_place, {"query": "Berghain"})
            check("not near home -> the plain name search finds it, before slow Photon",
                  "Berghain, Am Wriezener Bahnhof, Berlin" in out and "photon.komoot.io" not in hosts(),
                  out)
        finally:
            prefs.home_location = real_home
            reply["nominatim.openstreetmap.org"] = nominatim
    finally:
        om.http_get, om.http_post, settings.user_tz, om.NOMINATIM_GAP = real
        CACHE.clear()

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    raise SystemExit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
