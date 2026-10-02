"""Package-wide interprocedural clearing, measured (track D, 2026-10-02).

For every framework-corpus finding, find the sink argument and the values
it is built from ("leaves", through the sink function's local bindings).
A finding is CLEARABLE when every leaf is provably literal-shaped:

  * a literal, or a recognised sanitizer call (SANITIZER_BY_QUALIFIED,
    psycopg.sql), or
  * a PARAMETER whose every call site in the same distribution passes a
    clearable value (recursively, across modules), or
  * a call to a PACKAGE function whose every `return` is clearable, with
    the callee's own parameters bound to THIS call's arguments, or
  * (fields, a separate row) `self.x` where every store to `.x` anywhere in
    the distribution is clearable.

Call sites are over-approximated: a method `m` is called by EVERY
`<anything>.m(...)` in the distribution; a function is escaped (unclearable)
if its name is ever read other than as a callee, it is decorated, or it is a
dunder. A function with no call site is an entry point, never cleared.

Each clearing carries the weakest assumption it needed (its tier):
  0 SOUND       parameters of nested functions; summaries of module-level
                and nested functions (modulo monkeypatching, which no static
                pass sees)
  1 CONVENTION  parameters of `_private` functions/methods whose class has
                no base outside the distribution (a framework base may call
                them); summaries of `_private` methods reached through
                `self.`/`cls.` and not overridden in the distribution. Sound
                only if no outside code calls or overrides a `_name`; Python
                does not enforce that
  2 UNSOUND     public functions/methods: "assume no external callers or
                overrides"
LOOSE-UPPER-BOUND additionally drops every escape check and every call site
whose receiver the graph cannot resolve. It is not a design; it bounds what
a more precise call graph could add.
Then every cleared finding is CONFIRMED by a counterfactual: the leaves the
argument relies on are replaced by a string literal, the module is
unparsed, and check-py must drop the finding (function + code count).

Usage (repo root):
  python -B audits/ipa_probe_2026-10-02/pkg_ipa.py <fw_full.json> <SRC> [--verify] [--site]
--site: SRC is a site-packages dir; each package dir is one distribution.
"""
import ast
import collections
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from transpiler.aether.py_frontend import SANITIZER_BY_QUALIFIED  # noqa: E402

SOUND, CONV, UNSOUND = 0, 1, 2
TIER = {SOUND: "sound", CONV: "convention", UNSOUND: "unsound"}
STR_METHODS = {"format", "join", "replace", "strip", "lstrip", "rstrip", "lower", "upper",
               "title", "capitalize", "casefold", "removeprefix", "removesuffix", "ljust",
               "rjust", "center", "zfill", "encode", "decode", "format_map"}
PURE_BUILTINS = {"str", "repr", "int", "float", "bool", "len", "tuple", "list", "sorted", "abs"}
TRIVIAL_DECOS = {"staticmethod", "classmethod", "abstractmethod", "override"}
MAX_DEPTH = 12
IPA_KINDS = ("param", "pkgcall", "self.attr")
BAD_SITE_KINDS = collections.Counter()   # leaf kinds that block a caller's argument


def sanitizer(dotted):
    return dotted and (dotted in SANITIZER_BY_QUALIFIED
                       or dotted.startswith(("psycopg2.sql.", "psycopg.sql.")))


# ---------------------------------------------------------------- index
class Fn:
    def __init__(s, node, mod, cls, outer):
        s.node, s.mod, s.cls, s.outer, s.name = node, mod, cls, outer, node.name
        a = node.args
        s.pos = [x.arg for x in a.posonlyargs + a.args]
        s.kwonly = [x.arg for x in a.kwonlyargs]
        s.params = set(s.pos) | set(s.kwonly) | {x.arg for x in (a.vararg, a.kwarg) if x}
        s.star = {x.arg for x in (a.vararg, a.kwarg) if x}
        defs = a.defaults
        s.defaults = dict(zip(s.pos[len(s.pos) - len(defs):], defs))
        s.defaults.update({k.arg: d for k, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None})
        s.decos = [d for d in node.decorator_list]
        s.static = any(_tail(d) == "staticmethod" for d in s.decos)
        s.classm = any(_tail(d) == "classmethod" for d in s.decos)
        s.nested = {}            # name -> Fn defined directly in this body
        s.binds = collections.defaultdict(list)   # name -> [value expr | None]
        s.returns, s.gen = [], False

    def qual(s):
        return f"{s.mod.name}:{(s.cls.name + '.') if s.cls else ''}{s.name}"


class Cls:
    def __init__(s, node, mod):
        s.node, s.mod, s.name = node, mod, node.name
        s.methods, s.class_binds = {}, collections.defaultdict(list)


class Mod:
    def __init__(s, name, path, tree, is_pkg):
        s.name, s.path, s.tree, s.is_pkg = name, path, tree, is_pkg
        s.imports, s.funcs, s.classes = {}, {}, {}
        s.binds = collections.defaultdict(list)


def _tail(e):
    if isinstance(e, ast.Call):
        e = e.func
    return e.attr if isinstance(e, ast.Attribute) else (e.id if isinstance(e, ast.Name) else "")


def _body_nodes(stmts):
    """Every node of a body, not descending into nested defs/classes/lambdas/
    comprehensions (their own scopes)."""
    stack = list(stmts)
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                              ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                yield c          # the node itself (a def name is a binding) but not its body
                continue
            stack.append(c)


