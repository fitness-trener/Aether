"""Differential test: the Aether TOML v1.0.0 port (written from the spec,
bench/realworld_tomllib/toml_port.aeth) vs CPython's `tomllib.loads`.

Both sides are reduced to one normalized form: a sorted list of
(path, kind, value) for every value and every table in the document.
Integers compare exactly, floats by their binary64 bit pattern (the port's
exact decimal is rounded once, correctly), NaN as a class, strings exactly.

Every divergence is machine-classified; the run fails if one is left
unexplained. Every document both sides accept is also round-tripped:
the port's canonical encoding must parse back to the same document in the
port (its `ensures` clause) and in tomllib.

    python -B bench/realworld_tomllib/differential.py [--n N] [--mutant NAME]
"""

from __future__ import annotations

import argparse
import math
import os
import random
import struct
import sys
import tomllib
from collections import Counter
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

from transpiler.aether.diagnostics import AetherError  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

SEED = 20260930
N_DOCS = 110_000

# Mutants of the port, each breaking one spec rule. The harness must FAIL
# on every one of them (REPORT.md, "The harness can fail").
MUTANTS = {
    # Integer: "Leading zeros are not allowed."
    "leading-zeros": ('if charAt(cs, j) == "0" and ip.ndigits > 1 then',
                      'if false and charAt(cs, j) == "0" and ip.ndigits > 1 then'),
    # String: "The escape codes must be valid Unicode scalar values."
    "surrogate-escape": ("if not isScalarValue(v) then",
                         "if v > 1114111 then"),
    # Table: dotted keys cannot add to a table defined with [table].
    "dotted-into-header": ('elif st == "header" then\n          return Err("dotted keys',
                           'elif false then\n          return Err("dotted keys'),
}


def load_port(mutant: str | None = None) -> dict:
    path = os.path.join(HERE, "toml_port.aeth")
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if mutant:
        old, new = MUTANTS[mutant]
        assert src.count(old) == 1, f"mutant anchor not unique: {mutant}"
        src = src.replace(old, new)
    g = build_namespace()
    g["__name__"] = "aether_toml_port"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


# ---------------------------------------------------------------- normalize

def float_key(v: float):
    if math.isnan(v):
        return ("float", "nan")
    return ("float", struct.pack(">d", v).hex())


def exact_to_float(neg: bool, num: int, exp: int, special: str) -> float:
    """Round num * 10**exp to binary64 once, to nearest (IEEE 754);
    an overflow rounds to infinity."""
    if special == "inf":
        v = math.inf
    elif special == "nan":
        v = math.nan
    elif num == 0:
        v = 0.0
    else:
        est = exp + num.bit_length() * 0.30103
        if est > 400:
            v = math.inf
        elif est < -400:
            v = 0.0
        else:
            q = Fraction(num) * Fraction(10) ** exp
            try:
                v = float(q)  # int / int true division: correctly rounded
            except OverflowError:
                v = math.inf
    return -v if neg else v


def norm_port(entries) -> list:
    out = []
    for e in entries:  # an Aether record is emitted as a dict
        p = tuple(e["path"])
        k = e["kind"]
        if k == "table":
            val = ("table",)
        elif k == "int":
            val = ("int", hex(e["num"]))
        elif k == "bool":
            val = ("bool", e["flag"])
        elif k == "string":
            val = ("string", e["text"])
        else:
            val = float_key(exact_to_float(e["neg"], e["num"], e["exp"], e["special"]))
        out.append(repr((p, val)))
    return sorted(out)


class OutOfScope(Exception):
    pass


def norm_lib(d: dict) -> list:
    out = []
    oos = []

    def walk(t, prefix):
        for k, v in t.items():
            p = prefix + (k,)
            if isinstance(v, dict):
                out.append(repr((p, ("table",))))
                walk(v, p)
            elif isinstance(v, bool):
                out.append(repr((p, ("bool", v))))
            elif isinstance(v, int):
                out.append(repr((p, ("int", hex(v)))))
            elif isinstance(v, float):
                out.append(repr((p, float_key(v))))
            elif isinstance(v, str):
                out.append(repr((p, ("string", v))))
            else:  # list, date, time, datetime
                oos.append(type(v).__name__)

    walk(d, ())
    if oos:
        raise OutOfScope(",".join(sorted(set(oos))))
    return sorted(out)


