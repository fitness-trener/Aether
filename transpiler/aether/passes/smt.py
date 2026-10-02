"""SMT-backed contract checking (default-on with z3; `--prove` forces it).

v2 roadmap section 1.1 + 1.3. For every FunctionDecl that declares at
least one `ensures` clause, the body is executed symbolically into its
RETURN PATHS. Each path is (condition, returned value, locals at the
return). A path's condition holds exactly when the function reaches that
`return` without raising: it carries the param-refinement predicates and
the `requires` clauses (the runtime asserts both on entry), the branch
conditions, and the DEFINEDNESS of every partial operation on the way
(a non-zero divisor, a short-circuited operand, an inlined callee's own
requires). One obligation per clause:

    exists path:  cond AND result == value AND NOT (clause defined AND clause)

    unsat   -> PROVED   (no normal return can violate the clause)
    sat     -> REFUTED  (E0901, model plumbed into extra.counterexample)
    unknown -> TIMEOUT  (E0902, severity=warning; runtime check remains)

Paths that raise (division by zero, a failed refinement or requires) are
not returns, so they cannot violate a postcondition and are excluded.

Provable fragment (everything else -> skipped, no diagnostic):
  - types: Int, Bool, and user TypeDecl refinement chains that bottom
    out at Int/Bool (their `where` predicates become path conditions)
  - statements: `let`/`var`/assignment (SSA substitution), `if`/`elif`/
    `else` (path split, capped at _MAX_PATHS), `return <expr>`. A body
    that can fall off its end, a loop, a `match` or an expression
    statement skips the function.
  - exprs: Int/Bool literals, identifiers, not/neg, + - * / %,
    == != < <= > >=, and/or/implies (short-circuit definedness), `if`
    expressions, old(e) (the parameters' entry values), calls to
    abs/min/max on Int, and calls to user functions (below).
  - `/` and `%` are FLOOR division/remainder (grammar/types.md,
    BUG-103), encoded through z3's Euclidean div/mod on a positive
    divisor: a / b = (-a) div (-b) when b < 0. A zero divisor is a
    definedness condition, never an assumption.
  - a call to a user function is INLINED when its body is in the
    fragment (recursion and depth > _MAX_INLINE_DEPTH excepted). Any
    other call to a user function with an Int/Bool return is ABSTRACTED
    as a fresh value constrained only by its return-type refinement.

Exactness rule (the soundness bar: a wrong proof or a spurious
counterexample is worse than none). Weakening the premises keeps an
`unsat` a proof, so an untranslatable `requires`/refinement may be
DROPPED and a call may be ABSTRACTED. But such a run is inexact: a
model may not be a real execution. Inexact runs report only PROVED; a
sat or unknown result is counted "skipped" (records reason
"inconclusive"), never E0901. Exact runs model every runtime check and
operation on the path, so their counterexamples are real inputs.

Proofs are relative to the declared parameter types (an Int param holds
a Python int): there is no static type checker (vault q8), and calls
reach a function only through checked code.

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

# ponytail: fixed caps, not knobs; raise them if a real port hits one.
_MAX_PATHS = 64
_MAX_INLINE_DEPTH = 8


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
    if not isinstance(type_expr, dict) or type_expr.get("kind") != "TypeName":
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
    if decl.get("refinement") is None:
        # The runtime checks only types with their own `where` (emitter
        # ctx.refinements), and a refined type re-checks its base only
        # when that base is refined itself: `type Pct = Percentage` is
        # never checked, so its predicates must not be assumed.
        return (sort, [])
    return (sort, preds + [decl["refinement"]])


def _mk_var(name: str, sort: str):
    return z3.Int(name) if sort == "int" else z3.Bool(name)


def _is_int(e) -> bool:
    return isinstance(e, z3.ArithRef) and e.is_int()


def _is_bool(e) -> bool:
    return isinstance(e, z3.BoolRef)


def _sort_of(e) -> Optional[str]:
    return "int" if _is_int(e) else "bool" if _is_bool(e) else None


def _all(conds):
    return z3.And(*conds) if conds else z3.BoolVal(True)


def floor_div(a, b):
    """Python `a // b` for b != 0 (z3 div is Euclidean: they agree for
    b > 0; for b < 0, floor(a/b) == floor(-a/-b))."""
    return z3.If(b > 0, a / b, (-a) / (-b))


def floor_mod(a, b):
    """Python `a % b` for b != 0: the remainder takes the divisor's sign."""
    return z3.If(b > 0, a % b, -((-a) % (-b)))


class _Skip(Exception):
    """The construct is outside the provable fragment."""