def _record_binds(binds, stmts):
    for n in _body_nodes(stmts):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                _bind_target(binds, t, n.value)
        elif isinstance(n, ast.AnnAssign) and n.value is not None:
            _bind_target(binds, n.target, n.value)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            binds[n.target.id].append(n.value)
        elif isinstance(n, ast.NamedExpr):
            binds[n.target.id].append(n.value)
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            _bind_target(binds, n.target, None)
        elif isinstance(n, ast.withitem) and n.optional_vars is not None:
            _bind_target(binds, n.optional_vars, None)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            binds[n.name].append(None)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                binds[(a.asname or a.name).split(".")[0]].append(None)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            for nm in n.names:
                binds[nm].append(None)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            binds[n.name].append(None)
        elif isinstance(n, ast.MatchAs) and n.name:
            binds[n.name].append(None)
        elif isinstance(n, ast.MatchStar) and n.name:
            binds[n.name].append(None)


def _bind_target(binds, t, value):
    if isinstance(t, ast.Name):
        binds[t.id].append(value)
    elif isinstance(t, (ast.Tuple, ast.List)):
        for e in t.elts:
            _bind_target(binds, e.value if isinstance(e, ast.Starred) else e, None)


class Package:
    def __init__(s, root, prefix=""):
        # prefix: the import name of `root` itself (a site-packages package
        # dir) — empty for a wheel extraction root, which holds the package.
        s.root, s.mods, s.fns, s.classes = root, {}, [], []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if not d.endswith((".dist-info", ".data")) and d != "__pycache__"]
            for fn in fns:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, root).replace("\\", "/")[:-3]
                is_pkg = rel.endswith("/__init__") or rel == "__init__"
                name = rel[:-len("/__init__")] if rel.endswith("/__init__") else rel
                if prefix:
                    name = prefix if rel == "__init__" else f"{prefix}/{name}"
                try:
                    tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
                except Exception:
                    continue
                s.mods[name.replace("/", ".")] = Mod(name.replace("/", "."), rel + ".py", tree, is_pkg)
        for m in s.mods.values():
            s._index(m)
        s._sites()

    # ---- definitions
    def _index(s, m):
        for n in ast.walk(m.tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                s._imp(m, n)
        _record_binds(m.binds, s._toplevel(m.tree.body))
        s._defs(m, m.tree.body, None, None)

    def _toplevel(s, body):
        out = []
        for st in body:
            if isinstance(st, (ast.If, ast.Try)):
                out += s._toplevel(st.body + st.orelse + getattr(st, "finalbody", [])
                                   + [x for h in getattr(st, "handlers", []) for x in h.body])
            else:
                out.append(st)
        return out

    def _imp(s, m, n):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    m.imports[a.asname] = ("mod", a.name)
                else:
                    m.imports[a.name.split(".")[0]] = ("mod", a.name.split(".")[0])
        else:
            base = n.module or ""
            if n.level:
                parts = m.name.split(".")
                if not m.is_pkg:
                    parts = parts[:-1]
                parts = parts[:len(parts) - (n.level - 1)] if n.level > 1 else parts
                base = ".".join(parts + ([n.module] if n.module else []))
            for a in n.names:
                m.imports[a.asname or a.name] = ("sym", base, a.name)

    def _defs(s, m, body, cls, outer):
        for st in s._toplevel(body) if outer is None else body:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f = Fn(st, m, cls, outer)
                s.fns.append(f)
                if outer is not None:
                    outer.nested[st.name] = f
                elif cls is not None:
                    cls.methods[st.name] = f
                else:
                    m.funcs[st.name] = f
                _record_binds(f.binds, st.body)
                for n in _body_nodes(st.body):
                    if isinstance(n, ast.Return):
                        f.returns.append(n.value if n.value is not None else ast.Constant(None))
                    elif isinstance(n, (ast.Yield, ast.YieldFrom)):
                        f.gen = True
                s._defs(m, [n for n in _body_nodes(st.body)
                            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))],
                        None, f)
            elif isinstance(st, ast.ClassDef):
                c = Cls(st, m)
                s.classes.append(c)
                if outer is None and cls is None:
                    m.classes[st.name] = c
                _record_binds(c.class_binds, [x for x in st.body
                                              if not isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))])
                s._defs(m, st.body, c, None if outer is None else outer)

    # ---- resolution
    def symbol(s, modname, name, hops=0):
        if hops > 6:
            return None
        if f"{modname}.{name}" in s.mods:
            return ("mod", f"{modname}.{name}")
        m = s.mods.get(modname)
        if m is None:
            return None
        if name in m.funcs:
            return m.funcs[name]
        if name in m.classes:
            return m.classes[name]
        imp = m.imports.get(name)
        if imp:
            return s.imported(imp, hops + 1)
        if name in m.binds:
            return ("var", m, name)
        return None

    def imported(s, imp, hops=0):
        if imp[0] == "mod":
            return ("mod", imp[1]) if imp[1] in s.mods else ("ext", imp[1])
        r = s.symbol(imp[1], imp[2], hops)
        return r if r is not None else ("ext", f"{imp[1]}.{imp[2]}")

    def name(s, ident, mod, fn):
        """What a bare name means at a point inside `fn` (None = module level)."""
        f = fn
        while f is not None:
            if ident in f.nested:
                return f.nested[ident]
            if ident in f.params:
                return ("param", f, ident)
            if ident in f.binds:
                return ("local", f, ident)
            f = f.outer
        if ident in mod.funcs:
            return mod.funcs[ident]
        if ident in mod.classes:
            return mod.classes[ident]
        if ident in mod.imports:
            return s.imported(mod.imports[ident])
        if ident in mod.binds:
            return ("var", mod, ident)
        return ("ext", ident)

    def dotted(s, e, mod, fn):
        if isinstance(e, ast.Name):
            r = s.name(e.id, mod, fn)
            if isinstance(r, tuple) and r[0] in ("ext", "mod"):
                return r[1]
            return None
        if isinstance(e, ast.Attribute):
            b = s.dotted(e.value, mod, fn)
            return f"{b}.{e.attr}" if b else None
        return None

    def method(s, cls, name, seen=None):
        """MRO-ish lookup of `name` on an in-distribution class."""
        seen = seen or set()
        if cls is None or id(cls) in seen:
            return None
        seen.add(id(cls))
        if name in cls.methods:
            return cls.methods[name]
        for b in s.bases(cls):
            r = s.method(b, name, seen)
            if r:
                return r
        return None

    def bases(s, cls):
        out = []
        for b in cls.node.bases:
            r = None
            if isinstance(b, ast.Name):
                r = s.name(b.id, cls.mod, None)
            elif isinstance(b, ast.Attribute):
                d = s.dotted(b.value, cls.mod, None)
                r = s.symbol(d, b.attr) if d in s.mods else None
            if isinstance(r, Cls):
                out.append(r)
        return out

    def external_base(s, cls, seen=None):
        seen = seen or set()
        if id(cls) in seen:
            return False
        seen.add(id(cls))
        res = [b for b in cls.node.bases if not (isinstance(b, ast.Name) and b.id == "object")]
        ins = s.bases(cls)
        if len(ins) < len(res):
            return True
        return any(s.external_base(b, seen) for b in ins)

    def call_target(s, call, mod, fn):
        """('fn', Fn, bound) | ('ext', dotted) | ('attr', name) | None"""
        f = call.func
        if isinstance(f, ast.Name):
            r = s.name(f.id, mod, fn)
            if isinstance(r, Fn):
                return ("fn", r, False)
            if isinstance(r, Cls):
                return ("ctor", r)
            if isinstance(r, tuple) and r[0] == "ext":
                return ("ext", r[1])
            return None
        if isinstance(f, ast.Attribute):
            v = f.value
            cls = _enclosing_cls(fn)
            if isinstance(v, ast.Name) and v.id in ("self", "cls") and cls is not None:
                return ("meth", s.method(cls, f.attr), f.attr)
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "super" and cls:
                for b in s.bases(cls):
                    m = s.method(b, f.attr)
                    if m:
                        return ("meth", m, f.attr)
                return ("attr", f.attr)
            if isinstance(v, ast.Name):
                r = s.name(v.id, mod, fn)
                if isinstance(r, tuple) and r[0] == "mod":
                    t = s.symbol(r[1], f.attr)
                    if isinstance(t, Fn):
                        return ("fn", t, False)
                    if isinstance(t, Cls):
                        return ("ctor", t)
                    return ("ext", f"{r[1]}.{f.attr}")
                if isinstance(r, Cls):
                    return ("meth", s.method(r, f.attr), f.attr)
            d = s.dotted(f, mod, fn)
            if d and not isinstance(v, ast.Call):
                return ("ext", d)
            return ("attr", f.attr)
        return None

    # ---- call sites and escapes
    def _sites(s):
        s.by_fn = collections.defaultdict(list)       # id(Fn) -> [(call, mod, fn)]
        s.by_attr = collections.defaultdict(list)     # attr name -> [(call, mod, fn)]
        s.escaped_fn, s.escaped_attr = set(), set()
        for f in [None] + s.fns:
            mods = [s.mods[f.mod.name]] if f else list(s.mods.values())
            for mod in mods:
                body = f.node.body if f else mod.tree.body
                nodes = list(_body_nodes(body)) if f else _module_level_nodes(mod.tree)
                callfuncs = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
                for n in nodes:
                    if isinstance(n, ast.Call):
                        if isinstance(n.func, ast.Attribute):
                            s.by_attr[n.func.attr].append((n, mod, f))
                        t = s.call_target(n, mod, f)
                        if t and t[0] == "fn":
                            s.by_fn[id(t[1])].append((n, mod, f))
                        if isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) > 1 \
                                and isinstance(n.args[1], ast.Constant):
                            s.escaped_attr.add(str(n.args[1].value))
                    elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in callfuncs:
                        r = s.name(n.id, mod, f)
                        if isinstance(r, Fn):
                            s.escaped_fn.add(id(r))
                    elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and id(n) not in callfuncs:
                        s.escaped_attr.add(n.attr)
                        d = s.dotted(n.value, mod, f)
                        if d in s.mods:
                            t = s.symbol(d, n.attr)
                            if isinstance(t, Fn):
                                s.escaped_fn.add(id(t))
                    elif isinstance(n, (ast.ImportFrom,)):
                        pass

    def visibility(s, f):
        """Tier a parameter clearing of `f` needs, or None if `f` escapes."""
        if any(_tail(d) not in TRIVIAL_DECOS for d in f.decos):
            return None
        if f.name.startswith("__") and f.name.endswith("__"):
            return None
        if id(f) in s.escaped_fn:
            return None
        if f.cls is not None and f.name in s.escaped_attr:
            return None
        if f.outer is not None and f.cls is None:
            return SOUND
        if f.name.startswith("_") and not (f.cls and s.external_base(f.cls)):
            return CONV
        return UNSOUND

    def sites(s, f, resolved_only=False):
        """[(call, mod, caller_fn, skip_first)] — every in-distribution call that may reach f."""
        out = [(c, m, cf, 0) for c, m, cf in s.by_fn[id(f)]]
        if f.cls is not None:
            for c, m, cf in s.by_attr[f.name]:
                v = c.func.value
                r = s.name(v.id, m, cf) if isinstance(v, ast.Name) else None
                if resolved_only:
                    t = s.call_target(c, m, cf)
                    if not (t and t[0] == "meth" and t[1] is f):
                        continue
                unbound = isinstance(r, Cls) and not f.classm
                skip = 0 if (f.static or unbound) else 1
                out.append((c, m, cf, -1 if skip else 0))
        # skip encoding: 0 = no implicit first arg, -1 = the receiver fills params[0]
        return out