def run_port(parse_fn, s):
    try:
        r = parse_fn(s)
    except AetherError as e:  # a contract of the port fired
        return ("contract", str(e).splitlines()[0])
    if r[0] == "Ok":
        return ("ok", r[1])
    return ("err", r[1])


def run_lib(s):
    try:
        d = tomllib.loads(s)
    except tomllib.TOMLDecodeError as e:
        return ("err", str(e))
    except Exception as e:  # any other exception: not the documented rejection
        return ("crash", "%s: %s" % (type(e).__name__, e))
    try:
        return ("ok", norm_lib(d))
    except OutOfScope as e:
        return ("oos", str(e))


# ---------------------------------------------------------- classification

def has_long_decimal_int(s: str) -> bool:
    run = 0
    for ch in s:
        if ch.isdigit() and ch.isascii():
            run += 1
            if run > 4300:
                return True
        elif ch != "_":
            run = 0
    return False


def classify(s, port, lib):
    """A class name, or None for an unexplained divergence."""
    pk, pv = port
    lk, lv = lib
    if pk == "contract":
        return None
    if pk == "err" and lk == "oos" and pv.startswith("out of scope"):
        return "out_of_scope"
    # an inline table comes back from tomllib as a plain dict, so it cannot
    # be told apart from a table by the value alone
    if pk == "err" and lk == "ok" and pv == "out of scope: arrays and inline tables" and "{" in s:
        return "out_of_scope"
    # loads() takes a str; a str holding a lone surrogate is not Unicode
    # text, and no UTF-8 byte sequence decodes to one
    if pk == "err" and lk == "ok" and pv.startswith("input is not Unicode text") \
            and any(0xD800 <= ord(ch) <= 0xDFFF for ch in s):
        return "lone_surrogate_in_str"
    # tomllib converts a decimal integer with int() as soon as it has read
    # it, so past 4300 digits a ValueError escapes -- on a valid document,
    # and also on an invalid one before its syntax error is reached
    if lk == "crash" and lv.startswith("ValueError: Exceeds the limit (4300 digits)") \
            and has_long_decimal_int(s):
        return "int_max_str_digits/" + ("valid_doc" if pk == "ok" else "invalid_doc")
    return None


# ---------------------------------------------------------------- generators

def underscore(rng, digits: str, p=0.25) -> str:
    out = digits[0]
    for ch in digits[1:]:
        if rng.random() < p:
            out += "_"
        out += ch
    return out


def rand_digits(rng, n, alphabet="0123456789") -> str:
    return "".join(rng.choice(alphabet) for _ in range(n))


def gen_int(rng) -> str:
    r = rng.random()
    if r < 0.5:
        sign = rng.choice(["", "", "+", "-"])
        if rng.random() < 0.15:
            body = "0"
        elif rng.random() < 0.1:
            body = str(rng.choice([2**63 - 1, 2**63, 2**64, 10**18, 10**19, 2**63 + 1]))
        else:
            body = rng.choice("123456789") + rand_digits(rng, rng.choice([0, 0, 1, 2, 3, 5, 8, 12, 20, 30]))
        return sign + underscore(rng, body, 0.2 if rng.random() < 0.5 else 0.0)
    if r < 0.9995:
        prefix, alphabet = rng.choice([("0x", "0123456789abcdefABCDEF"), ("0o", "01234567"), ("0b", "01")])
        body = rand_digits(rng, rng.randint(1, 20), alphabet)
        return prefix + underscore(rng, body, 0.2 if rng.random() < 0.5 else 0.0)
    # rare: at CPython's 4300-digit int() guard
    return rng.choice(["", "-", "+"]) + rng.choice("123456789") + rand_digits(rng, rng.randint(4295, 4305))


