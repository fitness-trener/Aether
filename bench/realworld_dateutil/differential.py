"""Differential test: the Aether RFC 5545 recurrence port (written from the
RFC, bench/realworld_dateutil/rrule_port.aeth) vs python-dateutil
2.9.0.post0 `dateutil.rrule.rrule`.

Three parts:
  A. the RFC 5545 §3.8.5.3 examples inside the port's subset, each checked
     against the instance list the RFC publishes, on both sides;
  B. random rules (fixed seed), each expanded to at most LIMIT instances
     and no later than December 31 of DTSTART's year + YEARS, compared
     instance by instance;
  C. rules the RFC forbids or puts out of range, to see which ones dateutil
     accepts and what it returns.

Every divergence in B must fall into a named class, or the run fails.

    DATEUTIL_PYLIBS=<dir with dateutil 2.9.0.post0 and six> python -B bench/realworld_dateutil/differential.py
    (a leading "--mutant <file.aeth>" runs a port mutant instead, at 1/10 scale)
"""

from __future__ import annotations

import datetime as _dt
import itertools
import os
import random
import sys
import types
import warnings
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
PYLIBS = os.environ.get("DATEUTIL_PYLIBS")
if PYLIBS:
    sys.path.insert(0, PYLIBS)

import dateutil  # noqa: E402
import dateutil.rrule as du  # noqa: E402

from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

SEED = 20260930
N_RULES = 50_000
LIMIT = 60        # instances compared per rule
YEARS = 20        # horizon: Dec 31 of DTSTART's year + YEARS
YEARLY, MONTHLY, WEEKLY, DAILY = 0, 1, 2, 3
FREQ_NAME = ["YEARLY", "MONTHLY", "WEEKLY", "DAILY"]
WD_NAME = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def load_port(path):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_rrule_port"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


