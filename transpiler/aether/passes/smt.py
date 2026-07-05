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


def _is_int(e) -> bool:
    return isinstance(e, z3.ArithRef) and e.is_int()


def _is_bool(e) -> bool:
    return isinstance(e, z3.BoolRef)


def translate_expr(expr: Dict[str, Any], env: Dict[str, Any]):
    """Aether expr AST -> z3 expression, or None when outside the fragment.

    `env` maps identifier names to z3 variables. Unknown identifiers,
    unsupported node kinds, unsupported operators, and sort mismatches
    (e.g. Int + Bool) all return None. Sorts are checked explicitly:
    z3py would otherwise silently coerce Bool to Int in arithmetic
    (x + b -> x + If(b, 1, 0)), which is not Aether semantics.
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
                return z3.Not(v) if _is_bool(v) else None
            if expr["op"] == "neg":
                return -v if _is_int(v) else None
            return None
        if k == "BinOp":
            left = translate_expr(expr["left"], env)
            right = translate_expr(expr["right"], env)
            if left is None or right is None:
                return None
            op = expr["op"]
            if op in ("+", "-", "*", "<", "<=", ">", ">="):
                if not (_is_int(left) and _is_int(right)):
                    return None
                if op == "+":
                    return left + right
                if op == "-":
                    return left - right
                if op == "*":
                    return left * right
                if op == "<":
                    return left < right
                if op == "<=":
                    return left <= right
                if op == ">":
                    return left > right
                return left >= right
            if op in ("==", "!="):
                same_sort = ((_is_int(left) and _is_int(right))
                             or (_is_bool(left) and _is_bool(right)))
                if not same_sort:
                    return None
                return left == right if op == "==" else left != right
            if op in ("and", "or", "implies"):
                if not (_is_bool(left) and _is_bool(right)):
                    return None
                if op == "and":
                    return z3.And(left, right)
                if op == "or":
                    return z3.Or(left, right)
                return z3.Implies(left, right)
            return None
        return None
    except (TypeError, z3.Z3Exception):
        # belt-and-braces: anything the guards missed is outside the fragment
        return None
