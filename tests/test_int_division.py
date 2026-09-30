"""BUG-103: `Int` `/` and `%` are floor division and floor remainder.

`grammar/types.md` did not say how they round with a negative operand, so a
port transcribed from a truncating language (C, Java, Rust, Go) computed
silently different values. The runtime always floored; this pins it.

Run: python -B tests/test_int_division.py   (exit 0 = pass)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse  # noqa: E402
from aether.emitter import emit  # noqa: E402
from aether.runtime import build_namespace, mangle  # noqa: E402

SRC = """
function q(a: Int, b: Int) returns Int
  effects pure
do
  return a / b
end

function r(a: Int, b: Int) returns Int
  effects pure
do
  return a % b
end
"""


def test_int_division_floors():
    g = build_namespace()
    exec(compile(emit(parse(SRC, "<div>")), "<div>", "exec"), g)
    cases = [(7, 2, 3, 1), (-7, 2, -4, 1), (7, -2, -4, -1), (-7, -2, 3, -1),
             (-8, 2, -4, 0)]
    for a, b, quot, rem in cases:
        assert g[mangle("q")](a, b) == quot, (a, b, g[mangle("q")](a, b))
        assert g[mangle("r")](a, b) == rem, (a, b, g[mangle("r")](a, b))
    for a, b in [(a, b) for a, b, _, _ in cases] + [(10**40 + 1, -3), (-(10**40), 7)]:
        # the law that pins both together: a == b*q + r, r has b's sign
        qq, rr = g[mangle("q")](a, b), g[mangle("r")](a, b)
        assert a == b * qq + rr and (rr == 0 or (rr > 0) == (b > 0)), (a, b)
    print("BUG-103: Int / and % floor (-7/2 == -4, -7%2 == 1, 7%-2 == -1)")


if __name__ == "__main__":
    test_int_division_floors()
    print("INT DIVISION TESTS PASS")