def gen_float(rng) -> str:
    r = rng.random()
    if r < 0.12:
        return rng.choice(["", "+", "-"]) + rng.choice(["inf", "nan"])
    sign = rng.choice(["", "", "+", "-"])
    ip = "0" if rng.random() < 0.3 else rng.choice("123456789") + rand_digits(rng, rng.randint(0, 17))
    s = sign + underscore(rng, ip, 0.1)
    has_frac = rng.random() < 0.8
    has_exp = (not has_frac) or rng.random() < 0.35
    if has_frac:
        s += "." + underscore(rng, rand_digits(rng, rng.choice([1, 1, 2, 3, 6, 10, 17, 20, 25])), 0.1)
    if has_exp:
        mag = rng.choice([1, 2, 5, 22, 300, 307, 308, 309, 320, 323, 324, 325, 340, 400])
        ev = rng.randint(0, mag)
        es = str(ev)
        if rng.random() < 0.15:
            es = "0" * rng.randint(1, 3) + es
        s += rng.choice("eE") + rng.choice(["", "+", "-", "-"]) + underscore(rng, es, 0.1)
    return s


BASIC_POOL = (
    list("abcxyz AZ09.,;:!?/-_#=[]{}'") + ["\t", "é", "日", "😀", "\u00a0", "\u0085", "\u2028"]
    + ["\\b", "\\t", "\\n", "\\f", "\\r", '\\"', "\\\\", "\\u00E9", "\\u00e9", "\\u0000",
       "\\u001F", "\\u007F", "\\U0001F600", "\\U0010FFFF", "\\uE000", "\\uFFFF", "\\uD7FF"]
)
BASIC_BAD = [
    "\\uD800", "\\uDFFF", "\\udc00", "\\U0000D800", "\\U00110000", "\\UFFFFFFFF", "\\u12", "\\u12G4",
    "\\U1234567", "\\x41", "\\e", "\\a", "\\ ", "\\0", "\\/", "\\", "\x00", "\x01", "\x1f", "\x7f",
    "\r", "\n", "\x0b", "\x0c",
]


def gen_basic_chars(rng, n, bad_p):
    out = []
    for _ in range(n):
        out.append(rng.choice(BASIC_BAD) if rng.random() < bad_p else rng.choice(BASIC_POOL))
    return "".join(out)


def gen_string(rng) -> str:
    kind = rng.random()
    bad_p = 0.0 if rng.random() < 0.6 else 0.08
    n = rng.randint(0, 12)
    if kind < 0.35:
        return '"' + gen_basic_chars(rng, n, bad_p) + '"'
    if kind < 0.55:
        pool = [c for c in BASIC_POOL if not c.startswith("\\") and c != "'"] + ["\\", '"', "\\n"]
        body = "".join(rng.choice(pool) for _ in range(n))
        if rng.random() < bad_p * 3:
            body += rng.choice(["'", "\n", "\x00", "\x7f", "\r", "\x1b"])
        return "'" + body + "'"
    if kind < 0.8:
        parts = []
        if rng.random() < 0.5:
            parts.append(rng.choice(["\n", "\r\n"]))
        for _ in range(rng.randint(0, 6)):
            r = rng.random()
            if r < 0.35:
                parts.append(gen_basic_chars(rng, rng.randint(1, 4), bad_p))
            elif r < 0.55:
                parts.append(rng.choice(["\n", "\r\n", "\n\n"]))
            elif r < 0.7:
                parts.append(rng.choice(['"', '""']))
            elif r < 0.85:  # line ending backslash
                parts.append("\\" + rng.choice(["", " ", "\t ", "  "]) + rng.choice(["\n", "\r\n"])
                             + rng.choice(["", "  ", "\n  ", "\t\n\n "]))
            else:
                parts.append(rng.choice(["\\ x", "\\\\\n", "\r", '\\"""', '\\""', "\\u0022\"\""]))
        tail = rng.choice(["", "", '"', '""', '"""'] if rng.random() < 0.3 else [""])
        return '"""' + "".join(parts) + tail + '"""'
    parts = []
    if rng.random() < 0.5:
        parts.append(rng.choice(["\n", "\r\n"]))
    pool = [c for c in BASIC_POOL if not c.startswith("\\")] + ["\\", '"', "\\n", "'", "''"]
    for _ in range(rng.randint(0, 8)):
        r = rng.random()
        if r < 0.75:
            parts.append(rng.choice(pool))
        elif r < 0.9:
            parts.append(rng.choice(["\n", "\r\n"]))
        else:
            parts.append(rng.choice(["'''", "\x00", "\x7f", "\r", "\x08"]) if bad_p else "\n")
    tail = rng.choice(["", "'", "''", "'''"]) if rng.random() < 0.3 else ""
    return "'''" + "".join(parts) + tail + "'''"


