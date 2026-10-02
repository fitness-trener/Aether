"""Tests for the opt-in SMT contract-proving pass (--prove; E0901/E0902).

Runs standalone (`python -B tests/test_smt.py`, exit 0) or under pytest.
Every test body no-ops when z3-solver is not installed: the pass is
opt-in and the core toolchain stays stdlib-only, so a z3-less machine
must stay green.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False

from aether.parser import parse  # noqa: E402
from aether.emitter import emit  # noqa: E402
from aether.runtime import build_namespace, mangle  # noqa: E402
from aether.diagnostics import AetherError  # noqa: E402

if HAVE_Z3:
    from aether.passes.smt import (  # noqa: E402
        translate_expr, _resolve_param_sort, _mk_var, check_contracts_smt,
        floor_div, floor_mod, _Translator)


# One function whose clauses exercise the whole fragment. `requires`
# and `ensures` clause ASTs are pulled out of the parse result so the
# translator tests track the real parser shapes, not hand-built dicts.
FRAGMENT_SRC = """
function frag(x: Int, b: Bool) returns Int
  requires x >= 0 and x < 100
  requires b or not b
  requires -x <= 0
  requires x + 1 > x - 1
  requires x * 2 >= 0 implies x >= 0
  requires x != 3
  ensures result == old(x)
  effects pure
do
  return x
end
"""

UNTRANSLATABLE_SRC = """
function bad(x: Int, s: String) returns Int
  requires isFine(x)
  requires s == "hi"
  requires x band 1 == 0
  effects pure
do
  return x
end
"""


def _clauses(src, name="frag"):
    ast = parse(src, "<smt-test>")
    fn = next(d for d in ast["decls"] if d.get("kind") == "FunctionDecl"
              and d["name"] == name)
    return fn


def test_translate_full_fragment():
    if not HAVE_Z3:
        return
    fn = _clauses(FRAGMENT_SRC)
    env = {"x": _mk_var("x", "int"), "b": _mk_var("b", "bool")}
    for clause in fn["requires"]:
        z = translate_expr(clause, env)
        assert z is not None, clause
    env["result"] = _mk_var("result", "int")
    z = translate_expr(fn["ensures"][0], env)
    assert z is not None
    # old(x) must translate as x: prove result == old(x) equivalent to
    # result == x under this env.
    s = z3.Solver()
    s.add(z3.Not(z == (env["result"] == env["x"])))
    assert s.check() == z3.unsat


def test_untranslatable_returns_none():
    if not HAVE_Z3:
        return
    fn = _clauses(UNTRANSLATABLE_SRC, "bad")
    env = {"x": _mk_var("x", "int")}
    for clause in fn["requires"]:
        assert translate_expr(clause, env) is None, clause


def test_unknown_ident_returns_none():
    if not HAVE_Z3:
        return
    fn = _clauses(FRAGMENT_SRC)
    # empty env: every clause mentions x or b, so all must be None
    for clause in fn["requires"]:
        assert translate_expr(clause, {}) is None


def test_sort_mismatch_returns_none():
    if not HAVE_Z3:
        return
    src = """
function m(x: Int, b: Bool) returns Bool
  requires x + b > 0
  effects pure
do
  return b
end
"""
    fn = _clauses(src, "m")
    env = {"x": _mk_var("x", "int"), "b": _mk_var("b", "bool")}
    assert translate_expr(fn["requires"][0], env) is None


def test_resolve_param_sort_refinement_chain():
    if not HAVE_Z3:
        return
    src = """
type Percentage = Int where self >= 0 and self <= 100
type Half = Percentage where self <= 50

function f(p: Half) returns Int
  effects pure
do
  return p
end
"""
    ast = parse(src, "<smt-test>")
    type_decls = {d["name"]: d for d in ast["decls"]
                  if d.get("kind") == "TypeDecl"}
    fn = next(d for d in ast["decls"] if d.get("kind") == "FunctionDecl")
    resolved = _resolve_param_sort(fn["params"][0]["type"], type_decls)
    assert resolved is not None
    sort, preds = resolved
    assert sort == "int"
    assert len(preds) == 2  # Percentage's predicate + Half's predicate
    # unsupported types resolve to None
    assert _resolve_param_sort({"kind": "TypeName", "name": "String"},
                               type_decls) is None
    assert _resolve_param_sort({"kind": "GenericType", "name": "List",
                                "args": []}, type_decls) is None


REFUTABLE = """
function myAbs(x: Int) returns Int
  ensures result >= 0
  effects pure
do
  return x
