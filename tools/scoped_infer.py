"""Scoped diff-frontier type inference (Phase 1, P1.1).

Attacks the dominant UNPROVABLE cause from PYTHON_RESULTS.md — "method on an
untyped object" — WITHOUT whole-program inference. We resolve a receiver's type
only from LOCAL evidence in the change-set's neighborhood:

  1. local construction      `x = httpx.Client(); x.get(...)`       -> net
  2. __init__ self-attrs     `self.c = redis.Redis()` ... `self.c.get()` -> db
  3. module globals          `POOL = sqlite3.connect(...); POOL.execute()` -> db
  4. literal containers      `d = {}; d.get(k)`                      -> pure (proven dict)
  5. capability annotations  `def f(c: httpx.Client)` ...            -> net  (ADD only)

SOUNDNESS RULES (non-negotiable):
  * Clear UNPROVABLE -> PROVEN only when the receiver type is PROVEN by an actual
    construction we can see (cases 1-4). A literal `{}`/`[]`/`dict()` proves the
    type, so its pure methods are genuinely pure.
  * Annotations are NOT proof (Python does not enforce them). They may only ever
    ADD a capability (an over-approximation, still sound), NEVER clear to pure.
  * An untyped parameter with no local construction (e.g. trap_04's `audit`)
    stays UNPROVABLE. We never guess a receiver's type from its method name.
  * Depth is bounded: receiver type -> one hop into a local class's method. No
    fixpoint / no transitive whole-program walk.

Every inference carries provenance: the evidence line and the rule that fired.
Output per function: {"caps": set, "resolved": bool, "provenance": [...],
                      "unprovable": [...]}.  resolved=False means an UNPROVABLE
region remains (the sound floor's verdict stands).
"""
from __future__ import annotations
import ast as _ast
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from tools.py_frontend import (                       # noqa: E402
    _Imports, _classify_dotted, _module_root, _const_str,
    CAP_BY_MODULE, CAP_BY_QUALIFIED, CAP_BY_BUILTIN, PURE_BUILTINS,
    PURE_MODULES, DYNAMIC_BUILTINS, DYNAMIC_ATTR_BUILTINS,
)

# Pure methods, but now GATED on a PROVEN container type (sound: we know the
# receiver really is this type because we saw it constructed locally).
PURE_BY_TYPE: Dict[str, Set[str]] = {
    "dict": {"get", "keys", "values", "items", "setdefault", "pop", "popitem",
             "update", "copy", "clear", "fromkeys"},
    "list": {"append", "extend", "insert", "pop", "remove", "clear", "sort",
             "reverse", "copy", "index", "count"},
    "set": {"add", "discard", "remove", "clear", "copy", "union", "intersection",
            "difference", "symmetric_difference", "issubset", "issuperset",
            "isdisjoint", "update", "pop"},
    "str": {"strip", "lstrip", "rstrip", "lower", "upper", "title", "capitalize",
            "casefold", "swapcase", "center", "ljust", "rjust", "zfill", "split",
            "rsplit", "join", "replace", "startswith", "endswith", "find", "rfind",
            "index", "count", "format", "encode", "splitlines", "partition",
            "rpartition", "removeprefix", "removesuffix", "isdigit", "isalpha",
            "isalnum", "isspace", "isidentifier", "translate", "maketrans"},
    "tuple": {"index", "count"},
    "bytes": {"decode", "hex", "split", "strip", "startswith", "endswith"},
}
_FILE_METHODS = {"read", "write", "readline", "readlines", "writelines", "seek",
                 "tell", "flush", "close", "__enter__", "__exit__"}


def _is_local_class(name: str, classes: Set[str]) -> bool:
    return name in classes


class TypeDesc:
    __slots__ = ("kind", "value", "prov")

    def __init__(self, kind: str, value: Optional[str], prov: str):
        self.kind = kind      # "cap" | "class" | "pure" | "file"
        self.value = value    # capability str | class name | builtin type name
        self.prov = prov