def gen_value(rng) -> str:
    r = rng.random()
    if r < 0.33:
        return gen_int(rng)
    if r < 0.63:
        return gen_float(rng)
    if r < 0.68:
        return rng.choice(["true", "false"])
    return gen_string(rng)


KEY_PARTS = ["a", "b", "c", "1", "a-b", "_", "A", "3", "14159", '"a"', "'a'", '"a.b"', '""', "''",
             '"\\u0061"', '"b"', '"é"', "'c d'", '"\\U00000062"', "'\"'", '"\\t"']


def gen_key(rng, maxparts=3) -> str:
    parts = [rng.choice(KEY_PARTS) for _ in range(rng.randint(1, maxparts))]
    out = parts[0]
    for p in parts[1:]:
        out += rng.choice([".", ".", ".", " . ", ". ", "\t.", " ."]) + p
    return out


def ws(rng) -> str:
    return rng.choice(["", " ", " ", " ", "  ", "\t", " \t"])


def trailer(rng) -> str:
    r = rng.random()
    if r < 0.8:
        return ws(rng)
    return ws(rng) + "#" + rng.choice(["", " c", " é", "#", " \"'[]=", "\t x"])


def gen_table_doc(rng) -> str:
    """Headers and dotted keys over three names, so that paths collide:
    the Keys and Table redefinition rules."""
    def path(k):
        return rng.choice([".", " . "]).join(rng.choice(["a", "b", "c", '"a"'])
                                              for _ in range(rng.randint(1, k)))
    lines = []
    for _ in range(rng.randint(2, 6)):
        if rng.random() < 0.45:
            lines.append("[" + path(3) + "]")
        else:
            lines.append(path(3) + " = " + rng.choice(["1", "true", "'x'", "1.5"]))
    return "\n".join(lines)


def gen_doc(rng) -> str:
    if rng.random() < 0.2:
        return gen_table_doc(rng)
    if rng.random() < 0.4:  # a single key/value pair: hammers the value grammar
        return "v" + ws(rng) + "=" + ws(rng) + gen_value(rng) + trailer(rng) + rng.choice(["", "\n"])
    lines = []
    for _ in range(rng.randint(1, 7)):
        r = rng.random()
        if r < 0.55:
            lines.append(ws(rng) + gen_key(rng) + ws(rng) + "=" + ws(rng) + gen_value(rng) + trailer(rng))
        elif r < 0.85:
            lines.append(ws(rng) + "[" + ws(rng) + gen_key(rng) + ws(rng) + "]" + trailer(rng))
        elif r < 0.93:
            lines.append(ws(rng) + "#" + rng.choice(["", " comment", " é 日", " = [a]"]))
        else:
            lines.append(ws(rng))
    nl = "\n" if rng.random() < 0.85 else "\r\n"
    return nl.join(lines) + rng.choice(["", nl])


ALPHABET = list("abc01_-+.eExob\"'#=[]{} \t\n\\") + ["\r", "\r\n", "\x00", "\x7f", "\x0c", "é", "\u00a0",
                                                      "\ufeff", "inf", "nan", "true", '"""', "'''"]


