"""E0209 — implicit Int/Float coercion, refused where both types are KNOWN.

`Int` is exact and arbitrary-precision; `Float` is IEEE-754
(`grammar/types.md`). The emitted Python mixes them silently: `1 + 2.5`
is `3.5`, an Int above 2**53 compared with a Float is compared after
rounding, and `/` is floor division on two Ints but true division
otherwise — so a `Float`-annotated binding that actually holds an Int
changes what `/` computes. This pass refuses the mix at the three places
it happens:

  - `binop`:   an arithmetic (`+ - * / %`) or comparison
               (`== != < <= > >=`) operator with one Int and one Float
               operand;
  - `return`:  `return e` where `e` is of the other numeric type than the
               function's declared `returns Int|Float`;
  - `binding`: an annotated `let`/`var`/`const`, or an assignment to a
               name of known type, whose value is of the other numeric
               type (`var n = 0` then `n = 2.5`).

Type knowledge is local and conservative — this is NOT a type checker and
there is no inference engine. A type is known only for: a numeric
literal; a name bound by an `Int`/`Float` (or refined-alias-of-those)
parameter, `let`/`var`/`const` annotation, or an unannotated `let`/`var`
whose first value has a known type; a `for` variable over
`range(...)`; `result` in `ensures`, `self` in a refinement; a call to a
user function declaring `returns Int|Float`, or to one of the stdlib
functions whose result type does not follow its argument (`_STDLIB`);
and arithmetic / unary minus / if-expressions over those. Anything else
is unknown and yields no finding. Scopes follow the E0208 resolver
(`names.py`): block-scoped, parameters and locals shadow globals, and
`match` pattern bindings are unknown.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from ..diagnostics import Diagnostic, Position
from .names import _complete, _pattern_names

NUM = ("Int", "Float")
_ARITH = {"+", "-", "*", "/", "%"}
_CMP = {"==", "!=", "<", "<=", ">", ">="}
_BITS = {"band", "bor", "bxor", "shl", "shr"}

# Stdlib functions whose documented return type (`grammar/stdlib.md`)
# holds for every argument at run time. Left out on purpose: `abs`, `min`,
# `max`, `sum`, `product`, `pow` — documented as Int (pow: Float) but the
# runtime returns the argument's type, so typing them would flag programs
# the runtime computes exactly. `tests/test_numeric_coercion.py` pins each
# row against stdlib.md.
_STDLIB = {
    "length": "Int", "count": "Int", "size": "Int", "bytesLen": "Int",
    "byteAt": "Int", "ord": "Int", "gcd": "Int", "lcm": "Int",
    "floor": "Int", "ceil": "Int", "sqrt": "Float",
}


class _Checker:
    def __init__(self, fn: str, aliases: Dict[str, Optional[str]],
                 consts: Dict[str, Optional[str]],
                 funcs: Dict[str, Optional[str]]):
        self.fn = fn
        self.aliases = aliases
        self.consts = consts
        self.funcs = funcs
        self.diags: List[Diagnostic] = []

    def ann(self, t: Any) -> Optional[str]:
        """Int/Float for a TypeName naming one (or a refined alias of one)."""
        if isinstance(t, dict) and t.get("kind") == "TypeName":
            n = t.get("name")
            return n if n in NUM else self.aliases.get(n)
        return None

    def _report(self, pos, kind: str, lt: str, rt: str, op: Optional[str],
                hint: str) -> None:
        pos = pos or {}
        where = {"binop": f"operator {op!r} mixes {lt} and {rt}",
                 "return": f"returns a {rt} from a function declared "
                           f"`returns {lt}`",
                 "binding": f"binds a {rt} value to {op!r}, which is {lt} "
                            f"(its annotation, or the type of its first "
                            f"value)"}[kind]
        self.diags.append(Diagnostic(
            code="E0209", category="type", severity="error",
            message=(f"function {self.fn!r}: {where} — an implicit numeric "
                     f"coercion; Int is exact and Float is IEEE-754, and the "
                     f"emitted Python converts silently (and `/` floors only "
                     f"when both operands are Int)"),
            position=Position(pos.get("line", 0), pos.get("column", 0)),
            suggestion=hint, confidence=1.0,
            extra={"function": self.fn, "kind": kind, "op": op,
                   "left_type": lt, "right_type": rt},
        ))

    @staticmethod
    def _hint(pairs) -> str:
        """pairs: [(expr, its type)], the operands whose type disagrees."""
        for e, t in pairs:
            neg = isinstance(e, dict) and e.get("kind") == "UnaryOp"
            lit = e.get("value") if neg else e
            sign = "-" if neg else ""
            if isinstance(lit, dict) and lit.get("kind") == "IntLit":
                return (f"decide which type is meant: for Float arithmetic "
                        f"write the literal as `{sign}{lit['value']}.0`")
            if (isinstance(lit, dict) and lit.get("kind") == "FloatLit"
                    and float(lit["value"]).is_integer()):
                return (f"decide which type is meant: for Int arithmetic "
                        f"write the literal as `{sign}{int(lit['value'])}` "
                        f"(then `/` is floor division)")
        return ("make the conversion explicit: `floor(x)` or `ceil(x)` turns "
                "a Float into an Int (grammar/stdlib.md, Math); the stdlib "
                "has no Int-to-Float conversion, so keep the value Int or "
                "compute it as a Float from the start")

    # --- expressions: returns "Int" | "Float" | None, reports as it goes
    def ty(self, e: Any, env: Dict[str, Optional[str]], pos) -> Optional[str]:
        if isinstance(e, list):
            for x in e:
                self.ty(x, env, pos)
            return None
        if not isinstance(e, dict):
            return None
        pos = e.get("pos") or pos
        k = e.get("kind")
        if k == "IntLit":
            return "Int"
        if k == "FloatLit":
            return "Float"
        if k == "Ident":
            n = e.get("name")
            return env[n] if n in env else self.consts.get(n)
        if k in ("UnaryOp", "Old"):
            t = self.ty(e.get("value"), env, pos)
            return t if (k == "Old" or e.get("op") == "neg") else None
        if k == "BinOp":
            op = e.get("op")
            if op == "is":
                self.ty(e.get("left"), env, pos)
                return None
            lt = self.ty(e.get("left"), env, pos)
            rt = self.ty(e.get("right"), env, pos)
            if op in _ARITH | _CMP and {lt, rt} == set(NUM):
                self._report(pos, "binop", lt, rt, op, self._hint(
                    [(e.get("left"), lt), (e.get("right"), rt)]))
                # What the emitted Python computes: a mix is a float.
                return "Float" if op in _ARITH else None
            if lt == rt and (op in _ARITH or (op in _BITS and lt == "Int")):
                return lt
            return None
        if k == "Call":
            f = e.get("func") or {}
            self.ty(e.get("args"), env, pos)
            if f.get("kind") != "Ident":
                self.ty(f, env, pos)
                return None
            n = f.get("name")
            if n in env or n in self.consts:
                return None                     # a local/const called: unknown
            if n in self.funcs:
                return self.funcs[n]
            return _STDLIB.get(n)
        if k == "IfExpr":
            self.ty(e.get("cond"), env, pos)
            ts = [self.ty(e.get("then"), env, pos),
                  self.ty(e.get("else"), env, pos)]
            for el in e.get("elifs") or []:
                self.ty(el.get("cond"), env, pos)
                ts.append(self.ty(el.get("value"), env, pos))
            return ts[0] if len(set(ts)) == 1 else None
        if k == "MatchExpr":
            self.ty(e.get("scrutinee"), env, pos)
            ts = [self.ty(arm.get("value"),
                          {**env, **dict.fromkeys(_pattern_names(arm.get("pattern")))},
                          pos)
                  for arm in e.get("arms") or []]
            return ts[0] if ts and len(set(ts)) == 1 else None
        for v in e.values():
            if isinstance(v, (dict, list)):
                self.ty(v, env, pos)
        return None

    def bind_check(self, name: str, want: Optional[str], got: Optional[str],
                   value: Any, pos) -> None:
        if want in NUM and got in NUM and want != got:
            self._report(pos, "binding", want, got, name,
                         self._hint([(value, got)]))

    # --- statements ---------------------------------------------------
    def block(self, stmts: Any, env: Dict[str, Optional[str]],
              ret: Optional[str], pos=None) -> None:
        env = dict(env)         # block scope, as in names._Resolver.block
        for s in stmts or []:
            if not isinstance(s, dict):
                continue
            p = s.get("pos") or pos
            k = s.get("kind")
            if k in ("Let", "Var"):
                got = self.ty(s.get("value"), env, p)
                want = self.ann(s.get("type"))
                name = s.get("name")
                self.bind_check(name, want, got, s.get("value"), p)
                # Unannotated: the first value's type is the name's type,
                # so a later assignment of the other type is E0209 too.
                env[name] = want if s.get("type") is not None else got
            elif k == "Assign":
                got = self.ty(s.get("value"), env, p)
                tgt = s.get("target")
                if tgt in env:
                    self.bind_check(tgt, env[tgt], got, s.get("value"), p)
                else:           # an assignment with no earlier let binds
                    env[tgt] = got
            elif k == "Return":
                got = self.ty(s.get("value"), env, p)
                if ret in NUM and got in NUM and ret != got:
                    self._report(p, "return", ret, got, None,
                                 self._hint([(s.get("value"), got)]))
            elif k == "If":
                self.ty(s.get("cond"), env, p)
                self.block(s.get("then"), env, ret, p)
                for el in s.get("elifs") or []:
                    self.ty(el.get("cond"), env, p)
                    self.block(el.get("body"), env, ret, p)
                self.block(s.get("else"), env, ret, p)
            elif k == "While":
                self.ty(s.get("cond"), env, p)
                self.block(s.get("body"), env, ret, p)
            elif k == "For":
                it = s.get("iter") or {}
                self.ty(it, env, p)
                f = it.get("func") or {}
                is_range = (it.get("kind") == "Call" and f.get("kind") == "Ident"
                            and f.get("name") == "range" and "range" not in env
                            and "range" not in self.funcs
                            and "range" not in self.consts)
                self.block(s.get("body"),
                           {**env, s.get("var"): "Int" if is_range else None},
                           ret, p)
            elif k == "Match":
                self.ty(s.get("scrutinee"), env, p)
                for arm in s.get("arms") or []:
                    self.block(arm.get("body"),
                               {**env, **dict.fromkeys(_pattern_names(arm.get("pattern")))},
                               ret, p)
            else:       # ExprStmt, Break, Continue
                self.ty({k2: v for k2, v in s.items() if k2 != "kind"}, env, p)


def check_numeric_coercion(ast: Dict[str, Any]) -> List[Diagnostic]:
    """E0209 for an Int/Float mix whose two types are both statically known."""
    if not _complete(ast):
        return []
    decls = ast.get("decls", [])
    aliases: Dict[str, Optional[str]] = {}
    probe = _Checker("", aliases, {}, {})
    for _ in decls:     # ponytail: fixpoint by repetition; alias chains are short
        for d in decls:
            if d.get("kind") == "TypeDecl":
                aliases[d["name"]] = probe.ann(d.get("base"))
    consts = {d["name"]: probe.ann(d.get("type"))
              for d in decls if d.get("kind") == "ConstDecl"}
    funcs = {d["name"]: probe.ann(d.get("return_type"))
             for d in decls if d.get("kind") == "FunctionDecl"}
    # Every other top-level name is a value of unknown numeric type.
    for d in decls:
        if d.get("kind") == "RecordDecl":
            funcs.setdefault(d["name"], None)
        elif d.get("kind") == "UnionDecl":
            for c in d.get("cases") or []:
                funcs.setdefault(c["name"], None)
    diags: List[Diagnostic] = []
    for d in decls:
        k = d.get("kind")
        pos = d.get("pos")
        if k == "ConstDecl":
            c = _Checker(f"<const {d.get('name')}>", aliases, consts, funcs)
            c.bind_check(d["name"], consts[d["name"]],
                         c.ty(d.get("value"), {}, pos), d.get("value"), pos)
        elif k == "FunctionDecl":
            c = _Checker(d["name"], aliases, consts, funcs)
            env = {p["name"]: c.ann(p.get("type")) for p in d.get("params") or []}
            ret = funcs[d["name"]]
            c.ty(d.get("requires"), env, pos)
            c.ty(d.get("ensures"), {**env, "result": ret}, pos)
            c.block(d.get("body"), env, ret, pos)
        elif k == "TypeDecl" and d.get("refinement") is not None:
            c = _Checker(f"<type {d.get('name')} where>", aliases, consts, funcs)
            c.ty(d["refinement"], {"self": aliases.get(d["name"])}, pos)
        else:
            continue
        diags.extend(c.diags)
    return diags
