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


def test_rehydrate_handles_every_harness_diagnostic_shape():
    """`bench.harness` speaks partial dicts — three of the five shapes
    `compile_and_run` returns carry only code/category/message, and one
    carries a full position. All five must coerce, and the CODE must
    survive: a fix-loop dispatches on it.

    This coercion used to live inside `except Exception: pass`, so a
    harness shape it could not handle became `diagnostic=None` on a run
    that DID fail — ok=False with nothing to act on. The assertions below
    are what that swallow made unobservable."""
    shapes = [
        # e.diag.to_dict() — the full form, from a real AetherError.
        {"code": "E0301", "category": "contract", "severity": "error",
         "message": "requires violated", "position": {"line": 7, "column": 3},
         "suggestion": "fix the caller", "confidence": 1.0,
         "extra": {"function": "safeDiv"}},
        # emit / emit-compile / runtime — code, category, message only.
        {"message": "boom", "category": "emit", "code": "E9001"},
        {"message": "bad python", "category": "internal", "code": "E9002"},
        {"message": "TypeError: x", "category": "runtime", "code": "E9003"},
        # timeout — literal dict with a position.
        {"code": "E0601", "category": "timeout", "severity": "error",
         "message": "exceeded timeout_ms=5000",
         "suggestion": "check for infinite loops",
         "position": {"line": 0, "column": 0}},
    ]
    for d in shapes:
        got = sdk._rehydrate(d)
        assert got.code == d["code"], (d, got)
        assert got.message == d["message"], (d, got)
        assert isinstance(got.position.line, int), got
        assert got.severity, f"severity must default, not be empty: {got}"

    full = sdk._rehydrate(shapes[0])
    assert full.position.line == 7 and full.position.column == 3, full
    assert full.extra["function"] == "safeDiv", full

    partial = sdk._rehydrate(shapes[1])
    assert partial.position.line == 0, partial
    assert partial.suggestion is None and partial.extra == {}, partial

    # A position of an unexpected SHAPE is the case the old `**` splat
    # would have raised on, and the swallow would have hidden.
    odd = sdk._rehydrate({"code": "E9003", "message": "m",
                          "position": [1, 2]})
    assert odd.code == "E9003" and odd.position.line == 0, odd
    print("C.2 sdk._rehydrate: all 5 harness diagnostic shapes coerce, "
          "code preserved")


def test_run_of_failing_program_carries_a_code():
    """End-to-end: the swallow's real cost was `run()` reporting failure
    with no diagnostic. A contract violation must come back WITH its
    code."""
    bad = """
function safeDiv(a: Int, b: Int) returns Int
  requires b != 0
  effects pure
do
  return a / b
end

function main() returns Unit
  effects log
do
  print(intToString(safeDiv(10, 0)))
end
"""
    r = sdk.run(bad)
    assert not r.ok, r
    assert r.diagnostic is not None, f"run() lost the diagnostic: {r}"
    assert r.diagnostic.code == "E0301", r.diagnostic
    assert r.diagnostic.extra.get("clause_kind") == "requires", r.diagnostic
    print("C.2 sdk.run: a failing program returns its code (E0301), not None")


def test_run_works_without_bench_importable():
    """BUG-008. `sdk.run` used to reach `bench.harness` for its runner, and
    `bench/` is not in the wheel — so in every pip-installed copy the
    ImportError was caught by the function's own `except Exception` and
    returned as `RunResult(ok=False, ...)`. A working program reported as a
    failed run is worse than a crash: it is exactly what a bad candidate
    looks like, so a caller grading candidates saw them all fail.

    Reproduces the installed layout: `transpiler/` on the path, repo root
    NOT on it, so `bench` cannot be imported at all."""
    import subprocess
    prog = (
        "import sys\n"
        f"sys.path.insert(0, {os.path.join(ROOT, 'transpiler')!r})\n"
        "import importlib.util\n"
        "assert importlib.util.find_spec('bench') is None, "
        "'bench must NOT be importable for this test to mean anything'\n"
        "from aether import sdk\n"
        "r = sdk.run('function main() returns Unit\\n"
        "  effects log\\ndo\\n  print(\"hi\")\\nend\\n')\n"
        "print(repr((r.ok, r.stdout.strip(), r.stderr.strip())))\n"
    )
    # cwd outside the repo so the root cannot sneak back in via sys.path[0].
    r = subprocess.run([sys.executable, "-B", "-c", prog],
                       cwd=os.path.dirname(ROOT),
                       capture_output=True, text=True)
    assert r.returncode == 0, f"sdk.run failed without bench: {r.stderr}"
    ok, out, err = eval(r.stdout.strip())
    assert ok, f"sdk.run must work without bench importable; stderr={err!r}"
    assert out == "hi", f"stdout must survive the move: {out!r}"
    print("C.2 sdk.run: works with bench/ absent, as in an installed copy")


def test_run_reports_whether_the_timeout_was_actually_armed():
    """`timeout_ms` is POSIX-only. A caller must be able to tell "no timeout
    fired" from "this platform has no timer", instead of inferring it."""
    import signal as _signal
    r = sdk.run(_CLEAN)
    assert r.timeout_enforced == hasattr(_signal, "SIGALRM"), (
        f"timeout_enforced={r.timeout_enforced} disagrees with the platform")
    print(f"C.2 sdk.run: timeout_enforced reported honestly "
          f"({r.timeout_enforced})")


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
    test_rehydrate_handles_every_harness_diagnostic_shape()
    test_run_of_failing_program_carries_a_code()
    test_run_works_without_bench_importable()
    test_run_reports_whether_the_timeout_was_actually_armed()
    print("C.2 ALL SDK TESTS PASS")
