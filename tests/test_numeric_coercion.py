"""E0209 — implicit Int/Float coercion, refused where both types are known.

Before: `let a = 1 + 2.5` passed `check` (exit 0) and evaluated to 3.5
(`grammar/types.md`, "Excluded by design but not refused"). A Float
compared with an exact Int above 2**53 — the humanize 4.16.0 intword
carry defect — was invisible to the language. Now an arithmetic or
comparison operator, a `return`, or a binding that meets Int with Float
is E0209 when BOTH types are statically known.

This is a local check, not a type checker: an operand of unknown type
(a list element, a match binding, a polymorphic stdlib call) is never a
finding.

Run: python -B tests/test_numeric_coercion.py   (exit 0 = pass)
"""
from __future__ import annotations
import io
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse                                 # noqa: E402
from aether.passes import analyze_flat                          # noqa: E402
from aether.passes.numeric import check_numeric_coercion, _STDLIB  # noqa: E402


def _e(src: str):
    return [(d.extra["kind"], d.extra["op"], d.extra["left_type"],
             d.extra["right_type"]) for d in check_numeric_coercion(parse(src))]


def _fn(body: str, params: str = "", ret: str = "Unit",
        pre: str = "") -> str:
    return (f"{pre}function f({params}) returns {ret}\n  effects pure\ndo\n"
            f"{body}\nend\n")


MIX = _fn("  let a = 1 + 2.5\n  return a", ret="Float")


def test_red_before_literal_mix():
    ds = analyze_flat(parse(MIX))
    # Red before E0209: every other detector is silent on this program,
    # so `check` exited 0 (measured at 6e7a48d: exit 0, run prints 3.5).
    assert [d.code for d in ds if d.code != "E0209"] == [], ds
    assert [d.code for d in ds] == ["E0209"], [d.code for d in ds]
    d = ds[0]
    assert d.extra == {"function": "f", "kind": "binop", "op": "+",
                       "left_type": "Int", "right_type": "Float"}, d.extra
    assert (d.position.line, d.position.column) == (4, 3), d.position
    assert "`1.0`" in d.suggestion, d.suggestion
    print("E0209: `1 + 2.5` refused (red before: check exit 0)")


def test_every_source_of_type_knowledge():
    # parameter annotation, both directions, arithmetic and comparison
    assert _e(_fn("  return n * x", "n: Int, x: Float", "Float")) == [
        ("binop", "*", "Int", "Float")]
    assert _e(_fn("  return x < n", "n: Int, x: Float", "Bool")) == [
        ("binop", "<", "Float", "Int")]
    # let/var annotation; binder propagation through an unannotated let
    assert _e(_fn("  let a: Float = 1.5\n  let b = a\n  return b - 1",
                  ret="Float")) == [("binop", "-", "Float", "Int")]
    # const
    assert _e(_fn("  return K + 1", ret="Float",
                  pre="const K: Float = 2.0\n")) == [("binop", "+", "Float", "Int")]
    # refined alias of Int
    assert _e(_fn("  return p == 1.5", "p: Pos", "Bool",
                  pre="type Pos = Int where self > 0\n")) == [
        ("binop", "==", "Int", "Float")]
    # a user function declaring `returns Float`, and a stdlib call
    assert _e(_fn("  return half() + length(s)", "s: String", "Float",
                  pre="function half() returns Float\n  effects pure\ndo\n"
                      "  return 0.5\nend\n")) == [("binop", "+", "Float", "Int")]
    assert _e(_fn("  return sqrt(x) % 2", "x: Float", "Float")) == [
        ("binop", "%", "Float", "Int")]
    # `for` over range(...), `result` in ensures, `self` in a refinement
    assert _e(_fn("  for i in range(0, 3) do\n    let y = i / 2.0\n"
                  "  end", ret="Unit")) == [("binop", "/", "Int", "Float")]
    src = ("function g(x: Float) returns Int\n  ensures result > x\n"
           "  effects pure\ndo\n  return floor(x) + 1\nend\n")
    assert _e(src) == [("binop", ">", "Int", "Float")]
    assert _e("type Prob = Float where self >= 0 and self <= 1.0\n") == [
        ("binop", ">=", "Float", "Int")]
    print("E0209: params, annotations, let propagation, const, alias, "
          "user/stdlib returns, for-range, result, self")


def test_unknown_types_are_never_a_finding():
    clean = [
        _fn("  return get(xs, 0) == 1.5", "xs: List<Float>", "Bool"),
        _fn("  return abs(n) + 1.5", "n: Int", "Float"),     # polymorphic at run time
        _fn("  return unknownT(n) + 1.5", "n: Int", "Float",
            pre="function unknownT(n: Int) returns T\n  effects pure\ndo\n"
                "  return n\nend\n"),
        _fn("  match o do\n    case Some(v) do return v + 1.5 end\n"
            "    case None do return 0.0 end\n  end", "o: Option<Int>", "Float"),
        # a local shadowing a const, of unknown type
        _fn("  let K = get([1], 0)\n  return K", ret="Int",
            pre="const K: Float = 2.0\n"),
        # same-type arithmetic, and a for variable over a non-range list
        _fn("  for v in xs do\n    let y = v * 2.5\n  end\n  return 1 + 2 * 3",
            "xs: List<Int>", "Int"),
    ]
    for src in clean:
        assert _e(src) == [], (src, _e(src))
    print("E0209: silent when either operand's type is not known")