def _module_level_nodes(tree):
    return [n for n in _body_nodes(tree.body)]


def _enclosing_cls(fn):
    while fn is not None:
        if fn.cls is not None:
            return fn.cls
        fn = fn.outer
    return None


# ---------------------------------------------------------------- leaves
class Leaf(tuple):
    pass


def L(kind, node, *rest):
    return Leaf((kind, node) + rest)


class Analyzer:
    def __init__(s, pkg, fields=False, summaries=True, optimistic=False):
        # optimistic: a LOOSE UPPER BOUND, not a design. No escape check, and
        # only call sites the graph resolves (self/cls/super/Class receivers,
        # imported names); every `obj.m(...)` with an unknown receiver ignored.
        s.p, s.fields, s.summaries, s.optimistic = pkg, fields, summaries, optimistic
        s.memo = {}
        s.bad_site_kinds = BAD_SITE_KINDS

    def leaves(s, e, mod, fn, seen, depth=0):
        p = s.p
        if depth > MAX_DEPTH:
            return [L("deep", e)]
        rec = lambda x: s.leaves(x, mod, fn, seen, depth + 1)  # noqa: E731
        if e is None:
            return []
        if isinstance(e, ast.Constant):
            return []
        if isinstance(e, ast.JoinedStr):
            return [l for v in e.values for l in rec(v)]
        if isinstance(e, ast.FormattedValue):
            return rec(e.value)
        if isinstance(e, ast.BinOp):
            return rec(e.left) + rec(e.right)
        if isinstance(e, ast.UnaryOp):
            return rec(e.operand)
        if isinstance(e, (ast.BoolOp,)):
            return [l for v in e.values for l in rec(v)]
        if isinstance(e, ast.Compare):
            return []
        if isinstance(e, ast.IfExp):
            return rec(e.body) + rec(e.orelse)
        if isinstance(e, (ast.Tuple, ast.List, ast.Set)):
            return [l for v in e.elts for l in rec(v)]
        if isinstance(e, ast.Dict):
            return [l for v in e.keys + e.values if v is not None for l in rec(v)]
        if isinstance(e, ast.Await):
            return rec(e.value)
        if isinstance(e, ast.NamedExpr):
            return rec(e.value)
        if isinstance(e, ast.Starred):
            return [L("starred", e)]
        if isinstance(e, ast.Name):
            r = p.name(e.id, mod, fn)
            if isinstance(r, tuple) and r[0] in ("param", "local"):
                f = r[1]
                key = (id(f), e.id)
                if key in seen:
                    return []           # a cycle adds no new leaf; the others decide
                seen = seen | {key}
                out = [L("param", e, f, e.id)] if e.id in f.params else []
                for v in f.binds.get(e.id, []):
                    out += [L("local-other", e)] if v is None else s.leaves(v, f.mod, f, seen, depth + 1)
                return out
            if isinstance(r, tuple) and r[0] == "var":
                m, nm = r[1], r[2]
                key = (m.name, nm)
                if key in seen:
                    return []
                seen = seen | {key}
                out = []
                for v in m.binds[nm]:
                    out += [L("global-other", e)] if v is None else s.leaves(v, m, None, seen, depth + 1)
                return out
            if isinstance(r, (Fn, Cls)):
                return [L("fnobj", e)]
            return [L("global-other", e)]
        if isinstance(e, ast.Attribute):
            if isinstance(e.value, ast.Name) and e.value.id in ("self", "cls"):
                return [L("self.attr", e, _enclosing_cls(fn), e.attr)]
            d = p.dotted(e.value, mod, fn)
            if d in p.mods:
                t = p.symbol(d, e.attr)
                if isinstance(t, tuple) and t[0] == "var":
                    return s.leaves(ast.Name(e.attr, ast.Load()), t[1], None, seen, depth + 1)
            return [L("attr", e)]
        if isinstance(e, ast.Subscript):
            return [L("subscript", e)]
        if isinstance(e, ast.Call):
            t = p.call_target(e, mod, fn)
            if t and t[0] == "ext" and sanitizer(t[1]):
                return [L("sanitizer", e, t[1])]
            if t and t[0] == "fn":
                return [L("pkgcall", e, t[1], mod, fn, 0)]
            if t and t[0] == "meth" and t[1] is not None:
                return [L("pkgcall", e, t[1], mod, fn, 1)]
            f = e.func
            tail = _tail(f)
            if (t and t[0] == "ext" and t[1].split(".")[-1] in ("text", "literal_column")) or \
                    (isinstance(f, ast.Attribute) and f.attr == "text"):
                return rec(e.args[0]) if e.args else []      # sqlalchemy text(): pass-through
            if isinstance(f, ast.Attribute) and f.attr in STR_METHODS:
                return rec(f.value) + [l for a in e.args for l in rec(a)] + \
                    [l for k in e.keywords for l in rec(k.value)]
            if isinstance(f, ast.Name) and t and t[0] == "ext" and tail in PURE_BUILTINS:
                return [l for a in e.args for l in rec(a)]
            return [L("extcall", e, (t[1] if t and t[0] == "ext" else tail))]
        return [L("other:" + type(e).__name__, e)]

    # ---- safety: returns (tier, used_nodes) or None
    def safe_expr(s, e, mod, fn, env, stack):
        tier, used = SOUND, []
        for lf in s.leaves(e, mod, fn, frozenset()):
            r = s.safe_leaf(lf, env, stack)
            if r is None:
                return None
            tier, used = max(tier, r[0]), used + r[1]
        return tier, used

    def safe_leaf(s, lf, env, stack):
        kind, node = lf[0], lf[1]
        p = s.p
        if kind == "sanitizer":
            return SOUND, [("sanitizer", node)]
        if kind == "param":
            f, nm = lf[2], lf[3]
            if (id(f), nm) in env:                  # bound by the call being summarised
                arg, amod, afn, aenv = env[(id(f), nm)]
                if arg is None:
                    return None
                r = s.safe_expr(arg, amod, afn, aenv, stack)
                return None if r is None else (r[0], [("param", node)] + r[1])
            key = ("param", id(f), nm)
            if key in stack:
                return None
            if key not in s.memo:
                s.memo[key] = s._param(f, nm, stack | {key})
            r = s.memo[key]
            return None if r is None else (r[0], [("param", node)])
        if kind == "pkgcall" and s.summaries:
            g, cmod, cfn, via_self = lf[2], lf[3], lf[4], lf[5]
            key = ("ret", id(g), id(node))
            if key in stack or len(stack) > 40 or g.gen:
                return None
            disp = SOUND
            if via_self or g.cls is not None:
                if g.cls is not None and any(
                        g.name in c.methods for c in p.classes
                        if c is not g.cls and g.cls in _all_bases(p, c)):
                    return None                     # overridden inside the distribution
                # A subclass anywhere may override the helper; an external
                # BASE does not matter here (it calls, it does not replace).
                disp = CONV if g.name.startswith("_") else UNSOUND
            # bind g's parameters to this call's arguments
            skip = 1 if (g.cls is not None and not g.static and isinstance(node.func, ast.Attribute)) else 0
            genv = {}
            for pn in g.params:
                genv[(id(g), pn)] = (_arg_for(g, pn, node, skip), cmod, cfn, env)
            tier, used = disp, [("pkgcall", node)]
            for rv in g.returns or [ast.Constant(None)]:
                r = s.safe_expr(rv, g.mod, g, genv, stack | {key})
                if r is None:
                    return None
                tier = max(tier, r[0])
            return tier, used
        if kind == "self.attr" and s.fields:
            cls, attr = lf[2], lf[3]
            key = ("field", id(cls), attr)
            if key in stack or cls is None:
                return None
            if key not in s.memo:
                s.memo[key] = s._field(cls, attr, stack | {key})
            r = s.memo[key]
            return None if r is None else (r[0], [("self.attr", node)])
        return None

    def explain_pkgcall(s, lf):
        """Why a package-function call at the sink is not literal-shaped:
        the unsafe leaf kinds of its returns ('caller-arg' = a parameter
        whose argument at this call is itself unsafe)."""
        g, cmod, cfn = lf[2], lf[3], lf[4]
        if g.gen:
            return {"generator"}
        if g.cls is not None and any(g.name in c.methods for c in s.p.classes
                                     if c is not g.cls and g.cls in _all_bases(s.p, c)):
            return {"overridden in the distribution"}
        skip = 1 if (g.cls is not None and not g.static and isinstance(lf[1].func, ast.Attribute)) else 0
        genv = {(id(g), pn): (_arg_for(g, pn, lf[1], skip), cmod, cfn, {}) for pn in g.params}
        out = set()
        for rv in g.returns or [ast.Constant(None)]:
            for l in s.leaves(rv, g.mod, g, frozenset()):
                if s.safe_leaf(l, genv, frozenset()) is None:
                    out.add("caller-arg" if l[0] == "param" and (id(l[2]), l[3]) in genv else l[0])
        return out or {"recursion/depth"}

    def explain_param(s, f, nm):
        """(visibility class, why a parameter is or is not cleared)."""
        p = s.p
        dunder = f.name.startswith("__") and f.name.endswith("__")
        vis = "nested" if f.outer is not None and f.cls is None else             "dunder" if dunder else "private" if f.name.startswith("_") else "public"
        if vis in ("private", "public") and f.cls is not None and p.external_base(f.cls):
            vis += "+extbase"
        if nm in f.star:
            return vis, "*args/**kw parameter"
        if any(_tail(d) not in TRIVIAL_DECOS for d in f.decos):
            return vis, "decorated (called by a framework)"
        if dunder:
            return vis, "dunder (called implicitly)"
        if id(f) in p.escaped_fn or (f.cls is not None and f.name in p.escaped_attr):
            return vis, "referenced as a value"
        sites = p.sites(f)
        if not sites:
            return vis, "no caller in the distribution"
        stack = frozenset({("param", id(f), nm)})
        args = [(_arg_for(f, nm, c, 1 if k == -1 else 0), m, cf) for c, m, cf, k in sites]
        if any(a is None for a, _, _ in args):
            return vis, "a caller passes *args/**kw or omits it"
        bad = [(a, m, cf) for a, m, cf in args if s.safe_expr(a, m, cf, {}, stack) is None]
        if bad:
            for a, m, cf in bad:
                kinds = {l[0] for l in s.leaves(a, m, cf, frozenset())
                         if s.safe_leaf(l, {}, stack) is None}
                for k in kinds:
                    s.bad_site_kinds[k] += 1
            return vis, "a caller passes a non-literal"
        return vis, "every caller passes a literal/sanitized value"

    def _param(s, f, nm, stack):
        vis = UNSOUND if s.optimistic else s.p.visibility(f)
        if vis is None or nm in f.star:
            return None
        sites = s.p.sites(f, resolved_only=s.optimistic)
        if not sites:
            return None
        tier = vis
        for call, mod, cfn, skip in sites:
            arg = _arg_for(f, nm, call, 1 if skip == -1 else 0)
            if arg is None:
                return None
            r = s.safe_expr(arg, mod, cfn, {}, stack)
            if r is None:
                return None
            tier = max(tier, r[0])
        return tier, []

    def _field(s, cls, attr, stack):
        """Every store to `<x>.attr` in the distribution, plus a class-level binding."""
        p = s.p
        tier = CONV if attr.startswith("_") else UNSOUND
        stores = 0
        for v in cls.class_binds.get(attr, []):
            if v is None:
                return None
            r = s.safe_expr(v, cls.mod, None, {}, stack)
            if r is None:
                return None
            stores += 1
        fam = {id(cls)} | {id(c) for c in p.classes if cls in _all_bases(p, c)}             | {id(b) for b in _all_bases(p, cls)}
        for f in p.fns:
            if s.optimistic and id(_enclosing_cls(f)) not in fam:
                continue
            for n in _body_nodes(f.node.body):
                tgts = n.targets if isinstance(n, ast.Assign) else \
                    [n.target] if isinstance(n, (ast.AnnAssign, ast.AugAssign)) else []
                for t in tgts:
                    for tt in ([t] if not isinstance(t, (ast.Tuple, ast.List)) else t.elts):
                        if isinstance(tt, ast.Attribute) and tt.attr == attr:
                            if s.optimistic and not (isinstance(tt.value, ast.Name) and tt.value.id == "self"):
                                continue
                            if isinstance(t, (ast.Tuple, ast.List)) or n.value is None:
                                return None
                            r = s.safe_expr(n.value, f.mod, f, {}, stack)
                            if r is None:
                                return None
                            tier, stores = max(tier, r[0]), stores + 1
                if isinstance(n, ast.Call) and _tail(n.func) == "setattr" and not s.optimistic:
                    return None
        return (tier, []) if stores else None


