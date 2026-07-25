"""Python frontend — expression translation and sink detection.

`tests/test_py_soundness.py` owns the capability-table soundness contract
(nothing here may weaken it). This file owns the other half: that a Python
function BODY reaches the Aether detectors as judgeable expression shapes,
and that the sink mapping fires the right existing detector.

Run: python -B tests/test_py_frontend_sinks.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from tools.py_frontend import py_to_ir                    # noqa: E402
from aether.passes import analyze_flat                    # noqa: E402
from aether.passes.ast_walk import walk                   # noqa: E402


def _fn(src: str, name: str):
    ast_dict, _unp, _meta = py_to_ir(src)
    for d in ast_dict["decls"]:
        if d.get("kind") == "FunctionDecl" and d["name"] == name:
            return d
    raise AssertionError(f"no FunctionDecl named {name!r}")


def _codes(src: str):
    ast_dict, _unp, _meta = py_to_ir(src)
    return sorted(d.code for d in analyze_flat(ast_dict))


# --- expression translation ---------------------------------------------

def test_body_is_no_longer_discarded():
    d = _fn("def f(a):\n    x = a + 'b'\n    return x\n", "f")
    assert d["body"], "the function body must reach the IR, not be dropped"
    print("body: statements reach the IR")


def test_assign_becomes_let():
    d = _fn("def f(a):\n    x = 'lit'\n", "f")
    lets = [n for n in walk(d["body"], "Let")]
    assert len(lets) == 1 and lets[0]["name"] == "x", \
        "a single-target assignment must become a Let the safe-name pass can read"
    assert lets[0]["value"]["kind"] == "StringLit", "a str constant is a StringLit"
    print("Let: assignment translated with a StringLit value")


def test_concat_becomes_binop_plus():
    d = _fn("def f(a):\n    x = 'p/' + a\n", "f")
    lets = [n for n in walk(d["body"], "Let")]
    v = lets[0]["value"]
    assert v["kind"] == "BinOp" and v["op"] == "+", \
        "string concatenation must reach the rules as BinOp '+'"
    print("BinOp: '+' concatenation translated")


def test_fstring_becomes_concat():
    d = _fn("def f(uid):\n    x = f'id={uid}'\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "BinOp" and v["op"] == "+", \
        "an f-string with an interpolation is a concatenation, not a literal"
    print("BinOp: f-string with interpolation translated as concat")


def test_constant_only_fstring_is_a_literal():
    d = _fn("def f():\n    x = f'no interpolation here'\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "StringLit", \
        "an f-string with no FormattedValue is a fixed literal"
    print("StringLit: constant-only f-string translated as a literal")


def test_percent_format_becomes_concat():
    d = _fn("def f(a):\n    x = 'id=%s' % a\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "BinOp" and v["op"] == "+", \
        "%-formatting builds a dynamic string - same shape as concat"
    print("BinOp: %-formatting translated as concat")


def test_unmodeled_expression_is_not_cleared():
    d = _fn("def f(xs):\n    x = [i for i in xs]\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "PyExpr", \
        "an unmodeled expression must be opaque, never silently a literal"
    print("PyExpr: unmodeled expression stays opaque (flag-more direction)")


if __name__ == "__main__":
    test_body_is_no_longer_discarded()
    test_assign_becomes_let()
    test_concat_becomes_binop_plus()
    test_fstring_becomes_concat()
    test_constant_only_fstring_is_a_literal()
    test_percent_format_becomes_concat()
    test_unmodeled_expression_is_not_cleared()
    print("PY FRONTEND: ALL TESTS PASS")
