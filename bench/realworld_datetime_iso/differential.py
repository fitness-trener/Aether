"""Differential test: the Aether ISO 8601 port (written from the standard and
the CPython 3.11 docs, bench/realworld_datetime_iso/datetime_iso_port.aeth)
vs CPython's own `date/time/datetime.fromisoformat` and `isoformat`.

Four runs, fixed seed:
  1. parse: every generated string goes to all three fromisoformat APIs and
     to the port under the documented profile. Every divergence is
     attributed by re-running the port with ONE (then two) named CPython
     relaxations switched on; it counts as explained only if the port then
     returns exactly CPython's value.
  2. round trip: isoformat -> fromisoformat on generated values, both sides.
  3. week dates: 22 Dec-10 Jan of every year plus every 29th day (every
     day 0001-01-01..9999-12-31 with --full-weeks, ~20 min) through the
     port's week <-> calendar functions (runtime contracts on) vs
     isocalendar() and fromisocalendar().
  4. RFC 3339 §5.6: the strings of run 1 that are RFC 3339 date-times, and
     what CPython does with them.

The run fails on any unexplained divergence, round-trip failure or
contract violation.

    python -B bench/realworld_datetime_iso/differential.py [--scale 0.05] [--mutant NAME] [--full-weeks]
"""

from __future__ import annotations

import argparse
import itertools
import os
import random
import re
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

SEED = 20260930
N_PARSE = 210_000
N_ROUNDTRIP = 60_000

# Each mutant breaks one rule of the spec in the port's source.
MUTANTS = {
    "leap_no_century": (  # Gregorian leap rule without the 100/400 exceptions
        "return (y % 4 == 0 and y % 100 != 0) or y % 400 == 0",
        "return y % 4 == 0"),
    "week1_contains_jan1": (  # week 01 = the week containing 1 January
        "let firstThursday = jan1 + (3 - weekday0(jan1)) % 7\n  return firstThursday - 3",
        "return jan1 - weekday0(jan1)"),
    "comma_not_decimal_sign": (  # ISO: the decimal sign is "," or "."
        'let markedFraction = c == "." or c == ","',
        'let markedFraction = c == "."'),
}

# The named CPython 3.11 relaxations the port can model (Profile.lax*).
LAX = ["laxMixed", "laxColonFraction", "laxFracHourMinute", "laxFracNoMark",
       "laxEmptyFraction", "laxOffsetRange", "laxJunkBeforeTz"]
PROFILE_FIELDS = ["anySeparator", "offsetSeconds", "timeWithoutT", "midnight24"] + LAX
DOC = dict(anySeparator=True, offsetSeconds=True, timeWithoutT=True, midnight24=True)
ISO = dict(midnight24=True)
EXTENSIONS = ["anySeparator", "offsetSeconds", "timeWithoutT"]


def load_port(mutant: str | None) -> dict:
    path = os.path.join(HERE, "datetime_iso_port.aeth")
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if mutant:
        old, new = MUTANTS[mutant]
        assert old in src, mutant
        src = src.replace(old, new, 1)
    g = build_namespace()
    g["__name__"] = "aether_datetime_iso_port"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


class Port:
    def __init__(self, g):
        self.g = g
        self.mk = g["_ae_Profile"]
        self.cache = {}
        self.fn = {"date": g["_ae_parseDate"], "time": g["_ae_parseTime"],
                   "datetime": g["_ae_parseDateTime"]}

    def profile(self, **flags):
        key = tuple(sorted(k for k, v in flags.items() if v))
        if key not in self.cache:
            self.cache[key] = self.mk(*[bool(flags.get(f)) for f in PROFILE_FIELDS])
        return self.cache[key]

    def run(self, api, s, **flags):
        try:
            r = self.fn[api](s, self.profile(**flags))
        except Exception as e:  # a contract violation inside the port
            return ("contract", f"{type(e).__name__}: {e}")
        if r[0] == "Ok":
            return ("ok", stamp_tuple(r[1]))
        return ("err", r[1])