def _all_bases(p, c, seen=None):
    seen = seen or set()
    out = []
    for b in p.bases(c):
        if id(b) not in seen:
            seen.add(id(b))
            out += [b] + _all_bases(p, b, seen)
    return out


def _arg_for(f, nm, call, skip):
    """The expression `call` passes for parameter `nm` of `f`, its default,
    or None when unknown (*args/**kw at the site, or missing)."""
    if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
        return None
    for k in call.keywords:
        if k.arg == nm:
            return k.value
    if nm in f.pos:
        i = f.pos.index(nm) - skip
        if 0 <= i < len(call.args):
            return call.args[i]
    return f.defaults.get(nm)


# ---------------------------------------------------------------- findings
def sink_call(tree, line, col, callee):
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and n.lineno == line]
    for c in calls:
        if c.col_offset == col - 1:
            return c
    leaf = (callee or "").rsplit(".", 1)[-1]
    for c in calls:
        if _tail(c.func) == leaf:
            return c
    return calls[0] if calls else None


def sink_arg(call):
    if call.args:
        return call.args[0]
    return call.keywords[0].value if call.keywords else None


def fn_at(pkg, mod, line):
    best = None
    for f in pkg.fns:
        if f.mod is mod and f.node.lineno <= line <= (f.node.end_lineno or f.node.lineno):
            if best is None or f.node.lineno > best.node.lineno:
                best = f
    return best


