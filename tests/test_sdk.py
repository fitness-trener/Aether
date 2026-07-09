"""C.2 regression tests for the agent SDK.

Six contracts:
  1. sdk.parse on clean source returns ok=True with full AST.
  2. sdk.parse on broken source uses recovery; ok=False, partial AST.
  3. sdk.check surfaces both parse diagnostics and static-pass
     diagnostics (B.1 effect violation, B.3 capability leak) in one go.
  4. sdk.run executes a clean program and returns stdout.
  5. sdk.grade returns ok=True on byte-matching stdout.
  6. sdk.edit applies a structural AST transform and re-pretties.
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether import sdk  # noqa: E402


_CLEAN = """
function main() returns Unit
  effects log
do
  print("hi")
end
"""


def test_parse_clean():
    r = sdk.parse(_CLEAN)
    assert r.ok
    assert r.ast["kind"] == "Program"
    assert len(r.ast["decls"]) == 1
    print("C.2 sdk.parse: clean source ok=True")


def test_parse_recovers_with_partial_ast():
    src = """
function ok1() returns Unit
  effects log
do
  print("a")
end

function bad() returns
  effects log
do
  print("b")
end

function ok2() returns Unit
  effects log
do
  print("c")
end
"""
    r = sdk.parse(src)
    assert not r.ok
    assert len(r.diagnostics) >= 1
    assert all(d.code == "E0201" for d in r.diagnostics)
    names = [d["name"] for d in r.ast["decls"] if d.get("kind") == "FunctionDecl"]
    assert "ok1" in names and "ok2" in names, names
    print("C.2 sdk.parse: recovery returns partial AST + diagnostics")


def test_check_surfaces_effect_violation():
    src = """
function validate(s: String) returns Bool
  effects pure
do
  print("dbg")
  return true
end

function main() returns Unit
  effects log
do
  if validate("x") then
    print("ok")
  end
end
"""
    r = sdk.check(src)
    assert not r.ok
    codes = [d.code for d in r.diagnostics]
    assert "E0801" in codes, codes
    print("C.2 sdk.check: surfaces B.1 E0801 effect violation")


def test_check_surfaces_capability_violation():
    src = """
module App
  requires capability log
  exports main
end

function logger(line: String) returns Unit
  effects fs.write
do
  let _r: Result<Unit, String> = writeFile("/tmp/x.log", line)
end

function main() returns Unit
  effects log
do
  print("hi")
end
"""
    r = sdk.check(src)
    codes = [d.code for d in r.diagnostics]
    assert any(c == "E0701" for c in codes), codes
    print("C.2 sdk.check: surfaces B.3 E0701 capability violation")


def test_run_executes_clean_program():
    r = sdk.run(_CLEAN)
    assert r.ok, (r.stderr, r.diagnostic)
    assert r.stdout == "hi\n", repr(r.stdout)
    assert r.exit_code == 0
    print("C.2 sdk.run: clean program returns ok=True stdout='hi'")


def test_run_deterministic_yields_pinned_clock():
    src = """
function main() returns Unit
  effects log, time.now
do
  print(intToString(now().epochMillis))
end
"""
    a = sdk.run(src, deterministic=True)
    b = sdk.run(src, deterministic=True)
    assert a.ok and b.ok, (a.stderr, b.stderr)
    assert a.stdout == b.stdout, (a.stdout, b.stdout)
    print(f"C.2 sdk.run deterministic: identical stdout {a.stdout.strip()}")


def test_grade_matches_expected_stdout():
    g = sdk.grade(_CLEAN, expected_stdout="hi\n")
    assert g.ok, (g.actual, g.stderr)
    assert g.expected == g.actual
    # Negative case
    g2 = sdk.grade(_CLEAN, expected_stdout="nope\n")
    assert not g2.ok
    assert g2.actual == "hi\n"
    print("C.2 sdk.grade: byte-match on hit, mismatch on miss")


def test_edit_applies_ast_transform():
    def rename_print(ast):
        def walk(n):
            if isinstance(n, dict):
                if n.get("kind") == "Ident" and n.get("name") == "print":
                    n["name"] = "println"
                for v in n.values(): walk(v)
            elif isinstance(n, list):
                for x in n: walk(x)
        walk(ast)
        return ast
    new = sdk.edit(_CLEAN, rename_print)
    assert "println" in new
    assert "print(" not in new.replace("println(", "")
    # The result must still be valid Aether (parseable).
    r = sdk.parse(new)
    assert r.ok, r.diagnostics
    print("C.2 sdk.edit: AST transform produces parseable source")


def test_Source_class_caches_parse():
    s = sdk.Source.from_text(_CLEAN)
    r1 = s.parse()
    r2 = s.parse()
    assert r1.ast is r2.ast            # cache identity
    print("C.2 sdk.Source: parse is cached across calls")


if __name__ == "__main__":
    test_parse_clean()
    test_parse_recovers_with_partial_ast()
    test_check_surfaces_effect_violation()
    test_check_surfaces_capability_violation()
    test_run_executes_clean_program()
    test_run_deterministic_yields_pinned_clock()
    test_grade_matches_expected_stdout()
    test_edit_applies_ast_transform()
    test_Source_class_caches_parse()
    print("C.2 ALL SDK TESTS PASS")
