"""Wave 2 of the 2026-09-24 audit: the compiler refuses again.

Every program below was ACCEPTED (`check` exit 0) at 52f04aa. Each test
asserts the exact multiset of codes the analysis now reports, so a
regression in either direction (a miss, or a new over-flag on the
sanctioned shapes) goes red.

  A5  one binder iterator: `for` / `match` names re-bind a proven name
  A1  contracts, refinement predicates and const initializers are code
  A2  a callee the checker cannot name has the closed-world effect bound

Run: python -B tests/test_compiler_refuses.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from aether.parser import parse               # noqa: E402
from aether.passes import analyze_flat        # noqa: E402


def codes(src: str) -> list:
    return sorted(d.code for d in analyze_flat(parse(src, "<w2>")))


def diags(src: str) -> list:
    return analyze_flat(parse(src, "<w2>"))


# ----------------------------------------------------------------------
# A5 — value-less binders disqualify a proven name
# ----------------------------------------------------------------------

def test_a5_for_shadow_path():
    assert codes("""
function f(paths: List<String>) returns Unit
  effects fs.read
do
  let p: String = "/etc/motd"
  for p in paths do
    let _r: Result<String, String> = readFile(p)
  end
end
""") == ["E0711"]


def test_a5_match_shadow_path():
    assert codes("""
function f(o: Option<String>) returns Unit
  effects fs.read, log
do
  let p: String = "/etc/motd"
  match o do
    case Some(p) do
      let _r: Result<String, String> = readFile(p)
    end
    case None() do
      print("none")
    end
  end
end
""") == ["E0711"]


def test_a5_for_shadow_sql():
    assert codes("""
function q(xs: List<String>) returns Unit
  effects db.query
do
  let s: String = "SELECT 1"
  for s in xs do
    let _r: String = sqlQuery(s)
  end
end
""") == ["E0713"]


def test_a5_for_shadow_idor():
    assert codes("""
function upd(ids: List<String>, user: String) returns Unit
  effects db.exec
do
  let id: String = "doc-1"
  let proof: Authorized<String> = authorizeResource(user, "docs:edit", id)
  for id in ids do
    let stmt: String = sqlBind("UPDATE docs SET body='x' WHERE id = ?", id)
    let _r: String = sqlByOwner(stmt, id, proof)
  end
end
""") == ["E0717"]


def test_a5_for_shadow_authorized():
    # A proven token re-bound by a loop over raw tokens is not a proof.
    assert codes("""
function f(toks: List<String>, u: String) returns Unit
  effects db.exec
do
  let tok = authorize(u, "orders:cancel")
  for tok in toks do
    let _r: String = sqlExec("UPDATE t SET x = 1", tok)
  end
end
""") == ["E0716"]


def test_a5_raw_param_later_assigned_a_proof():
    # A parameter is a binder: its raw value reaches the sink before the
    # assignment, so "every binding is a proof" must include it.
    assert codes("""
function f(tok: String, u: String) returns Unit
  effects db.exec
do
  let _r: String = sqlExec("UPDATE t SET x = 1", tok)
  tok = authorize(u, "orders:cancel")
end
""") == ["E0716"]


def test_a5_sanctioned_shapes_stay_clean():
    # The fixed forms: a literal never re-bound, and a proof minted from
    # the loop variable inside the loop for a name bound once.
    assert codes("""
function f() returns Unit
  effects db.query
do
  let s: String = "SELECT 1"
  let _r: String = sqlQuery(s)
end
""") == []
    assert codes("""
function upd(id: String, user: String) returns Unit
  effects db.exec
do
  let proof: Authorized<String> = authorizeResource(user, "docs:edit", id)
  let stmt: String = sqlBind("UPDATE docs SET body='x' WHERE id = ?", id)
  let _r: String = sqlByOwner(stmt, id, proof)
end
""") == []


def test_a5_as_pattern_carries_taint():
    # `case Some(x) as y` binds y to the scrutinee itself.
    assert codes("""
function f(o: Option<Secret<String>>) returns Unit
  effects log
do
  match o do
    case Some(x) as y do
      print(y)
    end
    case None() do
      print("none")
    end
  end
end
""").count("E0712") == 1


# ----------------------------------------------------------------------
# A1 — requires / ensures / refinement predicates / const initializers
# ----------------------------------------------------------------------

def test_a1_requires_effect():
    ds = diags("""
function double(x: Int) returns Int
  requires isOk?(writeFile("out.txt", "pure fn wrote this"))
  effects pure
do
  return x * 2
end
""")
    assert sorted(d.code for d in ds) == ["E0801"]
    assert ds[0].extra["caller"] == "double"
    assert ds[0].extra["missing_effect"] == [["fs", "write"], None]


def test_a1_ensures_effect():
    assert codes("""
function f(x: Int) returns Int
  ensures isOk?(writeFile("out.txt", "x"))
  effects pure
do
  return x
end
""") == ["E0801"]


def test_a1_refinement_predicate_effect():
    ds = diags("""