def orig_bucket(tree, fn_node, line, params):
    """The 2026-10-02 classify.py bucket (direct parameter / local call at the sink)."""
    calls = [n for n in ast.walk(fn_node or tree) if isinstance(n, ast.Call)
             and n.lineno <= line <= (n.end_lineno or n.lineno)]
    args = [a for c in calls for a in c.args[:2]] + [k.value for c in calls for k in c.keywords]
    defs = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for a in args:
        if isinstance(a, ast.Name) and a.id in params:
            return "param"
        if isinstance(a, ast.Call):
            nm = a.func.id if isinstance(a.func, ast.Name) else (
                a.func.attr if isinstance(a.func, ast.Attribute) and isinstance(a.func.value, ast.Name)
                and a.func.value.id in ("self", "cls") else None)
            if nm in defs:
                return "local-call"
    return "other"


def count_findings(src_text, code, fn_name, tmpdir, tag):
    path = os.path.join(tmpdir, f"{tag}.py")
    open(path, "w", encoding="utf-8").write(src_text)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = subprocess.run([sys.executable, "-B", "-m", "transpiler.aether.cli", "--json", "check-py", path],
                       cwd=root, capture_output=True, text=True, encoding="utf-8")
    d = json.loads(r.stdout)
    return sum(1 for f in d["files"] for x in f["diagnostics"]
               if x["code"] == code and (x.get("extra") or {}).get("function") == fn_name)


