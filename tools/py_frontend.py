"""Python -> Aether-IR translation frontend.

THIS FILE DOES NOT ANALYZE. It TRANSLATES Python source into the exact
dict-AST shape the existing Aether passes (`aether.passes.capability`,
`aether.passes.effects`) and the dashboard projection (`tools.alsp_surface`)
already consume, then lets those untouched passes do the proving.

The mapping from Python constructs to capability/effect signals is the
analysis surface, and it is intentionally explicit and auditable below:

    CAP_BY_MODULE      import name        -> capability        (whole module)
    CAP_BY_QUALIFIED   module.attr        -> capability        (specific call)
    CAP_BY_BUILTIN     builtin name       -> (capability,verb)
    DYNAMIC_BUILTINS   builtin name       -> reason            (UNPROVABLE)
    PURE_MODULES       import name        -> resolvable, no capability
    PURE_BUILTINS      builtin name       -> resolvable, no capability

SOUNDNESS DISCIPLINE (the whole point of the Python experiment):
  A call whose capability surface we CANNOT determine is NEVER assumed
  clean. It is emitted as an UNPROVABLE record. We only treat a call as
  capability-free when it is (a) a local function, (b) a known-pure
  builtin, or (c) a call into a known-pure module. Everything else —
  unmapped imports, methods on unknown objects, dynamic dispatch — is
  UNPROVABLE. This is why real Python may collapse to UNPROVABLE; the
  experiment is to measure exactly how much.

Output of `py_to_ir(source)`:
    (ast_dict, unprovable_map, meta)
  ast_dict       : {"kind":"Program","decls":[ModuleDecl, FunctionDecl...]}
  unprovable_map : { fn_name: [ {fn,line,granularity,callee/construct,
                                 reason,detail,needs}, ... ] }
  meta           : { "lang":"python", "module": name, "n_functions": int,
                     "pymap_version": str }
"""
from __future__ import annotations
import ast as _pyast
from typing import Any, Dict, List, Optional, Set, Tuple

PYMAP_VERSION = "py-cap-map/0.1"

# ----------------------------------------------------------------------
# THE AUDITABLE CAPABILITY MAPPING TABLE
# ----------------------------------------------------------------------
# Whole-module imports that confer a capability on ANY call through them.
CAP_BY_MODULE: Dict[str, str] = {
    # network
    "socket": "net", "ssl": "net", "http": "net", "httplib": "net",
    "urllib": "net", "urllib2": "net", "requests": "net", "httpx": "net",
    "aiohttp": "net", "websocket": "net", "websockets": "net",
    "smtplib": "net", "ftplib": "net", "telnetlib": "net", "poplib": "net",
    "imaplib": "net", "xmlrpc": "net", "grpc": "net", "paramiko": "net",
    # filesystem
    "pathlib": "fs", "shutil": "fs", "tempfile": "fs", "glob": "fs",
    "fileinput": "fs", "csv": "fs", "configparser": "fs",
    # process / exec
    "subprocess": "process", "multiprocessing": "process", "pty": "process",
    "signal": "process",
    # database
    "sqlite3": "db", "psycopg2": "db", "psycopg": "db", "pymysql": "db",
    "mysql": "db", "sqlalchemy": "db", "pymongo": "db", "redis": "db",
    "asyncpg": "db", "aioredis": "db", "cassandra": "db", "elasticsearch": "db",
    # logging
    "logging": "log",
}