end
"""

PROVABLE = """
function clampLow(x: Int) returns Int
  requires x >= 0
  requires x <= 100
  ensures result >= 0
  ensures result <= 100
  effects pure
do
  return x
end
"""

REFINED = """
type Percentage = Int where self >= 0 and self <= 100

function keep(p: Percentage) returns Int
  ensures result >= 0
  effects pure
do
  return p
end
"""

VIA_CALL = """
function helper(x: Int) returns Int
  effects pure
do
  return x
end

function viaCall(x: Int) returns Int
  ensures result >= 0
  effects pure
do
  return helper(x)
end
"""

UNSOUND_ASSUMPTION = """
function trusted(x: Int) returns Int
  requires isFine(x)
  ensures result >= 0
  effects pure
do
  return x
end
"""


def test_refutable_emits_e0901_with_counterexample():
    if not HAVE_Z3:
        return
    diags, summary = check_contracts_smt(parse(REFUTABLE, "<smt>"))
    assert summary == {"proved": 0, "refuted": 1, "timeout": 0,
                       "skipped": 0}, summary
    d = diags[0]
    assert d.code == "E0901"
    assert d.category == "contract"
    assert d.severity == "error"
    assert d.extra["function"] == "myAbs"
    assert d.extra["clause_kind"] == "ensures"
    cx = d.extra["counterexample"]
    assert int(cx["x"]) < 0, cx        # roadmap 1.3: concrete violating input
    assert int(cx["result"]) < 0, cx


def test_provable_produces_no_diagnostics():
    if not HAVE_Z3:
        return
    diags, summary = check_contracts_smt(parse(PROVABLE, "<smt>"))
    assert diags == []
    assert summary == {"proved": 2, "refuted": 0, "timeout": 0, "skipped": 0}


def test_refinement_predicate_is_assumed():
    if not HAVE_Z3:
        return
    diags, summary = check_contracts_smt(parse(REFINED, "<smt>"))
    assert diags == []
    assert summary["proved"] == 1, summary


def test_call_is_inlined_and_refuted():
    # helper's body is in the fragment, so the call is inlined exactly
    # and x = -1 is a real violation (was skipped before calls inlined).
    if not HAVE_Z3:
        return
    _refuted_and_replayed(VIA_CALL, "viaCall")


def test_untranslatable_requires_skips_whole_function():
    # Soundness: without the isFine(x) assumption, x = -1 would "refute"
    # the ensures. The pass must skip, not fabricate a counterexample.
    if not HAVE_Z3:
        return
    diags, summary = check_contracts_smt(parse(UNSOUND_ASSUMPTION, "<smt>"))
    assert diags == []
    assert summary == {"proved": 0, "refuted": 0, "timeout": 0, "skipped": 1}


def _run_cli(src: str, *flags: str, as_json: bool = False):
    # --json is a top-level flag and must precede the subcommand;
    # --prove & co. belong to the `check` subparser and follow the file.
    pre = ["--json"] if as_json else []
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "prog.aeth")
        with open(path, "w") as f:
            f.write(src)
        return subprocess.run(
            [sys.executable, "-B", "-m", "transpiler.aether.cli",
             *pre, "check", path, *flags],
            cwd=ROOT, capture_output=True, text=True)


def test_cli_prove_refuted_exits_1():
    if not HAVE_Z3:
        return
    r = _run_cli(REFUTABLE, "--prove", as_json=True)
    # 1 = findings; --json is one document on stdout (Wave 5b D5/D6; the
    # exit was 2 and the diagnostics JSONL on stderr).
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    doc = json.loads(r.stdout)
    assert doc["ok"] is False and doc["prove"]["refuted"] >= 1, doc
    d = next(d for d in doc["diagnostics"] if d["code"] == "E0901")
    assert d["stage"] == "smt" and "counterexample" in r.stdout, d


def test_cli_prove_proved_exits_0_with_summary():
    if not HAVE_Z3:
        return
    r = _run_cli(PROVABLE, "--prove", as_json=True)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    data = json.loads(r.stdout.strip().splitlines()[-1])
    assert data["ok"] is True
    assert data["prove"]["proved"] == 2
    assert data["prove"]["refuted"] == 0


def test_cli_prove_is_default_on_when_z3_present():
    if not HAVE_Z3:
        return
    r = _run_cli(REFUTABLE)           # no flag: default-on since wave 1
    assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
    assert "E0901" in (r.stdout + r.stderr)


def test_cli_no_prove_disables():
    if not HAVE_Z3:
        return
    r = _run_cli(REFUTABLE, "--no-prove")
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "E0901" not in (r.stdout + r.stderr)


# --- widened fragment (2026-10-02): every construct is tested three ways:
# a true clause is PROVED; a false one is REFUTED and its counterexample,
# RUN through the runtime, really violates the clause (E0304); and an
# untranslatable piece makes the clause skipped, never a spurious proof.

def _summary(src):
    return check_contracts_smt(parse(src, "<smt>"))


def _proved(src, n=1):
    diags, summary = _summary(src)
    assert diags == [] and summary["proved"] == n, (summary, diags)


def _skipped(src, n=1):
    diags, summary = _summary(src)
    assert diags == [] and summary == {"proved": 0, "refuted": 0,
                                       "timeout": 0, "skipped": n}, summary


def _refuted_and_replayed(src, fn_name):
    """Refuted, and the counterexample really breaks the ensures when
    the transpiled function runs: E0304, not a ZeroDivisionError, not a
    requires failure, not a normal return."""
    ast = parse(src, "<smt>")
    diags, summary = check_contracts_smt(ast)
    assert summary["refuted"] == 1, (summary, diags)
    d = next(x for x in diags if x.code == "E0901")
    assert d.extra["function"] == fn_name, d.extra
    fn = next(x for x in ast["decls"] if x.get("kind") == "FunctionDecl"
              and x["name"] == fn_name)
    cx = d.extra["counterexample"]
    args = [cx[p["name"]] == "True" if cx[p["name"]] in ("True", "False")
            else int(cx[p["name"]]) for p in fn["params"]]
    g = build_namespace()
    exec(compile(emit(ast), "<smt>", "exec"), g)
    try:
        out = g[mangle(fn_name)](*args)
    except AetherError as e:
        assert [x.code for x in e.diagnostics] == ["E0304"], e.diagnostics
        return cx
    raise AssertionError(f"counterexample {cx} returned {out} normally")


def test_floor_div_mod_match_python_on_a_sign_grid():
    if not HAVE_Z3:
        return
    for a in range(-9, 10):
        for b in (-4, -3, -2, -1, 1, 2, 3, 4):
            q = z3.simplify(floor_div(z3.IntVal(a), z3.IntVal(b)))
            r = z3.simplify(floor_mod(z3.IntVal(a), z3.IntVal(b)))
            assert (q.as_long(), r.as_long()) == (a // b, a % b), (a, b)
    # And for EVERY a (symbolic; b fixed keeps it linear): the pair meets
    # the law that pins floor division uniquely (a == b*q + r, with r in
    # [0, b) for b > 0 and in (b, 0] for b < 0).
    a = z3.Int("a")
    for bv in (-7, -3, -2, -1, 1, 2, 3, 7):
        b = z3.IntVal(bv)
        q, r = floor_div(a, b), floor_mod(a, b)
        s = z3.Solver()
        s.set("timeout", 5000)
        s.add(z3.Not(z3.And(
            a == b * q + r,
            z3.And(r >= 0, r < b) if bv > 0 else z3.And(r <= 0, r > b))))
        assert s.check() == z3.unsat, bv


AGREE_EXPRS = ["a / b", "a % b", "(a + 7) / (b - 1) * 2", "0 - a % (b * b + 1)",
               "(if a > b then a / b else b % a end)", "abs(a) / max(b, 1)",
               "min(a, b) % 3", "a - b / 2 % 5"]


def test_body_encoding_agrees_with_the_runtime_on_a_grid():
    # Definedness is false exactly when the runtime raises; otherwise
    # the encoded value is the runtime's value.
    if not HAVE_Z3:
        return
    for text in AGREE_EXPRS:
        src = (f"function f(a: Int, b: Int) returns Int\n  effects pure\n"
               f"do\n  return {text}\nend\n")
        ast = parse(src, "<agree>")
        fn = ast["decls"][0]
        g = build_namespace()
        exec(compile(emit(ast), "<agree>", "exec"), g)
        a, b = z3.Ints("a b")
        [(cond, value, _)] = _Translator({}, {}).function_paths(fn, [a, b])
        for x in range(-5, 6):
            for y in range(-5, 6):
                sub = [(a, z3.IntVal(x)), (b, z3.IntVal(y))]
                defined = z3.is_true(z3.simplify(z3.substitute(cond, *sub)))
                try:
                    got = g[mangle("f")](x, y)
                except ZeroDivisionError:
                    assert not defined, (text, x, y)
                    continue
                assert defined, (text, x, y)
                v = z3.simplify(z3.substitute(value, *sub)).as_long()
                assert v == got, (text, x, y, v, got)


LET_CHAIN = """
function yearStart(y: Int) returns Int
  effects pure
  requires y >= {lo}
  ensures result >= 1