def main():
    fw, SRC = sys.argv[1], sys.argv[2]
    verify = "--verify" in sys.argv
    rows = json.load(open(fw, encoding="utf-8"))["findings"]
    by_dist = collections.defaultdict(list)
    for r in rows:
        by_dist[r["dist"]].append(r)
    res = []
    for dist, fs in sorted(by_dist.items()):
        pkg = Package(os.path.join(SRC, dist), dist if "--site" in sys.argv else "")
        cfg = {"params": Analyzer(pkg, fields=False, summaries=False),
               "params+summaries": Analyzer(pkg, fields=False, summaries=True),
               "params+summaries+fields": Analyzer(pkg, fields=True, summaries=True),
               "LOOSE-UPPER-BOUND": Analyzer(pkg, fields=True, summaries=True, optimistic=True)}
        for f in fs:
            mod = next((m for m in pkg.mods.values() if m.path == f["file"]), None)
            out = {"dist": dist, "file": f["file"], "line": f["line"], "code": f["code"],
                   "function": f["extra"].get("function")}
            res.append(out)
            if mod is None:
                out["kind"] = "unparsed"
                continue
            fn = fn_at(pkg, mod, f["line"])
            call = sink_call(mod.tree, f["line"], f["col"], f["extra"].get("callee"))
            arg = sink_arg(call) if call else None
            out["orig"] = orig_bucket(mod.tree, fn.node if fn else None, f["line"], fn.params if fn else set())
            if arg is None:
                out["kind"] = "no-arg"
                continue
            lv = cfg["params"].leaves(arg, mod, fn, frozenset())
            out["leaf_kinds"] = sorted({l[0] for l in lv})
            out["pkgcall_fns"] = sorted({l[2].qual() for l in lv if l[0] == "pkgcall"})
            out["pkgcall_xmod"] = any(l[0] == "pkgcall" and l[2].mod is not mod for l in lv)
            ps = cfg["params+summaries"]
            out["pkgcall_why"] = sorted({w for l in lv if l[0] == "pkgcall"
                                         and ps.safe_leaf(l, {}, frozenset()) is None
                                         for w in ps.explain_pkgcall(l)})
            for name, an in cfg.items():
                r = an.safe_expr(arg, mod, fn, {}, frozenset())
                # Cleared only when an interprocedural fact was needed: a
                # sanitizer-only argument is an intraprocedural matter.
                ipa = r is not None and any(k in IPA_KINDS for k, _ in r[1])
                out[name] = TIER[r[0]] if ipa else None
                if r is not None and lv and not ipa:
                    out["intra_only"] = True
                if ipa and name == "params+summaries+fields":
                    out["used"] = r[1]
            out["param_why"] = sorted({cfg["params+summaries"].explain_param(l[2], l[3])
                                       for l in lv if l[0] == "param"})
            out["_ctx"] = (pkg, mod, fn)
    report(res)
    if "--dump" in sys.argv:
        json.dump([{k: v for k, v in r.items() if k not in ("_ctx", "used")} for r in res],
                  open(sys.argv[sys.argv.index("--dump") + 1], "w", encoding="utf-8"), indent=1)
    if verify:
        do_verify(res)


