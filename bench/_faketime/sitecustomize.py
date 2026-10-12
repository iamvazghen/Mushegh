"""Pretend it is another day, so date-dependent tests can be caught on purpose.

Imported automatically by CPython at startup when this directory is on PYTHONPATH — which means
it lands BEFORE any test does `from datetime import date`, so the name a test binds is already the
patched one. Set MUSHEGH_FAKE_TODAY=YYYY-MM-DD to arm it; unset, this file does nothing at all. Add
MUSHEGH_FAKE_CLOCK=HH:MM to move the TIME OF DAY as well, which is the axis that caught two fixtures
building "today" from a relative offset — they walked backwards over midnight and failed for a few
minutes every night.

Why it exists: `test_calendar_dates` asserted `"T" not in s` against an all-day string formatted
as "on Tue 11 August" — the T in "Tue". It failed on Tuesdays and Thursdays and passed the other
five days, and was only caught because one run happened to straddle midnight into a Tuesday.
Finding that class of bug by luck does not scale; running the suite on a chosen weekday does.
"""
import os

_fake = os.environ.get("MUSHEGH_FAKE_TODAY", "").strip()
if _fake:
    import datetime as _dt

    _y, _m, _d = (int(x) for x in _fake.split("-"))
    _real_date, _real_datetime = _dt.date, _dt.datetime

    class _Date(_real_date):
        @classmethod
        def today(cls):
            return cls(_y, _m, _d)

    # MUSHEGH_FAKE_CLOCK=HH:MM moves the time of day too. It is expressed as a fixed DELTA computed
    # once, not as a pinned hour: a pinned clock stops advancing inside the minute, and a test that
    # measures a duration would then measure zero. With a delta, "now" starts at the requested time
    # and then ticks normally, which is what a test replayed "just after midnight" actually needs.
    _clock = os.environ.get("MUSHEGH_FAKE_CLOCK", "").strip()
    _delta = None
    if _clock:
        _hh, _mm = (int(x) for x in _clock.split(":")[:2])
        _delta = (_real_datetime.now().replace(year=_y, month=_m, day=_d, hour=_hh, minute=_mm,
                                               second=0, microsecond=0)
                  - _real_datetime.now())

    class _DateTime(_real_datetime):
        @classmethod
        def now(cls, tz=None):
            # Keep the real wall-clock TIME (unless MUSHEGH_FAKE_CLOCK moved it); only move the
            # calendar day. A test that measures a duration must still see time advance, so this
            # cannot be a frozen instant.
            real = _real_datetime.now(tz)
            if _delta is not None:
                return real + _delta
            return real.replace(year=_y, month=_m, day=_d)

        @classmethod
        def today(cls):
            return cls.now()

        @classmethod
        def utcnow(cls):
            real = _real_datetime.utcnow()
            if _delta is not None:
                return real + _delta
            return real.replace(year=_y, month=_m, day=_d)

    _dt.date = _Date
    _dt.datetime = _DateTime

    # `time.time()` has to move by the SAME amount, or code that mixes the two clocks breaks in a
    # way that looks like a product bug and is not. `presence` stamps rows with time.time() and
    # then computes the day's bounds from datetime.now(): shift only the second and every row
    # falls outside every window, so screen_time reports "no activity recorded for today".
    # Shift by whole days so the wall-clock time of day, and every duration, is untouched.
    import time as _time

    # Whole days is NOT the right offset across a DST boundary. `datetime.now()` moves the
    # calendar and keeps the local wall-clock time, so faking 31 December (CET) from a day in
    # September (CEST) shifts the two clocks by amounts that differ by exactly one hour: the
    # process then had `datetime.now()` reading 00:20 on the 31st while `time.time()` read 23:20 on
    # the 30th. A row stamped with one and filtered by the other falls outside its own day, which
    # is the "looks like a product bug and is not" failure this block was written to prevent —
    # present in the block itself. `.timestamp()` on a naive datetime applies the local rules for
    # THAT date, so the difference it yields carries the DST hour with it.
    _now_real = _real_datetime.now()
    _anchor = ((_now_real + _delta) if _delta is not None
               else _now_real.replace(year=_y, month=_m, day=_d))
    _offset = _anchor.timestamp() - _now_real.timestamp()
    if _offset:
        _real_time = _time.time
        _time.time = lambda: _real_time() + _offset
        # `localtime` has to move with it. Shifting one and not the other leaves the process with
        # two clocks that disagree about which day it is — which is precisely the defect class this
        # shim exists to expose, so having it inside the shim is not a joke worth keeping. A
        # fixture that builds "today" from `time.localtime()` was landing on the real date while
        # `screen_time` computed the day from the faked `datetime.now()`, and nothing lined up.
        _real_localtime = _time.localtime
        _time.localtime = lambda secs=None: _real_localtime(
            _real_time() + _offset if secs is None else secs)
        _real_gmtime = _time.gmtime
        _time.gmtime = lambda secs=None: _real_gmtime(
            _real_time() + _offset if secs is None else secs)
