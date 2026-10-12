"""Can a fresh machine start from `.env.example`? Load it and find out.

This tool exists because a static prediction was wrong here. It first classified every
line in `.env.example` by its Settings annotation and reported "15 lines will NOT start"
from trailing comments. That was false: pydantic-settings reads an env FILE through
python-dotenv, which strips inline comments. Only OS environment variables keep them.
The real failure was two blank values on typed int fields, which no amount of comment
analysis would have found.

So the check here is not a prediction. It loads `Settings` against `.env.example` exactly
as a fresh install would, and reports what actually breaks.

Two findings recorded 2026-10-08, both measured:
  * the 61 inline comments in `.env.example` are HARMLESS - python-dotenv strips them.
    They are house style and should stay.
  * `env_ignore_empty` is False, so a blank value on a typed field is passed through as
    the empty string and raises. `audio_input_device_index` and `telegram_api_id` are both
    blank in the template, so a fresh install does not start.

Usage:
    python tools/verify_env_template.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from mushegh.config import Settings  # noqa: E402

ASSIGN_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)=(.*)$")


def blank_typed_keys() -> list[tuple[int, str, str]]:
    """Lines whose value is blank and whose field is typed - the ones that raise."""
    typed: dict[str, str] = {}
    for name, field in Settings.model_fields.items():
        ann = field.annotation
        if isinstance(ann, type) and issubclass(ann, (int, float, bool)):
            typed[name.upper()] = ann.__name__
    hits: list[tuple[int, str, str]] = []
    template = ROOT / ".env.example"
    for n, line in enumerate(template.read_text(encoding="utf-8").splitlines(), 1):
        m = ASSIGN_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if value.split("#", 1)[0].strip():  # has a real value
            continue
        field_name = key.removeprefix("MUSHEGH_").upper()
        if field_name in typed:
            hits.append((n, key, typed[field_name]))
    return hits


def main() -> int:
    template = ROOT / ".env.example"
    if not template.is_file():
        print(f"missing {template}")
        return 1

    print("Fresh-install check: load Settings against .env.example\n")

    ignore_empty = Settings.model_config.get("env_ignore_empty")
    print(f"  env_ignore_empty : {ignore_empty}"
          + ("  (a blank value is passed through and validated)"
             if ignore_empty is False else "  (blank values are ignored)"))

    try:
        settings = Settings(_env_file=str(template), _env_file_encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"  RESULT           : FAILS TO LOAD - {type(exc).__name__}")
        errors = getattr(exc, "errors", None)
        if callable(errors):
            for err in errors():
                loc = ".".join(str(p) for p in err.get("loc", ()))
                print(f"    {loc}: {err.get('msg')}")
                print(f"      input_value={err.get('input')!r}")
        print("\n  A fresh machine cannot start from this template.")
        loaded = False
    else:
        print(f"  RESULT           : loads cleanly "
              f"(brain_port={settings.brain_port}, daily_budget="
              f"{settings.proactive_daily_budget})")
        loaded = True

    comments = sum(
        1 for line in template.read_text(encoding="utf-8").splitlines()
        if (m := ASSIGN_RE.match(line)) and "#" in m.group(2)
        and m.group(2).split("#", 1)[0].strip()
    )
    print(f"\n  inline comments on valued lines: {comments}")
    print("    These are harmless: python-dotenv strips a trailing comment from an env")
    print("    FILE. Only an OS environment variable keeps it, which is a different path.")

    blanks = blank_typed_keys()
    if blanks:
        print(f"\n  blank value on a typed field: {len(blanks)}")
        for n, key, kind in blanks:
            print(f"    .env.example:{n}  {key}=          # typed {kind}, no default to fall back on")

    return 0 if loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())