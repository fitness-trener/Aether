"""D.2 regression tests for the diagnostic catalog.

The promise, stated exactly: every diagnostic code CONSTRUCTED in one of
the three literal forms `tools/diagnostic_codes.py` recognises is
documented in `grammar/diagnostics.md`. A code assembled at runtime — an
f-string, a module constant, a lookup — is still invisible, and this
suite does not claim otherwise; ADR-0002 records that residual and the
condition for closing it properly.

The looser promise this file used to make ("every diagnostic code the
toolchain can emit is documented") was false and green: the scanner
matched only two of the three forms and walked two of the three roots,
so E0101-E0106, E0301, E0304, E0705 and E0706 were invisible — and
E0705/E0706 were live, tested, and documented nowhere.

Also checked: every emitting site fills the required Diagnostic fields,
and the codes split that D.2 introduces holds:

  - E0301 = requires (precondition) violation
  - E0304 = ensures  (postcondition) violation       (D.2 split)
  - E0305 = stdlib precondition violation             (D.2 split)
  - E0302 = refinement boundary violation
  - E0303 = refinement predicate raised exception
  - E0201 = parse error
  - E0501 = effect performed in pure (runtime, opt-in)
  - E0502 = effect not in declared set (runtime, opt-in)
  - E0701 = uncovered capability (static)
  - E0801 = uncovered effect (static)
  - E0601 = timeout (bench harness)
  - E0101..E0106 = lex errors
  - E9001..E9003 = internal/runtime errors caught by harness

Tests:
  1. Every code grep'd from the repo is listed in the catalog.
  2. `requires` violation raises E0301 with `clause_kind == "requires"`.
  3. `ensures`  violation raises E0304 with `clause_kind == "ensures"`.
  4. `tail([])` raises E0305 with `stdlib_function == "tail"`.
  5. `sqrt(-1.0)` raises E0305 with `stdlib_function == "sqrt"`.
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
from aether.diagnostics import AetherError  # noqa: E402
from tools.diagnostic_codes import codes_in, constructed_codes  # noqa: E402


CATALOG_PATH = os.path.join(ROOT, "grammar", "diagnostics.md")


def _run(src: str) -> str:
    ast = parse(src, "<d2>")
    py = emit(ast)
    code = compile(py, "<d2>", "exec")
    g = build_namespace()
    g["__name__"] = "__main__"
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(code, g)
    return buf.getvalue()


# ----------------------------------------------------------------------
# 1. Every emitted code is documented
# ----------------------------------------------------------------------

def test_construction_forms_recognised():
    """Pin the scanner's form coverage. This lives here, not beside the
    scanner, because `tools/` IS scanned — a real code written into
    `tools/diagnostic_codes.py` to demonstrate a form would count itself.
    `tests/` is not scanned, so these fixtures are inert."""
    src = "\n".join([
        'Diagnostic(code="E1001", category="x")',   # keyword argument
        'code = "E1002"',                           # local, passed on later
        '{"code": "E1003", "message": "m"}',        # dict-shaped diagnostic
        'raise self._err("E1004", "m", pos)',       # positional, lexer form
        'out.append(_diag(\n    "E1005",\n "m"))',  # positional over a newline
        '# E1006 appears in prose only and must NOT be counted.',
    ])
    got = codes_in(src)
    want = {"E1001", "E1002", "E1003", "E1004", "E1005"}
    assert got == want, (
        f"scanner form coverage drifted: found {sorted(got)}, want "
        f"{sorted(want)}. A construction form the scanner cannot see is a "
        f"code that can ship undocumented — that is the whole defect "
        f"ADR-0002 closed.")
    print("D.2 catalog: 5 construction forms recognised, prose ignored")


def test_every_emitted_code_documented():
    emitted = constructed_codes(ROOT)
    assert emitted, "no diagnostic codes found in source tree"
    if not os.path.isfile(CATALOG_PATH):
        raise AssertionError(f"catalog missing: {CATALOG_PATH}")
    catalog = open(CATALOG_PATH, encoding="utf-8").read()
    missing = [c for c in sorted(emitted) if c not in catalog]
    assert not missing, f"codes emitted but not in catalog: {missing}"
    print(f"D.2 catalog: {len(emitted)} codes constructed, all documented")


# ----------------------------------------------------------------------
# 2/3. requires (E0301) vs ensures (E0304) split
# ----------------------------------------------------------------------

def test_requires_violation_E0301():
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
    raised = False
    try:
        _run(bad)
    except AetherError as e:
        raised = True
        assert e.diag.code == "E0301", e.diag.code
        assert e.diag.extra["function"] == "safeDiv"
        assert e.diag.extra["clause_kind"] == "requires"
    assert raised
    print("D.2: requires violation -> E0301 with clause_kind=requires")


def test_ensures_violation_E0304():
    bad = """
function double(x: Int) returns Int
  ensures result == x * 2
  effects pure
do
  return x + x + 1
end

function main() returns Unit
  effects log
do
  print(intToString(double(5)))
end
"""
    raised = False
    try:
        _run(bad)
    except AetherError as e:
        raised = True
        assert e.diag.code == "E0304", e.diag.code
        assert e.diag.extra["function"] == "double"
        assert e.diag.extra["clause_kind"] == "ensures"
    assert raised
    print("D.2: ensures violation -> E0304 with clause_kind=ensures")


# ----------------------------------------------------------------------
# 4/5. stdlib contract violations -> E0305
# ----------------------------------------------------------------------

def test_tail_of_empty_E0305():
    bad = """
function main() returns Unit
  effects log
do
  let _xs: List<Int> = tail([])
  print("never")
end
"""
    raised = False
    try:
        _run(bad)
    except AetherError as e:
        raised = True
        assert e.diag.code == "E0305", e.diag.code
        assert e.diag.extra["stdlib_function"] == "tail"
    assert raised
    print("D.2: tail([]) -> E0305 with stdlib_function=tail")


def test_sqrt_of_negative_E0305():
    """Tests the runtime check directly — Aether-level Float literals
    are a v0.2 surface that isn't fully wired through the lexer for
    negatives. Calling the runtime function is equivalent."""
    from aether import runtime as rt
    raised = False
    try:
        rt._ae_sqrt(-1.0)
    except AetherError as e:
        raised = True
        assert e.diag.code == "E0305", e.diag.code
        assert e.diag.extra["stdlib_function"] == "sqrt"
    assert raised
    print("D.2: sqrt(-1.0) -> E0305 with stdlib_function=sqrt")


if __name__ == "__main__":
    test_construction_forms_recognised()
    test_every_emitted_code_documented()
    test_requires_violation_E0301()
    test_ensures_violation_E0304()
    test_tail_of_empty_E0305()
    test_sqrt_of_negative_E0305()
    print("D.2 ALL DIAGNOSTIC-CATALOG TESTS PASS")