def stamp_tuple(d) -> tuple:
    return (d["year"], d["month"], d["day"], d["hour"], d["minute"], d["second"],
            d["micro"], d["hasOffset"], d["offsetMicros"])


def td_micros(td: timedelta) -> int:
    return (td.days * 86400 + td.seconds) * 1_000_000 + td.microseconds


def lib_tuple(v) -> tuple:
    if isinstance(v, datetime):
        off = v.utcoffset()
        return (v.year, v.month, v.day, v.hour, v.minute, v.second, v.microsecond,
                off is not None, td_micros(off) if off is not None else 0)
    if isinstance(v, date):
        return (v.year, v.month, v.day, 0, 0, 0, 0, False, 0)
    off = v.utcoffset()
    return (0, 0, 0, v.hour, v.minute, v.second, v.microsecond,
            off is not None, td_micros(off) if off is not None else 0)


LIB = {"date": date.fromisoformat, "time": time.fromisoformat,
       "datetime": datetime.fromisoformat}


def run_lib(api, s):
    try:
        return ("ok", lib_tuple(LIB[api](s)))
    except ValueError as e:
        return ("err", str(e))
    except Exception as e:  # anything else is a rejection too, reported apart
        return ("crash", f"{type(e).__name__}: {e}")


def zero_offset_dropped(port_v, lib_v) -> bool:
    """3.11 C: an offset whose whole-second part is 0 comes back as UTC,
    losing its microseconds (gh-152079, fixed in 3.13+)."""
    return (port_v[:8] == lib_v[:8] and port_v[7] and lib_v[8] == 0
            and port_v[8] != 0 and abs(port_v[8]) < 1_000_000)


# ---------------------------------------------------------------- classification

def c_separator(s: str) -> int:
    """Where CPython looks for the date/time separator: a transcription of
    `_find_isoformat_datetime_separator` (Modules/_datetimemodule.c), whose
    comment calls the week-date case "best effort because this is an
    extension of the spec anyway"."""
    if len(s) == 7:
        return 7
    if s[4] == "-":
        if s[5] == "W":
            if len(s) > 8 and s[8] == "-":
                return 8 if len(s) > 10 and s[10] in "0123456789" else 10
            return 8
        return 10
    if s[4] == "W":
        idx = 7
        while idx < len(s) and s[idx] in "0123456789":
            idx += 1
        if idx < 9:
            return idx
        return 7 if idx % 2 == 0 else 8
    return 8


def reduced_week_rewrite(api, s):
    """If CPython reads a reduced week date YYYY-Www / YYYYWww (as day 1,
    which its test suite asserts), the same string with the day spelled
    out, split where CPython splits it; else None."""
    if len(s) < 7:
        return None
    sep = len(s) if api == "date" else c_separator(s)
    d = s[:sep]
    if len(d) == 7 and d[4] == "W":
        return d + "1" + s[sep:]
    if len(d) == 8 and d[4:6] == "-W":
        return d + "-1" + s[sep:]
    return None


def explain(port: Port, api, s, lv):
    """The CPython relaxation(s) under which the port returns exactly
    CPython's value: up to three lax flags, optionally after the reduced-week
    rewrite. None if no combination reproduces it."""
    cands = [(s, [])]
    s2 = reduced_week_rewrite(api, s)
    if s2 is not None:
        cands.append((s2, ["ReducedWeek"]))
    for k in (0, 1, 2, 3):
        for text, pre in cands:
            for combo in itertools.combinations(LAX, k):
                if k == 0 and not pre:
                    continue
                r = port.run(api, text, **DOC, **{c: True for c in combo})
                if r[0] != "ok":
                    continue
                if r[1] == lv[1]:
                    return "+".join(pre + [c[3:] for c in combo])
                if zero_offset_dropped(r[1], lv[1]):
                    return "+".join(pre + [c[3:] for c in combo] + ["zero_offset_drops_subsecond"])
    return None