do
  let p = y - 1
  return 365 * p + p / 4 - p / 100 + p / 400 + 1
end
"""


def test_let_chain_with_floor_division():
    if not HAVE_Z3:
        return
    _proved(LET_CHAIN.format(lo=1))
    cx = _refuted_and_replayed(LET_CHAIN.format(lo=0), "yearStart")
    assert int(cx["y"]) <= 0, cx


IF_CHAIN = """
function cmpInt(a: Int, b: Int) returns Int
  ensures {clause}
  effects pure
do
  if a < b then
    return 0 - 1
  elif a > b then
    return 1
  end
  return 0
end
"""


def test_if_elif_paths():
    if not HAVE_Z3:
        return
    _proved(IF_CHAIN.format(clause="result == 0 - 1 or result == 0 or result == 1"))
    _proved(IF_CHAIN.format(clause="(result == 0) == (a == b)"))
    cx = _refuted_and_replayed(IF_CHAIN.format(clause="result >= 0"), "cmpInt")
    assert int(cx["a"]) < int(cx["b"]), cx


def test_fall_through_body_is_skipped():
    # `if` without a final return can fall off the end and return None.
    if not HAVE_Z3:
        return
    _skipped("""
function f(x: Int) returns Int
  ensures result >= 0
  effects pure
