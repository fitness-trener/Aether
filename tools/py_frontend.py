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

# ----------------------------------------------------------------------
# THE AUDITABLE SINK MAPPING TABLE
# ----------------------------------------------------------------------
# Python call -> the Aether SINK NAME the existing detectors already know.
# Every value here must be a sink string that appears in
# `aether.passes.detector_specs.LITERAL_OR_WRAPPER_SPECS`; an unmapped
# string matches no row and would silently do nothing.
#
# WHY MATCHING BY METHOD NAME IS LEGITIMATE HERE, having been unsound for
# purity (see the PURE_METHODS note further down):
#   Clearing `obj.append()` as pure from the method NAME, with no proof of
#   the receiver's type, certified a capability-using module CLEAN — a
#   silent false negative, the contract-breach class (trap_04).
#   Treating `cursor.execute(...)` as a SQL sink from the method name,
#   with exactly the same absence of proof, can only produce a finding on
#   code that was not a sink — an over-flag.
#   One rule covers both: never assume clean from a name; freely assume
#   dangerous from a name. The asymmetry is not a double standard, it is
#   the direction of the error.

SINK_BY_QUALIFIED: Dict[str, str] = {
    "os.system": "shellExec", "os.popen": "shellExec",
    "pickle.loads": "deserialize", "pickle.load": "deserialize",
    "marshal.loads": "deserialize", "shelve.open": "deserialize",
    "flask.render_template_string": "renderTemplate",
    "jinja2.Template": "renderTemplate",
    "django.template.Template": "renderTemplate",
    "flask.redirect": "redirect",
    "django.shortcuts.redirect": "redirect",
    "lxml.etree.fromstring": "parseXml", "lxml.etree.parse": "parseXml",
    "lxml.etree.XML": "parseXml",
    "xml.etree.ElementTree.fromstring": "parseXml",
    "xml.etree.ElementTree.parse": "parseXml",
    "xml.dom.minidom.parseString": "parseXml",
}

# Calls whose sink status depends on an argument — never mapped blindly.
#   subprocess.*  : a shell sink ONLY with shell=True (an argv list never
#                   reaches a shell, which is the documented fix).
#   yaml.load     : a deserialization sink ONLY without an explicit safe
#                   Loader (PyYAML 5.1+ requires one; that IS the fix).
SINK_GATED_SUBPROCESS = {"subprocess.run", "subprocess.call",
                         "subprocess.check_call", "subprocess.check_output",
                         "subprocess.Popen"}
SINK_GATED_YAML = {"yaml.load", "yaml.full_load", "yaml.unsafe_load"}

# Method name on a receiver of unresolved type -> sink (over-flag direction).
SINK_BY_METHOD: Dict[str, str] = {
    "execute": "sqlQuery", "executemany": "sqlQuery",
    "executescript": "sqlExec", "raw": "sqlQuery",
}

# Builtins that are sinks.
SINK_BY_BUILTIN: Dict[str, str] = {"open": "readFile"}

