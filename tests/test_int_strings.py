"""BUG-102: `parseInt` / `intToString` follow Aether's spec, not Python's
`int()` / `str()`.

`grammar/types.md` specifies `Int` as arbitrary-precision. The runtime used
to inherit two accidents of CPython:

  * `int()`'s grammar: surrounding whitespace, `_` separators, a leading
    `+` and any Unicode decimal digit parsed (`parseInt(" 12 ")` -> 12);
  * the 4300-digit `int_max_str_digits` guard: a valid long decimal was
    `Err`, and `intToString` of a long `Int` crashed with a raw ValueError.

Run: python -B tests/test_int_strings.py   (exit 0 = pass)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from transpiler.aether.runtime import build_namespace, mangle  # noqa: E402

NS = build_namespace()
parse_int = NS[mangle("parseInt")]
int_to_string = NS[mangle("intToString")]


def _ok(r):
    return r[0] == "Ok"          # a Result is the tuple (tag, payload)


def _value(r):
    assert r[0] == "Ok", r
    return r[1]


def test_parse_int_accepts_ascii_decimal_only():
    for s, n in (("0", 0), ("12", 12), ("-7", -7), ("007", 7), ("-0", 0)):
        r = parse_int(s)
        assert _ok(r) and _value(r) == n, (s, r)
    for s in (" 12", "12 ", "1_000", "+7", "\u0661\u0662", "12\n", "", "-", "1.0", "0x10", "\uff11"):
        assert not _ok(parse_int(s)), f"parseInt({s!r}) must be Err, got {parse_int(s)!r}"
    print("BUG-102: parseInt accepts ASCII -?[0-9]+ only")


def test_long_ints_round_trip_past_the_cpython_digit_guard():
    for digits in (4300, 4301, 12001):
        s = "9" * digits
        r = parse_int(s)
        assert _ok(r), f"parseInt of a {digits}-digit decimal must be Ok"
        n = _value(r)
        assert n == 10 ** digits - 1
        assert int_to_string(n) == s
        assert int_to_string(-n) == "-" + s
        assert _value(parse_int("-" + s)) == -n
    big = 10 ** 5000
    assert int_to_string(big) == "1" + "0" * 5000
    assert int_to_string(big + 7) == "1" + "0" * 4999 + "7"
    print("BUG-102: parseInt/intToString round-trip Ints past 4300 digits")


if __name__ == "__main__":
    test_parse_int_accepts_ascii_decimal_only()
    test_long_ints_round_trip_past_the_cpython_digit_guard()
    print("INT STRINGS: ALL TESTS PASS")
