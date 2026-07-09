# SMT Contract-Proving Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the opt-in SMT contract-proving pass (`aether check --prove`) that discharges or refutes `ensures` clauses with Z3, plumbing counterexamples into diagnostics (v2 roadmap §1.1 + §1.3).

**Architecture:** A new pass module `transpiler/aether/passes/smt.py` translates a restricted fragment of Aether expressions (Int/Bool arithmetic and logic) into Z3 terms, builds one proof obligation per `ensures` clause (assume `requires` clauses + param refinement predicates, equate `result` with the body's single return expression, negate the goal), and returns `Diagnostic` objects: E0901 (refuted, with counterexample model in `extra`) and E0902 (solver timeout/unknown, warning). The CLI gains an opt-in `--prove` flag on `aether check`.

**Tech Stack:** Python (stdlib-only core), `z3-solver` as an optional `[smt]` extra, existing dict-based AST from `aether.parser`, existing `Diagnostic`/`Position` dataclasses.

## Global Constraints

- Core install stays **zero-dependency**: `dependencies = []` in `pyproject.toml` must not change. Z3 ships only as optional extra `smt = ["z3-solver >= 4.12"]`.
- `smt.py` must import-guard z3 (`try: import z3 ... except ImportError`); importing the module without z3 installed must not raise.
- All tests (including the new suite) must pass **both with and without** z3 installed. Without z3 the new suite prints a SKIP line and exits 0.
- `--prove` is **opt-in** (default off) — the opposite polarity of the existing default-on `--no-*` flags. This matches roadmap §1.1 ("default-off in v0.3").
- Diagnostic codes are exactly **E0901** (refuted ensures) and **E0902** (solver timeout/unknown), category `contract` — these are reserved in `grammar/diagnostics.md` (currently lines 218–219). Note: roadmap §1.1 says "E0507-class"; that is stale — the catalog reservation wins.
- Per-obligation timeout default **5000 ms** (`--prove-timeout-ms`), per roadmap §1.1.
- `tests/test_diagnostic_catalog.py` greps every `code="EXXXX"` in `transpiler/` and asserts it appears in `grammar/diagnostics.md` — the catalog rows MUST land in the same task/commit as the code that emits E0901/E0902, or the suite goes red.
- Test files are standalone scripts: `python -B tests/test_smt.py` must exit 0 (this is how `scripts/run_all.py` invokes gates). Also keep them pytest-collectable (`test_*` functions).
- Python >= 3.10 syntax only.
- Docs style: no emojis, no marketing-speak; surface every scope reduction explicitly (handoff.md §2 discipline).

## Scope Reductions (surface at the gate — do not hide)

The v1 provable fragment is deliberately narrow. Everything outside it is counted `skipped` (no diagnostic, runtime checks remain in force):

1. **Types:** only `Int`, `Bool` params/returns, plus user `type X = Int where ...` refinement chains that bottom out at Int/Bool. No String, Float, List, records, unions, generics.
2. **Bodies:** only functions whose body is exactly one `return <expr>` statement. No let/if/while/match bodies (no weakest-precondition engine in v1).
3. **Expressions:** `+ - * == != < <= > >= and or implies not neg`, literals, identifiers, `old(e)` (translated as `e` — sound because the accepted fragment has no mutation between entry and return). **`/` and `%` are excluded on purpose**: Z3 Int division semantics differ from the runtime's for negative operands; a wrong proof is worse than no proof.
4. **Soundness rule:** a function is only analyzed if *every assumption* (each `requires` clause, each param refinement predicate) translates. Dropping an untranslatable assumption would manufacture spurious counterexamples, so the whole function is skipped instead.
5. Roadmap §1.2 (compile-time discharge downgrading `_ae_check_refinement` runtime checks to no-ops) and `--explain-proofs` are **not in this plan** — deferred; the summary line (`prove: N proved, ...`) is the v1 answer to "what got discharged".

## File Structure

- **Create** `transpiler/aether/passes/smt.py` — the entire pass: z3 import guard, type-sort resolution, expression translator, obligation builder/prover. One file, one responsibility, mirrors sibling passes (`capability.py`, `effects.py`).
- **Create** `tests/test_smt.py` — pass-level tests (direct `check_contracts_smt` calls) + two CLI integration tests. Standalone-runnable.
- **Modify** `pyproject.toml` — add `smt` optional extra; add z3 to `dev` extra.
- **Modify** `transpiler/aether/cli.py` — `_run_smt_check` helper, `--prove` / `--prove-timeout-ms` args on the `check` subparser, hook in `cmd_check`.
- **Modify** `grammar/diagnostics.md` — replace the two "reserved" rows with real E0901/E0902 documentation.
- **Modify** `scripts/run_all.py` — add a `tests/test_smt.py` gate line (copy the existing per-suite block pattern).
- **Modify** `yc/v2_ROADMAP.md` §1.1 — status note: `--prove` shipped opt-in; correct the stale "B.5 already ships a Z3 bridge" and "E0507-class" claims.

## AST facts the implementer needs (verified against the current parser)

The AST is plain dicts. From `transpiler/aether/parser.py`:

- `FunctionDecl`: `{"kind": "FunctionDecl", "name": str, "generics": [...], "params": [{"name": str, "type": <type-expr>}], "return_type": <type-expr>, "requires": [<expr>], "ensures": [<expr>], "effects": [...], "body": [<stmt>], "pos": {"line": int, "column": int}}`
- `TypeDecl`: `{"kind": "TypeDecl", "name": str, "base": <type-expr>, "refinement": <expr>|None, "pos": ...}` — refinement predicate refers to the value as `self` (parsed as `{"kind": "Ident", "name": "self"}`).
- Type exprs: `{"kind": "TypeName", "name": str}` | `{"kind": "GenericType", ...}` | `{"kind": "FunctionType", ...}`.
- Exprs: `{"kind": "IntLit", "value": ...}`, `{"kind": "FloatLit", ...}`, `{"kind": "BoolLit", "value": bool}`, `{"kind": "StringLit", ...}`, `{"kind": "NullLit"}`, `{"kind": "Ident", "name": str}` (the `result` keyword parses to `Ident` named `"result"`, `self` to `"self"`), `{"kind": "BinOp", "op": str, "left": ..., "right": ...}` (ops: `or and implies == != < <= > >= is in + - * / %`), `{"kind": "UnaryOp", "op": "not"|"neg", "value": ...}`, `{"kind": "Call", "func": ..., "args": [...]}`, `{"kind": "Field", ...}`, `{"kind": "Index", ...}`, `{"kind": "Old", "value": <expr>}`.
- Return stmt: `{"kind": "Return", "value": <expr>|None, "pos": ...}`.
- Every function MUST declare `effects` (use `effects pure` in all test fixtures).
- `Diagnostic` (from `transpiler/aether/diagnostics.py`): fields `code, category, severity, message, position (Position(line, column)), suggestion, confidence, extra (dict)`.

---

### Task 1: Packaging extra + expression translator

**Files:**
- Modify: `pyproject.toml` (the `[project.optional-dependencies]` table, currently lines 37–39)
- Create: `transpiler/aether/passes/smt.py`
- Create: `tests/test_smt.py`

**Interfaces:**
- Produces: `translate_expr(expr: dict, env: dict) -> z3 expr | None` (None = outside fragment), `_resolve_param_sort(type_expr: dict, type_decls: dict, _seen=None) -> tuple[str, list] | None` (returns `("int"|"bool", [refinement expr ASTs])`), `_mk_var(name: str, sort: str) -> z3 var`, module constant `HAVE_Z3: bool`. Task 2 builds `check_contracts_smt` on top of these in the same file.

- [ ] **Step 1: Add the packaging extras**

In `pyproject.toml`, change:

```toml
[project.optional-dependencies]
llm = ["anthropic >= 0.34.0"]
dev = ["pytest >= 7.0"]
```

to:

```toml
[project.optional-dependencies]
llm = ["anthropic >= 0.34.0"]
smt = ["z3-solver >= 4.12"]
dev = ["pytest >= 7.0", "z3-solver >= 4.12"]
```

- [ ] **Step 2: Install z3 locally so the tests can run**

Run: `pip install "z3-solver>=4.12"`
Expected: successful install (verify with `python -c "import z3; print(z3.get_version_string())"`).

- [ ] **Step 3: Write the failing translator tests**

Create `tests/test_smt.py`:

```python
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

if HAVE_Z3:
    from aether.passes.smt import translate_expr, _resolve_param_sort, _mk_var  # noqa: E402


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
  requires x / 2 == 0
  requires x % 2 == 0
  requires s == "hi"
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -B tests/test_smt.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'aether.passes.smt'` (raised from the `if HAVE_Z3:` import block).

- [ ] **Step 5: Write the translator module**

Create `transpiler/aether/passes/smt.py`:

```python
"""SMT-backed contract checking (opt-in via `aether check --prove`).

v2 roadmap section 1.1 + 1.3. For every FunctionDecl that declares at
least one `ensures` clause, build one proof obligation per clause:

    assumptions = translated `requires` clauses
                + translated param-refinement predicates (`where` clauses
                  on the params' type declarations, `self` bound to the
                  param variable)
    obligation  = assumptions AND result == <body expr> AND NOT ensures

and ask Z3 for satisfiability:

    unsat   -> PROVED   (no diagnostic; the clause cannot be violated)
    sat     -> REFUTED  (E0901, model plumbed into extra.counterexample)
    unknown -> TIMEOUT  (E0902, severity=warning; runtime check remains)

Soundness rule: a function is only analyzed when EVERY assumption
translates. Dropping an untranslatable assumption would manufacture
spurious counterexamples, so such functions are counted "skipped".
An untranslatable `ensures` clause skips just that clause.

v1 provable fragment (everything else -> skipped, no diagnostic):
  - types: Int, Bool, and user TypeDecl refinement chains that bottom
    out at Int/Bool (their `where` predicates become assumptions)
  - bodies: exactly one `return <expr>` statement
  - exprs: Int/Bool literals, identifiers, not/neg,
    + - * == != < <= > >= and or implies, old(e) -> e (sound: the
    accepted fragment has no mutation between entry and return)
  - `/` and `%` are deliberately excluded: Z3's Int division semantics
    differ from the runtime's for negative operands; a wrong proof is
    worse than no proof.

The z3 import is guarded: importing this module without z3-solver
installed is safe (HAVE_Z3 is False and the CLI surfaces an install
hint). Core stays stdlib-only; z3 ships as the `[smt]` extra.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from ..diagnostics import Diagnostic, Position

try:
    import z3
    HAVE_Z3 = True
except ImportError:  # pragma: no cover — exercised on z3-less installs
    z3 = None
    HAVE_Z3 = False


def _resolve_param_sort(type_expr: Dict[str, Any],
                        type_decls: Dict[str, Dict[str, Any]],
                        _seen: Optional[set] = None
                        ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
    """Resolve a type expression to ("int"|"bool", [refinement expr ASTs]).

    Follows TypeDecl alias chains (type Half = Percentage where ...),
    accumulating every `where` predicate on the way down. Returns None
    when the type is outside the provable fragment.
    """
    if _seen is None:
        _seen = set()
    if type_expr.get("kind") != "TypeName":
        return None
    name = type_expr["name"]
    if name == "Int":
        return ("int", [])
    if name == "Bool":
        return ("bool", [])
    if name in _seen:
        return None  # cyclic alias — be safe
    decl = type_decls.get(name)
    if decl is None:
        return None
    _seen.add(name)
    base = _resolve_param_sort(decl["base"], type_decls, _seen)
    if base is None:
        return None
    sort, preds = base
    if decl.get("refinement") is not None:
        preds = preds + [decl["refinement"]]
    return (sort, preds)


def _mk_var(name: str, sort: str):
    return z3.Int(name) if sort == "int" else z3.Bool(name)


def translate_expr(expr: Dict[str, Any], env: Dict[str, Any]):
    """Aether expr AST -> z3 expression, or None when outside the fragment.

    `env` maps identifier names to z3 variables. Unknown identifiers,
    unsupported node kinds, unsupported operators, and sort mismatches
    (e.g. Int + Bool) all return None.
    """
    k = expr.get("kind")
    try:
        if k == "IntLit":
            return z3.IntVal(int(expr["value"]))
        if k == "BoolLit":
            return z3.BoolVal(bool(expr["value"]))
        if k == "Ident":
            return env.get(expr["name"])
        if k == "Old":
            return translate_expr(expr["value"], env)
        if k == "UnaryOp":
            v = translate_expr(expr["value"], env)
            if v is None:
                return None
            if expr["op"] == "not":
                return z3.Not(v)
            if expr["op"] == "neg":
                return -v
            return None
        if k == "BinOp":
            left = translate_expr(expr["left"], env)
            right = translate_expr(expr["right"], env)
            if left is None or right is None:
                return None
            op = expr["op"]
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "and":
                return z3.And(left, right)
            if op == "or":
                return z3.Or(left, right)
            if op == "implies":
                return z3.Implies(left, right)
            return None
        return None
    except (TypeError, z3.Z3Exception):
        # sort mismatch — outside the fragment
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -B tests/test_smt.py`
Expected: PASS — `ok test_...` lines, ending `OK: 5 SMT tests`, exit 0.

- [ ] **Step 7: Verify the z3-less path**

Run: `python -c "import sys; sys.modules['z3'] = None; import importlib" ` is NOT a reliable simulation — instead verify the guard statically: run

`python -c "import ast, sys; tree = ast.parse(open('transpiler/aether/passes/smt.py').read()); print('guarded')"`

and confirm by inspection that the only `import z3` sits inside the try/except. Then run the full existing suite to confirm nothing regressed: `python -B tests/test_regressions.py`
Expected: same result as before this task (green).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml transpiler/aether/passes/smt.py tests/test_smt.py
git commit -m "feat: SMT expression translator + optional [smt] extra (v2 roadmap 1.1)"
```

---

### Task 2: Obligation builder / prover with E0901 + E0902 and catalog rows

**Files:**
- Modify: `transpiler/aether/passes/smt.py` (append after `translate_expr`)
- Modify: `tests/test_smt.py` (append tests)
- Modify: `grammar/diagnostics.md` (the reserved-codes table near the bottom, rows currently at lines 218–219)

**Interfaces:**
- Consumes: `translate_expr`, `_resolve_param_sort`, `_mk_var`, `HAVE_Z3` from Task 1.
- Produces: `check_contracts_smt(ast: dict, timeout_ms: int = 5000) -> tuple[list[Diagnostic], dict]` where the dict is `{"proved": int, "refuted": int, "timeout": int, "skipped": int}` (clause-level counts). Task 3's CLI helper calls exactly this.

- [ ] **Step 1: Write the failing prover tests**

Append to `tests/test_smt.py` (before `main()`; also extend the `if HAVE_Z3:` import to `from aether.passes.smt import translate_expr, _resolve_param_sort, _mk_var, check_contracts_smt`):

```python
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


def test_call_body_is_skipped_not_guessed():
    if not HAVE_Z3:
        return
    diags, summary = check_contracts_smt(parse(VIA_CALL, "<smt>"))
    assert diags == []
    assert summary == {"proved": 0, "refuted": 0, "timeout": 0, "skipped": 1}


def test_untranslatable_requires_skips_whole_function():
    # Soundness: without the isFine(x) assumption, x = -1 would "refute"
    # the ensures. The pass must skip, not fabricate a counterexample.
    if not HAVE_Z3:
        return
    diags, summary = check_contracts_smt(parse(UNSOUND_ASSUMPTION, "<smt>"))
    assert diags == []
    assert summary == {"proved": 0, "refuted": 0, "timeout": 0, "skipped": 1}
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -B tests/test_smt.py`
Expected: FAIL with `ImportError: cannot import name 'check_contracts_smt'`.

- [ ] **Step 3: Implement the prover**

Append to `transpiler/aether/passes/smt.py`:

```python
def check_contracts_smt(ast: Dict[str, Any], timeout_ms: int = 5000
                        ) -> Tuple[List[Diagnostic], Dict[str, int]]:
    """Prove every `ensures` clause the fragment admits.

    Returns (diagnostics, summary). The summary counts CLAUSES:
    {"proved", "refuted", "timeout", "skipped"}. Refuted clauses emit
    E0901 (error, counterexample in extra); solver-unknown clauses emit
    E0902 (warning). Skipped clauses emit nothing — their runtime
    checks remain in force.
    """
    assert HAVE_Z3, "check_contracts_smt requires z3-solver"
    diags: List[Diagnostic] = []
    summary = {"proved": 0, "refuted": 0, "timeout": 0, "skipped": 0}
    type_decls = {d["name"]: d for d in ast["decls"]
                  if d.get("kind") == "TypeDecl"}

    for d in ast["decls"]:
        if d.get("kind") != "FunctionDecl" or not d.get("ensures"):
            continue
        pos = d.get("pos") or {"line": 1, "column": 1}
        position = Position(line=pos["line"], column=pos["column"])
        n_clauses = len(d["ensures"])

        # 1. Param environment + refinement-predicate assumptions.
        env: Dict[str, Any] = {}
        assumptions: List[Any] = []
        translatable = True
        for p in d["params"]:
            resolved = _resolve_param_sort(p["type"], type_decls)
            if resolved is None:
                translatable = False
                break
            sort, preds = resolved
            var = _mk_var(p["name"], sort)
            env[p["name"]] = var
            for pred in preds:
                zpred = translate_expr(pred, {"self": var})
                if zpred is None:
                    translatable = False
                    break
                assumptions.append(zpred)
            if not translatable:
                break

        # 2. `requires` clauses. Soundness rule: every assumption must
        # translate, or any counterexample could be spurious.
        if translatable:
            for clause in d["requires"]:
                zclause = translate_expr(clause, env)
                if zclause is None:
                    translatable = False
                    break
                assumptions.append(zclause)

        # 3. Result variable + body equation (single-Return bodies only).
        body = d.get("body") or []
        body_eq = None
        result_var = None
        if translatable:
            ret = _resolve_param_sort(d["return_type"], type_decls)
            if (ret is None or len(body) != 1
                    or body[0].get("kind") != "Return"
                    or body[0].get("value") is None):
                translatable = False
            else:
                result_var = _mk_var("_ae_smt_result", ret[0])
                body_z = translate_expr(body[0]["value"], env)
                if body_z is None:
                    translatable = False
                else:
                    try:
                        body_eq = (result_var == body_z)
                    except (TypeError, z3.Z3Exception):
                        translatable = False

        if not translatable:
            summary["skipped"] += n_clauses
            continue

        env_with_result = dict(env)
        env_with_result["result"] = result_var

        # 4. One obligation per ensures clause.
        for idx, clause in enumerate(d["ensures"]):
            goal = translate_expr(clause, env_with_result)
            if goal is None:
                summary["skipped"] += 1
                continue
            solver = z3.Solver()
            solver.set("timeout", timeout_ms)
            solver.add(*assumptions)
            solver.add(body_eq)
            solver.add(z3.Not(goal))
            res = solver.check()
            if res == z3.unsat:
                summary["proved"] += 1
            elif res == z3.sat:
                summary["refuted"] += 1
                model = solver.model()
                counterexample = {
                    name: str(model.eval(var, model_completion=True))
                    for name, var in env.items()
                }
                counterexample["result"] = str(
                    model.eval(result_var, model_completion=True))
                diags.append(Diagnostic(
                    code="E0901", category="contract", severity="error",
                    message=(f"ensures clause #{idx + 1} of function "
                             f"{d['name']!r} is refutable: the SMT solver "
                             f"found inputs that satisfy every requires "
                             f"clause but violate this postcondition"),
                    position=position,
                    suggestion=("strengthen the requires clauses or fix the "
                                "implementation; concrete violating inputs "
                                "are in extra.counterexample"),
                    confidence=1.0,
                    extra={"function": d["name"],
                           "clause_kind": "ensures",
                           "clause_index": idx,
                           "counterexample": counterexample},
                ))
            else:  # z3.unknown — timeout or incomplete theory
                summary["timeout"] += 1
                diags.append(Diagnostic(
                    code="E0902", category="contract", severity="warning",
                    message=(f"SMT solver returned 'unknown' for ensures "
                             f"clause #{idx + 1} of function {d['name']!r} "
                             f"(timeout {timeout_ms} ms); the clause keeps "
                             f"its runtime check"),
                    position=position,
                    suggestion=("raise --prove-timeout-ms or simplify the "
                                "clause"),
                    confidence=0.5,
                    extra={"function": d["name"],
                           "clause_kind": "ensures",
                           "clause_index": idx,
                           "timeout_ms": timeout_ms},
                ))
    return diags, summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B tests/test_smt.py`
Expected: PASS — `OK: 10 SMT tests`, exit 0.

- [ ] **Step 5: Document E0901/E0902 in the catalog (same commit — the catalog suite enforces this)**

First `Read` the bottom of `grammar/diagnostics.md` to see the reserved-codes table's exact formatting (the rows are at ~lines 218–219). Replace these two rows:

```
| E0901 | reserved for SMT-discharged contract failure |
| E0902 | reserved for SMT solver timeout |
```

with rows marking them as now-live (match the table's column count exactly — if the reserved table is 2-column, keep 2 columns and add prose below the table instead):

```
| **E0901** | SMT-refuted `ensures` clause (opt-in `--prove` pass) |
| **E0902** | SMT solver timeout/unknown on a proof obligation (opt-in `--prove` pass) |
```

Then append this prose section after that table:

```markdown
## SMT contract proving — E09xx (opt-in, `aether check --prove`)

E0901 (error, category `contract`): the solver found concrete inputs that
satisfy every `requires` clause and every param refinement predicate but
violate an `ensures` clause. `extra` carries `function`, `clause_kind`
(`"ensures"`), `clause_index` (0-based), and `counterexample` — a map of
param names (plus `result`) to the violating values, so a fix-loop can
re-prompt with them.

E0902 (warning, category `contract`): the solver returned `unknown`
(usually the per-obligation timeout, default 5000 ms, `--prove-timeout-ms`).
The clause keeps its runtime check; nothing is silently trusted. `extra`
carries `function`, `clause_kind`, `clause_index`, `timeout_ms`.

The pass only analyzes a restricted fragment (Int/Bool params, single-
`return` bodies, linear arithmetic without `/` and `%`); everything else
is counted `skipped` in the `prove:` summary and keeps runtime checks.
A function whose `requires` clauses or param refinements do not translate
is skipped entirely — dropping an assumption would fabricate spurious
counterexamples.
```

- [ ] **Step 6: Run the catalog gate + full smt suite**

Run: `python -B tests/test_diagnostic_catalog.py && python -B tests/test_smt.py`
Expected: both PASS (the catalog test greps E0901/E0902 out of `smt.py` and finds them documented).

- [ ] **Step 7: Commit**

```bash
git add transpiler/aether/passes/smt.py tests/test_smt.py grammar/diagnostics.md
git commit -m "feat: SMT prover — E0901 refuted ensures with counterexample, E0902 timeout"
```

---

### Task 3: CLI `--prove` flag, run_all gate, roadmap correction

**Files:**
- Modify: `transpiler/aether/cli.py` (helper near `_run_module_check` ~line 180; hook in `cmd_check` after the module check ~line 233; args on the `check` subparser ~line 446)
- Modify: `tests/test_smt.py` (append CLI integration tests)
- Modify: `scripts/run_all.py` (append a gate block after the `multi_file` block ~line 172)
- Modify: `yc/v2_ROADMAP.md` (§1.1)

**Interfaces:**
- Consumes: `check_contracts_smt(ast, timeout_ms) -> (List[Diagnostic], dict)` and `HAVE_Z3` from Task 2; existing `_emit_error(diag, as_json)` in cli.py.
- Produces: `aether check FILE --prove [--prove-timeout-ms N]`. Exit 2 on any E0901; exit 0 otherwise. Non-JSON prints `prove: N proved, M refuted, T timeout, K skipped`; JSON success dump gains a `"prove"` key with that summary dict.

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_smt.py` (before `main()`):

```python
def _run_cli(src: str, *flags: str):
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "prog.aeth")
        with open(path, "w") as f:
            f.write(src)
        return subprocess.run(
            [sys.executable, "-B", "-m", "transpiler.aether.cli",
             "check", path, *flags],
            cwd=ROOT, capture_output=True, text=True)


def test_cli_prove_refuted_exits_2():
    if not HAVE_Z3:
        return
    r = _run_cli(REFUTABLE, "--prove", "--json")
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert '"E0901"' in r.stdout
    assert "counterexample" in r.stdout


def test_cli_prove_proved_exits_0_with_summary():
    if not HAVE_Z3:
        return
    r = _run_cli(PROVABLE, "--prove", "--json")
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    data = json.loads(r.stdout.strip().splitlines()[-1])
    assert data["ok"] is True
    assert data["prove"]["proved"] == 2
    assert data["prove"]["refuted"] == 0


def test_cli_without_prove_flag_ignores_contracts():
    if not HAVE_Z3:
        return
    r = _run_cli(REFUTABLE)          # no --prove: stays opt-in
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "E0901" not in r.stdout
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -B tests/test_smt.py`
Expected: FAIL — the `--prove` runs exit 2 with `unrecognized arguments: --prove` in stderr (argparse), so the first CLI assert trips with the wrong reason visible in the tuple.

- [ ] **Step 3: Implement the CLI wiring**

In `transpiler/aether/cli.py`, add after `_run_module_check` (~line 188):

```python
def _run_smt_check(ast, as_json, timeout_ms):
    """Opt-in SMT contract proving (--prove, v2 roadmap 1.1).
    Returns (rc, summary|None). rc 2 iff any clause was refuted."""
    from .passes.smt import HAVE_Z3, check_contracts_smt
    if not HAVE_Z3:
        msg = ("--prove requires the z3-solver package "
               "(pip install 'aether-lang[smt]')")
        if as_json:
            json.dump({"ok": False, "error": msg}, sys.stdout)
            sys.stdout.write("\n")
        else:
            print(f"aether: {msg}", file=sys.stderr)
        return 2, None
    diags, summary = check_contracts_smt(ast, timeout_ms=timeout_ms)
    for d in diags:
        _emit_error(d, as_json)
    if not as_json:
        print("prove: {proved} proved, {refuted} refuted, "
              "{timeout} timeout, {skipped} skipped".format(**summary))
    rc = 2 if any(d.severity == "error" for d in diags) else 0
    return rc, summary
```

In `cmd_check`, insert between the module-check block (ends ~line 236) and the final `if args.json:` success dump:

```python
    # Opt-in SMT contract proving (v2 roadmap 1.1). Off by default;
    # enable with --prove. E0901 refutations fail the check; E0902
    # timeouts warn and pass.
    prove_summary = None
    if getattr(args, "prove", False):
        rc, prove_summary = _run_smt_check(
            ast, args.json, getattr(args, "prove_timeout_ms", 5000))
        if rc != 0:
            return rc
```

and change the success dump from:

```python
    if args.json:
        json.dump({"ok": True, "decls": len(ast["decls"])}, sys.stdout)
        sys.stdout.write("\n")
```

to:

```python
    if args.json:
        out = {"ok": True, "decls": len(ast["decls"])}
        if prove_summary is not None:
            out["prove"] = prove_summary
        json.dump(out, sys.stdout)
        sys.stdout.write("\n")
```

In the `check` subparser block (after the `--no-import-resolution` argument ~line 446), add:

```python
    sp.add_argument("--prove", action="store_true",
                    help="run the opt-in SMT contract-proving pass "
                         "(requires z3-solver: pip install 'aether-lang[smt]')")
    sp.add_argument("--prove-timeout-ms", type=int, default=5000,
                    help="per-obligation Z3 timeout in ms (default 5000)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B tests/test_smt.py`
Expected: PASS — `OK: 13 SMT tests`, exit 0.

- [ ] **Step 5: Add the run_all gate line**

In `scripts/run_all.py`, after the `multi_file` block (ends ~line 172), add (same shape as its neighbors):

```python
    smt_t = os.path.join(ROOT, "tests", "test_smt.py")
    if os.path.isfile(smt_t):
        cmd = [sys.executable, "-B", smt_t]
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        results["smt"] = {
            "ok": r.returncode == 0,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
        }
```

Before editing, `Read` the end of `scripts/run_all.py` to confirm how `results` entries feed the final ok/exit aggregation, and mirror whatever the `multi_file` entry does (if suites are also listed in an explicit summary/exit list, add `"smt"` there too).

- [ ] **Step 6: Correct the roadmap**

In `yc/v2_ROADMAP.md` §1.1, `Read` the section first, then update it to state honestly:
- The Z3 bridge did **not** previously exist in the repo (the "B.5 substrate already ships a Z3 bridge" sentence was wrong); it was created on 2026-07-06 as `transpiler/aether/passes/smt.py`.
- `--prove` + `--prove-timeout-ms` (default 5000 ms) are now shipped, opt-in, on `aether check`.
- The timeout diagnostic is **E0902** (not "E0507-class") and refutations are **E0901**, both per the `grammar/diagnostics.md` catalog; counterexamples are plumbed into `extra.counterexample` (this delivers §1.3 for the supported fragment).
- The `[smt]` extra now actually exists in `pyproject.toml` (the "already wired" claim was also stale).
- Remaining deferred: §1.2 compile-time discharge of refinement runtime checks, `--explain-proofs`, and everything outside the v1 fragment (see the "Scope Reductions" list in `docs/superpowers/plans/2026-07-06-smt-contract-pass.md`).

- [ ] **Step 7: Run the full gate suite**

Run: `python -B scripts/run_all.py`
Expected: exit 0, output includes an `"smt"` entry with `"ok": true`. If any pre-existing suite was already red before this plan started, report it — do not fix unrelated breakage silently.

- [ ] **Step 8: Commit**

```bash
git add transpiler/aether/cli.py tests/test_smt.py scripts/run_all.py yc/v2_ROADMAP.md
git commit -m "feat: opt-in 'aether check --prove' SMT pass + run_all gate; correct roadmap 1.1"
```