class _Translator:
    """Symbolic executor over the fragment. `inexact` is set the moment
    anything is dropped or abstracted (see the module docstring)."""

    def __init__(self, fns: Dict[str, Dict[str, Any]],
                 type_decls: Dict[str, Dict[str, Any]]):
        self.fns = fns
        self.type_decls = type_decls
        self.inexact = False
        self.stack: List[str] = []
        self.fresh = 0
        self.consts: Dict[str, Any] = {}

    # -- expressions: (value, definedness) or raise _Skip ---------------

    def expr(self, e: Dict[str, Any], env: Dict[str, Any], old_env):
        T = z3.BoolVal(True)
        k = e.get("kind")
        if k == "IntLit":
            return z3.IntVal(int(e["value"])), T
        if k == "BoolLit":
            return z3.BoolVal(bool(e["value"])), T
        if k == "Ident":
            v = env.get(e["name"])
            if v is None:
                raise _Skip
            return v, T
        if k == "Old":
            return self.expr(e["value"], old_env, old_env)
        if k == "UnaryOp":
            v, d = self.expr(e["value"], env, old_env)
            if e["op"] == "not" and _is_bool(v):
                return z3.Not(v), d
            if e["op"] == "neg" and _is_int(v):
                return -v, d
            raise _Skip
        if k == "BinOp":
            return self._binop(e, env, old_env)
        if k == "IfExpr":
            arms = [(e["cond"], e["then"])] + [
                (a["cond"], a["value"]) for a in e.get("elifs") or []]
            return self._if_chain(arms, e["else"], env, old_env)
        if k == "Call":
            return self._call(e, env, old_env)
        raise _Skip

    def _bool(self, e, env, old_env):
        v, d = self.expr(e, env, old_env)
        if not _is_bool(v):
            raise _Skip
        return v, d

    def _binop(self, e, env, old_env):
        op = e["op"]
        if op in ("and", "or", "implies"):
            l, dl = self._bool(e["left"], env, old_env)
            r, dr = self._bool(e["right"], env, old_env)
            # Python short-circuits: the right operand runs only when
            # the left one does not decide the result.
            if op == "and":
                return z3.And(l, r), z3.And(dl, z3.Implies(l, dr))
            if op == "or":
                return z3.Or(l, r), z3.And(dl, z3.Implies(z3.Not(l), dr))
            return z3.Implies(l, r), z3.And(dl, z3.Implies(l, dr))
        l, dl = self.expr(e["left"], env, old_env)
        r, dr = self.expr(e["right"], env, old_env)
        d = z3.And(dl, dr)
        if op in ("+", "-", "*", "/", "%", "<", "<=", ">", ">="):
            # Explicit sort guard: z3py would coerce Bool to Int in
            # arithmetic (x + b -> x + If(b, 1, 0)), not Aether semantics.
            if not (_is_int(l) and _is_int(r)):
                raise _Skip
            if op == "/":
                return floor_div(l, r), z3.And(d, r != 0)
            if op == "%":
                return floor_mod(l, r), z3.And(d, r != 0)
            return {"+": lambda: l + r, "-": lambda: l - r,
                    "*": lambda: l * r, "<": lambda: l < r,
                    "<=": lambda: l <= r, ">": lambda: l > r,
                    ">=": lambda: l >= r}[op](), d
        if op in ("==", "!="):
            if _sort_of(l) is None or _sort_of(l) != _sort_of(r):
                raise _Skip
            return (l == r if op == "==" else l != r), d
        raise _Skip

    def _if_chain(self, arms, else_e, env, old_env):
        if not arms:
            return self.expr(else_e, env, old_env)
        c, dc = self._bool(arms[0][0], env, old_env)
        t, dt = self.expr(arms[0][1], env, old_env)
        el, de = self._if_chain(arms[1:], else_e, env, old_env)
        if _sort_of(t) is None or _sort_of(t) != _sort_of(el):
            raise _Skip
        return z3.If(c, t, el), z3.And(dc, z3.If(c, dt, de))

    def _call(self, e, env, old_env):
        f = e["func"]
        if f.get("kind") != "Ident" or f["name"] in env:
            raise _Skip
        name = f["name"]
        args = [self.expr(a, env, old_env) for a in e["args"]]
        d = _all([ad for _, ad in args])
        vals = [v for v, _ in args]
        decl = self.fns.get(name)
        if decl is None:
            # Stdlib (runtime.py _ae_abs/_ae_min/_ae_max) on Int only; a
            # user function of the same name shadows it (checked above).
            if not all(_is_int(v) for v in vals):
                raise _Skip
            if name == "abs" and len(vals) == 1:
                return z3.If(vals[0] >= 0, vals[0], -vals[0]), d
            if name in ("min", "max") and len(vals) == 2:
                a, b = vals
                return (z3.If(a <= b, a, b) if name == "min"
                        else z3.If(a >= b, a, b)), d
            raise _Skip
        if len(vals) != len(decl["params"]):
            raise _Skip
        if name not in self.stack and len(self.stack) < _MAX_INLINE_DEPTH:
            try:
                paths = self.function_paths(decl, vals)
            except _Skip:
                paths = None
            if paths:
                value = paths[-1][1]
                for cond, v, _ in reversed(paths[:-1]):
                    value = z3.If(cond, v, value)
                return value, z3.And(d, z3.Or(*[c for c, _, _ in paths]))
        return self._abstract(decl, d)

    def _abstract(self, decl, d):
        ret = _resolve_param_sort(decl.get("return_type"), self.type_decls)
        if ret is None:
            raise _Skip
        self.inexact = True
        self.fresh += 1
        v = _mk_var(f"_ae_smt_call{self.fresh}_{decl['name']}", ret[0])
        return v, z3.And(d, _all(self._preds(ret[1], v)))

    def _preds(self, preds, value):
        """Refinement predicates on `value`, as conditions that hold when
        the runtime check passes. Untranslatable ones are dropped."""
        out = []
        for pred in preds:
            try:
                p, dp = self._bool(pred, {"self": value}, {"self": value})
            except _Skip:
                self.inexact = True
                continue
            out.append(z3.And(dp, p))
        return out

    # -- statements -------------------------------------------------------

    def function_paths(self, decl, arg_vals):
        """[(cond, value, locals)] for every return of `decl` called with
        `arg_vals`. Raises _Skip when the body leaves the fragment."""
        ret = _resolve_param_sort(decl.get("return_type"), self.type_decls)
        if ret is None:
            raise _Skip
        env: Dict[str, Any] = dict(self.consts)   # params shadow consts
        conds: List[Any] = []
        for p, v in zip(decl["params"], arg_vals):
            resolved = _resolve_param_sort(p["type"], self.type_decls)
            if resolved is None or resolved[0] != _sort_of(v):
                raise _Skip
            env[p["name"]] = v
            conds += self._preds(resolved[1], v)
        entry = dict(env)
        for clause in decl.get("requires") or []:
            try:
                c, dc = self._bool(clause, env, entry)
            except _Skip:
                self.inexact = True     # dropped premise: proofs only
                continue
            conds.append(z3.And(dc, c))
        ltypes = {n["name"]: n["type"] for n in _walk(decl.get("body") or [])
                  if n.get("kind") in ("Let", "Var") and n.get("type")}
        self.stack.append(decl["name"])
        try:
            returns, falls = self._block(decl.get("body") or [], env, entry,
                                         conds, ltypes)
        finally:
            self.stack.pop()
        if falls or not returns:
            raise _Skip  # can fall off the end and return None
        out = []
        for pc, v, renv in returns:
            if _sort_of(v) != ret[0]:
                raise _Skip
            out.append((_all(pc + self._preds(ret[1], v)), v, renv))
        return out

    def _block(self, stmts, env, old_env, pc, ltypes):
        states = [(env, pc)]
        returns = []
        for s in stmts:
            nxt = []
            for senv, spc in states:
                r, f = self._stmt(s, senv, old_env, spc, ltypes)
                returns += r
                nxt += f
            states = nxt
            if len(returns) + len(states) > _MAX_PATHS:
                raise _Skip
            if not states:
                break
        return returns, states

    def _stmt(self, s, env, old_env, pc, ltypes):
        k = s.get("kind")
        if k in ("Let", "Var", "Assign"):
            name = s["target"] if k == "Assign" else s["name"]
            v, d = self.expr(s["value"], env, old_env)
            conds = [d]
            ty = ltypes.get(name) if k == "Assign" else s.get("type")
            if ty is not None:   # emitter: refine_check on annotated binds
                resolved = _resolve_param_sort(ty, self.type_decls)
                if resolved is None or resolved[0] != _sort_of(v):
                    raise _Skip
                conds += self._preds(resolved[1], v)
            return [], [(dict(env, **{name: v}), pc + conds)]
        if k == "Return":
            if s.get("value") is None:
                raise _Skip
            v, d = self.expr(s["value"], env, old_env)
            return [(pc + [d], v, env)], []
        if k == "If":
            returns, falls = [], []
            rest = list(pc)
            arms = [(s["cond"], s["then"])] + [
                (a["cond"], a["body"]) for a in s.get("elifs") or []]
            for cond, body in arms:
                c, dc = self._bool(cond, env, old_env)
                r, f = self._block(body, env, old_env, rest + [dc, c], ltypes)
                returns += r
                falls += f
                rest = rest + [dc, z3.Not(c)]
            r, f = self._block(s.get("else") or [], env, old_env, rest, ltypes)
            return returns + r, falls + f
        raise _Skip


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def translate_expr(expr: Dict[str, Any], env: Dict[str, Any]):
    """Aether expr AST -> z3 expression, or None when outside the fragment.

    A Bool expression comes back as "defined AND true" (a zero divisor
    makes it false, as the runtime check would fail). An Int expression
    with a partial operation has no total value and returns None.
    """
    try:
        v, d = _Translator({}, {}).expr(expr, env, env)
    except (_Skip, TypeError, z3.Z3Exception):
        return None
    if z3.is_true(z3.simplify(d)):
        return v
    return z3.And(d, v) if _is_bool(v) else None