def mutate(rng, s: str) -> str:
    for _ in range(rng.randint(1, 2)):
        op = rng.randrange(8)
        i = rng.randint(0, len(s))
        if op == 0:  # insert
            s = s[:i] + rng.choice(ALPHABET) + s[i:]
        elif op == 1 and s:  # delete
            i = min(i, len(s) - 1)
            s = s[:i] + s[i + 1:]
        elif op == 2 and len(s) > 1:  # swap neighbours
            i = min(i, len(s) - 2)
            s = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        elif op == 3:  # duplicate a line: redefinition rules
            lines = s.split("\n")
            j = rng.randrange(len(lines))
            lines.insert(rng.randint(0, len(lines)), lines[j])
            s = "\n".join(lines)
        elif op == 4:  # reorder lines: header / dotted-key order rules
            lines = s.split("\n")
            rng.shuffle(lines)
            s = "\n".join(lines)
        elif op == 5:  # bare CR for LF
            s = s.replace("\n", "\r", 1)
        elif op == 6:  # a leading zero or a sign in front of a digit
            idx = [j for j, ch in enumerate(s) if ch.isdigit()]
            if idx:
                j = rng.choice(idx)
                s = s[:j] + rng.choice(["0", "+", "-", "_", "0x", "."]) + s[j:]
        else:  # upper-case one character
            if s:
                i = min(i, len(s) - 1)
                s = s[:i] + s[i].upper() + s[i + 1:]
    return s