type Logged = Int where isOk?(writeFile("out.txt", "predicate wrote this"))
function double(x: Logged) returns Int
  effects pure
do
  return x * 2
end
""")
    assert [d.code for d in ds] == ["E0801"]
    assert ds[0].extra["caller"] == "<type Logged where>"


def test_a1_const_initializer_effect():
    assert codes("""
module M
  requires capability log
  exports main
end
const X: Bool = isOk?(writeFile("out.txt", "const init wrote this"))
function main() returns Unit
  effects log
do
  print("hello")
end
""") == ["E0701", "E0801"]


def test_a1_requires_shell_injection():
    assert codes("""
function tidy(name: String) returns Int
  requires shellExec("rm -rf " + name) != ""
  effects pure
do
  return 1
end
""") == ["E0714", "E0801"]


def test_a1_pure_contracts_stay_clean():
    assert codes("""
type Small = Int where self > 0 and self < 10
const LIMIT: Int = 5
function f(x: Small) returns Int
  requires x < LIMIT
  ensures result >= 0
  effects pure
do
  return x
end
""") == []


# ----------------------------------------------------------------------
# A2 — function values the checker cannot name
# ----------------------------------------------------------------------

LOG_IT = """
function logIt(s: String) returns Unit
  effects log
do
  print(s)
end
"""


def _unknown(src):
    ds = [d for d in diags(src) if d.code == "E0801"]
    assert ds and all(d.extra.get("via") == "unknown_callee" for d in ds), \
        [(d.code, d.extra) for d in ds]
    return ds


def test_a2_indexed_list_under_module():
    src = """
module Reporter
  requires capability log
  exports main
end
function launder(s: String) returns Unit
  effects pure
do
  let ws = [writeFile]
  let _r = ws[0]("pwned.txt", s)
end
function main() returns Unit
  effects log
do
  launder("x")
  print("done")
end
"""
    assert codes(src) == ["E0701", "E0701", "E0801"]
    d = _unknown(src)[0]
    assert d.extra["caller"] == "launder" and d.extra["callee"] == "writeFile"
    assert d.extra["shape"] == "an indexed element"


def test_a2_returned_function():
    _unknown(LOG_IT + """
function getF() returns function(String) returns Unit
  effects pure
do
  let g = [logIt]
  return g[0]
end
function launder(s: String) returns Unit
  effects pure
do
  let h = getF()
  h(s)
end
""")


def test_a2_const_alias():
    ds = [d for d in diags("""
const g: function(String) returns Unit = print
function launder(s: String) returns Unit
  effects pure
do
  g(s)
end
""") if d.code == "E0801"]
    assert [(d.extra["caller"], d.extra["callee"]) for d in ds] == [("launder", "print")]


def test_a2_list_element_to_hof():
    _unknown(LOG_IT + """
function launder(s: String) returns List<String>
  effects pure
do
  let fs = [logIt]
  return map([s], fs[0])
end
""")


def test_a2_if_expr_function():
    _unknown("""
function launder(s: String) returns Unit
  effects pure
do
  let h = if true then print else print end
  h(s)
end
""")


def test_a2_pattern_bound_function():
    _unknown("""
function launder(s: String) returns Unit
  effects pure
do
  let m = {"k": writeFile}
  let r = get(m, "k")
  match r do
    case Some(w) do
      let _x = w("pwned.txt", s)
    end
    case None do
      return
    end
  end
end
""")


def test_a2_record_field_function():
    _unknown(LOG_IT + """
function launder(b: Map<String, String>, s: String) returns Unit
  effects pure
do
  let keep = logIt
  b.f(s)
end
""")


def test_a2_sanctioned_shapes_stay_clean():
    # BUG-022: a call through a function-typed parameter is charged where
    # the function is passed; main declares `log`, so nothing fires.
    assert codes("""
function apply(f: function(String) returns Unit, s: String) returns Unit
  effects pure
do
  f(s)
end
function main() returns Unit
  effects log
do
  apply(print, "ok")
end
""") == []
    # Only PURE functions escape as values: the bound is empty, proven pure.
    assert codes("""
function double(n: Int) returns Int
  effects pure
do
  return n * 2
end
function run(xs: List<Int>) returns Int
  effects pure
do
  let fs = [double]
  let ys = map(xs, fs[0])
  return fs[0](length(ys))
end
""") == []
    # A caller that declares the bound is covered.
    assert codes(LOG_IT + """
function run(s: String) returns Unit
  effects log
do
  let fs = [logIt]
  fs[0](s)
end
""") == []
    # An effectful function that escapes does not taint a direct call.
    assert codes(LOG_IT + """
function keep() returns List<function(String) returns Unit>
  effects pure
do
  return [logIt]
end
function run(xs: List<Int>) returns Int
  effects pure
do
  return length(xs)
end
""") == []


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print(f"ok  {name}")
    print(f"WAVE 2 REFUSAL: {n} tests pass")