do
  if x > 0 then
    return x
  end
end
""")


DIV = """
function q(a: Int, b: Int) returns Int
  requires a >= 0 and b >= 0
  ensures {clause}
  effects pure
do
  return a / b
end
"""


def test_zero_divisor_is_a_raising_path_not_a_counterexample():
    # b == 0 raises at runtime, so it cannot violate the postcondition:
    # result <= a holds on every normal return. z3's own a/0 is an
    # arbitrary value; without the definedness condition this would be
    # "refuted" with b = 0.
    if not HAVE_Z3:
        return
    _proved(DIV.format(clause="result <= a"))
    cx = _refuted_and_replayed(DIV.format(clause="result < a"), "q")
    assert int(cx["b"]) != 0, cx


def test_short_circuit_guards_division():
    if not HAVE_Z3:
        return
    _proved("""
function divides(a: Int, b: Int) returns Bool
  ensures result implies b != 0
  effects pure
do
  return b != 0 and a % b == 0
end
""")


FLOOR_MOD = """
function m(a: Int, b: Int) returns Int
  requires b < 0
  ensures {clause}
  effects pure
do
  return a % b
end
"""


def test_floor_remainder_takes_the_divisor_sign():
    # Euclidean mod (z3's native %) would make result >= 0 here; the
    # runtime floors, so the remainder of a negative divisor is <= 0.
    if not HAVE_Z3:
        return
    _proved(FLOOR_MOD.format(clause="result <= 0 and result > b"))
    # The ceiling: with a symbolic divisor the division law is nonlinear;
    # z3 gives up (E0902 warning, runtime check kept), it does not guess.
    diags, summary = check_contracts_smt(
        parse(FLOOR_MOD.format(clause="a == b * (a / b) + result"), "<smt>"),
        timeout_ms=500)
    assert summary["proved"] + summary["timeout"] == 1, summary
    assert all(d.code == "E0902" for d in diags), diags
    cx = _refuted_and_replayed(FLOOR_MOD.format(clause="result >= 0"), "m")
    assert int(cx["a"]) % int(cx["b"]) < 0, cx


def test_truncation_assumption_is_refuted():
    # A port from C assumes -(a/2) == (-a)/2; floor division breaks it.
    if not HAVE_Z3:
        return
    _refuted_and_replayed("""
function half(a: Int) returns Int
  ensures result == 0 - ((0 - a) / 2)
  effects pure
do
  return a / 2
end
""", "half")


LEAP = """
function isLeap(y: Int) returns Bool
  effects pure