def report(res):
    n = len(res)
    print(f"findings {n}")
    print("orig bucket:", collections.Counter(r.get("orig") for r in res).most_common())
    kinds = collections.Counter()
    for r in res:
        for k in r.get("leaf_kinds", []):
            kinds[k] += 1
    print("findings with a leaf of kind:", kinds.most_common())
    print("findings whose sink argument has no non-literal leaf:",
          sum(1 for r in res if r.get("leaf_kinds") == []))
    for cfgname in ("params", "params+summaries", "params+summaries+fields", "LOOSE-UPPER-BOUND"):
        c = collections.Counter(r.get(cfgname) for r in res)
        cum = {t: sum(c[x] for x in TIER.values() if list(TIER.values()).index(x) <= i)
               for i, t in enumerate(TIER.values())}
        print(f"\n[{cfgname}] cleared, cumulative by tier: {cum}")
        by_orig = collections.Counter((r.get("orig"), r.get(cfgname)) for r in res if r.get(cfgname))
        print("  by orig bucket:", dict(by_orig))
    # item 3 — 'other' findings with a package-function call among the leaves
    oth = [r for r in res if r.get("orig") == "other"]
    withpc = [r for r in oth if "pkgcall" in r.get("leaf_kinds", [])]
    print(f"\n'other' bucket {len(oth)}; with a package-function call in the argument's leaves: {len(withpc)}")
    print("  of those, cleared by params+summaries:",
          collections.Counter(r.get("params+summaries") for r in withpc))
    pc = [r for r in res if "pkgcall" in r.get("leaf_kinds", [])]
    print(f"\nfindings with a package-function call in the judged argument: {len(pc)} "
          f"(cross-module: {sum(1 for r in pc if r['pkgcall_xmod'])}; "
          f"orig 'local-call': {sum(1 for r in pc if r.get('orig') == 'local-call')})")
    print("  cleared [params+summaries]:", collections.Counter(r.get("params+summaries") for r in pc))
    print("  why a helper's result is not literal-shaped (per finding, a finding may count twice):",
          collections.Counter(w for r in pc for w in r["pkgcall_why"]).most_common())
    lc = [r for r in res if r.get("orig") == "local-call"]
    print(f"  the {len(lc)} orig 'local-call' findings:",
          collections.Counter(r.get("params+summaries") for r in lc),
          collections.Counter(w for r in lc for w in r.get("pkgcall_why", [])).most_common())
    # item 1 — parameter findings by the visibility of the function
    par = [r for r in res if "param" in r.get("leaf_kinds", [])]
    print(f"\nfindings with a parameter leaf: {len(par)}")
    for k in ("params", "params+summaries+fields"):
        print(f"  cleared [{k}]:", collections.Counter(r.get(k) for r in par))
    print("  (visibility, reason) over distinct parameters, counted per finding:")
    for (v, w), c in collections.Counter(w for r in par for w in r["param_why"]).most_common():
        print(f"    {c:4d}  {v:16s} {w}")
    dp = [r for r in res if r.get("orig") == "param"]
    print(f"  the {len(dp)} findings with a parameter directly at the sink (orig bucket 'param'):")
    for (v, w), c in collections.Counter(
            w for r in dp for w in (r.get("param_why") or [("-", "no parameter in the judged argument")])).most_common():
        print(f"    {c:4d}  {v:16s} {w}")
    print("  blocking leaf kinds in non-literal caller arguments (per call site):",
          BAD_SITE_KINDS.most_common())
    print("\nsanitizer/literal-only arguments (no IPA needed; not counted):",
          sum(1 for r in res if r.get("intra_only")))
    for r in res:
        if r.get("LOOSE-UPPER-BOUND") and not r.get("params+summaries+fields"):
            print(f"  loose bound only: {r['code']} {r['dist']}/{r['file']}:{r['line']} {r['function']}")
    cleared = [r for r in res if r.get("params+summaries+fields")]
    print("\ncleared findings (any tier):")
    for r in cleared:
        print(f"  {r['params+summaries+fields']:10s} {r['code']} {r['dist']}/{r['file']}:{r['line']} "
              f"{r['function']} leaves={r['leaf_kinds']} p={r['params']} ps={r['params+summaries']}")