# Python's sanctioned exits, mapped onto Aether's wrapper names so a fixed
# call site reads as clean instead of as an unknown call.
SANITIZER_BY_QUALIFIED: Dict[str, str] = {
    "shlex.quote": "shellArg", "pipes.quote": "shellArg",
    "yaml.safe_load": "schemaDecode",
    "json.loads": "schemaDecode", "json.load": "schemaDecode",
    "werkzeug.utils.secure_filename": "safeJoin",
    "flask.render_template": "trusted",
    "urllib.parse.quote": "trusted", "urllib.parse.quote_plus": "trusted",
    "html.escape": "trusted", "markupsafe.escape": "trusted",
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


# ----------------------------------------------------------------------
# EXPRESSION TRANSLATION
# ----------------------------------------------------------------------
# The detectors in `aether.passes.detector_specs` judge argument SHAPES:
# a fixed StringLit passes, a `+` concatenation is refused, a sanctioned
# wrapper call passes, an unknown expression is refused. Translating
# Python expressions into exactly those shapes is what lets the untouched
# Aether detectors run on Python.
#
# Anything not modeled becomes `PyExpr`, a kind no rule knows. `_arg_reason`
# falls through to `rule.default` for it — REFUSED, not cleared. That is the
# same direction as the UNPROVABLE discipline above: never assume clean.

def _pos(node: Any, fallback: int = 0) -> Dict[str, int]:
    return {"line": getattr(node, "lineno", fallback),
            "column": getattr(node, "col_offset", 0) + 1}


def _concat(parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Left-nested `+` tree over `parts` (>=1)."""
    out = parts[0]
    for p in parts[1:]:
        out = {"kind": "BinOp", "op": "+", "left": out, "right": p}
    return out


def _expr(node: Any, imp: "_Imports",
          safe_xml: Optional[Set[str]] = None) -> Dict[str, Any]:
    """One Python expression -> one Aether expression node. Total: always
    returns a dict, never None."""
    if isinstance(node, _pyast.Constant):
        if isinstance(node.value, str):
            return {"kind": "StringLit", "value": node.value}
        return {"kind": "PyExpr", "py": "Constant"}
    if isinstance(node, _pyast.Name):
        return {"kind": "Ident", "name": node.id}
    if isinstance(node, _pyast.BinOp):
        # `a + b` is concatenation; `"fmt" % x` builds a dynamic string and
        # is the same hazard, so it gets the same shape.
        if isinstance(node.op, _pyast.Add):
            return {"kind": "BinOp", "op": "+",
                    "left": _expr(node.left, imp, safe_xml), "right": _expr(node.right, imp, safe_xml)}
        if isinstance(node.op, _pyast.Mod) and _const_str(node.left) is not None:
            return _concat([_expr(node.left, imp, safe_xml), _expr(node.right, imp, safe_xml)])
        return {"kind": "PyExpr", "py": "BinOp"}
    if isinstance(node, _pyast.JoinedStr):
        # f-string. With >=1 FormattedValue it is a dynamic string — the
        # dominant modern injection shape — so it reaches the rules as a
        # concatenation. With none it is just a literal.
        parts: List[Dict[str, Any]] = []
        dynamic = False
        for v in node.values:
            if isinstance(v, _pyast.FormattedValue):
                dynamic = True
                parts.append(_expr(v.value, imp, safe_xml))
            elif isinstance(v, _pyast.Constant) and isinstance(v.value, str):
                parts.append({"kind": "StringLit", "value": v.value})
            else:
                dynamic = True
                parts.append({"kind": "PyExpr", "py": "FormattedValue"})
        if not parts:
            return {"kind": "StringLit", "value": ""}
        if not dynamic:
            return {"kind": "StringLit",
                    "value": "".join(p.get("value", "") for p in parts)}
        return _concat(parts)
    if isinstance(node, _pyast.Call):
        return _call_expr(node, imp, safe_xml)
    return {"kind": "PyExpr", "py": type(node).__name__}


def _has_kw_true(call: _pyast.Call, name: str) -> bool:
    for kw in call.keywords or []:
        if kw.arg == name and isinstance(kw.value, _pyast.Constant) \
                and kw.value.value is True:
            return True
    return False


def _has_kw(call: _pyast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in call.keywords or [])


# XML parser constructors whose keyword arguments carry the XXE guard.
_XML_PARSER_CTORS = {"lxml.etree.XMLParser", "xml.sax.make_parser"}


def _safe_xml_parser_names(fn_node: Any, imp: "_Imports") -> Set[str]:
    """Names bound to an XML parser constructed with entity resolution
    OFF. Passing one of these disarms the XXE sink.

    This is the GUARD-BOUND-ELSEWHERE class: in `lxml_repro.py` the
    vulnerable and safe call sites are byte-identical
    (`etree.fromstring(raw, parser)`) and the safety lives in a DIFFERENT
    statement, in a keyword of the parser. E0727 inspects argument 0, so
    no argument-shape rule can ever see it — resolving it is the
    frontend's job, because the frontend is where the Python-specific
    knowledge belongs.

    Conservative: a name is safe only when EVERY binding to it in this
    function is an explicit `resolve_entities=False`. Rebound, computed,
    keyword absent, or constructor unknown — not safe."""
    bound: Dict[str, List[bool]] = {}
    for stmt in _pyast.walk(fn_node):
        if not isinstance(stmt, _pyast.Assign) or len(stmt.targets) != 1:
            continue
        tgt = stmt.targets[0]
        if not isinstance(tgt, _pyast.Name) or not isinstance(stmt.value, _pyast.Call):
            continue
        dotted = _callee_spelling(stmt.value.func, imp)
        if dotted not in _XML_PARSER_CTORS:
            continue
        off = any(kw.arg == "resolve_entities"
                  and isinstance(kw.value, _pyast.Constant)
                  and kw.value.value is False
                  for kw in stmt.value.keywords or [])
        bound.setdefault(tgt.id, []).append(off)
    return {n for n, flags in bound.items() if flags and all(flags)}


def _is_parameterized_query(call: _pyast.Call) -> bool:
    """`cursor.execute(sql, params)` with a second argument is the DB-API
    parameterized form — the driver binds the values, so the string is not
    the injection vector. This is Python's `sqlBind`, expressed as a call
    SHAPE rather than as a wrapper function."""
    return len(call.args) >= 2


def _sink_name(call: _pyast.Call, imp: "_Imports",
               safe_xml: Optional[Set[str]] = None) -> Optional[str]:
    """The Aether sink name for this Python call, or None."""
    dotted = _callee_spelling(call.func, imp)
    if dotted is None:
        return None
    if dotted in SINK_GATED_SUBPROCESS:
        # An argv list never reaches a shell; shell=True is the hazard.
        return "shellExec" if _has_kw_true(call, "shell") else None
    if dotted in SINK_GATED_YAML:
        # An explicit Loader= is PyYAML's own documented fix.
        return None if _has_kw(call, "Loader") else "deserialize"
    sink = SINK_BY_QUALIFIED.get(dotted)
    if sink == "parseXml":
        for a in call.args[1:]:
            if isinstance(a, _pyast.Name) and a.id in (safe_xml or set()):
                return None      # entity resolution explicitly disabled
        return sink
    if sink is not None:
        return sink
    if dotted in SINK_BY_BUILTIN:
        return SINK_BY_BUILTIN[dotted]
    # Method on an unresolved receiver: over-flag by name (see doctrine note).
    if isinstance(call.func, _pyast.Attribute):
        m = SINK_BY_METHOD.get(call.func.attr)
        if m is not None and _is_parameterized_query(call):
            return None      # DB-API parameter binding — the sanctioned exit
        return m
    return None


def _call_expr(node: _pyast.Call, imp: "_Imports",
               safe_xml: Optional[Set[str]] = None) -> Dict[str, Any]:
    """A Python call as an Aether Call node, named so the existing
    detectors recognize it: the Aether SINK name when it maps to one, the
    Aether WRAPPER name when it is a sanctioned exit, otherwise its Python
    spelling (which matches neither, so an argument that is one of these
    calls is refused — the flag-more direction)."""
    dotted = _callee_spelling(node.func, imp)
    name = (_sink_name(node, imp, safe_xml)
            or SANITIZER_BY_QUALIFIED.get(dotted or "")
            or dotted or "<expr>")
    out: Dict[str, Any] = {"kind": "Call",
                           "func": {"kind": "Ident", "name": name},
                           "args": [_expr(a, imp, safe_xml) for a in node.args],
                           "pos": _pos(node)}
    # A call used as a RECEIVER is still a call: `open(p).read()`,
    # `conn.cursor().execute(sql)`, `requests.get(u).json()`. Chaining is
    # idiomatic Python, and dropping the receiver loses the sink entirely
    # (measured: `return open(base + name).read()` reported nothing).
    # `walk` descends dict values, so parking it under a key is enough for
    # every detector to find it; `_arg_reason` only ever reads `args[i]`,
    # so it cannot mistake a receiver for an argument.
    if isinstance(node.func, _pyast.Attribute) and \
            isinstance(node.func.value, _pyast.Call):
        out["recv"] = _call_expr(node.func.value, imp, safe_xml)
    return out


def _callee_spelling(func: Any, imp: "_Imports") -> Optional[str]:
    """Dotted path for a call target, using the file's imports; falls back
    to the bare attribute/name as written."""
    if isinstance(func, _pyast.Name):
        return imp.resolve_name(func.id) or func.id
    if isinstance(func, _pyast.Attribute):
        if isinstance(func.value, _pyast.Name):
            return imp.resolve_attr(func.value.id, func.attr) or func.attr
        return func.attr
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
                 fn_line: int, safe_xml: Optional[Set[str]] = None):
        self.imp = imports
        # Names bound to an XML parser with entity resolution disabled —
        # the guard lives in a different statement than the parse call.
        self.safe_xml: Set[str] = safe_xml or set()
        self.local_fns = local_fns
        self.fn_name = fn_name
        self.fn_line = fn_line
        self.effects: List[Dict[str, Any]] = []
        self.local_calls: List[str] = []
        self.stmts: List[Dict[str, Any]] = []
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

    def visit_stmt(self, stmt: Any):
        """Collect the statements the detectors read: single-target
        assignments (the safe-name pass's input) and expression calls
        (the sink sites). Everything else contributes nothing — control
        flow is not modeled, exactly as in the Aether passes themselves."""
        if isinstance(stmt, (_pyast.Assign, _pyast.AnnAssign)):
            targets = stmt.targets if isinstance(stmt, _pyast.Assign) else [stmt.target]
            if len(targets) == 1 and isinstance(targets[0], _pyast.Name) \
                    and stmt.value is not None:
                self.stmts.append({"kind": "Let", "name": targets[0].id,
                                   "value": _expr(stmt.value, self.imp, self.safe_xml),
                                   "pos": _pos(stmt, self.fn_line)})
            return
        if isinstance(stmt, _pyast.Expr) and isinstance(stmt.value, _pyast.Call):
            self.stmts.append(_expr(stmt.value, self.imp, self.safe_xml))
            return
        if isinstance(stmt, _pyast.Return) and stmt.value is not None:
            self.stmts.append({"kind": "Return", "value": _expr(stmt.value, self.imp, self.safe_xml),
                               "pos": _pos(stmt, self.fn_line)})

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
        v = _FnVisitor(imports, simple_names, qual, line,
                       _safe_xml_parser_names(node, imports))
        # Two separate walks, deliberately. `visit_call` drives the untouched
        # capability/UNPROVABLE analysis over EVERY call anywhere in the
        # function (including inside comprehensions and nested calls);
        # `visit_stmt` builds the expression shapes the detectors judge.
        # Merging them would change what the capability pass sees.
        for sub in _pyast.walk(node):
            if isinstance(sub, _pyast.Call):
                v.visit_call(sub)
        for sub in _pyast.walk(node):
            if isinstance(sub, (_pyast.Assign, _pyast.AnnAssign, _pyast.Expr,
                                _pyast.Return)):
                v.visit_stmt(sub)
        body_calls = [{"kind": "Call",
                       "func": {"kind": "Ident", "name": c},
                       "args": [], "pos": {"line": line, "column": 1}}
                      for c in v.local_calls]
        body = v.stmts + body_calls
        decls.append({
            "kind": "FunctionDecl",
            "name": qual,
            "effects": v.effects,
            "body": body,
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
        "sink_by_qualified": SINK_BY_QUALIFIED,
        "sink_by_method": SINK_BY_METHOD,
        "sink_by_builtin": SINK_BY_BUILTIN,
        "sink_gated": {"subprocess_shell_true": sorted(SINK_GATED_SUBPROCESS),
                       "yaml_without_loader": sorted(SINK_GATED_YAML)},
        "sanitizer_by_qualified": SANITIZER_BY_QUALIFIED,
        "mode": "sound",
    }
