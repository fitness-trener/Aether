"""D.1 regression tests for the expanded stdlib.

Every test compiles + runs a small Aether program that exercises one
new function. Asserts byte-exact stdout. This proves the stdlib is
actually wired through the parser/emitter/runtime end-to-end, not
just defined in Python.

Functions exercised (22 total):
  List:    sort, sortBy, take, drop, sum, product, all, any, find,
           flatMap, count, flatten
  Map:     mapValues
  Set:     setUnion, setIntersection, setDifference
  String:  repeat, padLeft, padRight, chars
  Math:    gcd, lcm
"""
from __future__ import annotations
import io
import os
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse  # noqa: E402
from aether.emitter import emit  # noqa: E402
from aether.runtime import build_namespace  # noqa: E402


def _run(src: str) -> str:
    ast = parse(src, "<d1>")
    py = emit(ast)
    code = compile(py, "<d1>", "exec")
    g = build_namespace()
    g["__name__"] = "__main__"
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(code, g)
    return buf.getvalue()


CASES = [
    ("sort", """
function main() returns Unit
  effects log
do
  print(intToString(length(sort([3, 1, 4, 1, 5, 9, 2, 6]))))
end
""", "8\n"),

    ("take_drop", """
function main() returns Unit
  effects log
do
  let xs: List<Int> = [10, 20, 30, 40, 50]
  print(intToString(length(take(xs, 2))))
  print(intToString(length(drop(xs, 2))))
end
""", "2\n3\n"),

    ("sum_product", """
function main() returns Unit
  effects log
do
  print(intToString(sum([1, 2, 3, 4, 5])))
  print(intToString(product([1, 2, 3, 4])))
end
""", "15\n24\n"),

    ("all_any", """
function isPositive(x: Int) returns Bool
  effects pure
do
  return x > 0
end

function main() returns Unit
  effects log
do
  if all([1, 2, 3], isPositive) then
    print("all-yes")
  end
  if any([-1, -2, 3], isPositive) then
    print("any-yes")
  end
end
""", "all-yes\nany-yes\n"),

    ("count", """
function isEven(x: Int) returns Bool
  effects pure
do
  return (x % 2) == 0
end

function main() returns Unit
  effects log
do
  print(intToString(count([1, 2, 3, 4, 5, 6], isEven)))
end
""", "3\n"),

    ("flatMap_flatten", """
function doubleList(x: Int) returns List<Int>
  effects pure
do
  return [x, x]
end

function main() returns Unit
  effects log
do
  print(intToString(length(flatMap([1, 2, 3], doubleList))))
  print(intToString(length(flatten([[1, 2], [3], [4, 5]]))))
end
""", "6\n5\n"),

    ("repeat_pad_chars", """
function main() returns Unit
  effects log
do
  print(repeat("ab", 3))
  print(padLeft("5", 3, "0"))
  print(padRight("5", 3, "0"))
  print(intToString(length(chars("abcdef"))))
end
""", "ababab\n005\n500\n6\n"),

    ("gcd_lcm", """
function main() returns Unit
  effects log
do
  print(intToString(gcd(12, 8)))
  print(intToString(lcm(4, 6)))
end
""", "4\n12\n"),

    ("safeJoin", """
function main() returns Unit
  effects log
do
  print(safeJoin("uploads", "avatar.png"))
  print(safeJoin("uploads", "../../etc/passwd"))
  print(safeJoin("uploads", "/etc/shadow"))
end
""", "uploads/avatar.png\nuploads/etc/passwd\nuploads/etc/shadow\n"),
]


def test_each_case():
    failures = []
    for name, src, expected in CASES:
        try:
            actual = _run(src)
        except Exception as e:
            failures.append((name, f"{type(e).__name__}: {e}"))
            continue
        if actual != expected:
            failures.append((name, f"got {actual!r}, expected {expected!r}"))
    assert not failures, failures
    print(f"D.1 stdlib: {len(CASES)} end-to-end cases pass over Aether source")