def check_contracts_smt(ast: Dict[str, Any], timeout_ms: int = 5000,
                        records: Optional[list] = None
                        ) -> Tuple[List[Diagnostic], Dict[str, int]]:
    """Prove every `ensures` clause the fragment admits.

    Returns (diagnostics, summary). The summary counts CLAUSES:
    {"proved", "refuted", "timeout", "skipped"}. Refuted clauses emit
    E0901 (error, counterexample in extra); solver-unknown clauses emit
    E0902 (warning). Skipped clauses emit nothing — their runtime
    checks remain in force. `records`, when given, receives one
    {function, clause, status, reason} dict per clause.
    """
    assert HAVE_Z3, "check_contracts_smt requires z3-solver"
    diags: List[Diagnostic] = []
    summary = {"proved": 0, "refuted": 0, "timeout": 0, "skipped": 0}
    type_decls = {d["name"]: d for d in ast["decls"]
                  if d.get("kind") == "TypeDecl"}
    fns = {d["name"]: d for d in ast["decls"]
           if d.get("kind") == "FunctionDecl"}
    # Module consts with a total Int/Bool value of the declared sort (a
    # refined const is checked when bound, so its predicate holds).
    consts: Dict[str, Any] = {}
    for c in ast["decls"]:
        if c.get("kind") != "ConstDecl":
            continue
        resolved = _resolve_param_sort(c.get("type"), type_decls)
        try:
            v, dv = _Translator({}, type_decls).expr(c["value"], consts,
                                                      consts)
        except (_Skip, TypeError, z3.Z3Exception):
            continue
        if (resolved is not None and resolved[0] == _sort_of(v)
                and z3.is_true(z3.simplify(dv))):
            consts[c["name"]] = v

    def record(d, idx, status, reason=""):
        if status == "skipped":
            summary["skipped"] += 1
        if records is not None:
            records.append({"function": d["name"], "clause": idx,
                            "status": status, "reason": reason})

    for d in ast["decls"]:
        if d.get("kind") != "FunctionDecl" or not d.get("ensures"):
            continue
        pos = d.get("pos") or {"line": 1, "column": 1}
        position = Position(line=pos["line"], column=pos["column"])

        # 1. Signature: every param and the result must have a sort.
        params: Dict[str, Any] = {}
        reason = ""
        for p in d["params"]:
            resolved = _resolve_param_sort(p["type"], type_decls)
            if resolved is None:
                reason = "param-type"
                break
            params[p["name"]] = _mk_var(p["name"], resolved[0])
        ret = _resolve_param_sort(d.get("return_type"), type_decls)
        if not reason and ret is None:
            reason = "return-type"

        # 2. Return paths (requires + refinements are inside each path).
        tr = _Translator(fns, type_decls)
        tr.consts = consts
        paths = None
        if not reason:
            try:
                paths = tr.function_paths(d, list(params.values()))
            except (_Skip, TypeError, z3.Z3Exception):
                reason = "body"
        if reason:
            for idx in range(len(d["ensures"])):
                record(d, idx, "skipped", reason)
            continue
        body_inexact = tr.inexact
        result_var = _mk_var("_ae_smt_result", ret[0])

        # 3. One obligation per ensures clause, over every return path.
        for idx, clause in enumerate(d["ensures"]):
            tr.inexact = body_inexact
            disjuncts = []
            try:
                for cond, value, renv in paths:
                    genv = dict(renv)
                    genv["result"] = result_var
                    g, dg = tr._bool(clause, genv, params)
                    disjuncts.append(z3.And(cond, result_var == value,
                                            z3.Not(z3.And(dg, g))))
            except (_Skip, TypeError, z3.Z3Exception):
                record(d, idx, "skipped", "ensures-expr")
                continue
            solver = z3.Solver()
            solver.set("timeout", timeout_ms)
            solver.add(z3.Or(*disjuncts))
            res = solver.check()
            if res == z3.unsat:
                summary["proved"] += 1
                record(d, idx, "proved")
            elif tr.inexact:
                # A model of an abstraction is not an execution.
                record(d, idx, "skipped", "inconclusive")
            elif res == z3.sat:
                summary["refuted"] += 1
                record(d, idx, "refuted")
                model = solver.model()
                counterexample = {
                    name: str(model.eval(var, model_completion=True))
                    for name, var in params.items()
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
                record(d, idx, "timeout")
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