def classify(port: Port, api, s, pv, lv):
    """A class name for a divergence, or None if unexplained."""
    pk, lk = pv[0], lv[0]
    if pk == "ok" and lk in ("err", "crash"):
        if port.run(api, s, **dict(DOC, midnight24=False))[0] == "err":
            return "port_accepts:midnight_24"
        # the port reads a complete week date; CPython's split heuristic
        # puts the separator elsewhere (a digit separator after the date)
        if api == "datetime" and len(s) > 10 and "W" in s[4:6] \
                and c_separator(s) != (10 if s[4] == "-" else 8):
            return "port_accepts:week_date_digit_separator"
        return None
    if pk == "err" and lk == "ok":
        # date.fromisoformat admits 10 UTF-8 BYTES, reads a basic date from
        # the first 8 and never looks at the rest
        if api == "date" and len(s.encode("utf-8", "surrogatepass")) == 10 \
                and s[4] != "-" and port.run(api, s[:8], **DOC) == lv:
            return "lib_accepts:date_ignores_trailing_bytes"
        e = explain(port, api, s, lv)
        return None if e is None else "lib_accepts:" + e
    if pk == "ok" and lk == "ok":
        if zero_offset_dropped(pv[1], lv[1]):
            return "value:zero_offset_drops_subsecond"
        e = explain(port, api, s, lv)
        return None if e is None else "value:" + e
    return None


def extension_used(port: Port, api, s) -> str:
    """For an agreed acceptance: '' if plain ISO 8601 accepts it, else the
    documented CPython widening(s) it needs."""
    if port.run(api, s, **ISO)[0] == "ok":
        return ""
    need = [e for e in EXTENSIONS if port.run(api, s, **dict(ISO, **{e: True}))[0] == "ok"]
    return "+".join(need) if need else "several"


# ---------------------------------------------------------------- generators

BOUNDARY_YEARS = [1, 2, 3, 4, 5, 6, 7, 8, 1582, 1600, 1700, 1900, 2000, 2004, 2015,
                  2020, 2021, 2026, 2100, 2400, 9990, 9995, 9996, 9997, 9998, 9999]
SEPARATORS = ["T", "T", "T", " ", "t", "_", "x", "1", "0", "-", "Z", "+", ":", ".",
              "\u00e9", "\u65e5", "\U0001F600", "\ud800"]


def rand_year(rng):
    return rng.choice(BOUNDARY_YEARS) if rng.random() < 0.3 else rng.randint(1, 9999)


def iso_weeks(y):
    return date(y, 12, 28).isocalendar()[1]


