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
