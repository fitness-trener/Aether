"""Line-by-line transliteration of main's C parse_hh_mm_ss_ff /
parse_isoformat_time (Modules/_datetimemodule.c), unpatched and with the
draft fix, run against datetimetester.py's time and datetime vectors.
Bytes model: the string is UTF-8 with a trailing NUL, as in the C code."""
import ast, importlib.util, sys, types

spec = importlib.util.spec_from_file_location("_pyd", "fix/a/Lib/_pydatetime.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def parse_digits(b, p, n):
    v = 0
    for _ in range(n):
        t = b[p] - 48
        p += 1
        if t < 0 or t > 9:
            return None, v
        v = v * 10 + t
    return p, v


def hhmmssff(b, p, p_end, patched):
    vals = [0, 0, 0]
    has_sep = True
    for i in range(3):
        p, vals[i] = parse_digits(b, p, 2)
        if p is None:
            return -3, vals, 0
        c = b[p]
        p += 1
        if i == 0:
            has_sep = c == 58
        if c in (46, 44):
            if i < 2 or p >= p_end:
                return -3, vals, 0
            break
        elif not patched and p >= p_end:
            return int(c != 0), vals, 0
        elif patched and p > p_end:
            return 0, vals, 0
        elif patched and p == p_end:
            return 1, vals, 0
        elif has_sep and c == 58:
            if i == 2:
                return -4, vals, 0
            continue
        elif not has_sep:
            p -= 1
        else:
            return -4, vals, 0
    to_parse = min(p_end - p, 6)
    p, us = parse_digits(b, p, to_parse)
    if p is None:
        return -3, vals, 0
    if to_parse < 6:
        us *= [100000, 10000, 1000, 100, 10][to_parse - 1]
    while 48 <= b[p] <= 57:
        p += 1
    return (int(p != p_end) if patched else int(b[p] != 0)), vals, us


def parse_time(b, p, p_end, patched):
    """Returns ('ok', (h, m, s, us, offset_us|None)) or ('err', code)."""
    tz = p
    while True:
        if b[tz] in (90, 43, 45):
            break
        tz += 1
        if tz >= p_end:
            break
    rv, (h, mi, s), us = hhmmssff(b, p, tz, patched)
    if rv < 0:
        return ("err", rv)
    if patched and rv == 1:
        return ("err", -5)
    if tz == p_end:
        return ("err", -5) if rv == 1 else ("ok", (h, mi, s, us, None))
    if b[tz] == 90:
        return ("ok", (h, mi, s, us, 0)) if b[tz + 1] == 0 else ("err", -5)
    sign = -1 if b[tz] == 45 else 1
    rv, (oh, om, os_), ous = hhmmssff(b, tz + 1, p_end, patched)
    if not (0 <= oh <= 23 and 0 <= om <= 59 and 0 <= os_ <= 59):
        return ("err", -6)
    if rv:
        return ("err", -5)
    return ("ok", (h, mi, s, us, sign * ((oh * 3600 + om * 60 + os_) * 10**6 + ous)))


def c_time(s, patched):
    b = s.encode("utf-8", "surrogatepass") + b"\0"
    p = 1 if b[0] == 84 else 0
    return parse_time(b, p, len(b) - 1, patched)


def c_datetime(s, patched):
    b = s.encode("utf-8", "surrogatepass") + b"\0"
    if len(s) < 7:
        return ("err", "short")
    try:
        sep = m._find_isoformat_datetime_separator(s)
        m._parse_isoformat_date(s[:sep])
    except Exception:
        return ("err", "date")
    if len(s) <= sep:
        return ("ok", None)
    start = len(s[:sep + 1].encode("utf-8", "surrogatepass"))
    return parse_time(b, start, len(b) - 1, patched)


def accepted(r):
    return r[0] == "ok"


tree = ast.parse(open("fix/b/Lib/test/datetimetester.py", encoding="utf-8").read())
bad = {"time": [], "datetime": []}
good = {"time": [], "datetime": []}
for cls_node in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
    for fn in [n for n in cls_node.body if isinstance(n, ast.FunctionDef)]:
        kind = {("TestTimeTZ", "test_fromisoformat_fails"): ("time", bad),
                ("TestTimeTZ", "test_fromisoformat_time_examples"): ("time", good),
                ("TestDateTime", "test_fromisoformat_fails_datetime"): ("datetime", bad),
                ("TestDateTime", "test_fromisoformat_datetime_examples"): ("datetime", good)}.get(
            (cls_node.name, fn.name))
        if not kind:
            continue
        for st in fn.body:
            if isinstance(st, ast.Assign) and st.targets[0].id in ("examples", "bad_strs"):
                ns = dict(self=types.SimpleNamespace(theclass=lambda *a, **k: None),
                          timezone=m.timezone, timedelta=m.timedelta, UTC=None, BST=None,
                          EST=None, EDT=None)
                for v in eval(compile(ast.Expression(st.value), "t", "eval"), ns):
                    kind[1][kind[0]].append(v[0] if isinstance(v, tuple) else v)

for patched in (False, True):
    f = {"time": c_time, "datetime": c_datetime}
    wrong = []
    for api in ("time", "datetime"):
        for s in good[api]:
            r = f[api](s, patched)
            if not accepted(r):
                wrong.append((api, "example rejected", s, r))
        for s in bad[api]:
            r = f[api](s, patched)
            # range errors (hour 25, 24:00 rules, day 32) are checked after
            # this parser by the constructors; only a clean parse of text
            # that has no valid reading counts here
            if accepted(r) and r[1] is not None:
                h, mi, sec, us, off = r[1]
                if h <= 24 and mi <= 59 and sec <= 59 and not (h == 24 and (mi or sec or us)):
                    wrong.append((api, "bad string parsed", s, r))
    print(f"patched={patched}: {sum(map(len, good.values()))} examples, "
          f"{sum(map(len, bad.values()))} bad strings, {len(wrong)} disagreements with the test file")
    for w in wrong:
        print("   ", w)