def dim(y, m):
    return 29 if m == 2 and (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else \
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def gen_date(rng):
    """(string, extended?) for a complete date, sometimes out of range."""
    ext = rng.random() < 0.5
    y = rand_year(rng)
    bad = rng.random() < 0.08
    if rng.random() < 0.7:
        m = rng.randint(1, 12)
        d = rng.randint(1, dim(y, m))
        if rng.random() < 0.1:
            d = dim(y, m)
        if bad:
            m, d = rng.choice([(0, d), (13, d), (m, 0), (m, dim(y, m) + 1), (2, 29), (m, 32)])
        body = f"{y:04d}-{m:02d}-{d:02d}" if ext else f"{y:04d}{m:02d}{d:02d}"
    else:
        w = rng.randint(1, iso_weeks(y))
        if rng.random() < 0.2:
            w = iso_weeks(y)
        d = rng.randint(1, 7)
        if bad:
            w, d = rng.choice([(53, d), (0, d), (54, d), (w, 0), (w, 8)])
        body = f"{y:04d}-W{w:02d}-{d}" if ext else f"{y:04d}W{w:02d}{d}"
    if rng.random() < 0.01:
        body = "0000" + body[4:]
    return body, ext


def gen_fraction(rng):
    n = rng.choice([1, 1, 2, 3, 3, 4, 5, 6, 6, 6, 7, 8, 9, 12])
    return rng.choice(".,") + "".join(rng.choice("0123456789") for _ in range(n))


def gen_clock(rng, ext):
    parts = rng.choices([1, 2, 3], [0.15, 0.25, 0.6])[0]
    h = rng.randint(0, 23)
    mi = rng.randint(0, 59)
    s = rng.randint(0, 59)
    r = rng.random()
    if r < 0.04:
        h, mi, s = 24, 0, 0
    elif r < 0.07:
        h = rng.randint(24, 99)
    elif r < 0.10:
        mi = rng.randint(60, 99)
    elif r < 0.12:
        s = 60
    elif r < 0.14:
        s = rng.randint(61, 99)
    sep = ":" if ext else ""
    out = f"{h:02d}"
    if parts >= 2:
        out += f"{sep}{mi:02d}"
    if parts == 3:
        out += f"{sep}{s:02d}"
        if rng.random() < 0.45:
            frac = gen_fraction(rng)
            if h == 24 and rng.random() < 0.7:
                frac = frac[0] + "0" * (len(frac) - 1)
            out += frac
    return out


def gen_offset(rng, ext):
    r = rng.random()
    if r < 0.4:
        return ""
    if r < 0.55:
        return "Z"
    sign = rng.choice("+-")
    oh = rng.randint(0, 23) if rng.random() > 0.03 else rng.randint(24, 99)
    om = rng.randint(0, 59) if rng.random() > 0.03 else rng.randint(60, 99)
    osec = rng.randint(0, 59)
    sep = ":" if ext else ""
    if r < 0.65:
        return f"{sign}{oh:02d}"
    if r < 0.9:
        return f"{sign}{oh:02d}{sep}{om:02d}"
    out = f"{sign}{oh:02d}{sep}{om:02d}{sep}{osec:02d}"
    if r > 0.96:
        out += gen_fraction(rng)
    return out


def gen_rfc3339(rng):
    y = rand_year(rng)
    m = rng.randint(1, 12)
    d = rng.randint(1, dim(y, m))
    s = 60 if rng.random() < 0.05 else rng.randint(0, 59)
    out = f"{y:04d}-{m:02d}-{d:02d}{rng.choice('TTTt')}{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{s:02d}"
    if rng.random() < 0.4:
        out += "." + "".join(rng.choice("0123456789") for _ in range(rng.randint(1, 9)))
    if rng.random() < 0.5:
        out += rng.choice("ZZZz")
    else:
        out += f"{rng.choice('+-')}{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}"
    return out


def gen_valid(rng):
    r = rng.random()
    if r < 0.08:
        return gen_rfc3339(rng)
    ext = rng.random() < 0.55
    if r < 0.2:
        return gen_date(rng)[0]
    clock = gen_clock(rng, ext) + gen_offset(rng, ext)
    if r < 0.4:
        return ("T" if rng.random() < 0.4 else "") + clock
    while True:  # a date in the same format as the time
        d, d_ext = gen_date(rng)
        if d_ext == ext:
            return d + rng.choice(SEPARATORS) + clock


ALPHABET = "0123456789-:.,TWZ+ tzwx\n\u00e9\u0661"


def mutate(rng, s):
    for _ in range(rng.randint(1, 2)):
        op = rng.randrange(13)
        i = rng.randint(0, len(s))
        if op == 0:  # insert a character
            s = s[:i] + rng.choice(ALPHABET) + s[i:]
        elif op == 1 and s:  # delete a character
            i = min(i, len(s) - 1)
            s = s[:i] + s[i + 1:]
        elif op == 2 and len(s) > 1:  # swap neighbours
            i = min(i, len(s) - 2)
            s = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        elif op == 3:  # a fraction on the hour or the minute
            m = re.search(r"(?:^T?|[^0-9W])(\d\d)(?::?(\d\d))?", s[8:] if len(s) > 10 else s)
            if m:
                base = 8 if len(s) > 10 else 0
                end = base + m.end(1 if rng.random() < 0.5 or not m.group(2) else 2)
                s = s[:end] + gen_fraction(rng) + s[end:]
        elif op == 4:  # mix basic and extended: drop or add one separator
            idx = [j for j, c in enumerate(s) if c in ":-"]
            if idx and rng.random() < 0.6:
                j = rng.choice(idx)
                s = s[:j] + s[j + 1:]
            else:
                digits = [j for j in range(2, len(s)) if s[j - 2:j].isdigit() and s[j:j + 1].isdigit()]
                if digits:
                    j = rng.choice(digits)
                    s = s[:j] + rng.choice(":-") + s[j:]
        elif op == 5:  # junk right before the UTC designator
            m = re.search(r"[Z+\-]", s[10:] if len(s) > 10 else "")
            if m:
                j = 10 + m.start()
                junk = rng.choice([" ", "x", ":", "0", "\u00e9", " junk ", "Q"])
                s = s[:j] + junk + s[j:]
        elif op == 6:  # drop a decimal sign
            s = re.sub(r"[.,]", "", s, count=1)
        elif op == 7:  # lower case designators
            s = s.lower()
        elif op == 8:  # reduced precision / ordinal / expanded forms
            s = rng.choice([s[:7], s[:8], s[:4], s[:5] + "123", s[:4] + "123",
                            "+0" + s, "-" + s, s[:8] + s[10:] if len(s) > 10 else s])
        elif op == 9:  # trailing garbage
            s = s + rng.choice(["\n", " ", "Z", "0", "x", "00", ":", "."])
        elif op == 10:  # empty fraction
            s = re.sub(r"([.,])\d+", r"\1", s, count=1)
        elif op == 11:  # unmarked fraction: glue digits after the seconds
            s = re.sub(r"(\d{6}|\d\d:\d\d:\d\d)(?![\d.,])", lambda m: m.group(1) + str(rng.randint(0, 999)), s, count=1)
        else:  # Z plus more
            s = s.replace("Z", rng.choice(["ZZ", "Z+01", "Z0"]), 1) if "Z" in s else s + "Z"
    return s


EDGE_CASES = [
    # docs examples (3.11)
    "2019-12-04", "20191204", "2021-W01-1", "2011-11-04", "20111104", "2011-11-04T00:05:23",
    "2011-11-04T00:05:23Z", "20111104T000523", "2011-W01-2T00:05:23.283",
    "2011-11-04 00:05:23.283", "2011-11-04 00:05:23.283+00:00", "2011-11-04T00:05:23+04:00",
    "04:23:01", "T04:23:01", "T042301", "04:23:01.000384", "04:23:01,000384",
    "04:23:01+04:00", "04:23:01Z", "04:23:01+00:00",
    # documented-unsupported forms
    "2019-12", "2019", "2019-338", "2019338", "+002019-12-04", "12.5", "12:30,5", "T1250.50",
    # week-date boundaries
    "0001-W01-1", "9999-W52-5", "9999-W52-6", "0000-W52-7", "2015-W53-4", "2015-W53-5",
    "2019-W53-1", "2020-W53-6", "2020W537", "2021-W53-1", "2025W01", "2025-W01", "2022W52",
    # probes from the investigation
    "12345678", "123456789", "1234567", "12:30x+05:00", "12:30:45 Z", "1230:Z", "12xZ",
    "12:30:45.1234567x-01:00", "12:30:45.400000 +02:30", "12:30:45.400 +02:30",
    "12:34:56.+05:00", "12:34:56.Z", "12:30:45+00:90:00", "12:30:45+05:60",
    "2020-01-01T12:34:56+00:00:00.000001", "2020-01-01T24:00", "24:00", "24:00:00.000",
    "9999-12-31T24:00", "2020-02-28T24:00:00", "20230808120000Z", "2020-01-01T",
    "2020W0112", "2020-W01-1234", "2024-01-17T15:21:00-0800", "20240117T15:21:00-08:00",
    "2020-01-01T12:34:56z", "2020-01-01t12:34:56Z", "2020-01-01T23:59:60Z",
    "12:34:56+05:30:15.5", "12:34:56+053015", "12:34:56-00:00", "00:00:00,000-23:59:59.999999",
    "2020-01-01\ud80012:00", "2020-01-01\U0001F60012:00", "", "T", "2020-01-01 ",
]


# ---------------------------------------------------------------- round trips

def gen_value(rng):
    y = rand_year(rng)
    m = rng.randint(1, 12)
    d = rng.randint(1, dim(y, m))
    r = rng.random()
    us = 0 if r < 0.4 else rng.choice([1, 999999, 500000, rng.randint(0, 999) * 1000]) if r < 0.6 \
        else rng.randint(0, 999999)
    r = rng.random()
    if r < 0.3:
        off = None
    elif r < 0.4:
        off = 0
    elif r < 0.75:
        off = rng.randint(-1439, 1439) * 60_000_000
    elif r < 0.85:
        off = rng.randint(-86399, 86399) * 1_000_000
    elif r < 0.95:
        off = rng.randint(-86_399_999_999, 86_399_999_999)
    else:
        off = rng.choice([1, -1]) * rng.randint(1, 999_999)
    return (y, m, d, rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59), us, off)