# Specific dotted calls that confer a capability (finer than whole-module).
CAP_BY_QUALIFIED: Dict[str, str] = {
    "os.system": "process", "os.popen": "process", "os.spawnv": "process",
    "os.spawnl": "process", "os.exec": "process", "os.execv": "process",
    "os.execl": "process", "os.fork": "process", "os.kill": "process",
    "os.remove": "fs", "os.unlink": "fs", "os.mkdir": "fs", "os.makedirs": "fs",
    "os.rmdir": "fs", "os.removedirs": "fs", "os.rename": "fs", "os.replace": "fs",
    "os.open": "fs", "os.read": "fs", "os.write": "fs", "os.listdir": "fs",
    "os.scandir": "fs", "os.walk": "fs", "os.chmod": "fs", "os.chown": "fs",
    "os.stat": "fs", "os.truncate": "fs", "os.link": "fs", "os.symlink": "fs",
    "os.getenv": "env", "os.putenv": "env", "os.unsetenv": "env",
    "os.urandom": "random",
    "time.time": "time", "time.sleep": "time", "time.monotonic": "time",
    "time.perf_counter": "time", "time.localtime": "time", "time.gmtime": "time",
    "time.process_time": "time",
    "datetime.now": "time", "datetime.today": "time", "datetime.utcnow": "time",
    "random.random": "random", "random.randint": "random", "random.choice": "random",
    "random.shuffle": "random", "random.uniform": "random", "random.seed": "random",
    "random.randrange": "random", "random.sample": "random", "random.getrandbits": "random",
    "secrets.token_bytes": "random", "secrets.token_hex": "random",
    "secrets.token_urlsafe": "random", "secrets.choice": "random",
    "secrets.randbelow": "random", "secrets.randbits": "random",
    "uuid.uuid1": "random", "uuid.uuid4": "random",
    # I/O-performing functions that previously hid inside PURE_MODULES.
    # Mapped to their real capability so the verdict is sound AND positively
    # identified rather than merely UNPROVABLE. See PURE_MODULES audit note.
    "pprint.pprint": "log", "pprint.pp": "log",   # write to stdout (a stream)
    "warnings.warn": "log",                          # writes to sys.stderr
    "codecs.open": "fs",                             # opens a file on disk
    # env via os.environ mapping object (the .get() method form; subscript form
    # os.environ['X'] is not a call and remains out of call-based analysis)
    "os.environ.get": "env", "os.environ.setdefault": "env",
    "os.environ.pop": "env",
    # pandas file readers (the module-level read_* functions perform fs I/O;
    # DataFrame .to_* writers are methods on an untyped frame -> UNPROVABLE)
    "pandas.read_csv": "fs", "pandas.read_parquet": "fs",
    "pandas.read_excel": "fs", "pandas.read_json": "fs", "pandas.read_table": "fs",
}

# Builtins that themselves confer a capability.
CAP_BY_BUILTIN: Dict[str, Tuple[str, str]] = {
    "open": ("fs", "open"),
    "print": ("log", "print"),
    "input": ("log", "input"),
}

# Builtins that DEFEAT sound static analysis -> always UNPROVABLE.
DYNAMIC_BUILTINS: Dict[str, str] = {
    "eval": "eval", "exec": "exec", "compile": "compile",
    "__import__": "dynamic_import",
    "globals": "reflection", "locals": "reflection", "vars": "reflection",
}
# getattr/setattr/delattr are dynamic ONLY when the attribute name is not a
# constant; handled specially in the visitor.
DYNAMIC_ATTR_BUILTINS = {"getattr", "setattr", "delattr"}

# Imports that are pure (CPU only, no capability) -> resolvable, no effect.
#
# SOUNDNESS AUDIT (P0.1): every entry below must perform NO I/O at module or
# call scope. Three former entries were removed because they CAN do I/O and
# were therefore unsound to trust wholesale:
#   * pprint   -> pprint.pprint/pp write to stdout  (now CAP_BY_QUALIFIED: log)
#   * warnings -> warnings.warn writes to stderr     (now CAP_BY_QUALIFIED: log)
#   * codecs   -> codecs.open opens a file           (now CAP_BY_QUALIFIED: fs)
# A bogus "dataclass" entry (not a real stdlib module; the module is
# "dataclasses") was also removed. Any *other* call into these modules now
# degrades to UNPROVABLE rather than being silently cleared.
#
# PURE_MODULE_CITATIONS gives the per-module justification (machine-readable
# provenance, surfaced via mapping_table()/the /pymap audit endpoint).
PURE_MODULE_CITATIONS: Dict[str, str] = {
    "math": "CPython Lib/math: pure C math, no I/O",
    "cmath": "complex math, no I/O",
    "json": "encode/decode in memory; file I/O happens on a caller-supplied fp (its own open() is gated)",
    "re": "regex compile/match over in-memory strings",
    "collections": "container datatypes, in-memory only",
    "itertools": "iterator algebra, in-memory only",
    "functools": "higher-order helpers (reduce/lru_cache), no I/O",
    "dataclasses": "class codegen at def time, no I/O",
    "typing": "type hints, erased at runtime, no I/O",
    "string": "string constants/templates/Formatter, no I/O",
    "decimal": "fixed-point arithmetic, no I/O",
    "fractions": "rational arithmetic, no I/O",
    "statistics": "numeric reductions over in-memory data",
    "operator": "operator functions, no I/O",
    "copy": "shallow/deep object copy, no I/O",
    "enum": "enumeration types, no I/O",
    "abc": "abstract base class machinery, no I/O",
    "numbers": "numeric tower ABCs, no I/O",
    "heapq": "heap algorithms over in-memory lists",
    "bisect": "binary search over in-memory sequences",
    "array": "typed array container; fromfile/tofile are object METHODS (UNPROVABLE), not module calls",
    "textwrap": "string wrapping/filling, no I/O",
    "base64": "byte<->ascii transforms in memory",
    "binascii": "binary/ascii conversions in memory",
    "hashlib": "cryptographic digests over in-memory bytes",
    "hmac": "keyed-hash MAC over in-memory bytes",
    "struct": "binary packing/unpacking in memory",
    "unicodedata": "Unicode database lookups, no I/O",
    "html": "HTML escaping/parsing of in-memory strings",
    "difflib": "sequence diffing in memory",
    "keyword": "Python keyword predicates, no I/O",
    "token": "tokenizer constants, no I/O",
    "graphlib": "topological sort over in-memory graph",
    "types": "dynamic type construction helpers, no I/O",
    "contextlib": "context-manager utilities; do not themselves perform I/O",
    "weakref": "weak references, no I/O",
}
PURE_MODULES: Set[str] = set(PURE_MODULE_CITATIONS)

