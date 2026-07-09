"""E0202 — static match-exhaustiveness check.

Aether's match traps an unhandled variant at RUNTIME. E0202 lifts that to a
static guarantee: a match whose scrutinee has a resolvable union type must
handle every case or carry a wildcard. This is the architectural-integrity
promise applied to control flow — a new union variant breaks every stale
match at compile time.

Run: python3 tests/test_exhaustiveness.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from aether.parser import parse                    # noqa: E402
from aether.passes.effects import (                # noqa: E402
    check_exhaustiveness, check_unreachable_arms, check_dead_code,
    check_unused_binding, check_ignored_result, check_unsatisfiable_refinement,
)

_U = """union Color do
  case Red
  case Green
  case Blue
end
"""


def _codes(body: str):
    return [d.code for d in check_exhaustiveness(parse(_U + body, "<ex>"))]


def test_missing_case_rejected():
    codes = _codes("""function f(c: Color) returns String
  effects pure
do
  match c do
    case Red() do
      return "r"
    end
    case Green() do
      return "g"
    end
  end
end
""")
    assert codes == ["E0202"], f"missing Blue must raise E0202, got {codes}"
    print("E0202: non-exhaustive match rejected")


def test_all_cases_clean():
    codes = _codes("""function f(c: Color) returns String
  effects pure
do
  match c do
    case Red() do
      return "r"
    end
    case Green() do
      return "g"
    end
    case Blue() do
      return "b"
    end
  end
end
""")
    assert codes == [], "an exhaustive match is clean"
    print("E0202: exhaustive match passes clean")


def test_wildcard_clean():
    codes = _codes("""function f(c: Color) returns String
  effects pure
do
  match c do
    case Red() do
      return "r"
    end
    case _ do
      return "other"
    end
  end
end
""")
    assert codes == [], "a wildcard catch-all is exhaustive"
    print("E0202: wildcard catch-all passes clean")


def test_unresolvable_scrutinee_silent():
    # Scrutinee is a call result with no annotation — type unresolvable, so
    # the check must stay silent (no false positive).
    codes = _codes("""function pick() returns Color
  effects pure
do
  return Color.Red()
end
function f() returns String
  effects pure
do
  match pick() do
    case Red() do
      return "r"
    end
  end
end
""")
    assert codes == [], "unresolvable scrutinee type must not be flagged"
    print("E0202: unresolvable scrutinee stays silent")


def _ur_codes(body: str):
    return [d.code for d in check_unreachable_arms(parse(_U + body, "<ur>"))]


def test_arm_after_wildcard_rejected():
    codes = _ur_codes("""function f(c: Color) returns String
  effects pure
do
  match c do
    case _ do
      return "any"
    end
    case Red() do
      return "r"
    end
  end
end
""")
    assert codes == ["E0203"], f"arm after wildcard must raise E0203, got {codes}"
    print("E0203: arm after wildcard rejected")


def test_duplicate_case_rejected():
    codes = _ur_codes("""function f(c: Color) returns String
  effects pure
do
  match c do
    case Red() do
      return "r"
    end
    case Red() do
      return "r2"
    end
    case Green() do
      return "g"
    end
    case Blue() do
      return "b"
    end
  end
end
""")
    assert codes == ["E0203"], f"duplicate case must raise E0203, got {codes}"
    print("E0203: duplicate case rejected")


def test_wildcard_last_clean():
    codes = _ur_codes("""function f(c: Color) returns String
  effects pure
do
  match c do
    case Red() do
      return "r"
    end
    case _ do
      return "other"
    end
  end
end
""")
    assert codes == [], "a wildcard in last position is reachable"
    print("E0203: trailing wildcard passes clean")


def test_dead_code_after_return_rejected():
    src = """function f(x: Int) returns Int
  effects pure
do
  return x
  return x