# Edge cases after the categories of the toml-test suite (valid/invalid x
# integer, float, bool, string, key, table, comment, control) and the
# examples in the v1.0.0 spec text.
EDGE_CASES = [
    # spec examples
    "int1 = +99\nint2 = 42\nint3 = 0\nint4 = -17",
    "int5 = 1_000\nint6 = 5_349_221\nint7 = 53_49_221\nint8 = 1_2_3_4_5",
    "hex1 = 0xDEADBEEF\nhex2 = 0xdeadbeef\nhex3 = 0xdead_beef\noct1 = 0o01234567\noct2 = 0o755\nbin1 = 0b11010110",
    "flt1 = +1.0\nflt2 = 3.1415\nflt3 = -0.01\nflt4 = 5e+22\nflt5 = 1e06\nflt6 = -2E-2\nflt7 = 6.626e-34",
    "flt8 = 224_617.445_991_228",
    "sf1 = inf\nsf2 = +inf\nsf3 = -inf\nsf4 = nan\nsf5 = +nan\nsf6 = -nan",
    "a = .7", "a = 7.", "a = 3.e+20", "a = -0.0", "a = +0.0", "a = -0", "a = +0",
    'str = "I\'m a string. \\"You can quote me\\". Name\\tJos\\u00E9\\nLocation\\tSF."',
    'str1 = """\nRoses are red\nViolets are blue"""',
    'str2 = """\nThe quick brown \\\n\n\n  fox jumps over \\\n    the lazy dog."""',
    'str3 = """\\\n       The quick brown \\\n       fox jumps over \\\n       the lazy dog.\\\n       """',
    'str4 = """Here are two quotation marks: "". Simple enough."""',
    'str5 = """Here are three quotation marks: """."""',
    'str5 = """Here are three quotation marks: ""\\"."""',
    'str7 = """"This," she said, "is just a pointless statement.""""',
    "winpath = 'C:\\Users\\nodejs\\templates'\nregex = '<\\i\\c*\\s*>'",
    "regex2 = '''I [dw]on't need \\d{2} apples'''",
    "lines = '''\nThe first newline is\ntrimmed in raw strings.\n   All other whitespace\n   is preserved.\n'''",
    "quot15 = '''Here are fifteen quotation marks: \"\"\"\"\"\"\"\"\"\"\"\"\"\"\"'''",
    "apos15 = '''Here are fifteen apostrophes: ''''''''''''''''''",
    "str = ''''That,' she said, 'is still pointless.''''",
    'key = # INVALID', 'first = "Tom" last = "Preston-Werner"',
    '"127.0.0.1" = "value"\n"character encoding" = "value"\n"ʎǝʞ" = "value"\n\'key2\' = "value"',
    '= "no key name"', '"" = "blank"', "'' = 'blank'", '"" = 1\n\'\' = 2',
    'fruit.name = "banana"\nfruit. color = "yellow"\nfruit . flavor = "banana"',
    'name = "Tom"\nname = "Pradyun"', 'spelling = "favorite"\n"spelling" = "favourite"',
    "fruit.apple.smooth = true\nfruit.orange = 2", "fruit.apple = 1\nfruit.apple.smooth = true",
    '3.14159 = "pi"',
    # tables
    "[a]\n[a]", "[a]\nb = 1\n[a]", "a = 1\n[a]", "a.b = 1\n[a]", "a.b = 1\n[a.b]", "a.b = 1\n[a.c]",
    "[a.b]\n[a]", "[a.b]\n[a]\n[a]", "[x.y.z.w]\n[x]",
    "[a.b.c]\nz = 9\n[a]\nb.c.t = 1", "[a.b.c]\n[a]\nb.d = 1", "[a.b.c]\n[a]\nb.d = 1\n[a.b]",
    "[fruit]\napple.color = 'red'\napple.taste.sweet = true\n[fruit.apple]",
    "[fruit]\napple.color = 'red'\napple.taste.sweet = true\n[fruit.apple.texture]\nsmooth = true",
    "a = 1\na.b = 2", "a.b = 1\na = 2", "a.b.c = 1\na.b = 2", '"\\u0061" = 1\na = 2',
    "[a]\nb = 1\n[a.b]", '[a]\n["a"]', "[ a . b ]", "[ j . \"ʞ\" . 'l' ]", "[]", "[a", "[a]]", "[a] b = 1",
    "[a]\nb.c = 1\nb.d = 2", "[a]\nb.c = 1\n[a.b.x]", "[a]\nb.c = 1\n[a]\nb.d = 2",
    "a\n= 1", "a =", "a = 1 # c\n", "a=1#c", "[a]#c", "a = true#", "a = 1\r\n", "a = 1\r", "\r",
    # values
    "a = 01", "a = 00", "a = 0_0", "a = 1__2", "a = 1_", "a = _1", "a = +0x1", "a = 0X1", "a = 0x",
    "a = 0x_1", "a = 0x1_", "a = -0b1", "a = 0o8", "a = 0b2", "a = 0xg", "a = 1 2", "a = 9223372036854775807",
    "a = 9223372036854775808", "a = -9223372036854775808", "a = -9223372036854775809",
    "a = 00.5", "a = 0_1.5", "a = 1.5_", "a = 1_.5", "a = 1._5", "a = 1e_5", "a = 1e5_", "a = 1e", "a = 1.0e",
    "a = 1e-_5", "a = 1.2.3", "a = 1e5.5", "a = 1e1_000", "a = 1e400", "a = -1e400", "a = 1e-400",
    "a = 4.9e-324", "a = 2.4703282292062327e-324", "a = 1.7976931348623157e308", "a = 1.7976931348623159e308",
    "a = 0e0", "a = -0e0", "a = 0.0e-0", "a = Inf", "a = NaN", "a = infinity", "a = -+1.0", "a = +-inf",
    "a = TRUE", "a = True", "a = truee", "a = tru", "a = false1",
    'a = "\\uD800"', 'a = "\\U00110000"', 'a = "\\U0010FFFF"', 'a = "\\x41"', 'a = "\\e"', 'a = "\\u00"',
    'a = "a\\\nb"', 'a = """a\\ \nb"""', 'a = """a\\ x"""', 'a = """a\\', 'a = """"""', 'a = """""',
    'a = """a""""""', "a = ''''''", "a = '''a''''''", 'a = """\r\na"""', 'a = """a\rb"""', "a = '''a\rb'''",
    'a = "\x7f"', "a = '\x7f'", "a = '''\x7f'''", "# \x7f", "# \x00", "# \r", "# é",
    "\ufeffa = 1", "a = 1\u00a0", "\u00a0a = 1",
    "a = " + "1" * 4300, "a = " + "1" * 4301, "a = -" + "9" * 4301, "a = 0x" + "f" * 5000,
    "a = " + "1" * 4301 + ".0", "a = 0." + "1" * 5000,
    # out of scope for the port, accepted by tomllib
    "a = [1]", "a = {b = 1}", "[[a]]", "a = 1979-05-27", "a = 07:32:00", "a = 1979-05-27T07:32:00Z",
    # lone surrogates in the str passed to loads (not a UTF-8 document)
    'a = "\ud800"', "a = '\udfff'", "# \ud800",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_DOCS)
    ap.add_argument("--mutant", choices=sorted(MUTANTS))
    args = ap.parse_args()

    rng = random.Random(SEED)
    g = load_port(args.mutant)
    port_parse = g["_ae_parseToml"]
    port_encode = g["_ae_encodeToml"]

    print(f"tomllib under test: CPython {sys.version.split()[0]} ({tomllib.__file__})")
    print(f"seed {SEED}" + (f", MUTANT {args.mutant}" if args.mutant else ""))

    inputs = list(EDGE_CASES)
    n_valid_gen = 0
    while len(inputs) < args.n:
        d = gen_doc(rng)
        if rng.random() < 0.45:
            inputs.append(d)
            n_valid_gen += 1
        else:
            inputs.append(mutate(rng, d))

    agree = Counter()
    reasons = Counter()  # tomllib's message on inputs both sides reject
    classes = Counter()
    examples: dict[str, list] = {}
    unexplained = []
    rt_ok = 0
    rt_fail = []
    rt_classes = Counter()
    for s in inputs:
        port = run_port(port_parse, s)
        lib = run_lib(s)
        if port[0] == "err" and lib[0] == "err":
            agree["reject"] += 1
            reasons[lib[1].split(" (at ")[0].split(" ('")[0].split(" {")[0]] += 1
            continue
        if port[0] == "ok" and lib[0] == "ok" and norm_port(port[1]) == lib[1]:
            agree["accept"] += 1
            # round trip through the port's canonical encoding
            try:
                enc = port_encode(port[1])  # ensures: parseToml(enc) is the same document
            except AetherError as e:
                rt_fail.append((s, "port contract: " + str(e).splitlines()[0]))
                continue
            back = run_lib(enc)
            if back[0] == "ok" and back[1] == lib[1]:
                rt_ok += 1
            elif back[0] == "crash" and back[1].startswith("ValueError: Exceeds the limit (4300 digits)"):
                rt_classes["int_max_str_digits"] += 1
            else:
                rt_fail.append((s, enc, back))
            continue
        c = classify(s, port, lib)
        if c is None:
            unexplained.append((s, port, lib))
            continue
        classes[c] += 1
        if len(examples.setdefault(c, [])) < 3:
            examples[c].append(s if len(s) < 60 else s[:40] + "...(%d chars)" % len(s))

    total = len(inputs)
    div = sum(classes.values()) + len(unexplained)
    print(f"\ndocuments: {total} ({len(EDGE_CASES)} edge cases, {n_valid_gen} generated valid-shaped, "
          f"{total - len(EDGE_CASES) - n_valid_gen} mutated)")
    print(f"  agree {total - div} ({agree['accept']} both accept, same value; {agree['reject']} both reject)")
    print("  both reject, by tomllib's reason:")
    for r, k in reasons.most_common():
        print(f"    {k:6d}  {r}")
    print(f"  divergences: {div} ({sum(classes.values())} attributed, {len(unexplained)} unexplained)")
    for c, k in sorted(classes.items()):
        print(f"    {c:24s} {k:6d}   e.g. {', '.join(repr(x) for x in examples[c])}")
    for s, port, lib in unexplained[:25]:
        pv = port[1] if port[0] != "ok" else norm_port(port[1])[:4]
        lv = lib[1] if lib[0] != "ok" else lib[1][:4]
        print(f"  UNEXPLAINED {s!r}\n      port={port[0]} {pv}\n      lib={lib[0]} {lv}")
    print(f"\nround trip (port encode -> port parse [ensures] and tomllib.loads): "
          f"{agree['accept']} documents | {rt_ok} pass"
          + "".join(f" | {k}: {v}" for k, v in rt_classes.items()) + f" | {len(rt_fail)} fail")
    for f in rt_fail[:10]:
        print(f"  RT FAIL {f!r}")

    ok = not unexplained and not rt_fail
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