def do_verify(res):
    cleared = [r for r in res if r.get("params+summaries+fields")]
    groups = collections.defaultdict(list)
    for r in cleared:
        groups[(r["dist"], r["file"], r["function"], r["code"])].append(r)
    tmp = tempfile.mkdtemp(prefix="ipa_cf_")
    print(f"\ncounterfactual check ({len(groups)} function/code groups):")
    confirmed = 0
    for i, ((dist, file, fname, code), rs) in enumerate(sorted(groups.items())):
        pkg, mod, fn = rs[0]["_ctx"]
        ids = {id(n) for r in rs for k, n in r["used"] if k in ("param", "pkgcall", "self.attr")}
        before = count_findings(ast.unparse(_clone(mod.tree, set())), code, fname, tmp, f"b{i}")
        tree2 = _clone(mod.tree, ids)
        after = count_findings(ast.unparse(tree2), code, fname, tmp, f"a{i}")
        ok = before - after
        confirmed += min(ok, len(rs))
        print(f"  {dist}/{file} {fname} {code}: claimed {len(rs)}, before {before}, after {after}")
    print(f"confirmed cleared by counterfactual: {confirmed} of {len(cleared)} claimed")


def _clone(tree, ids):
    """A copy of `tree` with the nodes in `ids` replaced by a str literal.
    deepcopy changes ids, so the two trees are walked in lockstep."""
    import copy
    clone = copy.deepcopy(tree)
    want = {id(c) for o, c in zip(ast.walk(tree), ast.walk(clone)) if id(o) in ids}
    return _subst(clone, want)


def _subst(tree, want):
    class T(ast.NodeTransformer):
        def visit(s, node):
            if id(node) in want:
                return ast.copy_location(ast.Constant("ipa"), node)
            node = super().visit(node)
            # Fold what the substitution made constant (`f"x {'ipa'}"`,
            # `"a" + "ipa"`): an IPA would hand the rule the literal itself.
            if isinstance(node, ast.JoinedStr) and all(
                    isinstance(v, ast.Constant) or (isinstance(v, ast.FormattedValue)
                                                    and isinstance(v.value, ast.Constant)
                                                    and v.conversion == -1 and v.format_spec is None)
                    for v in node.values):
                return ast.copy_location(ast.Constant("".join(
                    str(v.value if isinstance(v, ast.Constant) else v.value.value) for v in node.values)), node)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and \
                    all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in (node.left, node.right)):
                return ast.copy_location(ast.Constant(node.left.value + node.right.value), node)
            return node
    return ast.fix_missing_locations(T().visit(tree))


if __name__ == "__main__":
    main()