# Pure builtins -> resolvable, no capability.
PURE_BUILTINS: Set[str] = {
    "len", "range", "str", "int", "float", "bool", "complex", "list", "dict",
    "set", "frozenset", "tuple", "bytes", "bytearray", "memoryview",
    "enumerate", "zip", "map", "filter", "sorted", "reversed", "sum", "min",
    "max", "abs", "round", "isinstance", "issubclass", "hasattr", "repr",
    "format", "ord", "chr", "hex", "oct", "bin", "divmod", "pow", "all",
    "any", "iter", "next", "type", "id", "hash", "callable", "slice",
    "object", "super", "property", "staticmethod", "classmethod", "ascii",
}

# NOTE (P0.2): the former PURE_METHODS allowlist (pragmatic mode) was DELETED.
# It cleared an unknown object's method call (e.g. `.append()`) as pure based on
# the method NAME alone, with no proof of the receiver's type. That is unsound:
# trap_04's `AuditLog.append()` opens a file and writes to disk, yet was being
# certified PROVEN_CLEAN. A method on an object of unresolved type is now ALWAYS
# UNPROVABLE. Soundness is the product; this allowlist is never coming back.


def _module_root(dotted: str) -> str:
    return dotted.split(".", 1)[0]


class _Imports:
    """Resolves a local name used in a Call back to a dotted module path or
    builtin, using the file's import statements."""
    def __init__(self):
        self.alias_to_path: Dict[str, str] = {}    # local name -> dotted path
        self.fromimport: Dict[str, str] = {}       # local name -> module.attr

    def add_import(self, node: _pyast.Import):
        for a in node.names:
            local = a.asname or _module_root(a.name)
            self.alias_to_path[local] = a.name

    def add_importfrom(self, node: _pyast.ImportFrom):
        mod = node.module or ""
        for a in node.names:
            local = a.asname or a.name
            self.fromimport[local] = (mod + "." + a.name) if mod else a.name

    def resolve_attr(self, value_name: str, attr: str) -> Optional[str]:
        """`value_name.attr` -> dotted path using import aliases."""
        base = self.alias_to_path.get(value_name)
        if base is not None:
            return base + "." + attr
        if value_name in self.fromimport:        # from x import y; y.attr
            return self.fromimport[value_name] + "." + attr
        return None

    def resolve_name(self, name: str) -> Optional[str]:
        """bare `name(...)` -> dotted path if it came from a `from` import."""
        return self.fromimport.get(name)