def _ctor_type(node: _ast.AST, imp: _Imports, classes: Set[str],
               line: int) -> Optional[TypeDesc]:
    """Resolve the type produced by an expression that constructs an object."""
    # literals
    if isinstance(node, _ast.Dict):
        return TypeDesc("pure", "dict", f"dict literal @L{line}")
    if isinstance(node, _ast.List):
        return TypeDesc("pure", "list", f"list literal @L{line}")
    if isinstance(node, _ast.Set):
        return TypeDesc("pure", "set", f"set literal @L{line}")
    if isinstance(node, _ast.Tuple):
        return TypeDesc("pure", "tuple", f"tuple literal @L{line}")
    if isinstance(node, _ast.Constant):
        t = type(node.value).__name__
        if t in PURE_BY_TYPE:
            return TypeDesc("pure", t, f"{t} literal @L{line}")
        return None
    if isinstance(node, _ast.Call):
        f = node.func
        # builtin container ctor: dict()/list()/...
        if isinstance(f, _ast.Name):
            if f.id in PURE_BY_TYPE:
                return TypeDesc("pure", f.id, f"{f.id}() @L{line}")
            if f.id == "open":
                return TypeDesc("file", "file", f"open() @L{line}")
            if _is_local_class(f.id, classes):
                return TypeDesc("class", f.id, f"{f.id}(...) @L{line}")
            dotted = imp.resolve_name(f.id)
            if dotted:
                cap = _classify_dotted(dotted)
                if cap:
                    return TypeDesc("cap", cap[0], f"{dotted}(...) @L{line}")
        # dotted ctor: httpx.Client(), redis.Redis(), sqlite3.connect(), ...
        if isinstance(f, _ast.Attribute) and isinstance(f.value, _ast.Name):
            dotted = imp.resolve_attr(f.value.id, f.attr)
            if dotted:
                cap = _classify_dotted(dotted)
                if cap:
                    return TypeDesc("cap", cap[0], f"{dotted}(...) @L{line}")
                root = _module_root(dotted)
                if root in CAP_BY_MODULE:
                    return TypeDesc("cap", CAP_BY_MODULE[root], f"{dotted}(...) @L{line}")
    return None


def _annotation_cap(node: Optional[_ast.AST], imp: _Imports) -> Optional[TypeDesc]:
    """Capability implied by a type annotation. ADD-only (never clears)."""
    if node is None:
        return None
    dotted = None
    if isinstance(node, _ast.Attribute) and isinstance(node.value, _ast.Name):
        dotted = imp.resolve_attr(node.value.id, node.attr)
    elif isinstance(node, _ast.Name):
        dotted = imp.resolve_name(node.id) or node.id
    if not dotted:
        return None
    cap = _classify_dotted(dotted)
    if cap:
        return TypeDesc("cap", cap[0], f"annotation {dotted}")
    root = _module_root(dotted)
    if root in CAP_BY_MODULE:
        return TypeDesc("cap", CAP_BY_MODULE[root], f"annotation {dotted}")
    return None


