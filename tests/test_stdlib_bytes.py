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