def _const_str(node: Any) -> Optional[str]:
    if isinstance(node, _pyast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _classify_dotted(dotted: str) -> Optional[Tuple[str, str]]:
    """Return (capability, verb) for a dotted call path, or None if not a
    known capability. Checks exact qualified entry, then module root, then
    os.exec* prefix."""
    if dotted in CAP_BY_QUALIFIED:
        return (CAP_BY_QUALIFIED[dotted], dotted.split(".")[-1])
    root = _module_root(dotted)
    if root in CAP_BY_MODULE:
        return (CAP_BY_MODULE[root], dotted.split(".")[-1])
    if dotted.startswith("os.exec") or dotted.startswith("os.spawn"):
        return ("process", dotted.split(".")[-1])
    return None


class _FnVisitor:
    """Walk one function body and emit (effects, local_calls, unprovable)."""
    def __init__(self, imports: _Imports, local_fns: Set[str], fn_name: str,
                 fn_line: int):
        self.imp = imports
        self.local_fns = local_fns
        self.fn_name = fn_name
        self.fn_line = fn_line
        self.effects: List[Dict[str, Any]] = []
        self.local_calls: List[str] = []
        self.unprovable: List[Dict[str, Any]] = []
        self._eff_seen: Set[Tuple[str, str, Optional[str]]] = set()
        self._unp_seen: Set[str] = set()

    def _add_effect(self, cap: str, verb: str, arg: Optional[str]):
        key = (cap, verb, arg)
        if key in self._eff_seen:
            return
        self._eff_seen.add(key)
        eff: Dict[str, Any] = {"path": [cap, verb]}
        if arg is not None:
            eff["arg"] = {"kind": "StringLit", "value": arg}
        self.effects.append(eff)

    def _add_unprovable(self, reason: str, construct: str, detail: str,
                        line: int):
        key = reason + ":" + construct
        if key in self._unp_seen:
            return
        self._unp_seen.add(key)
        self.unprovable.append({
            "fn": self.fn_name, "line": self.fn_line, "granularity": "function",
            "callee": construct, "reason": reason, "detail": detail,
            "construct_line": line, "needs": "human review or a runtime check",
        })

    def visit_call(self, call: _pyast.Call):
        func = call.func
        arg0 = _const_str(call.args[0]) if call.args else None
        line = getattr(call, "lineno", self.fn_line)

        # bare name(...)
        if isinstance(func, _pyast.Name):
            name = func.id
            if name in DYNAMIC_BUILTINS:
                self._add_unprovable("dynamic_construct", name,
                    f"`{name}(...)` executes or imports code chosen at runtime; "
                    f"its capability surface cannot be determined statically", line)
                return
            if name in DYNAMIC_ATTR_BUILTINS:
                # getattr/setattr/delattr — dynamic unless attr name constant
                if len(call.args) >= 2 and _const_str(call.args[1]) is None:
                    self._add_unprovable("dynamic_attr", name,
                        f"`{name}` with a computed attribute name dispatches to "
                        f"a target unknown at analysis time", line)
                return
            if name in CAP_BY_BUILTIN:
                cap, verb = CAP_BY_BUILTIN[name]
                self._add_effect(cap, verb, arg0); return
            if name in self.local_fns:
                self.local_calls.append(name); return
            if name in PURE_BUILTINS:
                return
            dotted = self.imp.resolve_name(name)   # from-import
            if dotted is not None:
                self._handle_dotted(dotted, arg0, line); return
            # Unknown bare callable -> cannot prove capability-free.
            self._add_unprovable("unresolved_call", name,
                f"callee `{name}` is not a local function, a known-pure builtin, "
                f"or a mapped import; its capability surface is unknown", line)
            return

        # value.attr(...)
        if isinstance(func, _pyast.Attribute):
            attr = func.attr
            val = func.value
            if isinstance(val, _pyast.Name):
                dotted = self.imp.resolve_attr(val.id, attr)
                if dotted is not None:
                    self._handle_dotted(dotted, arg0, line); return
                # method on a local variable / unknown object
                self._add_unprovable("unresolved_method", val.id + "." + attr,
                    f"method `{attr}` is called on `{val.id}`, whose type is not "
                    f"resolved here; its capability surface is unknown", line)
                return
            if isinstance(val, _pyast.Attribute):
                # a.b.c(...) — try to flatten to dotted import path
                dotted = self._flatten_attr(func)
                if dotted is not None:
                    cls = _classify_dotted(dotted)
                    if cls is not None:
                        self._add_effect(cls[0], cls[1], arg0); return
                    if _module_root(dotted) in PURE_MODULES:
                        return
                self._add_unprovable("unresolved_method", attr,
                    f"chained attribute call `...{attr}(...)` could not be "
                    f"resolved to a known module path", line)
                return
            # self.method(), obj().method(), subscript().method() ...
            self._add_unprovable("dynamic_dispatch", attr,
                f"call target `{attr}` is dispatched on a runtime value "
                f"(self/expression); its effects cannot be traced statically", line)
            return

        # eval()() , (lambda...)() , etc.
        self._add_unprovable("computed_callee", "<expr>",
            "the call target is an expression, not a named function", line)

    def _flatten_attr(self, node: _pyast.Attribute) -> Optional[str]:
        parts = []
        cur: Any = node
        while isinstance(cur, _pyast.Attribute):
            parts.append(cur.attr); cur = cur.value
        if isinstance(cur, _pyast.Name):
            base = self.imp.alias_to_path.get(cur.id, cur.id)
            parts.append(base)
            return ".".join(reversed(parts))
        return None

    def _handle_dotted(self, dotted: str, arg0: Optional[str], line: int):
        if dotted == "importlib.import_module" or dotted.endswith(".import_module"):
            self._add_unprovable("dynamic_construct", dotted,
                "dynamic import selects a module at runtime; the imported "
                "capability surface is unknown", line); return
        cls = _classify_dotted(dotted)
        if cls is not None:
            self._add_effect(cls[0], cls[1], arg0); return
        root = _module_root(dotted)
        if root in PURE_MODULES:
            return
        if root == "os":
            # os.* not in the explicit table -> unknown, be honest.
            self._add_unprovable("unresolved_call", dotted,
                f"`{dotted}` is an os call not in the capability table; "
                f"treated as unknown rather than assumed safe", line); return
        # imported but unmapped module -> unknown capability surface.
        self._add_unprovable("unresolved_call", dotted,
            f"`{dotted}` comes from an unmapped import; its capability surface "
            f"is unknown and cannot be assumed empty", line)


def py_to_ir(source: str) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """Translate Python source into Aether IR + an UNPROVABLE map.

    Single sound mode only. (The former `strict`/pragmatic split was removed in
    P0.2: pragmatic mode was unsound.)"""
    tree = _pyast.parse(source)

    imports = _Imports()
    func_nodes: List[Tuple[str, Any]] = []   # (qualname, node)

    def collect(node, prefix=""):
        for child in node.body:
            if isinstance(child, _pyast.Import):
                imports.add_import(child)
            elif isinstance(child, _pyast.ImportFrom):
                imports.add_importfrom(child)
            elif isinstance(child, (_pyast.FunctionDef, _pyast.AsyncFunctionDef)):
                qual = (prefix + child.name)
                func_nodes.append((qual, child))
            elif isinstance(child, _pyast.ClassDef):
                for m in child.body:
                    if isinstance(m, (_pyast.FunctionDef, _pyast.AsyncFunctionDef)):
                        func_nodes.append((child.name + "." + m.name, m))
    collect(tree)

    local_fn_names: Set[str] = set(q for q, _ in func_nodes)
    # local-call resolution uses simple names too (module-level helpers)
    simple_names: Set[str] = set(q.split(".")[-1] for q, _ in func_nodes if "." not in q)

    decls: List[Dict[str, Any]] = []
    unprovable_map: Dict[str, List[Dict[str, Any]]] = {}
    export_names: List[str] = []

    for qual, node in func_nodes:
        line = getattr(node, "lineno", 0)
        v = _FnVisitor(imports, simple_names, qual, line)
        for sub in _pyast.walk(node):
            if isinstance(sub, _pyast.Call):
                v.visit_call(sub)
        body_calls = [{"kind": "Call",
                       "func": {"kind": "Ident", "name": c},
                       "args": [], "pos": {"line": line, "column": 1}}
                      for c in v.local_calls]
        decls.append({
            "kind": "FunctionDecl",
            "name": qual,
            "effects": v.effects,
            "body": body_calls,
            "pos": {"line": line, "column": 1},
        })
        export_names.append(qual)
        if v.unprovable:
            unprovable_map[qual] = v.unprovable

    module_name = "PythonModule"
    decls.insert(0, {
        "kind": "ModuleDecl",
        "name": module_name,
        "capabilities": [],         # default boundary: nothing allowed (policy overrides)
        "exports": export_names,
        "pos": {"line": 1, "column": 1},
    })

    ast_dict = {"kind": "Program", "decls": decls}
    meta = {"lang": "python", "module": module_name,
            "n_functions": len(func_nodes), "pymap_version": PYMAP_VERSION,
            "mode": "sound"}
    return ast_dict, unprovable_map, meta


def mapping_table() -> Dict[str, Any]:
    """Expose the capability mapping table for auditing (the /pymap endpoint)."""
    return {
        "pymap_version": PYMAP_VERSION,
        "cap_by_module": CAP_BY_MODULE,
        "cap_by_qualified": CAP_BY_QUALIFIED,
        "cap_by_builtin": {k: list(v) for k, v in CAP_BY_BUILTIN.items()},
        "dynamic_builtins": sorted(DYNAMIC_BUILTINS) + sorted(DYNAMIC_ATTR_BUILTINS),
        "pure_modules": sorted(PURE_MODULES),
        "pure_module_citations": PURE_MODULE_CITATIONS,
        "pure_builtins": sorted(PURE_BUILTINS),
        "mode": "sound",
    }