do
  return (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
end

function yearLength(y: Int) returns Int
  effects pure
  ensures {clause}
do
  if isLeap(y) then
    return 366
  end
  return 365
end
"""


def test_call_to_fragment_function_is_inlined():
    if not HAVE_Z3:
        return
    _proved(LEAP.format(clause="result == 365 or result == 366"))
    _proved(LEAP.format(clause="(result == 366) == (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))"))
    cx = _refuted_and_replayed(LEAP.format(clause="result == 365"), "yearLength")
    assert int(cx["y"]) % 4 == 0, cx


OPAQUE = """
function opaque(n: Int) returns Int
  effects pure
do
  var i = 0
  while i < n do
    i = i + 1
  end
  return i
end

function weekday(n: Int) returns Int
  effects pure
  ensures {clause}
do
  return (n - opaque(n) + 3) % 7
end
"""


def test_abstracted_call_proves_but_never_refutes():
    # opaque() has a loop, so the call is a fresh value. That still
    # proves a clause true for EVERY value; a false clause has no real
    # counterexample to report, so it is skipped, not E0901.
    if not HAVE_Z3:
        return
    _proved(OPAQUE.format(clause="result >= 0 and result <= 6"))
    _skipped(OPAQUE.format(clause="result <= 5"))


def test_dropped_requires_proves_but_never_refutes():
    if not HAVE_Z3:
        return
    src = """
function f(x: Int) returns Int
  requires isFine(x)
  requires x >= 0
  ensures {clause}
  effects pure
do
  return x
end
"""
    _proved(src.format(clause="result >= 0"))
    _skipped(src.format(clause="result >= 1"))


def test_recursion_is_abstracted_not_unrolled():
    if not HAVE_Z3:
        return
    _skipped("""
function fact(n: Int) returns Int
  ensures result >= 1
  effects pure
do
  if n <= 1 then
    return 1
  end
  return n * fact(n - 1)
end
""")


def test_loop_body_is_skipped():
    if not HAVE_Z3:
        return
    _skipped("""
function count(n: Int) returns Int
  ensures result >= 0
  effects pure
do
  var i = 0
  while i < n do
    i = i + 1
  end
  return i
end
""")


SHADOW = """
function bump(x: Int) returns Int
  ensures {clause}
  effects pure
do
  let x = x + 1
  return x
end
"""


def test_ensures_sees_locals_at_return_and_old_sees_entry():
    # The emitted ensures check runs in the function's scope at the
    # return, so `x` is the rebound local; old(x) is the entry value.
    if not HAVE_Z3:
        return
    _proved(SHADOW.format(clause="result == old(x) + 1"))
    _proved(SHADOW.format(clause="result == x"))
    _refuted_and_replayed(SHADOW.format(clause="result == old(x)"), "bump")


RET_REFINED = """
type Percentage = Int where self >= 0 and self <= 100

function clip(x: Int) returns Percentage
  ensures {clause}
  effects pure
do
  return x
end
"""


def test_return_refinement_is_a_path_condition():
    # The runtime checks the return refinement before the ensures, so
    # a normal return already satisfies it.
    if not HAVE_Z3:
        return
    _proved(RET_REFINED.format(clause="result <= 100"))
    cx = _refuted_and_replayed(RET_REFINED.format(clause="result <= 50"), "clip")
    assert 50 < int(cx["x"]) <= 100, cx


CONSTS = """
type Tokens = Int where self >= 0 and self <= 100
const CAPACITY: Int = 100
const PER_TICK: Int = 10

function refill(tokens: Tokens, ticks: Int) returns Tokens
  requires ticks >= 0
  ensures {clause}
  effects pure
do
  return min(CAPACITY, tokens + ticks * PER_TICK)
end
"""


def test_consts_and_stdlib_min():
    if not HAVE_Z3:
        return
    _proved(CONSTS.format(clause="result >= tokens"))
    _refuted_and_replayed(CONSTS.format(clause="result > tokens"), "refill")


ALIAS = """
type Percentage = Int where self >= 0 and self <= 100
type Pct = Percentage
type Small = Pct where self < 10

function keep(p: {ty}) returns Int
  ensures result >= 0
  effects pure
do
  return p
end
"""


def test_unrefined_alias_predicates_are_not_assumed():
    # Regression (found 2026-10-02, pre-existing): the runtime checks a
    # type only if it has its own `where`, and re-checks a base only if
    # the base is refined. `Pct` is never checked, so keep(-5) returns
    # -5; the prover used to assume Percentage's predicate and PROVE
    # result >= 0. Now: refuted, and the counterexample really fails.
    if not HAVE_Z3:
        return
    _proved(ALIAS.format(ty="Percentage"))
    for ty in ("Pct", "Small"):
        cx = _refuted_and_replayed(ALIAS.format(ty=ty), "keep")
        assert int(cx["p"]) < 0, (ty, cx)


def test_untranslatable_piece_in_body_skips():
    # A string, a list, a bitwise operator: outside the fragment.
    if not HAVE_Z3:
        return
    for body in ('return length("ab")', "return x band 1",
                 "let xs = [1, 2]\n  return x"):
        _skipped(f"""
function f(x: Int) returns Int
  ensures result >= 0
  effects pure
do
  {body}
end
""")


def main() -> int:
    if not HAVE_Z3:
        print("SKIP: z3-solver not installed; SMT pass tests skipped")
        return 0
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"ok {name}")
    print(f"OK: {len(tests)} SMT tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