end
"""
    codes = [d.code for d in check_dead_code(parse(src, "<dc>"))]
    assert codes == ["E0204"], f"code after return must raise E0204, got {codes}"
    print("E0204: dead code after return rejected")


def test_return_last_clean():
    src = """function f(x: Int) returns Int
  effects pure
do
  if x > 0 then
    return x
  end
  return 0
end
"""
    codes = [d.code for d in check_dead_code(parse(src, "<dc>"))]
    assert codes == [], "a return in last position of its block is clean"
    print("E0204: terminal return passes clean")


def test_unused_binding_rejected():
    src = """function f(x: Int) returns Int
  effects pure
do
  let dead: Int = 99
  return x
end
"""
    codes = [d.code for d in check_unused_binding(parse(src, "<ub>"))]
    assert codes == ["E0205"], f"unused let must raise E0205, got {codes}"
    print("E0205: unused binding rejected")


def test_underscore_discard_clean():
    src = """function f() returns Unit
  effects fs.write
do
  let _r: Result<Unit, String> = writeFile("/tmp/x", "y")
end
"""
    codes = [d.code for d in check_unused_binding(parse(src, "<ub>"))]
    assert codes == [], "_-prefixed discard is the sanctioned convention"
    print("E0205: _-prefixed discard passes clean")


def test_used_binding_clean():
    src = """function f(x: Int) returns Int
  effects pure
do
  let y: Int = x + 1
  return y
end
"""
    codes = [d.code for d in check_unused_binding(parse(src, "<ub>"))]
    assert codes == [], "a read binding is clean"
    print("E0205: used binding passes clean")


def test_ignored_result_rejected():
    src = """function save(data: String) returns Unit
  effects fs.write
do
  writeFile("/tmp/x", data)
end
"""
    codes = [d.code for d in check_ignored_result(parse(src, "<ir>"))]
    assert codes == ["E0206"], f"bare Result call must raise E0206, got {codes}"
    print("E0206: ignored Result rejected")


def test_bound_result_clean():
    src = """function save(data: String) returns Unit
  effects fs.write
do
  let _r: Result<Unit, String> = writeFile("/tmp/x", data)
end
"""
    codes = [d.code for d in check_ignored_result(parse(src, "<ir>"))]
    assert codes == [], "a bound (or _-discarded) Result is handled"
    print("E0206: bound Result passes clean")


def _ref(src: str):
    return [d.code for d in check_unsatisfiable_refinement(parse(src, "<ref>"))]


def test_reversed_bounds_rejected():
    assert _ref("type Bad = Int where self >= 10 and self <= 5") == ["E0207"]
    print("E0207: reversed bounds rejected")


def test_contradictory_eq_rejected():
    assert _ref("type Bad = Int where self == 5 and self == 7") == ["E0207"]
    print("E0207: contradictory == rejected")


def test_valid_refinement_clean():
    assert _ref("type Pct = Int where self >= 0 and self <= 100") == []
    print("E0207: valid refinement passes clean")


def test_unanalyzable_refinement_clean():
    # A predicate the interval analysis can't read must NOT be flagged.
    assert _ref("type T = Int where self >= 0 and (self % 2) == 0") == []
    print("E0207: unanalyzable predicate stays silent (sound)")


if __name__ == "__main__":
    test_missing_case_rejected()
    test_all_cases_clean()
    test_wildcard_clean()
    test_unresolvable_scrutinee_silent()
    test_arm_after_wildcard_rejected()
    test_duplicate_case_rejected()
    test_wildcard_last_clean()
    test_dead_code_after_return_rejected()
    test_return_last_clean()
    test_unused_binding_rejected()
    test_underscore_discard_clean()
    test_used_binding_clean()
    test_ignored_result_rejected()
    test_bound_result_clean()
    test_reversed_bounds_rejected()
    test_contradictory_eq_rejected()
    test_valid_refinement_clean()
    test_unanalyzable_refinement_clean()
    print("E0202..E0207 ALL STATIC-SEMANTIC TESTS PASS")