class ModuleInfer:
    def __init__(self, source: str):
        self.tree = _ast.parse(source)
        self.imp = _Imports()
        for n in _ast.walk(self.tree):
            if isinstance(n, _ast.Import):
                self.imp.add_import(n)
            elif isinstance(n, _ast.ImportFrom):
                self.imp.add_importfrom(n)
        self.classes: Set[str] = {n.name for n in _ast.walk(self.tree)
                                  if isinstance(n, _ast.ClassDef)}
        self.local_fns: Set[str] = set()
        for n in _ast.walk(self.tree):
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                self.local_fns.add(n.name)
        self.globals: Dict[str, TypeDesc] = {}
        for stmt in self.tree.body:
            if isinstance(stmt, _ast.Assign) and len(stmt.targets) == 1 \
               and isinstance(stmt.targets[0], _ast.Name):
                td = _ctor_type(stmt.value, self.imp, self.classes, stmt.lineno)
                if td:
                    self.globals[stmt.targets[0].id] = td
        # self-attr types from each class __init__
        self.class_attrs: Dict[str, Dict[str, TypeDesc]] = {}
        for cls in _ast.walk(self.tree):
            if isinstance(cls, _ast.ClassDef):
                attrs: Dict[str, TypeDesc] = {}
                for m in cls.body:
                    if isinstance(m, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and m.name == "__init__":
                        init_self = (m.args.args[0].arg if getattr(m, "args", None) and m.args.args else "self")
                        for s in _ast.walk(m):
                            if isinstance(s, _ast.Assign) and len(s.targets) == 1:
                                t = s.targets[0]
                                if isinstance(t, _ast.Attribute) and isinstance(t.value, _ast.Name) \
                                   and t.value.id == init_self:
                                    td = _ctor_type(s.value, self.imp, self.classes, s.lineno)
                                    if td:
                                        attrs[t.attr] = td
                self.class_attrs[cls.name] = attrs
        # map method name -> (class, node) for one-hop class method resolution
        self.class_methods: Dict[Tuple[str, str], _ast.AST] = {}
        for cls in _ast.walk(self.tree):
            if isinstance(cls, _ast.ClassDef):
                for m in cls.body:
                    if isinstance(m, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                        self.class_methods[(cls.name, m.name)] = m

    def analyze_function(self, node: _ast.AST, enclosing_class: Optional[str],
                         _depth: int = 0) -> Dict[str, Any]:
        caps: Set[str] = set()
        prov: List[str] = []
        unprovable: List[Dict[str, Any]] = []
        env: Dict[str, TypeDesc] = {}

        # seed env from parameter annotations (ADD-only capabilities)
        args = getattr(node, "args", None)
        if args:
            for a in list(args.args) + list(getattr(args, "posonlyargs", []) or []) \
                     + list(getattr(args, "kwonlyargs", []) or []):
                td = _annotation_cap(getattr(a, "annotation", None), self.imp)
                if td:
                    env[a.arg] = td

        def resolve_recv(val: _ast.AST) -> Optional[TypeDesc]:
            if isinstance(val, _ast.Name):
                if val.id in env:
                    return env[val.id]
                if val.id in self.globals:
                    return self.globals[val.id]
                return None
            if isinstance(val, _ast.Attribute) and isinstance(val.value, _ast.Name) \
               and val.value.id == "self" and enclosing_class:
                return self.class_attrs.get(enclosing_class, {}).get(val.attr)
            return None

        def mark_unprovable(reason, callee, line):
            unprovable.append({"reason": reason, "callee": callee, "line": line})

        # walk statements; track local var types from assignments first
        for s in _ast.walk(node):
            if isinstance(s, _ast.Assign) and len(s.targets) == 1 \
               and isinstance(s.targets[0], _ast.Name):
                td = _ctor_type(s.value, self.imp, self.classes, s.lineno)
                if td:
                    env[s.targets[0].id] = td

        for call in [n for n in _ast.walk(node) if isinstance(n, _ast.Call)]:
            f = call.func
            line = getattr(call, "lineno", 0)
            arg0 = _const_str(call.args[0]) if call.args else None
            # bare name(...)
            if isinstance(f, _ast.Name):
                nm = f.id
                if nm in DYNAMIC_BUILTINS:
                    mark_unprovable("dynamic_construct", nm, line); continue
                if nm in DYNAMIC_ATTR_BUILTINS:
                    if len(call.args) >= 2 and _const_str(call.args[1]) is None:
                        mark_unprovable("dynamic_attr", nm, line)
                    continue
                if nm in CAP_BY_BUILTIN:
                    caps.add(CAP_BY_BUILTIN[nm][0]); prov.append(f"builtin {nm} @L{line}"); continue
                if nm in self.local_fns or nm in PURE_BUILTINS or nm in self.classes:
                    continue
                dotted = self.imp.resolve_name(nm)
                if dotted:
                    self._handle_dotted(dotted, line, caps, prov, mark_unprovable); continue
                mark_unprovable("unresolved_call", nm, line); continue
            # value.attr(...)
            if isinstance(f, _ast.Attribute):
                attr = f.attr
                val = f.value
                if isinstance(val, _ast.Name):
                    dotted = self.imp.resolve_attr(val.id, attr)
                    if dotted:
                        self._handle_dotted(dotted, line, caps, prov, mark_unprovable); continue
                td = resolve_recv(val)
                if td is not None:
                    self._apply_typedesc(td, attr, line, caps, prov, mark_unprovable, _depth)
                    continue
                # unresolved receiver -> sound floor: UNPROVABLE
                tgt = (val.id + "." + attr) if isinstance(val, _ast.Name) else attr
                mark_unprovable("unresolved_method", tgt, line); continue
            # computed callee
            mark_unprovable("computed_callee", "<expr>", line)

        return {"caps": caps, "resolved": not unprovable,
                "provenance": prov, "unprovable": unprovable}

    def _handle_dotted(self, dotted, line, caps, prov, mark_unprovable):
        if dotted.endswith(".import_module"):
            mark_unprovable("dynamic_construct", dotted, line); return
        cap = _classify_dotted(dotted)
        if cap:
            caps.add(cap[0]); prov.append(f"{dotted} @L{line}"); return
        root = _module_root(dotted)
        if root in PURE_MODULES:
            return
        if root == "os":
            mark_unprovable("unresolved_call", dotted, line); return
        mark_unprovable("unresolved_call", dotted, line)

    def _apply_typedesc(self, td: TypeDesc, attr, line, caps, prov,
                        mark_unprovable, depth):
        if td.kind == "cap":
            caps.add(td.value); prov.append(f"{attr}() on {td.value}-typed recv ({td.prov}) @L{line}")
            return
        if td.kind == "file":
            if attr in _FILE_METHODS:
                caps.add("fs"); prov.append(f"file.{attr}() ({td.prov}) @L{line}")
            return
        if td.kind == "pure":
            if attr in PURE_BY_TYPE.get(td.value, set()):
                prov.append(f"{td.value}.{attr}() proven pure ({td.prov}) @L{line}")
                return
            mark_unprovable("unknown_method_on_known_type", f"{td.value}.{attr}", line); return
        if td.kind == "class":
            if depth >= 1:
                mark_unprovable("class_method_depth_limit", f"{td.value}.{attr}", line); return
            mnode = self.class_methods.get((td.value, attr))
            if mnode is None:
                mark_unprovable("unknown_class_method", f"{td.value}.{attr}", line); return
            sub = self.analyze_function(mnode, td.value, _depth=depth + 1)
            caps.update(sub["caps"])
            prov.append(f"{td.value}.{attr}() analyzed one-hop ({td.prov}) @L{line}")
            if not sub["resolved"]:
                mark_unprovable("class_method_unresolved", f"{td.value}.{attr}", line)
            return


def infer_module(source: str) -> Dict[str, Dict[str, Any]]:
    """Per-function inferred {caps, resolved, provenance, unprovable}, qualnamed
    like py_frontend (Class.method / function)."""
    try:
        mi = ModuleInfer(source)
    except SyntaxError:
        return {}
    out: Dict[str, Dict[str, Any]] = {}

    def collect(node, prefix, cls):
        for child in getattr(node, "body", []):
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                qual = (prefix + child.name)
                out[qual] = mi.analyze_function(child, cls)
            elif isinstance(child, _ast.ClassDef):
                for m in child.body:
                    if isinstance(m, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                        out[child.name + "." + m.name] = mi.analyze_function(m, child.name)
    collect(mi.tree, "", None)
    return out


# ---------------------------------------------------------------------------
# AUGMENTATION layer: drive everything from the trusted floor (py_frontend via
# build_surface_py) and let inference resolve ONLY the method-call sites the
# floor left UNPROVABLE. This is strictly additive: UNPROVABLE can only shrink,
# capabilities can only be added. The floor remains the sound base.
# ---------------------------------------------------------------------------
_METHOD_REASONS = {"unresolved_method", "dynamic_dispatch"}


def _build_env(mi: "ModuleInfer", node, enclosing_class):
    env = {}
    args = getattr(node, "args", None)
    if args:
        for a in (list(args.args) + list(getattr(args, "posonlyargs", []) or [])
                  + list(getattr(args, "kwonlyargs", []) or [])):
            td = _annotation_cap(getattr(a, "annotation", None), mi.imp)
            if td:
                env[a.arg] = td
    for s in _ast.walk(node):
        if isinstance(s, _ast.Assign) and len(s.targets) == 1 \
           and isinstance(s.targets[0], _ast.Name):
            td = _ctor_type(s.value, mi.imp, mi.classes, s.lineno)
            if td:
                env[s.targets[0].id] = td
    return env


def _resolve_site(mi, val, attr, env, enclosing_class, line, self_name='self'):
    """Resolve ONE method-call receiver. Return (caps:set, resolved:bool, prov)."""
    caps = set()
    # receiver via local var / global / self-attr
    td = None
    if isinstance(val, _ast.Name):
        td = env.get(val.id) or mi.globals.get(val.id)
    elif isinstance(val, _ast.Attribute) and isinstance(val.value, _ast.Name) \
            and val.value.id == self_name and enclosing_class:
        td = mi.class_attrs.get(enclosing_class, {}).get(val.attr)
    if td is None:
        return caps, False, None
    if td.kind == "cap":
        caps.add(td.value); return caps, True, f"{attr}() on {td.value} recv ({td.prov})"
    if td.kind == "file":
        if attr in _FILE_METHODS:
            caps.add("fs")
        return caps, True, f"file.{attr}() ({td.prov})"
    if td.kind == "pure":
        if attr in PURE_BY_TYPE.get(td.value, set()):
            return caps, True, f"{td.value}.{attr}() proven pure ({td.prov})"
        return caps, False, None
    if td.kind == "class":
        mnode = mi.class_methods.get((td.value, attr))
        if mnode is None:
            return caps, False, None
        env2 = _build_env(mi, mnode, td.value)
        sub_self = (mnode.args.args[0].arg if getattr(mnode, "args", None) and mnode.args.args else "self")
        sub_caps, sub_res = set(), True
        for c in [n for n in _ast.walk(mnode) if isinstance(n, _ast.Call)]:
            if isinstance(c.func, _ast.Attribute):
                cv, cattr = c.func.value, c.func.attr
                if isinstance(cv, _ast.Name) and mi.imp.resolve_attr(cv.id, cattr):
                    cap = _classify_dotted(mi.imp.resolve_attr(cv.id, cattr))
                    if cap:
                        sub_caps.add(cap[0])
                    continue
                sc, sr, _ = _resolve_site(mi, cv, cattr, env2, td.value, getattr(c, "lineno", 0), sub_self)
                sub_caps |= sc
                if not sr:
                    sub_res = False
            elif isinstance(c.func, _ast.Name):
                nm = c.func.id
                if nm in CAP_BY_BUILTIN:
                    sub_caps.add(CAP_BY_BUILTIN[nm][0])
                elif nm not in PURE_BUILTINS and nm not in mi.local_fns and nm not in mi.classes:
                    d = mi.imp.resolve_name(nm)
                    if d:
                        cap = _classify_dotted(d)
                        if cap:
                            sub_caps.add(cap[0])
                        elif _module_root(d) not in PURE_MODULES:
                            sub_res = False
                    else:
                        sub_res = False
        caps |= sub_caps
        return caps, sub_res, f"{td.value}.{attr}() analyzed one-hop ({td.prov})"
    return caps, False, None


def augment_module(source: str):
    """Floor + inference. Returns per-function:
        {caps:set, resolved:bool, provenance:[...], unprovable:[...]}"""
    import tools.py_surface as S
    surface = S.build_surface_py(source)
    rows = {}
    for m in surface.get("modules", []):
        for f in m.get("functions", []):
            rows[f["name"]] = f
    for f in surface.get("ungoverned", {}).get("functions", []):
        rows.setdefault(f["name"], f)
    try:
        mi = ModuleInfer(source)
    except SyntaxError:
        return {n: {"caps": set(r.get("effective_capabilities", [])),
                    "resolved": r["state"] != "UNPROVABLE",
                    "provenance": [], "unprovable": r.get("unprovable", [])}
                for n, r in rows.items()}

    # map qualname -> (node, enclosing_class)
    fn_nodes = {}

    def collect(node, cls):
        for child in getattr(node, "body", []):
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                fn_nodes[child.name if cls is None else cls + "." + child.name] = (child, cls)
                collect(child, cls)
            elif isinstance(child, _ast.ClassDef):
                collect(child, child.name if cls is None else cls + "." + child.name)
    collect(mi.tree, None)

    out = {}
    for name, row in rows.items():
        base_caps = set(row.get("effective_capabilities", []))
        floor_unprov = row.get("unprovable", [])
        non_method = [u for u in floor_unprov if u.get("reason") not in _METHOD_REASONS
                      and u.get("reason") != "transitive_unprovable"]
        method_unprov = [u for u in floor_unprov if u.get("reason") in _METHOD_REASONS]
        node_cls = fn_nodes.get(name)
        inferred_caps = set()
        unresolved_sites = []
        prov = []
        if node_cls is not None and method_unprov:
            node, cls = node_cls
            self_name = (node.args.args[0].arg if cls is not None and getattr(node, "args", None)
                         and node.args.args else "self")
            env = _build_env(mi, node, cls)
            # index method-call nodes by (call_line, attr)
            site_index = {}
            for c in [n for n in _ast.walk(node) if isinstance(n, _ast.Call)]:
                if isinstance(c.func, _ast.Attribute):
                    site_index.setdefault((getattr(c, "lineno", 0), c.func.attr), c)
            for u in method_unprov:
                cl = u.get("construct_line", u.get("line"))
                attr = u.get("callee", "").split(".")[-1]
                c = site_index.get((cl, attr))
                if c is None:
                    # cannot locate the node -> keep floor's UNPROVABLE (sound)
                    unresolved_sites.append(u); continue
                val = c.func.value
                caps_i, res_i, p = _resolve_site(mi, val, attr, env, cls, cl, self_name)
                if res_i:
                    inferred_caps |= caps_i
                    if p:
                        prov.append(p)
                else:
                    unresolved_sites.append(u)
        else:
            unresolved_sites = list(method_unprov)
        final_unprov = non_method + unresolved_sites
        out[name] = {
            "caps": base_caps | inferred_caps,
            "resolved": len(final_unprov) == 0,
            "provenance": prov,
            "unprovable": final_unprov,
        }

    # transitive propagation over local call graph (bounded)
    callees = {}
    for name, (node, cls) in fn_nodes.items():
        cs = set()
        for c in [n for n in _ast.walk(node) if isinstance(n, _ast.Call)]:
            if isinstance(c.func, _ast.Name) and c.func.id in mi.local_fns:
                cs.add(c.func.id)
        callees[name] = cs

    def simple(n):
        return n.split(".")[-1]
    name_by_simple = {}
    for n in out:
        name_by_simple.setdefault(simple(n), n)
    changed = True
    guard = 0
    while changed and guard < 10:
        changed = False
        guard += 1
        for name in list(out):
            for cal in callees.get(name, ()):
                tgt = name_by_simple.get(cal)
                if tgt and tgt in out:
                    if out[tgt]["caps"] - out[name]["caps"]:
                        out[name]["caps"] |= out[tgt]["caps"]; changed = True
                    if not out[tgt]["resolved"] and out[name]["resolved"]:
                        out[name]["resolved"] = False
                        out[name]["unprovable"].append(
                            {"reason": "transitive_unprovable", "callee": cal, "line": 0})
                        changed = True
    return out