def test_return_mismatch():
    assert _e(_fn("  return 1", ret="Float")) == [("return", None, "Float", "Int")]
    assert _e(_fn("  return x", "x: Float", "Int")) == [("return", None, "Int", "Float")]
    assert _e(_fn("  return floor(x)", "x: Float", "Int")) == []
    d = check_numeric_coercion(parse(_fn("  return 1", ret="Float")))[0]
    assert d.code == "E0209" and "`1.0`" in d.suggestion, d
    print("E0209: `returns Float` + `return 1` and `returns Int` + Float refused")


def test_binding_mismatch():
    assert _e(_fn("  let x: Float = 3\n  return x", ret="Float")) == [
        ("binding", "x", "Float", "Int")]
    assert _e(_fn("  var n = 0\n  n = 2.5\n  return n", ret="Int")) == [
        ("binding", "n", "Int", "Float")]
    assert _e("const K: Int = 2.5\n") == [("binding", "K", "Int", "Float")]
    print("E0209: annotated let/const and a var re-bound to the other type")


def test_humanize_carry_shape():
    # The humanize 4.16.0 intword defect: a Float times an exact Int power,
    # compared with an exact Int (bench/realworld_humanize/).
    implicit = _fn("  let roundedF = t / 10.0\n"
                   "  return floor(roundedF * power) == nextPower",
                   "t: Int, power: Int, nextPower: Int", "Bool")
    assert _e(implicit) == [("binop", "/", "Int", "Float"),
                            ("binop", "*", "Float", "Int")], _e(implicit)
    # The port's reproduction converts explicitly (its own intToFloat
    # helper returns Float), so the language accepts it.
    explicit = _fn("  let roundedF = intToFloat(t) / 10.0\n"
                   "  return floor(roundedF * intToFloat(power)) == nextPower",
                   "t: Int, power: Int, nextPower: Int", "Bool",
                   pre="function intToFloat(n: Int) returns Float\n"
                       "  effects pure\ndo\n"
                       "  return unwrapOr(parseFloat(intToString(n)), 0.0)\nend\n")
    assert _e(explicit) == [], _e(explicit)
    print("E0209: the humanize carry shape is refused; the explicit port is clean")


def test_stdlib_rows_match_stdlib_md():
    doc = open(os.path.join(ROOT, "grammar", "stdlib.md"), encoding="utf-8").read()
    for name, t in _STDLIB.items():
        sig = re.findall(rf"function {re.escape(name)}\b[^\n]*returns (\w+)", doc)
        assert sig and set(sig) == {t}, (name, t, sig)
    from aether.passes.names import RUNTIME_NAMES
    assert set(_STDLIB) <= RUNTIME_NAMES
    print(f"E0209: {len(_STDLIB)} stdlib return types pinned to stdlib.md")


def test_python_never_gets_E0209():
    # check-py skips the `semantic` stage, where E0209 lives; its output is
    # the same with or without the pass registered.
    from aether.py_frontend import PY_SKIP_STAGES, py_to_ir
    from aether.passes import analyze, STAGES
    from aether import cli
    assert "semantic" in PY_SKIP_STAGES
    ir = py_to_ir("def f(n):\n    return 1 + 2.5 < n\n")[0]
    assert [d.code for _s, ds in analyze(ir, skip=PY_SKIP_STAGES) for d in ds] == []
    src = ("import os\n\ndef f(p):\n    x = 1 + 2.5\n"
           "    os.system('ls ' + p)\n    return x\n")
    semantic = dict(STAGES)["semantic"]
    outs = []
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "probe.py")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(src)
        try:
            for keep in (True, False):
                if not keep:
                    semantic.remove(check_numeric_coercion)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = cli.main(["--json", "check-py", target])
                outs.append((rc, buf.getvalue()))
        finally:
            if check_numeric_coercion not in semantic:
                semantic.append(check_numeric_coercion)
    assert outs[0] == outs[1], outs
    assert outs[0][0] == 1 and '"code": "E07' in outs[0][1], outs[0]
    print("E0209: never emitted on Python; check-py output byte-identical")


if __name__ == "__main__":
    test_red_before_literal_mix()
    test_every_source_of_type_knowledge()
    test_unknown_types_are_never_a_finding()
    test_return_mismatch()
    test_binding_mismatch()
    test_humanize_carry_shape()
    test_stdlib_rows_match_stdlib_md()
    test_python_never_gets_E0209()
    print("E0209 implicit numeric coercion: ALL PASS")