TIMESPECS = ["auto", "auto", "auto", "hours", "minutes", "seconds", "milliseconds", "microseconds"]
TRUNC = {"auto": 1, "microseconds": 1, "milliseconds": 1000, "seconds": 10**6,
         "minutes": 60 * 10**6, "hours": 3600 * 10**6}


def truncate(t, spec):
    """(h, mi, s, us) with the components `spec` leaves out set to 0."""
    h, mi, s, us = t
    total = ((mi * 60 + s) * 10**6 + us) // TRUNC[spec] * TRUNC[spec]
    return (h, total // (60 * 10**6), total // 10**6 % 60, total % 10**6)


def roundtrip(port: Port, g, rng, kind):
    y, m, d, h, mi, s, us, off = gen_value(rng)
    tz = None if off is None else timezone.utc if off == 0 else timezone(timedelta(microseconds=off))
    spec = rng.choice(TIMESPECS)
    sep = rng.choice(SEPARATORS)
    stamp = g["_ae_Stamp"](y, m, d, h, mi, s, us, off is not None, off or 0)
    if kind == "date":
        obj = date(y, m, d)
        lib_s = obj.isoformat()
        port_s = g["_ae_formatDate"](stamp)
        want = (y, m, d, 0, 0, 0, 0, False, 0)
    elif kind == "time":
        obj = time(h, mi, s, us, tzinfo=tz)
        lib_s = obj.isoformat(timespec=spec)
        port_s = g["_ae_formatTime"](stamp, spec)
        want = (0, 0, 0) + truncate((h, mi, s, us), spec) + (off is not None, off or 0)
    else:
        obj = datetime(y, m, d, h, mi, s, us, tzinfo=tz)
        lib_s = obj.isoformat(sep=sep, timespec=spec)
        port_s = g["_ae_formatDateTime"](stamp, sep, spec)
        want = (y, m, d) + truncate((h, mi, s, us), spec) + (off is not None, off or 0)
    back = run_lib(kind, lib_s)
    checks = {
        "format strings equal": port_s == lib_s,
        "port reads its string back": port.run(kind, port_s, **DOC) == ("ok", want),
        "port reads CPython's string": port.run(kind, lib_s, **DOC) == ("ok", want),
        "CPython reads its string back": back == ("ok", want),
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed == ["CPython reads its string back"] and back[0] == "ok" \
            and zero_offset_dropped(want, back[1]):
        return "explained:zero_offset_drops_subsecond", (lib_s, back)
    return ("pass" if not failed else "FAIL"), (kind, lib_s, port_s, failed, back)


# ---------------------------------------------------------------- RFC 3339

RFC3339 = re.compile(r"\A(\d{4})-(\d\d)-(\d\d)[Tt](\d\d):(\d\d):(\d\d)(\.\d+)?"
                     r"([Zz]|[+-](\d\d):(\d\d))\Z", re.ASCII)


def rfc3339_valid(s):
    m = RFC3339.match(s)
    if not m:
        return False
    y, mo, d, h, mi, sec = (int(m.group(i)) for i in range(1, 7))
    if not (1 <= mo <= 12 and 1 <= d <= dim(max(y, 1), mo) and h <= 23 and mi <= 59 and sec <= 60):
        return False
    return m.group(9) is None or (int(m.group(9)) <= 23 and int(m.group(10)) <= 59)


def rfc3339_reason(s, lib):
    if lib[0] == "ok":
        return "accepted"
    if s[-1] == "z":
        return "rejected: lower-case z (RFC 3339 §5.6 NOTE allows it)"
    if s[17:19] == "60":
        return "rejected: second 60 (leap second)"
    if s[:4] == "0000":
        return "rejected: year 0000"
    return "rejected: OTHER"


# ---------------------------------------------------------------- main

def week_days(full: bool, stride: int):
    """Every day if `full`; else every day from 22 December to 10 January
    of every year (where the ISO year can differ from the calendar year)
    plus every `stride`-th day."""
    for o in range(1, date(9999, 12, 31).toordinal() + 1):
        dd = date.fromordinal(o)
        if full or o % stride == 0 or (dd.month == 12 and dd.day >= 22) \
                or (dd.month == 1 and dd.day <= 10):
            yield dd


def week_sweep(g, full, stride):
    to_week, to_ymd = g["_ae_ymdToIsoWeek"], g["_ae_isoWeekToYmd"]
    weeks = g["_ae_weeksInYear"]
    bad = []
    n = 0
    for dd in week_days(full, stride):
        iso = tuple(dd.isocalendar())
        n += 1
        try:
            w = to_week(dd.year, dd.month, dd.day)
            back = to_ymd(*iso)
        except Exception as e:  # the port's bijection contract fired
            bad.append((dd, iso, f"{type(e).__name__}: {e}"[:160]))
            continue
        if (w["year"], w["week"], w["day"]) != iso or (back["year"], back["month"], back["day"]) \
                != (dd.year, dd.month, dd.day) or date.fromisocalendar(*iso) != dd:
            bad.append((dd, iso, w, back))
    wy = [y for y in range(1, 10000) if weeks(y) != iso_weeks(y)]
    return n, bad, wy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--mutant", choices=sorted(MUTANTS))
    ap.add_argument("--full-weeks", action="store_true",
                    help="week sweep over every day 0001-01-01..9999-12-31 (about 16 min)")
    args = ap.parse_args()
    rng = random.Random(SEED)
    g = load_port(args.mutant)
    port = Port(g)
    print(f"python {sys.version.split()[0]}, seed {SEED}, scale {args.scale}"
          + (f", MUTANT {args.mutant}" if args.mutant else ""))

    # ---- 1. parse differential
    n_parse = int(N_PARSE * args.scale)
    inputs = list(EDGE_CASES)
    while len(inputs) < n_parse:
        v = gen_valid(rng)
        inputs.append(v if rng.random() < 0.4 else mutate(rng, v))
    agree = Counter()
    ext_used = Counter()
    classes = Counter()
    examples: dict[str, list] = {}
    crashes = Counter()
    rfc = Counter()
    rfc_examples: dict[str, list] = {}
    contract = []
    unexplained = []
    for s in inputs:
        for api in ("date", "time", "datetime"):
            pv = port.run(api, s, **DOC)
            lv = run_lib(api, s)
            if pv[0] == "contract":
                contract.append((api, s, pv[1]))
                continue
            if lv[0] == "crash":
                crashes[(api, lv[1].split(":")[0])] += 1
            if api == "datetime" and rfc3339_valid(s):
                reason = rfc3339_reason(s, lv)
                if lv[0] == "ok" and pv[0] == "ok" and pv != lv:
                    reason = "accepted, value differs from the port"
                rfc[reason] += 1
                rfc_examples.setdefault(reason, [])
                if len(rfc_examples[reason]) < 2:
                    rfc_examples[reason].append(s)
            both_reject = pv[0] == "err" and lv[0] in ("err", "crash")
            if both_reject:
                agree["reject"] += 1
                continue
            if pv[0] == "ok" and lv == pv:
                agree["accept"] += 1
                used = extension_used(port, api, s)
                if used:
                    ext_used[used] += 1
                continue
            c = classify(port, api, s, pv, lv)
            if c is None:
                unexplained.append((api, s, pv, lv))
                continue
            classes[c] += 1
            examples.setdefault(c, [])
            if len(examples[c]) < 3:
                examples[c].append(f"{api}:{s!r}")
    total = len(inputs) * 3
    div = sum(classes.values()) + len(unexplained)
    print(f"\nparse: {len(inputs)} strings x 3 APIs = {total} comparisons | "
          f"agree {agree['accept'] + agree['reject']} ({agree['accept']} both accept, same value; "
          f"{agree['reject']} both reject)")
    print(f"  of the agreed acceptances, {sum(ext_used.values())} need a documented widening of ISO 8601:")
    for k, n in sorted(ext_used.items()):
        print(f"    {k:40s} {n:7d}")
    print(f"  divergences: {div} ({sum(classes.values())} attributed, {len(unexplained)} unexplained)")
    for c, n in sorted(classes.items()):
        print(f"    {c:58s} {n:6d}   e.g. {', '.join(examples[c])}")
    cause = Counter()
    for c, n in classes.items():
        for part in c.split(":", 1)[1].split("+"):
            cause[part] += n
    print("  divergences per cause (one divergence can involve several):")
    for k, n in sorted(cause.items(), key=lambda kv: -kv[1]):
        print(f"    {k:40s} {n:6d}")
    if crashes:
        print(f"  CPython exceptions other than ValueError: {dict(crashes)}")
    for u in unexplained[:25]:
        print(f"  UNEXPLAINED {u}")
    for c in contract[:10]:
        print(f"  CONTRACT {c}")
    print("\nRFC 3339 §5.6 date-times among the inputs (datetime.fromisoformat):")
    for k, n in sorted(rfc.items()):
        print(f"    {k:58s} {n:6d}   e.g. {', '.join(repr(x) for x in rfc_examples[k])}")

    # ---- 2. round trips
    n_rt = int(N_ROUNDTRIP * args.scale)
    rt = Counter()
    rt_fail = []
    rt_examples = {}
    for i in range(n_rt):
        kind = "datetime" if i % 5 < 3 else ("time" if i % 5 == 3 else "date")
        try:
            status, info = roundtrip(port, g, rng, kind)
        except Exception as e:  # the port's own round-trip ensures fired
            status, info = "FAIL", (kind, f"{type(e).__name__}: {e}")
        rt[status] += 1
        rt_examples.setdefault(status, info)
        if status == "FAIL":
            rt_fail.append(info)
    print(f"\nround trip: {n_rt} values (date/time/datetime, random sep and timespec)")
    for k, n in sorted(rt.items()):
        print(f"    {k:58s} {n:6d}   e.g. {rt_examples[k]!r}"[:220])
    for f in rt_fail[:15]:
        print(f"  FAIL {f!r}")

    # ---- 3. week dates
    stride = 29 if args.scale >= 1 else 997
    n_days, week_bad, weeks_bad = week_sweep(g, args.full_weeks, stride)
    scope = "every day" if args.full_weeks else f"22 Dec-10 Jan of every year + every {stride}th day"
    print(f"\nweek dates: {n_days} days ({scope}) through ymdToIsoWeek / isoWeekToYmd "
          f"(contracts on) vs isocalendar()/fromisocalendar(): {len(week_bad)} mismatches; "
          f"weeksInYear vs CPython for 9999 years: {len(weeks_bad)} mismatches")
    for b in week_bad[:5]:
        print(f"  WEEK {b}")

    ok = not unexplained and not rt_fail and not contract and not week_bad and not weeks_bad \
        and not rfc.get("rejected: OTHER") and not rfc.get("accepted, value differs from the port")
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