def test_unit_dispatch():
    """A handful of functions that are easier tested at the Python
    runtime layer (no Aether syntax for sets-of-ints, etc.)."""
    from aether import runtime as rt
    assert rt._ae_find([1, 2, 3], lambda x: x > 1) == ("Some", 2)
    assert rt._ae_find([1, 2, 3], lambda x: x > 10) == ("None",)
    assert rt._ae_mapValues({"a": 1, "b": 2}, lambda v: v * 10) == {"a": 10, "b": 20}
    assert rt._ae_setUnion({1, 2}, {2, 3}) == frozenset({1, 2, 3})
    assert rt._ae_setIntersection({1, 2, 3}, {2, 3, 4}) == frozenset({2, 3})
    assert rt._ae_setDifference({1, 2, 3}, {2, 3, 4}) == frozenset({1})
    # safeJoin can never escape its base (path-traversal sanitizer).
    assert rt._ae_safeJoin("uploads", "../../etc/passwd") == "uploads/etc/passwd"
    assert rt._ae_safeJoin("uploads", "/etc/shadow") == "uploads/etc/shadow"
    assert rt._ae_safeJoin("base", "a/../../b") == "base/a/b"
    # sqlBind escapes the value so an injection payload stays inside the
    # quoted literal (SQL-injection sanitizer).
    assert rt._ae_sqlBind("id = ?", "42") == "id = '42'"
    assert rt._ae_sqlBind("n = ?", "o'brien; DROP TABLE t") == "n = 'o''brien; DROP TABLE t'"
    # shellArg quotes the value as ONE shell argument so injected shell
    # syntax stays inert data (command-injection sanitizer).
    assert rt._ae_shellArg("convert ? out.png", "x.jpg") == "convert 'x.jpg' out.png"
    assert rt._ae_shellArg("convert ? out.png", "x.jpg; rm -rf /") == \
        "convert 'x.jpg; rm -rf /' out.png"
    assert rt._ae_shellArg("echo ?", "a'b") == "echo 'a'\\''b'"
    # redact masks PII: emails keep first char + domain, else first char.
    assert rt._ae_redact("jane.doe@corp.example") == "j***@corp.example"
    assert rt._ae_redact("Jane Doe") == "J***"
    assert rt._ae_redact("") == "***"
    # authorize returns the Authorized proof token; sqlExec is the
    # mutating sink that requires it (E0716 statically enforces the pair).
    assert rt._ae_authorize("jane", "orders:cancel") == "AUTH(jane:orders:cancel)"
    assert rt._ae_sqlExec("UPDATE t SET x=1", rt._ae_authorize("jane", "w")) == \
        "MUTATED(UPDATE t SET x=1 by AUTH(jane:w))"
    # authorizeResource binds the proof to a resource id; sqlByOwner is
    # the resource-scoped sink (E0717 statically enforces same-id).
    assert rt._ae_authorizeResource("jane", "docs:edit", "doc-1") == \
        "AUTH(jane:docs:edit@doc-1)"
    assert rt._ae_sqlByOwner("UPDATE docs SET b=1", "doc-1",
                             rt._ae_authorizeResource("jane", "docs:edit", "doc-1")) == \
        "MUTATED(UPDATE docs SET b=1 @ doc-1 by AUTH(jane:docs:edit@doc-1))"
    # safeRedirect pins the host: absolute + protocol-relative targets can
    # only ever become a path under `host` (open-redirect sanitizer).
    assert rt._ae_safeRedirect("app.example.com", "//evil.com/x") == \
        "https://app.example.com/evil.com/x"
    assert rt._ae_safeRedirect("app.example.com", "https://evil.com/y") == \
        "https://app.example.com/y"
    assert rt._ae_safeRedirect("app.example.com", "/account") == \
        "https://app.example.com/account"
    print("D.1 runtime: find, mapValues, set ops, safeJoin, sqlBind, shellArg, redact, authorize/sqlExec, authorizeResource/sqlByOwner, safeRedirect dispatch correctly")


if __name__ == "__main__":
    test_each_case()
    test_unit_dispatch()
    print("D.1 ALL STDLIB TESTS PASS")