def key(d) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def date_of(k: int) -> _dt.date:
    return _dt.date(k // 10000, k // 100 % 100, k % 100)


# ------------------------------------------------------------------ rules
#
# A rule is a plain dict; `port_rule` and `lib_rule` build each side's form.

def rule(freq, start, interval=1, count=0, until=0, bymonth=(), bymonthday=(),
         byday=(), bysetpos=(), wkst=0):
    """byday: sequence of (weekday 0=MO..6=SU, n) with n == 0 for no ordinal."""
    return dict(freq=freq, start=start, interval=interval, count=count, until=until,
                bymonth=tuple(bymonth), bymonthday=tuple(bymonthday), byday=tuple(byday),
                bysetpos=tuple(bysetpos), wkst=wkst)


def rrule_text(r) -> str:
    parts = [f"FREQ={FREQ_NAME[r['freq']]}"]
    if r["interval"] != 1:
        parts.append(f"INTERVAL={r['interval']}")
    if r["count"]:
        parts.append(f"COUNT={r['count']}")
    if r["until"]:
        parts.append(f"UNTIL={r['until']}")
    if r["bymonth"]:
        parts.append("BYMONTH=" + ",".join(map(str, r["bymonth"])))
    if r["bymonthday"]:
        parts.append("BYMONTHDAY=" + ",".join(map(str, r["bymonthday"])))
    if r["byday"]:
        parts.append("BYDAY=" + ",".join((str(n) if n else "") + WD_NAME[w] for w, n in r["byday"]))
    if r["bysetpos"]:
        parts.append("BYSETPOS=" + ",".join(map(str, r["bysetpos"])))
    parts.append("WKST=" + WD_NAME[r["wkst"]])
    return f"DTSTART={r['start']} " + ";".join(parts)


class Port:
    def __init__(self, g):
        self.g = g
        self.mk = g["_ae_mkRule"]
        self.expand_fn = g["_ae_expand"]

    def rule(self, r):
        s = r["start"]
        return self.mk(r["freq"], s // 10000, s // 100 % 100, s % 100, r["interval"], r["count"],
                       r["until"], list(r["bymonth"]), list(r["bymonthday"]),
                       [w for w, _ in r["byday"]], [n for _, n in r["byday"]],
                       list(r["bysetpos"]), r["wkst"])

    def valid(self, r):
        return self.g["_ae_validRule"](self.rule(r))

    def expand(self, r, horizon, limit):
        return list(self.expand_fn(self.rule(r), horizon, limit))

    def synchronized(self, r):
        return self.g["_ae_isSynchronized"](self.rule(r))

    def first_week(self, r):
        """(week start, the whole first week's set before BYSETPOS)."""
        e = self.g["_ae_effective"](self.rule(r))
        s = self.g["_ae_startOrdinal"](e)
        ws = self.g["_ae_weekStart"](e, s)
        return ws, list(self.g["_ae_weekCandidates"](e, ws))


# dateutil stops iterating once the period's year passes datetime.MAXYEAR.
# The module sees `datetime` through this proxy, whose MAXYEAR is set to the
# horizon year before each rule, so a rule with no instance in the horizon
# ends there instead of scanning to 9999. Only the stop year changes; the
# instances up to it are the library's own.
_PROXY = types.ModuleType("datetime_horizon")
_PROXY.__dict__.update({k: v for k, v in _dt.__dict__.items() if not k.startswith("__")})
du.datetime = _PROXY


def lib_rule(r, until_override=None):
    s = date_of(r["start"])
    byday = None
    if r["byday"]:
        byday = tuple(du.weekday(w, n if n else None) for w, n in r["byday"])
    until = r["until"] if until_override is None else until_override
    return du.rrule(
        r["freq"], dtstart=_dt.datetime(s.year, s.month, s.day), interval=r["interval"],
        wkst=r["wkst"], count=r["count"] or None,
        until=_dt.datetime.combine(date_of(until), _dt.time()) if until else None,
        bymonth=r["bymonth"] or None, bymonthday=r["bymonthday"] or None,
        byweekday=byday, bysetpos=r["bysetpos"] or None)


def lib_expand(r, horizon, limit):
    _PROXY.MAXYEAR = min(9999, horizon // 10000)
    try:
        out = []
        if limit == 0:
            return out
        for d in lib_rule(r):
            k = key(d)
            if k > horizon:
                break
            out.append(k)
            if len(out) == limit:
                break
        return out
    finally:
        _PROXY.MAXYEAR = _dt.MAXYEAR


# ------------------------------------------------------------ A. RFC vectors
#
# RFC 5545 §3.8.5.3, "All examples assume the Eastern United States time
# zone", every instance at 09:00 local. Dates only here. A UTC UNTIL becomes
# the last local date whose 09:00 instance is not after it:
#   19971224T000000Z = 1997-12-23 19:00 EST -> 19971223
#   20000131T140000Z = 2000-01-31 09:00 EST -> 20000131
#   19971007T000000Z = 1997-10-06 20:00 EDT -> 19971006
# For an open-ended example, the published prefix is compared.

def _ks(year, month, days):
    return [year * 10000 + month * 100 + d for d in days]


RFC = [
    ("Daily for 10 occurrences", rule(DAILY, 19970902, count=10),
     _ks(1997, 9, range(2, 12))),
    ("Daily until December 24, 1997", rule(DAILY, 19970902, until=19971223),
     _ks(1997, 9, range(2, 31)) + _ks(1997, 10, range(1, 32)) + _ks(1997, 11, range(1, 31))
     + _ks(1997, 12, range(1, 24))),
    ("Every other day - forever", rule(DAILY, 19970902, interval=2),
     _ks(1997, 9, range(2, 31, 2)) + _ks(1997, 10, range(2, 31, 2)) + _ks(1997, 11, range(1, 30, 2))
     + _ks(1997, 12, [1, 3])),
    ("Every 10 days, 5 occurrences", rule(DAILY, 19970902, interval=10, count=5),
     _ks(1997, 9, [2, 12, 22]) + _ks(1997, 10, [2, 12])),
    ("Every day in January, for 3 years (YEARLY form)",
     rule(YEARLY, 19980101, until=20000131, bymonth=[1], byday=[(w, 0) for w in range(7)]),
     _ks(1998, 1, range(1, 32)) + _ks(1999, 1, range(1, 32)) + _ks(2000, 1, range(1, 32))),
    ("Every day in January, for 3 years (DAILY form)",
     rule(DAILY, 19980101, until=20000131, bymonth=[1]),
     _ks(1998, 1, range(1, 32)) + _ks(1999, 1, range(1, 32)) + _ks(2000, 1, range(1, 32))),
    ("Weekly for 10 occurrences", rule(WEEKLY, 19970902, count=10),
     _ks(1997, 9, [2, 9, 16, 23, 30]) + _ks(1997, 10, [7, 14, 21, 28]) + _ks(1997, 11, [4])),
    ("Weekly until December 24, 1997", rule(WEEKLY, 19970902, until=19971223),
     _ks(1997, 9, [2, 9, 16, 23, 30]) + _ks(1997, 10, [7, 14, 21, 28]) + _ks(1997, 11, [4, 11, 18, 25])
     + _ks(1997, 12, [2, 9, 16, 23])),
    ("Every other week - forever", rule(WEEKLY, 19970902, interval=2, wkst=6),
     _ks(1997, 9, [2, 16, 30]) + _ks(1997, 10, [14, 28]) + _ks(1997, 11, [11, 25])
     + _ks(1997, 12, [9, 23]) + _ks(1998, 1, [6, 20]) + _ks(1998, 2, [3, 17])),
    ("Weekly on Tuesday and Thursday for five weeks (UNTIL)",
     rule(WEEKLY, 19970902, until=19971006, wkst=6, byday=[(1, 0), (3, 0)]),
     _ks(1997, 9, [2, 4, 9, 11, 16, 18, 23, 25, 30]) + _ks(1997, 10, [2])),
    ("Weekly on Tuesday and Thursday for five weeks (COUNT)",
     rule(WEEKLY, 19970902, count=10, wkst=6, byday=[(1, 0), (3, 0)]),
     _ks(1997, 9, [2, 4, 9, 11, 16, 18, 23, 25, 30]) + _ks(1997, 10, [2])),
    ("Every other week on Monday, Wednesday, and Friday until December 24, 1997",
     rule(WEEKLY, 19970901, interval=2, until=19971223, wkst=6, byday=[(0, 0), (2, 0), (4, 0)]),
     _ks(1997, 9, [1, 3, 5, 15, 17, 19, 29]) + _ks(1997, 10, [1, 3, 13, 15, 17, 27, 29, 31])
     + _ks(1997, 11, [10, 12, 14, 24, 26, 28]) + _ks(1997, 12, [8, 10, 12, 22])),
    ("Every other week on Tuesday and Thursday, for 8 occurrences",
     rule(WEEKLY, 19970902, interval=2, count=8, wkst=6, byday=[(1, 0), (3, 0)]),
     _ks(1997, 9, [2, 4, 16, 18, 30]) + _ks(1997, 10, [2, 14, 16])),
    ("Monthly on the first Friday for 10 occurrences",
     rule(MONTHLY, 19970905, count=10, byday=[(4, 1)]),
     [19970905, 19971003, 19971107, 19971205, 19980102, 19980206, 19980306, 19980403,
      19980501, 19980605]),
    ("Monthly on the first Friday until December 24, 1997",
     rule(MONTHLY, 19970905, until=19971223, byday=[(4, 1)]),
     [19970905, 19971003, 19971107, 19971205]),
    ("Every other month on the first and last Sunday of the month for 10 occurrences",
     rule(MONTHLY, 19970907, interval=2, count=10, byday=[(6, 1), (6, -1)]),
     [19970907, 19970928, 19971102, 19971130, 19980104, 19980125, 19980301, 19980329,
      19980503, 19980531]),
    ("Monthly on the second-to-last Monday of the month for 6 months",
     rule(MONTHLY, 19970922, count=6, byday=[(0, -2)]),
     [19970922, 19971020, 19971117, 19971222, 19980119, 19980216]),
    ("Monthly on the third-to-the-last day of the month, forever",
     rule(MONTHLY, 19970928, bymonthday=[-3]),
     [19970928, 19971029, 19971128, 19971229, 19980129, 19980226]),
    ("Monthly on the 2nd and 15th of the month for 10 occurrences",
     rule(MONTHLY, 19970902, count=10, bymonthday=[2, 15]),
     [19970902, 19970915, 19971002, 19971015, 19971102, 19971115, 19971202, 19971215,
      19980102, 19980115]),
    ("Monthly on the first and last day of the month for 10 occurrences",
     rule(MONTHLY, 19970930, count=10, bymonthday=[1, -1]),
     [19970930, 19971001, 19971031, 19971101, 19971130, 19971201, 19971231, 19980101,
      19980131, 19980201]),
    ("Every 18 months on the 10th thru 15th of the month for 10 occurrences",
     rule(MONTHLY, 19970910, interval=18, count=10, bymonthday=range(10, 16)),
     _ks(1997, 9, range(10, 16)) + _ks(1999, 3, range(10, 14))),
    ("Every Tuesday, every other month", rule(MONTHLY, 19970902, interval=2, byday=[(1, 0)]),
     _ks(1997, 9, [2, 9, 16, 23, 30]) + _ks(1997, 11, [4, 11, 18, 25]) + _ks(1998, 1, [6, 13, 20, 27])
     + _ks(1998, 3, [3, 10, 17, 24, 31])),
    ("Yearly in June and July for 10 occurrences",
     rule(YEARLY, 19970610, count=10, bymonth=[6, 7]),
     [y * 10000 + m * 100 + 10 for y in range(1997, 2002) for m in (6, 7)]),
    ("Every other year on January, February, and March for 10 occurrences",
     rule(YEARLY, 19970310, interval=2, count=10, bymonth=[1, 2, 3]),
     [19970310] + [y * 10000 + m * 100 + 10 for y in (1999, 2001, 2003) for m in (1, 2, 3)]),
    ("Every 20th Monday of the year, forever", rule(YEARLY, 19970519, byday=[(0, 20)]),
     [19970519, 19980518, 19990517]),
    ("Every Thursday in March, forever", rule(YEARLY, 19970313, bymonth=[3], byday=[(3, 0)]),
     _ks(1997, 3, [13, 20, 27]) + _ks(1998, 3, [5, 12, 19, 26]) + _ks(1999, 3, [4, 11, 18, 25])),
    ("Every Thursday, but only during June, July, and August, forever",
     rule(YEARLY, 19970605, bymonth=[6, 7, 8], byday=[(3, 0)]),
     _ks(1997, 6, [5, 12, 19, 26]) + _ks(1997, 7, [3, 10, 17, 24, 31]) + _ks(1997, 8, [7, 14, 21, 28])
     + _ks(1998, 6, [4, 11, 18, 25]) + _ks(1998, 7, [2, 9, 16, 23, 30]) + _ks(1998, 8, [6, 13, 20, 27])
     + _ks(1999, 6, [3, 10, 17, 24]) + _ks(1999, 7, [1, 8, 15, 22, 29]) + _ks(1999, 8, [5, 12, 19, 26])),
    # The RFC adds EXDATE:19970902 so that the unsynchronized DTSTART is not
    # an instance; both sides already drop it, so the EXDATE is not modelled.
    ("Every Friday the 13th, forever", rule(MONTHLY, 19970902, byday=[(4, 0)], bymonthday=[13]),
     [19980213, 19980313, 19981113, 19990813, 20001013]),
    ("The first Saturday that follows the first Sunday of the month, forever",
     rule(MONTHLY, 19970913, byday=[(5, 0)], bymonthday=range(7, 14)),
     [19970913, 19971011, 19971108, 19971213, 19980110, 19980207, 19980307, 19980411,
      19980509, 19980613]),
    ("Every 4 years, the first Tuesday after a Monday in November, forever",
     rule(YEARLY, 19961105, interval=4, bymonth=[11], byday=[(1, 0)], bymonthday=range(2, 9)),
     [19961105, 20001107, 20041102]),
    ("The third instance into the month of one of Tuesday, Wednesday, or Thursday",
     rule(MONTHLY, 19970904, count=3, byday=[(1, 0), (2, 0), (3, 0)], bysetpos=[3]),
     [19970904, 19971007, 19971106]),
    ("The second-to-last weekday of the month",
     rule(MONTHLY, 19970929, byday=[(w, 0) for w in range(5)], bysetpos=[-2]),
     [19970929, 19971030, 19971127, 19971230, 19980129, 19980226, 19980330]),
    ("WKST=MO", rule(WEEKLY, 19970805, interval=2, count=4, byday=[(1, 0), (6, 0)], wkst=0),
     [19970805, 19970810, 19970819, 19970824]),
    ("WKST=SU", rule(WEEKLY, 19970805, interval=2, count=4, byday=[(1, 0), (6, 0)], wkst=6),
     [19970805, 19970817, 19970819, 19970831]),
    ("An invalid date (i.e., February 30) is ignored",
     rule(MONTHLY, 20070115, count=5, bymonthday=[15, 30]),
     [20070115, 20070130, 20070215, 20070315, 20070330]),
]
# Examples outside the subset: BYYEARDAY (1), BYWEEKNO (1), HOURLY (1),
# MINUTELY (2, and the MINUTELY/BYHOUR alternative of the DAILY one), BYHOUR (1).


def part_a(port):
    fails = []
    for name, r, want in RFC:
        assert port.valid(r), name
        try:
            p = port.expand(r, 99991231, len(want))
        except Exception as e:  # a port contract (E0301/E0304) failed
            p = f"raised {type(e).__name__}: {str(e)[:160]}"
        lib = lib_expand(r, 99991231, len(want))
        if p != want:
            fails.append(("port", name, p, want))
        if lib != want:
            fails.append(("dateutil", name, lib, want))
    return fails


# ---------------------------------------------------------- B. random rules

EDGE_YEARS = [1899, 1900, 1901, 1904, 1999, 2000, 2001, 2004, 2096, 2099, 2100, 2101, 2104]


def days_in(y, m):
    return (_dt.date(y + (m == 12), m % 12 + 1, 1) - _dt.timedelta(days=1)).day


def gen_start(rng):
    r = rng.random()
    y = rng.choice(EDGE_YEARS) if rng.random() < 0.5 else rng.randint(1970, 2060)
    m = rng.randint(1, 12)
    if r < 0.15:  # Feb 29 of a leap year
        y = rng.choice([1904, 1996, 2000, 2004, 2024, 2096, 2104])
        return y * 10000 + 229
    if r < 0.45:  # a month end, 28..31
        d = rng.choice([28, 29, 30, 31])
        if d > days_in(y, m):
            d = days_in(y, m)
        return y * 10000 + m * 100 + d
    if r < 0.55:
        return y * 10000 + rng.choice([101, 1231])
    return y * 10000 + m * 100 + rng.randint(1, days_in(y, m))


MONTHDAY_POOL = [1, 2, 15, 28, 29, 30, 31, -1, -2, -3, -28, -29, -30, -31]


def gen_rule(rng):
    freq = rng.randrange(4)
    start = gen_start(rng)
    x = rng.random()
    interval = 1 if x < 0.5 else rng.randint(2, 4) if x < 0.85 else rng.randint(5, 27)
    count = until = 0
    x = rng.random()
    if x < 0.45:
        count = rng.randint(1, 70)
    elif x < 0.75:
        u = date_of(start) + _dt.timedelta(days=rng.randint(-40, 3000))
        until = key(u)
    bymonth = sorted(rng.sample(range(1, 13), rng.randint(1, 4))) if rng.random() < 0.3 else []
    bymonthday = []
    if freq != WEEKLY and rng.random() < 0.35:
        n = rng.randint(1, 4)
        bymonthday = [rng.choice(MONTHDAY_POOL) if rng.random() < 0.7
                      else rng.choice([1, -1]) * rng.randint(1, 31) for _ in range(n)]
    byday = []
    if rng.random() < 0.45:
        for w in rng.sample(range(7), rng.randint(1, 4)):
            n = 0
            if freq in (YEARLY, MONTHLY) and rng.random() < 0.5:
                if freq == YEARLY and not bymonth and rng.random() < 0.4:
                    n = rng.choice([1, 2, 20, 26, 52, 53, -1, -2, -52, -53])
                else:
                    n = rng.choice([1, 2, 3, 4, 5, -1, -2, -4, -5])
            byday.append((w, n))
        # the same weekday both plain and with an ordinal ("FR,1FR")
        plain = [w for w, n in byday if n == 0]
        if freq in (YEARLY, MONTHLY) and plain and rng.random() < 0.15:
            byday.append((rng.choice(plain), rng.choice([1, 2, -1, 5])))
    bysetpos = []
    if (bymonth or bymonthday or byday) and rng.random() < 0.35:
        bysetpos = [rng.choice([1, 2, 3, -1, -2, -3]) if rng.random() < 0.8
                    else rng.choice([1, -1]) * rng.randint(1, 12) for _ in range(rng.randint(1, 2))]
    return rule(freq, start, interval, count, until, bymonth, bymonthday, byday, bysetpos,
                rng.randrange(7))


def synchronize(port, r):
    """The same rule with DTSTART moved to its first instance, when that
    DTSTART is synchronized (it can shift a part taken from DTSTART)."""
    first = port.expand(r, (r["start"] // 10000 + YEARS) * 10000 + 1231, 1)
    if not first or first[0] == r["start"]:
        return r
    s = dict(r, start=first[0])
    if s["until"] and s["until"] < s["start"]:
        return r
    return s if port.synchronized(s) else r


def horizon_of(r):
    return min(99991231, (r["start"] // 10000 + YEARS) * 10000 + 1231)


def weekly_first_week_model(port, r, p):
    """What the port returns if the first WEEKLY set starts at DTSTART
    instead of at WKST: BYSETPOS over the first week's instances on or after
    DTSTART, then the port's own later weeks, then COUNT/UNTIL/limit."""
    ws, week = port.first_week(r)
    s_ord = date_of(r["start"]).toordinal()
    part = [c for c in week if c >= s_ord]
    n = len(part)
    picked = set()
    for pos in r["bysetpos"]:
        if 0 < pos <= n:
            picked.add(part[pos - 1])
        elif pos < 0 and n + pos >= 0:
            picked.add(part[n + pos])
    first = [key(_dt.date.fromordinal(o)) for o in sorted(picked)]
    week_end = key(_dt.date.fromordinal(ws + 6))
    # the port's instances after the first week, from an uncapped expansion
    rest_rule = dict(r, count=0)
    later = [k for k in port.expand(rest_rule, horizon_of(r), 10**6) if k > week_end]
    out = [k for k in first + later if k <= horizon_of(r) and (not r["until"] or k <= r["until"])]
    if r["count"]:
        out = out[:r["count"]]
    return out[:LIMIT]


def mixed_byday_model(port, r):
    """What the port returns if a BYDAY list that mixes plain weekdays (MO)
    with ordinal ones (1FR) is read as an intersection: a day must have one
    of the plain weekdays AND be one of the ordinal days. That is the same
    as keeping only the ordinal entries whose weekday is also listed plain;
    when none is left, the rule has no instance."""
    plain = {w for w, n in r["byday"] if n == 0}
    kept = [(w, n) for w, n in r["byday"] if n != 0 and w in plain]
    if not kept:
        return []
    return port.expand(dict(r, byday=kept), horizon_of(r), LIMIT)


def is_mixed_byday(r):
    ns = [n for _, n in r["byday"]]
    return r["freq"] in (YEARLY, MONTHLY) and 0 in ns and any(ns)


def classify(port, r, p, lib):
    if r["freq"] == WEEKLY and r["bysetpos"] and weekly_first_week_model(port, r, p) == lib:
        sync = "synchronized" if port.synchronized(r) else "unsynchronized"
        return "weekly_bysetpos_first_week/" + sync
    if is_mixed_byday(r) and mixed_byday_model(port, r) == lib:
        return "mixed_byday_intersected/" + ("empty" if not lib else "narrowed")
    return None


def part_b(port, n_rules, rng):
    stats = Counter()
    classes = Counter()
    examples = {}
    unexplained = []
    for i in range(n_rules):
        r = gen_rule(rng)
        if rng.random() < 0.4:
            r = synchronize(port, r)
        assert port.valid(r), r
        sync = port.synchronized(r)
        stats["synchronized" if sync else "unsynchronized"] += 1
        stats[FREQ_NAME[r["freq"]]] += 1
        if r["bysetpos"]:
            stats["with BYSETPOS"] += 1
        if any(n for _, n in r["byday"]):
            stats["with a BYDAY ordinal"] += 1
        if r["start"] % 10000 == 229:
            stats["DTSTART Feb 29"] += 1
        if r["freq"] == WEEKLY and r["bysetpos"]:
            stats["WEEKLY+BYSETPOS"] += 1
            if sync:
                stats["WEEKLY+BYSETPOS synchronized"] += 1
        if is_mixed_byday(r):
            stats["mixed BYDAY"] += 1
        h = horizon_of(r)
        p = port.expand(r, h, LIMIT)
        lib = lib_expand(r, h, LIMIT)
        stats["instances compared"] += len(p)
        if not p:
            stats["empty in the horizon"] += 1
        if p == lib:
            stats["agree"] += 1
            continue
        c = classify(port, r, p, lib)
        if c is None:
            unexplained.append((r, p, lib))
            continue
        classes[c] += 1
        if len(examples.setdefault(c, [])) < 3:
            examples[c].append((r, p[:4], lib[:4]))
    return stats, classes, examples, unexplained


# ------------------------------------------------ C. rules the RFC forbids

def probe(r, n=6):
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            rr = lib_rule(r)
            out = [key(d) for d in itertools.islice(rr, n)]
        note = "; warns " + w[0].category.__name__ if w else ""
        return "accepted: " + str(out) + note
    except Exception as e:  # the library's rejection
        return f"rejected: {type(e).__name__}: {e}"


INVALID = [
    ("BYDAY ordinal with WEEKLY (§3.3.10 MUST NOT)",
     rule(WEEKLY, 20240101, count=3, byday=[(0, 1)])),
    ("BYDAY ordinal with DAILY (§3.3.10 MUST NOT)",
     rule(DAILY, 20240101, count=3, byday=[(0, 2)])),
    ("BYMONTHDAY with WEEKLY (§3.3.10 MUST NOT; table N/A)",
     rule(WEEKLY, 20240101, count=3, bymonthday=[15])),
    ("BYSETPOS without another BYxxx (§3.3.10 MUST only be used in conjunction)",
     rule(MONTHLY, 20240115, count=3, bysetpos=[1])),
    ("COUNT and UNTIL together (§3.3.10 MUST NOT occur in the same recur)",
     rule(DAILY, 20240101, count=3, until=20240110)),
    ("BYMONTHDAY=0 (ordmoday is 1 to 31)",
     rule(MONTHLY, 20240115, count=6, bymonthday=[0])),
    ("BYMONTHDAY=0 via rrulestr", None),
    ("BYMONTH=13 (monthnum is 1 to 12), COUNT=1", rule(YEARLY, 20240115, count=1, bymonth=[13])),
    ("BYDAY ordinal 54 (ordwk is 1 to 53), YEARLY, COUNT=1",
     rule(YEARLY, 20240101, count=1, byday=[(0, 54)])),
    ("BYSETPOS=0 (setposday is 1 to 366)", rule(MONTHLY, 20240101, count=3, byday=[(0, 0)], bysetpos=[0])),
    ("BYDAY ordinal 0", rule(MONTHLY, 20240101, count=3, byday=[(0, 0)])),
]


def part_c():
    rows = []
    for name, r in INVALID:
        if r is None:
            try:
                rr = du.rrulestr("FREQ=MONTHLY;BYMONTHDAY=0;COUNT=6", dtstart=_dt.datetime(2024, 1, 15))
                res = "accepted: " + str([key(d) for d in rr])
            except Exception as e:
                res = f"rejected: {type(e).__name__}: {e}"
        elif name == "BYDAY ordinal 0":
            try:
                du.weekday(0, 0)
                res = "accepted"
            except Exception as e:
                res = f"rejected: {type(e).__name__}: {e}"
        elif r["bymonth"] == (13,) or any(abs(n) > 53 for _, n in r["byday"]):
            # an empty rule: dateutil scans every year to 9999 (issue #523)
            _PROXY.MAXYEAR = 9999
            res = probe(r, 1)
            _PROXY.MAXYEAR = _dt.MAXYEAR
        else:
            res = probe(r)
        rows.append((name, res))
    return rows


# ---------------------------------------------------------------- main

def main(argv) -> int:
    port_path = os.path.join(HERE, "rrule_port.aeth")
    n_rules = N_RULES
    if len(argv) > 2 and argv[1] == "--mutant":
        port_path = argv[2]
        n_rules = N_RULES // 10
    port = Port(load_port(port_path))
    rng = random.Random(SEED)
    print(f"dateutil version under test: {dateutil.__version__}")
    print(f"python: {sys.version.split()[0]}, seed {SEED}, port {os.path.basename(port_path)}")

    fails = part_a(port)
    print(f"\nA. RFC 5545 §3.8.5.3 examples in the subset: {len(RFC)}; "
          f"port matches {len(RFC) - sum(f[0] == 'port' for f in fails)}, "
          f"dateutil matches {len(RFC) - sum(f[0] == 'dateutil' for f in fails)}")
    for side, name, got, want in fails:
        print(f"  MISMATCH {side}: {name}\n    got  {got}\n    want {want}")

    try:
        stats, classes, examples, unexplained = part_b(port, n_rules, rng)
    except Exception as e:  # a port contract (E0301/E0304) or crash stops the run
        print(f"\nB. port raised {type(e).__name__}: {e}\nFAIL")
        return 1
    div = sum(classes.values()) + len(unexplained)
    print(f"\nB. random rules: {n_rules} | agree {stats['agree']} | divergences {div} "
          f"({sum(classes.values())} attributed, {len(unexplained)} unexplained)")
    print("   instances compared: %d; rules empty in the horizon: %d" %
          (stats["instances compared"], stats["empty in the horizon"]))
    print("   " + ", ".join(f"{k} {stats[k]}" for k in (
        "YEARLY", "MONTHLY", "WEEKLY", "DAILY", "synchronized", "unsynchronized",
        "with BYSETPOS", "with a BYDAY ordinal", "DTSTART Feb 29", "WEEKLY+BYSETPOS",
        "WEEKLY+BYSETPOS synchronized", "mixed BYDAY")))
    for c, n in sorted(classes.items()):
        print(f"   {c:48s} {n:6d}")
        for r, p, lib in examples[c]:
            print(f"      {rrule_text(r)}\n        port {p}  dateutil {lib}")
    for r, p, lib in unexplained[:15]:
        print(f"   UNEXPLAINED {rrule_text(r)}\n        port {p[:6]}\n        dateutil {lib[:6]}")

    if port_path.endswith("rrule_port.aeth"):
        print("\nC. rules the RFC forbids or puts out of range:")
        for name, res in part_c():
            print(f"   {name}: {res}")

    ok = not fails and not unexplained
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
