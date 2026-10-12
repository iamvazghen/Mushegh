"""34.R4 — a raw FIT file from the watch becomes dated readings, offline.

The file is built here byte by byte (header, definitions, data, CRC), so the test needs no fixture
and no device: it proves the decoder path, the Garmin cumulative-steps rule, `timestamp_16`
reconstruction and that a broken file is reported rather than half-read.

    uv run python bench/test_health_ingest.py
"""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    mark = "[PASS]" if ok else "[FAIL]"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  {mark} {name}" + (f"  {detail}" if detail and not ok else ""))


_CRC = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
        0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]


def _crc(data: bytes, c: int = 0) -> int:
    for b in data:
        for nib in (b & 0xF, b >> 4):
            t = _CRC[c & 0xF]
            c = ((c >> 4) & 0x0FFF) ^ t ^ _CRC[nib]
    return c


def fit_file(messages: list[tuple[int, list[tuple[int, int, int, str]], list[tuple]]]) -> bytes:
    """(global msg number, [(field num, size, base type, struct fmt)], rows) -> a valid FIT file."""
    body = b""
    for local, (gnum, fields, rows) in enumerate(messages):
        body += struct.pack("<BBBHB", 0x40 | local, 0, 0, gnum, len(fields))
        body += b"".join(struct.pack("<BBB", n, s, bt) for n, s, bt, _ in fields)
        for row in rows:
            body += bytes([local]) + b"".join(struct.pack("<" + f, v) for (*_, f), v in zip(fields, row))
    head = struct.pack("<BBHI4s", 14, 0x20, 2132, len(body), b".FIT")
    head += struct.pack("<H", _crc(head))
    return head + body + struct.pack("<H", _crc(head + body))


FIT_EPOCH = 631065600            # 1989-12-31T00:00:00Z
T0 = 1791800000                  # 2026-10-12 10:13:20 UTC — midday everywhere it runs
TS = (253, 4, 0x86, "I")         # timestamp
TS16 = (26, 2, 0x84, "H")        # monitoring.timestamp_16
WALKING = 6


def main() -> None:
    from mushegh.brain import vitals

    tmp = Path(tempfile.mkdtemp(prefix="mushegh-fit-"))
    monitoring_full = (55, [TS, (5, 1, 0x00, "B"), (3, 4, 0x86, "I"), (27, 1, 0x02, "B")], [
        (T0 - FIT_EPOCH, WALKING, 4000, 0),
        (T0 + 3600 - FIT_EPOCH, WALKING, 9000, 72),
    ])
    # A later sample carrying only timestamp_16, as most Garmin monitoring samples do.
    monitoring_short = (55, [TS16, (5, 1, 0x00, "B"), (3, 4, 0x86, "I"), (27, 1, 0x02, "B")], [
        ((T0 + 7200 - FIT_EPOCH) & 0xFFFF, WALKING, 9500, 80),
    ])
    resting = (211, [TS, (0, 1, 0x02, "B")], [(T0 - FIT_EPOCH, 55)])
    good = tmp / "monitor.fit"
    good.write_bytes(fit_file([monitoring_full, monitoring_short, resting]))

    print("[1] a Garmin monitoring file becomes readings")
    v = vitals.read_export(good)
    check("read without error", v.ok, v.error)
    day = vitals.Reading("x", 0, at=T0).day()
    steps = v.by_day("steps")
    check("steps are the day's running total, not the sum of samples", steps == {day: 9500.0}, str(steps))
    hr = [r for r in v.readings if r.kind == "heart rate"]
    check("zero heart rate is not a reading", [r.value for r in hr] == [72.0, 80.0], str([r.value for r in hr]))
    check("timestamp_16 is rebuilt from the last full timestamp", hr[-1].at == T0 + 7200, str(hr[-1].at))
    check("resting heart rate is read", v.by_day("resting heart rate") == {day: 55.0},
          str(v.by_day("resting heart rate")))

    print("\n[2] since= skips what was already imported")
    later = vitals.read_export(good, since=T0 + 1)
    check("only readings after `since`", all(r.at > T0 + 1 for r in later.readings) and later.readings,
          str([(r.kind, r.at) for r in later.readings]))

    print("\n[3] failures are reported, not half-read")
    broken = tmp / "broken.fit"
    broken.write_bytes(good.read_bytes()[:-9])
    b = vitals.read_export(broken)
    check("a truncated file is an error, said in words", not b.ok and "FIT" in b.error, b.error)
    check("a missing file is an error", not vitals.read_export(tmp / "nope.fit").ok)
    xml = tmp / "export.xml"
    xml.write_text('<HealthData><Record type="HKQuantityTypeIdentifierStepCount" '
                   'startDate="2026-10-12 12:00:00 +0200" value="1200" unit="count"/></HealthData>')
    check("an .xml path still goes to the Apple Health reader", vitals.read_export(xml).kinds == {"steps": 1},
          str(vitals.read_export(xml).kinds))

    print(f"\n=== {passed}/{passed + failed} checks passed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
