"""End-to-end tests: bitwise keyword operators, Bytes<->Int bridge,
ord/chr, formatFloat (gap shortlist wave 1).

Standalone (`python -B tests/test_stdlib_bytes.py`, exit 0) and
pytest-collectable. Same harness as tests/test_stdlib_d1.py.
"""
from __future__ import annotations
import io
import os
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse      # noqa: E402
from aether.emitter import emit      # noqa: E402
from aether.pretty import pretty     # noqa: E402
from aether.runtime import build_namespace  # noqa: E402


def _run(src: str) -> str:
    ast = parse(src, "<bytes>")
    py = emit(ast)
    code = compile(py, "<bytes>", "exec")
    g = build_namespace()
    g["__name__"] = "__main__"
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(code, g)
    return buf.getvalue()


BITWISE_SRC = """
function main() returns Unit
  effects log
do
  print(intToString(12 band 10))
  print(intToString(12 bor 10))
  print(intToString(12 bxor 10))
  print(intToString(1 shl 5))
  print(intToString(1024 shr 3))
  print(intToString(2 + 1 shl 5))
  print(intToString(1 bor 2 bxor 2))
end
"""


def test_bitwise_operators():
    # 2 + 1 shl 5: additive binds tighter than shift -> 3 shl 5 = 96.
    # 1 bor 2 bxor 2: bxor binds tighter than bor -> 1 bor 0 = 1.
    assert _run(BITWISE_SRC) == "8\n14\n6\n32\n128\n96\n1\n"


def test_bitwise_pretty_roundtrip():
    ast1 = parse(BITWISE_SRC, "<rt>")
    ast2 = parse(pretty(ast1), "<rt2>")
    py1, py2 = emit(ast1), emit(ast2)
    assert py1 == py2


BYTES_SRC = """
function main() returns Unit
  effects log
do
  print(intToString(ord("A")))
  print(chr(66))
  let b: Bytes = bytesFromList([222, 173, 190, 239])
  print(intToString(bytesLen(b)))
  print(intToString(byteAt(b, 0)))
  print(intToString(byteAt(b, 3)))
  let h: Bytes = sha256(stringToBytes("abc"))
  print(intToString(bytesLen(h)))
  print(intToString(byteAt(h, 0)))
  print(bytesToString(bytesFromList([104, 105])))
  print(intToString(sum(bytesToList(bytesFromList([1, 2, 3])))))
end
"""


def test_bytes_bridge():
    # sha256("abc") = ba7816bf... -> first byte 0xba = 186
    assert _run(BYTES_SRC) == "65\nB\n4\n222\n239\n32\n186\nhi\n6\n"


def test_bytes_domain_errors():
    from aether.diagnostics import AetherError
    from aether import runtime as rt
    for bad in [
        lambda: rt._ae_byteAt(b"ab", 2),
        lambda: rt._ae_byteAt(b"ab", -1),
        lambda: rt._ae_ord("ab"),
        lambda: rt._ae_ord(""),
        lambda: rt._ae_chr(-1),
        lambda: rt._ae_chr(1114112),
        lambda: rt._ae_bytesFromList([0, 256]),
        lambda: rt._ae_bytesFromList([-1]),
    ]:
        try:
            bad()
        except AetherError as e:
            assert e.diag.code == "E0305", e.diag.code
        else:
            raise AssertionError(f"no E0305 from {bad}")


FFLOAT_SRC = """
function main() returns Unit
  effects log
do
  print(formatFloat(2.25, 1))
  print(formatFloat(2.35, 1))
  print(formatFloat(2.675, 2))
  print(formatFloat(1.5, 0))
  print(formatFloat(0.0 - 0.04, 1))
  print(formatFloat(3.0, 3))
end
"""


def test_format_float():
    # 2.25 is exactly representable -> half-even ties to 2.2.
    # 2.35 in binary is 2.350000000000000088... -> above the tie -> 2.4.
    # 2.675 in binary is 2.674999999999999822... -> below the tie -> 2.67.
    # 1.5 with 0 digits: half-even ties to 2.
    assert _run(FFLOAT_SRC) == "2.2\n2.4\n2.67\n2\n-0.0\n3.000\n"


def test_format_float_matches_python_format():
    from aether import runtime as rt
    for x in [0.1, 2.5, 2.675, 1e10, -3.14159, 123456.789]:
        for nd in [0, 1, 2, 6]:
            assert rt._ae_formatFloat(x, nd) == format(x, f".{nd}f"), (x, nd)


def test_format_float_domain():
    from aether.diagnostics import AetherError
    from aether import runtime as rt
    try:
        rt._ae_formatFloat(1.0, -1)
    except AetherError as e:
        assert e.diag.code == "E0305"
    else:
        raise AssertionError("no E0305 for ndigits < 0")


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f()
        print(f"ok {n}")
    print(f"OK: {len(tests)} bytes/bitwise tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
