"""Static effect-checking pass (Phase B.1 + B.2).

Walks every FunctionDecl, builds a name → declared-effects map (user
functions plus the stdlib registry below), then for each call site within
a function body verifies the callee's declared effects are covered by
the caller's declared effects. Diagnostic E0801 on violation.

B.2 update: effects can carry a literal-string argument
(e.g. `net.fetch("https://api.x/*")`). The argument is a glob that the
caller's permission must cover. Subsumption rules below.

Effect representation:
  An effect is a (path_tuple, arg_or_None) pair.
    - path_tuple: tuple of dotted-path segments, e.g. ("net", "fetch")
    - arg: literal string (typically a glob), or None if not specified

Subsumption (caller_eff ⊇ callee_eff):
  - paths must be equal, AND one of:
    1. caller_arg is None — caller permits this effect on any argument
    2. caller_arg == callee_arg — exact match
    3. caller_arg is a glob (contains `*`) and the regex derived from
       caller_arg matches callee_arg as a string

Notes / limits (v1 scope):
  - Only direct calls of named functions (`foo(x)`) are checked. Calls
    through HOFs or function-typed parameters are skipped.
  - The `pure` annotation declares the empty effect set.
  - Constructors (Some/None/Ok/Err and user-defined union cases) are pure.
  - Glob comparison is one-way: caller_arg is treated as a glob, callee_arg
    as the literal it must match. Two-glob comparison ("does caller's glob
    cover callee's glob") is approximated by string regex match — true
    glob-language subset is undecidable in general; for v1 the common case
    of "caller has the wildcard, callee has the URL" works correctly.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Set, Tuple, Iterable, Optional

from ..diagnostics import Diagnostic, Position


# (path_tuple, arg_or_None)
EffectEntry = Tuple[Tuple[str, ...], Optional[str]]


# ----------------------------------------------------------------------
# Stdlib effect registry
# ----------------------------------------------------------------------
# Tuples mirror the dotted paths emitted by `record_effect(*path)` in
# runtime.py. Pure stdlib functions are absent from this map (lookup
# returns the empty list). Stdlib effects don't carry args (no glob).

_STDLIB_EFFECTS: Dict[str, List[EffectEntry]] = {
    "print":      [(("log",),         None)],
    "readLine":   [(("log",),         None)],
    "readFile":   [(("fs", "read"),   None)],
    "writeFile":  [(("fs", "write"),  None)],
    "now":        [(("time", "now"),  None)],
    "sqlQuery":   [(("db", "query"),  None)],
    "sqlExec":    [(("db", "exec"),   None)],
    "sqlByOwner": [(("db", "exec"),   None)],
    "shellExec":  [(("exec", "run"),  None)],
    "redirect":   [(("net", "redirect"), None)],
}


def _arg_str(eff_node: Dict[str, Any]) -> Optional[str]:
    """Extract a literal-string arg from an effect AST node, or None."""
    arg = eff_node.get("arg")
    if arg is None:
        return None
    if isinstance(arg, dict) and arg.get("kind") == "StringLit":
        return arg.get("value")
    # Non-string args (rare) are not modelled; treat as no arg.
    return None


def _declared_effects(fn_decl: Dict[str, Any]) -> List[EffectEntry]:
    """Compute the effect list declared by a FunctionDecl AST node.

    `effects pure` declares the empty list. Other entries are stored as
    (path_tuple, arg_str_or_None).
    """
    out: List[EffectEntry] = []
    for eff in fn_decl.get("effects", []):
        path = tuple(eff.get("path", []))
        if not path or path == ("pure",):
            continue
        out.append((path, _arg_str(eff)))
    return out


# ----------------------------------------------------------------------
# Subsumption: does any caller effect cover this callee effect?
# ----------------------------------------------------------------------

_GLOB_REGEX_CACHE: Dict[str, re.Pattern] = {}


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Compile a glob pattern (`*` is wildcard) to a regex anchored start-to-end.

    Cached because compilation is hot-path inside the subsumption check.
    """
    cached = _GLOB_REGEX_CACHE.get(pattern)
    if cached is not None:
        return cached
    parts = ["^"]
    for c in pattern:
        if c == "*":
            parts.append(".*")
        elif c in r".+?^$()[]{}|\\":
            parts.append("\\" + c)
        else:
            parts.append(c)
    parts.append("$")
    rx = re.compile("".join(parts))
    _GLOB_REGEX_CACHE[pattern] = rx
    return rx


def _arg_covers(caller_arg: Optional[str], callee_arg: Optional[str]) -> bool:
    """Does the caller's arg permission cover the callee's arg requirement?"""
    if caller_arg is None:
        return True
    if callee_arg is None:
        # Caller is restricted; callee says it does the unrestricted form.
        return False
    if caller_arg == callee_arg:
        return True
    if "*" in caller_arg:
        return bool(_glob_to_regex(caller_arg).match(callee_arg))
    return False


def _effect_covered(caller_effects: List[EffectEntry],
                    callee_eff: EffectEntry) -> bool:
    """Does any entry in caller_effects cover this single callee entry?"""
    callee_path, callee_arg = callee_eff
    for c_path, c_arg in caller_effects:
        if c_path == callee_path and _arg_covers(c_arg, callee_arg):
            return True
    return False


# ----------------------------------------------------------------------
# E0710 — overly-broad effect scope (SSRF / capability-smuggling class)
# ----------------------------------------------------------------------
# A declared effect whose glob leaves the host/authority unpinned admits
# ANY host — including internal endpoints like the cloud metadata service
# at 169.254.169.254. That is the structural precondition of the entire
# SSRF vulnerability class (CVE-2026-53754 crawl4ai, CVE-2026-46556
# FlaskBB, and many more): a fetch scope broad enough that attacker-
# controlled input can steer it inward. E0801/E0701 are satisfied by
# such a scope, so a dedicated check refuses the broad promise itself.
#
# The rule is deliberately conservative and one-directional: it only
# fires on net.fetch effects whose WILDCARD spans the authority. Path and
# query wildcards (`https://api.x/charge/*`) and subdomain pins
# (`https://*.corp.example/*`) are host-pinned and pass untouched.

def _net_authority_wildcarded(arg: Optional[str]) -> Optional[str]:
    """If this net.fetch glob leaves the host/authority unpinned, return a
    short human reason; otherwise None (the scope is host-pinned)."""
    if arg is None:
        return "no URL scope declared - admits any host"
    if arg == "*":
        return "bare '*' - admits any host"
    if "://" in arg:
        scheme, rest = arg.split("://", 1)
        if "*" in scheme:
            return "wildcard scheme - admits any protocol and host"
    else:
        rest = arg
    # Authority = everything up to the first path/query separator.
    authority = re.split(r"[/?#]", rest, maxsplit=1)[0]
    if authority in ("", "*"):
        return "wildcard host - admits any host (e.g. 169.254.169.254)"
    # A leading '*' that is not a subdomain pin (`*.host`) spans the host.
    if authority.startswith("*") and not authority.startswith("*."):
        return "wildcard host prefix - admits arbitrary hosts"
    return None


def check_effect_scope(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0710 diagnostics for net.fetch effects with an unpinned host.

    One diagnostic per (function, broad effect). Runs on declared effects,
    so it flags the over-broad promise regardless of call sites.
    """
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        pos = d.get("pos") or {"line": 0, "column": 0}
        for path, arg in _declared_effects(d):
            if path != ("net", "fetch"):
                continue
            reason = _net_authority_wildcarded(arg)
            if reason is None:
                continue
            shown = "net.fetch" if arg is None else f"net.fetch({arg!r})"
            diags.append(Diagnostic(
                code="E0710",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} declares effect '{shown}' with an "
                    f"unpinned host ({reason}); pin the host so the scope "
                    f"cannot be steered to an internal endpoint"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    "replace the wildcard host with a concrete host, e.g. "
                    "net.fetch(\"https://api.your-service.example/path/*\"); "
                    "path/query wildcards and *.subdomain pins are allowed"
                ),
                confidence=1.0,
                extra={
                    "function": fn,
                    "effect_arg": arg,
                    "reason": reason,
                },
            ))
    return diags


# ----------------------------------------------------------------------
# E0721 — cleartext transmission (CWE-319)
# ----------------------------------------------------------------------
# A net.fetch scope with an `http://` scheme sends the request (and any
# credentials/PII in it) unencrypted — a passive network attacker reads or
# tampers with it. E0710 checks host *pinning*; a pinned `http://` host
# satisfies E0710 yet is still cleartext, so this is an orthogonal sibling.
# Loopback (localhost / 127.0.0.0/8 / ::1 / 0.0.0.0) is exempt — those
# never leave the host, so plain http there is not a transmission risk.

_LOOPBACK_HOSTS = ("localhost", "::1", "0.0.0.0")


def _net_is_cleartext(arg: Optional[str]) -> Optional[str]:
    """If this net.fetch glob transmits over cleartext http:// to a
    non-loopback host, return a short reason; otherwise None."""
    if not arg or "://" not in arg:
        return None
    scheme, rest = arg.split("://", 1)
    if scheme.lower() != "http":
        return None  # https, or a wildcard scheme (E0710's concern)
    authority = re.split(r"[/?#]", rest, maxsplit=1)[0]
    host = authority.split(":", 1)[0].lower()  # strip any :port
    if host in _LOOPBACK_HOSTS or host.startswith("127."):
        return None
    return f"http:// scheme sends '{host}' traffic unencrypted"


def check_cleartext_transmission(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0721 diagnostics for net.fetch effects using cleartext
    http:// to a non-loopback host."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        pos = d.get("pos") or {"line": 0, "column": 0}
        for path, arg in _declared_effects(d):
            if path != ("net", "fetch"):
                continue
            reason = _net_is_cleartext(arg)
            if reason is None:
                continue
            diags.append(Diagnostic(
                code="E0721",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} declares effect 'net.fetch({arg!r})' "
                    f"over cleartext ({reason}); credentials and PII in the "
                    f"request are exposed to a passive network attacker"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    "use the https:// scheme, e.g. "
                    "net.fetch(\"https://...\"); plain http is allowed only "
                    "for loopback hosts (localhost / 127.0.0.1)"
                ),
                confidence=1.0,
                extra={"function": fn, "effect_arg": arg, "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0722 — server-side request to the link-local / metadata range (CWE-918)
# ----------------------------------------------------------------------
# E0710 refuses an UNPINNED fetch scope (the wildcard SSRF precondition).
# But a scope PINNED to the link-local range 169.254.0.0/16 — which holds
# the cloud metadata endpoint 169.254.169.254 (AWS/GCP/Azure IMDS, the
# crown-jewel SSRF target for IAM-credential theft) — is host-pinned, so
# it satisfies E0710 and E0721 (if https) and slips through. Fetching that
# range from application code is almost never legitimate; this refuses it
# as a declared reach. Private RFC-1918 ranges are deliberately NOT flagged
# (legit in microservice meshes); link-local IMDS is the high-signal case.

def _net_is_link_local(arg: Optional[str]) -> Optional[str]:
    """If this net.fetch glob pins a host in 169.254.0.0/16, return a
    short reason; otherwise None."""
    if not arg:
        return None
    rest = arg.split("://", 1)[1] if "://" in arg else arg
    authority = re.split(r"[/?#]", rest, maxsplit=1)[0]
    host = authority.split(":", 1)[0]
    if host.startswith("169.254."):
        return f"link-local host {host!r} — the cloud metadata range (IMDS)"
    return None


def check_metadata_fetch(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0722 diagnostics for net.fetch effects pinned to the
    link-local / cloud-metadata range."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        pos = d.get("pos") or {"line": 0, "column": 0}
        for path, arg in _declared_effects(d):
            if path != ("net", "fetch"):
                continue
            reason = _net_is_link_local(arg)
            if reason is None:
                continue
            diags.append(Diagnostic(
                code="E0722",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} declares effect 'net.fetch({arg!r})' "
                    f"to the {reason}; a server-side request to the metadata "
                    f"endpoint exfiltrates IAM credentials (SSRF)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    "application code should never fetch 169.254.0.0/16; if a "
                    "cloud credential is needed, obtain it through the SDK/"
                    "credential provider, not a raw metadata HTTP request"
                ),
                confidence=1.0,
                extra={"function": fn, "effect_arg": arg, "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0711 — path traversal precondition (fs path built from dynamic input)
# ----------------------------------------------------------------------
# Zip-Slip / arbitrary-file-write (the entire path-traversal class) has
# one structural precondition: a filesystem path fed to a read/write
# sink that is NOT a fixed literal — i.e. it can be steered by attacker
# input (`writeFile(base + entryName, ...)` where entryName is
# `../../etc/passwd`). A string literal cannot be steered; a value
# routed through the `safeJoin` sanitizer cannot escape its base. Any
# other path expression is the traversal precondition, and E0711 refuses
# it — the same posture as E0710 for net hosts.

_FS_SINKS = ("writeFile", "readFile")
_PATH_SANITIZER = "safeJoin"


def _expr_is_safe_path(node: Dict[str, Any], safe_names: Set[str]) -> Optional[str]:
    """Return None if this path expression is safe (fixed literal, a
    safeJoin(...) call, or a name proven to hold one of those), else a
    short reason it is a traversal risk."""
    if not isinstance(node, dict):
        return "path is not a fixed literal - can be steered by input"
    kind = node.get("kind")
    if kind == "StringLit":
        if ".." in (node.get("value") or ""):
            return "literal path contains '..' - escapes its directory"
        return None
    if kind == "Call":
        if _callee_name(node) == _PATH_SANITIZER:
            return None
        return f"path is a computed call - route it through {_PATH_SANITIZER}()"
    if kind == "Ident" and node.get("name") in safe_names:
        return None
    return f"path is a dynamic expression - route it through {_PATH_SANITIZER}()"


def _safe_path_names(body: Any) -> Set[str]:
    """Names that are bound ONLY to safe path expressions (a string
    literal without '..' or a safeJoin call) across every Let/Assign to
    them in this function body. A single unsafe binding disqualifies the
    name (sound for straight-line path construction)."""
    bindings: Dict[str, List[Dict[str, Any]]] = {}

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                bindings.setdefault(node["name"], []).append(node["value"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(body)
    safe: Set[str] = set()
    for name, values in bindings.items():
        if all(_expr_is_safe_path(v, safe) is None for v in values):
            safe.add(name)
    return safe


def check_fs_path_safety(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0711 diagnostics for read/write sinks fed a non-literal,
    unsanitized path (the path-traversal precondition)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        body = d.get("body", [])
        safe_names = _safe_path_names(body)
        for call in _walk_calls(body):
            if _callee_name(call) not in _FS_SINKS:
                continue
            args = call.get("args") or []
            if not args:
                continue
            reason = _expr_is_safe_path(args[0], safe_names)
            if reason is None:
                continue
            sink = _callee_name(call)
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0711",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} calls {sink!r} with an unsafe path "
                    f"({reason}); a path traversal here can read or "
                    f"overwrite arbitrary files"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"use a fixed string literal, or build the path with "
                    f"{_PATH_SANITIZER}(baseDir, untrustedPart) which strips "
                    f"'..' and absolute roots so it cannot escape baseDir"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": sink, "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0712 — secret / PII exfiltration into a log sink (CWE-532)
# ----------------------------------------------------------------------
# A value carrying a `Secret<T>` marker must not reach a logging sink
# (`print`) unless explicitly unwrapped with `reveal(...)`. This is the
# "we accidentally logged the password/token" incident class. `Secret<T>`
# is a compile-time-only taint marker (erased at runtime); `reveal()` is
# the sanctioned, auditable disclosure. Detection reuses the same
# straight-line dataflow as E0711: taint originates at Secret-typed
# params and propagates through let/assign bindings; a `reveal(...)`
# subtree is pruned (intentional exposure).

# sink name -> arg indices to inspect (None = all args). A Secret must
# not reach a log sink (`print`) NOR be persisted to disk (the contents
# argument of `writeFile`) — both exfiltrate the credential.
_SECRET_SINKS: Dict[str, Any] = {"print": None, "writeFile": (1,)}
_SECRET_MARKER = "Secret"
_SECRET_REVEAL = "reveal"
_SECRET_CLASSIFY = "classify"


def _is_marker_type(ty: Any, marker: str) -> bool:
    return isinstance(ty, dict) and ty.get("kind") == "GenericType" \
        and ty.get("name") == marker


# Stdlib constructors that produce a marker-carrying value. User functions
# declared `returns <Marker><...>` are added per-module by
# _marker_source_fns; a call to any of these is a taint source.
_STDLIB_MARKER_CONSTRUCTORS: Dict[str, frozenset] = {
    "Secret":    frozenset({"classify"}),
    "PII":       frozenset({"classifyPII"}),
    "Untrusted": frozenset({"classifyUntrusted"}),
}


def _marker_source_fns(ast: Dict[str, Any], marker: str) -> frozenset:
    """Functions whose call results carry `marker`: the stdlib
    constructors plus every user function declared with a marker-typed
    return. Signature-level only — bodies are not analyzed."""
    names = set(_STDLIB_MARKER_CONSTRUCTORS.get(marker, frozenset()))
    for d in ast.get("decls", []):
        if d.get("kind") == "FunctionDecl" \
                and _is_marker_type(d.get("return_type"), marker):
            names.add(d["name"])
    return frozenset(names)


def _marker_param_mask(ast: Dict[str, Any], marker: str) -> Dict[str, Tuple[bool, ...]]:
    """fn name -> per-param mask, True where the declared param type
    carries `marker`. Passing a marked value into such a slot is a
    sanctioned crossing — the callee owns the value from there (its own
    body is checked; what escapes is its return, covered by
    _marker_source_fns)."""
    out: Dict[str, Tuple[bool, ...]] = {}
    for d in ast.get("decls", []):
        if d.get("kind") == "FunctionDecl":
            out[d["name"]] = tuple(_is_marker_type(p.get("type"), marker)
                                   for p in d.get("params", []))
    return out


def _expr_leaks_marked(node: Any, tainted: Set[str], unwrap,
                       source_fns: frozenset = frozenset(),
                       param_mask: Optional[Dict[str, Tuple[bool, ...]]] = None) -> bool:
    """True if `node` exposes a tainted name, or a call to a marker-
    producing function, outside an `unwrap(...)` call (the sanctioned
    exit for this marker). `unwrap` is a single name or a set of names.
    An argument consumed by a marker-typed parameter of a user-declared
    callee (per `param_mask`) is pruned — that crossing is sanctioned."""
    unwraps = {unwrap} if isinstance(unwrap, str) else unwrap
    if isinstance(node, dict):
        kind = node.get("kind")
        if kind == "Call":
            callee = _callee_name(node)
            if callee in unwraps:
                return False  # sanctioned, audited exit — prune
            if callee in source_fns:
                return True   # call returns a marker-typed value
            mask = (param_mask or {}).get(callee)
            if mask:
                args = node.get("args") or []
                open_args = [a for i, a in enumerate(args)
                             if i >= len(mask) or not mask[i]]
                rest = [v for k, v in node.items() if k != "args"]
                return _expr_leaks_marked(open_args + rest, tainted, unwrap,
                                          source_fns, param_mask)
        if kind == "Ident" and node.get("name") in tainted:
            return True
        return any(_expr_leaks_marked(v, tainted, unwrap, source_fns, param_mask)
                   for v in node.values())
    if isinstance(node, list):
        return any(_expr_leaks_marked(x, tainted, unwrap, source_fns, param_mask)
                   for x in node)
    return False


def _marked_tainted_names(fn_decl: Dict[str, Any], marker: str, unwrap,
                          source_fns: frozenset = frozenset(),
                          param_mask: Optional[Dict[str, Tuple[bool, ...]]] = None) -> Set[str]:
    """Names holding a `marker`-typed value: marker-typed params, plus any
    let/assign target bound to an expression carrying a tainted name
    (fixpoint; an `unwrap(...)` call breaks the taint). A call to a
    `source_fns` member seeds taint (signature-level interprocedural)."""
    tainted: Set[str] = {
        p["name"] for p in fn_decl.get("params", []) if _is_marker_type(p.get("type"), marker)
    }
    binds: List[Tuple[str, Any]] = []

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                binds.append((node["name"], node["value"]))
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(fn_decl.get("body", []))
    changed = True
    while changed:
        changed = False
        for name, value in binds:
            if name not in tainted and _expr_leaks_marked(value, tainted, unwrap, source_fns, param_mask):
                tainted.add(name)
                changed = True
    return tainted


# Thin wrappers preserving the E0712 call sites.
def _is_secret_type(ty: Any) -> bool:
    return _is_marker_type(ty, _SECRET_MARKER)


def _expr_leaks_secret(node: Any, tainted: Set[str],
                       source_fns: frozenset = frozenset(),
                       param_mask: Optional[Dict[str, Tuple[bool, ...]]] = None) -> bool:
    return _expr_leaks_marked(node, tainted, _SECRET_REVEAL, source_fns,
                              param_mask)


def _secret_tainted_names(fn_decl: Dict[str, Any],
                          source_fns: frozenset = frozenset(),
                          param_mask: Optional[Dict[str, Tuple[bool, ...]]] = None) -> Set[str]:
    return _marked_tainted_names(fn_decl, _SECRET_MARKER, _SECRET_REVEAL,
                                 source_fns, param_mask)


def check_secret_flow(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0712 diagnostics for a Secret value reaching a log sink
    (`print`) or being persisted to disk (`writeFile` contents)."""
    diags: List[Diagnostic] = []
    src_fns = _marker_source_fns(ast, _SECRET_MARKER)
    pmask = _marker_param_mask(ast, _SECRET_MARKER)
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        tainted = _secret_tainted_names(d, src_fns, pmask)
        if not tainted and not src_fns:
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        for call in _walk_calls(d.get("body", [])):
            sink = _callee_name(call)
            if sink not in _SECRET_SINKS:
                continue
            args = call.get("args") or []
            idxs = _SECRET_SINKS[sink]
            checked = args if idxs is None else [args[i] for i in idxs if i < len(args)]
            if not any(_expr_leaks_secret(a, tainted, src_fns, pmask) for a in checked):
                continue
            where = "logs" if sink == "print" else "persists to disk"
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0712",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} {where} a Secret value via "
                    f"{sink!r}; a value marked Secret<...> must not reach a "
                    f"log or persistence sink in the clear"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"do not expose the secret; if disclosure is truly "
                    f"intended, wrap it in {_SECRET_REVEAL}(...) at the "
                    f"call site so the exposure is explicit and auditable"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": sink},
            ))
    return diags


# ----------------------------------------------------------------------
# E0713 — SQL injection (query built by raw concatenation) — CWE-89
# ----------------------------------------------------------------------
# Injection's precondition: a command/query string assembled by
# concatenating untrusted input, instead of a parameterized form. The
# `sqlQuery` sink must receive a fixed literal or a `sqlBind(...)`
# parameterized query; a raw `BinOp +` concatenation (or any other
# dynamic expression) is the injection precondition and is refused —
# the same sink+sanitizer+literal shape as E0711/safeJoin.

_SQL_SINKS = ("sqlQuery", "sqlExec", "sqlByOwner")
_SQL_BIND = "sqlBind"


def _query_expr_is_safe(node: Any, safe_names: Set[str]) -> Optional[str]:
    if not isinstance(node, dict):
        return "query is not a fixed literal"
    kind = node.get("kind")
    if kind == "StringLit":
        return None
    if kind == "Call":
        if _callee_name(node) == _SQL_BIND:
            return None
        return f"query is a computed call - use {_SQL_BIND}(template, value)"
    if kind == "Ident" and node.get("name") in safe_names:
        return None
    if kind == "BinOp" and node.get("op") == "+":
        return "query is built by string concatenation - use sqlBind(...)"
    return f"query is a dynamic expression - use {_SQL_BIND}(template, value)"


def _safe_query_names(body: Any) -> Set[str]:
    binds: Dict[str, List[Dict[str, Any]]] = {}

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                binds.setdefault(node["name"], []).append(node["value"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(body)
    safe: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, values in binds.items():
            if name in safe:
                continue
            if all(_query_expr_is_safe(v, safe) is None for v in values):
                safe.add(name)
                changed = True
    return safe


def check_injection(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0713 diagnostics for a sqlQuery fed a concatenated /
    non-parameterized query string (the injection precondition)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        body = d.get("body", [])
        safe_names = _safe_query_names(body)
        for call in _walk_calls(body):
            if _callee_name(call) not in _SQL_SINKS:
                continue
            args = call.get("args") or []
            if not args:
                continue
            reason = _query_expr_is_safe(args[0], safe_names)
            if reason is None:
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0713",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} builds a SQL query for "
                    f"{_callee_name(call)!r} unsafely ({reason}); untrusted "
                    f"input concatenated into a query is an injection"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"use a fixed literal, or parameterize with "
                    f"{_SQL_BIND}(\"... ? ...\", value) which escapes the "
                    f"value so it cannot break out of the query"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call), "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0714 — command injection (shell command built by concatenation) — CWE-78
# ----------------------------------------------------------------------
# The command sibling of E0713 (OpenSSL c_rehash CVE-2022-1292 shape: a
# filename concatenated into a shell command line). The `shellExec` sink
# must receive a fixed literal or a `shellArg(...)`-quoted command; a raw
# `BinOp +` concatenation (or any other dynamic expression) lets the
# untrusted part inject `;`/`|`/`$( )` shell syntax and is refused —
# the same sink+sanitizer+literal shape as E0713/sqlBind.

_SHELL_SINKS = ("shellExec",)
_SHELL_ARG = "shellArg"


def _command_expr_is_safe(node: Any, safe_names: Set[str]) -> Optional[str]:
    if not isinstance(node, dict):
        return "command is not a fixed literal"
    kind = node.get("kind")
    if kind == "StringLit":
        return None
    if kind == "Call":
        if _callee_name(node) == _SHELL_ARG:
            return None
        return f"command is a computed call - use {_SHELL_ARG}(template, value)"
    if kind == "Ident" and node.get("name") in safe_names:
        return None
    if kind == "BinOp" and node.get("op") == "+":
        return "command is built by string concatenation - use shellArg(...)"
    return f"command is a dynamic expression - use {_SHELL_ARG}(template, value)"


def _safe_command_names(body: Any) -> Set[str]:
    binds: Dict[str, List[Dict[str, Any]]] = {}

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                binds.setdefault(node["name"], []).append(node["value"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(body)
    safe: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, values in binds.items():
            if name in safe:
                continue
            if all(_command_expr_is_safe(v, safe) is None for v in values):
                safe.add(name)
                changed = True
    return safe


def check_command_injection(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0714 diagnostics for a shellExec fed a concatenated /
    unquoted command string (the command-injection precondition)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        body = d.get("body", [])
        safe_names = _safe_command_names(body)
        for call in _walk_calls(body):
            if _callee_name(call) not in _SHELL_SINKS:
                continue
            args = call.get("args") or []
            if not args:
                continue
            reason = _command_expr_is_safe(args[0], safe_names)
            if reason is None:
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0714",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} builds a shell command for "
                    f"{_callee_name(call)!r} unsafely ({reason}); untrusted "
                    f"input concatenated into a command line is a command "
                    f"injection"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"use a fixed literal, or place the untrusted value with "
                    f"{_SHELL_ARG}(\"... ? ...\", value) which quotes it as a "
                    f"single argument so it cannot inject shell syntax"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call), "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0715 — PII egress: personal data persisted / logged unredacted
# ----------------------------------------------------------------------
# The data-residency / GDPR-leak class that dominates bigtech incident
# reviews: a value carrying a `PII<T>` marker (email, name, address,
# device id) is written to a log or to disk in the clear, from where it
# flows to aggregators, backups, and analytics far outside the consent
# boundary. Reuses the E0712 taint machinery with a distinct marker and
# a distinct sanctioned exit — `redact(...)`, which masks the value.
# Sinks: `print` (logs) and the CONTENTS argument of `writeFile` (disk).
# `net.fetch` egress is a declared effect, not a call, so a network body
# sink is deferred until a body-carrying stdlib sink exists (noted).

_PII_MARKER = "PII"
_PII_REDACT = "redact"
# sink name -> arg indices to inspect (None = all args)
_PII_SINKS: Dict[str, Any] = {"print": None, "writeFile": (1,)}


def check_pii_flow(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0715 diagnostics for a PII value reaching a persistence /
    log sink without redact(...)."""
    diags: List[Diagnostic] = []
    src_fns = _marker_source_fns(ast, _PII_MARKER)
    pmask = _marker_param_mask(ast, _PII_MARKER)
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        tainted = _marked_tainted_names(d, _PII_MARKER, _PII_REDACT, src_fns, pmask)
        if not tainted and not src_fns:
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        for call in _walk_calls(d.get("body", [])):
            sink = _callee_name(call)
            if sink not in _PII_SINKS:
                continue
            args = call.get("args") or []
            idxs = _PII_SINKS[sink]
            checked = args if idxs is None else [args[i] for i in idxs if i < len(args)]
            if not any(_expr_leaks_marked(a, tainted, _PII_REDACT, src_fns, pmask) for a in checked):
                continue
            where = "logs" if sink == "print" else "persists to disk"
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0715",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} {where} a PII value via {sink!r}; "
                    f"personal data marked PII<...> must not cross a "
                    f"log/persistence sink in the clear"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"mask it with {_PII_REDACT}(...) before the sink, or "
                    f"keep PII out of logs/files entirely; redact(...) is "
                    f"the auditable, consent-safe disclosure"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": sink},
            ))
    return diags


# ----------------------------------------------------------------------
# E0724 — log injection / forging (CWE-117)
# ----------------------------------------------------------------------
# `Untrusted<T>` is the taint-SOURCE marker — the sound, explicit dual of
# provenance inference: a value crossing a trust boundary (a request field,
# an uploaded filename) is marked Untrusted at that boundary. Logging it
# raw lets embedded CR/LF forge fake log lines (audit-log poisoning, SIEM
# spoofing). The sanctioned exit is `sanitizeLog(...)`, which strips the
# control characters. Reuses the generalized taint machinery: taint
# originates at Untrusted-typed params and propagates through straight-line
# bindings; a sanitizeLog(...) subtree clears it.

_UNTRUSTED_MARKER = "Untrusted"
_UNTRUSTED_SANITIZE = "sanitizeLog"


def check_log_injection(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0724 diagnostics for an Untrusted value reaching a log sink
    (`print`) without sanitizeLog(...)."""
    diags: List[Diagnostic] = []
    src_fns = _marker_source_fns(ast, _UNTRUSTED_MARKER)
    pmask = _marker_param_mask(ast, _UNTRUSTED_MARKER)
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        tainted = _marked_tainted_names(d, _UNTRUSTED_MARKER, _UNTRUSTED_SANITIZE, src_fns, pmask)
        if not tainted and not src_fns:
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        for call in _walk_calls(d.get("body", [])):
            if _callee_name(call) != "print":
                continue
            args = call.get("args") or []
            if not any(_expr_leaks_marked(a, tainted, _UNTRUSTED_SANITIZE, src_fns, pmask) for a in args):
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0724",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} logs an Untrusted value via 'print'; "
                    f"embedded CR/LF can forge fake log entries (log "
                    f"injection)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"wrap it in {_UNTRUSTED_SANITIZE}(...), which strips the "
                    f"control characters an attacker uses to forge log lines"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": "print"},
            ))
    return diags


# ----------------------------------------------------------------------
# E0725 — reflected XSS: untrusted value in an HTML response (CWE-79)
# ----------------------------------------------------------------------
# The #2 OWASP risk. An Untrusted value written into an HTML response
# without escaping lets `<script>` execute in the victim's browser. Same
# taint marker as E0724, but the sanctioned exit is `htmlEscape(...)`, NOT
# sanitizeLog — stripping CR/LF does not neutralize HTML, so only an
# HTML-escaping exit clears the taint for this sink.

_HTML_SINKS = ("htmlResponse",)
_HTML_ESCAPE = "htmlEscape"


def check_reflected_xss(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0725 diagnostics for an Untrusted value reaching an HTML
    response sink without htmlEscape(...)."""
    diags: List[Diagnostic] = []
    src_fns = _marker_source_fns(ast, _UNTRUSTED_MARKER)
    pmask = _marker_param_mask(ast, _UNTRUSTED_MARKER)
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        tainted = _marked_tainted_names(d, _UNTRUSTED_MARKER, _HTML_ESCAPE, src_fns, pmask)
        if not tainted and not src_fns:
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        for call in _walk_calls(d.get("body", [])):
            if _callee_name(call) not in _HTML_SINKS:
                continue
            args = call.get("args") or []
            if not any(_expr_leaks_marked(a, tainted, _HTML_ESCAPE, src_fns, pmask) for a in args):
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0725",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} writes an Untrusted value into an HTML "
                    f"response via {_callee_name(call)!r}; unescaped markup "
                    f"executes in the victim's browser (reflected XSS)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"wrap it in {_HTML_ESCAPE}(...), which escapes "
                    f"<, >, &, \" and ' so the value renders as text, not "
                    f"markup (sanitizeLog does NOT protect here)"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call)},
            ))
    return diags


# ----------------------------------------------------------------------
# E0726 — HTTP response splitting / header injection (CWE-113)
# ----------------------------------------------------------------------
# The third sink for `Untrusted<T>`: an untrusted value in a response
# header. Embedded CR/LF ends the header block and injects attacker
# headers or a second response (cache poisoning, session fixation via a
# forged Set-Cookie). The sanctioned exit is `sanitizeHeader(...)`, which
# strips CR/LF — distinct from htmlEscape (E0725), which would leave a raw
# newline intact, and named separately for per-sink clarity.

_HEADER_SINKS = ("setHeader",)
_HEADER_SANITIZE = "sanitizeHeader"


def check_header_injection(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0726 diagnostics for an Untrusted value reaching a response
    header sink without sanitizeHeader(...)."""
    diags: List[Diagnostic] = []
    src_fns = _marker_source_fns(ast, _UNTRUSTED_MARKER)
    pmask = _marker_param_mask(ast, _UNTRUSTED_MARKER)
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        tainted = _marked_tainted_names(d, _UNTRUSTED_MARKER, _HEADER_SANITIZE, src_fns, pmask)
        if not tainted and not src_fns:
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        for call in _walk_calls(d.get("body", [])):
            if _callee_name(call) not in _HEADER_SINKS:
                continue
            args = call.get("args") or []
            if not any(_expr_leaks_marked(a, tainted, _HEADER_SANITIZE, src_fns, pmask) for a in args):
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0726",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} puts an Untrusted value in a response "
                    f"header via {_callee_name(call)!r}; embedded CR/LF "
                    f"injects headers or a second response (response "
                    f"splitting)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"wrap it in {_HEADER_SANITIZE}(...), which strips the "
                    f"CR/LF used to break out of the header value"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call)},
            ))
    return diags


# ----------------------------------------------------------------------
# E0728 — CSV / formula injection (CWE-1236)
# ----------------------------------------------------------------------
# The fourth `Untrusted<T>` sink — and the first in a NON-HTTP context,
# proving the marker generalizes past web output. A cell of exported data
# that begins with =, +, -, @ (or tab/CR) is interpreted as a FORMULA when
# the CSV is opened in Excel / Google Sheets: `=WEBSERVICE(...)` exfiltrates
# other cells, `=cmd|...` can reach DDE → code execution. The sanctioned
# exit is `csvEscape(...)`, which neutralizes a leading formula trigger.

_CSV_SINKS = ("csvCell",)
_CSV_ESCAPE = "csvEscape"


def check_csv_injection(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0728 diagnostics for an Untrusted value reaching a CSV cell
    sink without csvEscape(...)."""
    diags: List[Diagnostic] = []
    src_fns = _marker_source_fns(ast, _UNTRUSTED_MARKER)
    pmask = _marker_param_mask(ast, _UNTRUSTED_MARKER)
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        tainted = _marked_tainted_names(d, _UNTRUSTED_MARKER, _CSV_ESCAPE, src_fns, pmask)
        if not tainted and not src_fns:
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        for call in _walk_calls(d.get("body", [])):
            if _callee_name(call) not in _CSV_SINKS:
                continue
            args = call.get("args") or []
            if not any(_expr_leaks_marked(a, tainted, _CSV_ESCAPE, src_fns, pmask) for a in args):
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0728",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} writes an Untrusted value into a CSV "
                    f"cell via {_callee_name(call)!r}; a leading = + - @ makes "
                    f"it a formula when opened in a spreadsheet (CSV injection)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"wrap it in {_CSV_ESCAPE}(...), which neutralizes a "
                    f"leading formula trigger so the value stays inert text"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call)},
            ))
    return diags


# ----------------------------------------------------------------------
# E0729 — marker laundering: a marked value passed to an unmarked param
# ----------------------------------------------------------------------
# A value carrying a confidentiality/taint marker (Secret<T>, PII<T>,
# Untrusted<T>) must not be passed to a user-function parameter typed
# WITHOUT that marker: inside the callee the value carries no taint, so
# every sink pass goes blind (the launder that lets `logIt(password)`
# print the secret unflagged). Sanctioned exits: the marker's own
# unwrappers at the call site, or declaring the callee parameter with the
# marker type so taint travels with the value. v1 scope: user-declared
# callees only (direct named calls); stdlib transforms and HOF /
# function-typed callees are recorded residuals. Authorized<T> is
# deliberately excluded — it is a proof marker, and dropping a proof only
# over-restricts the callee.

def _boundary_markers() -> Dict[str, frozenset]:
    """Marker -> sanctioned call-site unwrappers. Built lazily because
    _TRUSTED is defined further down the module (near its E0719/E0720
    users)."""
    return {
        _SECRET_MARKER:    frozenset({_SECRET_REVEAL}),
        _PII_MARKER:       frozenset({_PII_REDACT}),
        _UNTRUSTED_MARKER: frozenset({_UNTRUSTED_SANITIZE, _HTML_ESCAPE,
                                      _HEADER_SANITIZE, _CSV_ESCAPE,
                                      _TRUSTED}),
    }


def check_marker_boundary(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0729 diagnostics for a marker-carrying value passed to a
    user-declared function parameter not typed with that marker."""
    decls = {d["name"]: d for d in ast.get("decls", [])
             if d.get("kind") == "FunctionDecl"}
    diags: List[Diagnostic] = []
    for marker, unwraps in _boundary_markers().items():
        src_fns = _marker_source_fns(ast, marker)
        pmask = _marker_param_mask(ast, marker)
        for d in decls.values():
            tainted = _marked_tainted_names(d, marker, unwraps, src_fns, pmask)
            if not tainted and not src_fns:
                continue
            fn = d["name"]
            fpos = d.get("pos") or {"line": 0, "column": 0}
            for call in _walk_calls(d.get("body", [])):
                callee = decls.get(_callee_name(call))
                if callee is None:
                    continue  # stdlib / unknown: covered by sink passes
                params = callee.get("params", [])
                for i, arg in enumerate(call.get("args") or []):
                    if i >= len(params):
                        break
                    if _is_marker_type(params[i].get("type"), marker):
                        continue  # marker declared — taint travels
                    if not _expr_leaks_marked(arg, tainted, unwraps,
                                              src_fns, pmask):
                        continue
                    pos = call.get("pos") or fpos
                    diags.append(Diagnostic(
                        code="E0729",
                        category="capability",
                        severity="error",
                        message=(
                            f"function {fn!r} passes a {marker}<...>-marked "
                            f"value to parameter {params[i].get('name')!r} of "
                            f"{callee['name']!r}, which is not typed "
                            f"{marker}<...>; inside the callee the marker is "
                            f"erased and every sink check goes blind "
                            f"(taint laundering)"
                        ),
                        position=Position(pos.get("line", 0),
                                          pos.get("column", 0)),
                        suggestion=(
                            f"type the parameter as {marker}<...> so the "
                            f"marker travels with the value, or unwrap "
                            f"explicitly at the call site via one of: "
                            + ", ".join(sorted(unwraps)) + "(...)"
                        ),
                        confidence=1.0,
                        extra={"function": fn, "callee": callee["name"],
                               "param": params[i].get("name"),
                               "marker": marker},
                    ))
    return diags


# ----------------------------------------------------------------------
# E0730 — return laundering: tainted value under a plain return type
# ----------------------------------------------------------------------

def _walk_returns(node: Any):
    """Yield every Return node in a body (generic dict/list walk)."""
    if isinstance(node, dict):
        if node.get("kind") == "Return":
            yield node
        for v in node.values():
            yield from _walk_returns(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_returns(x)


def check_return_laundering(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0730 diagnostics for a function that RETURNS a
    marker-carrying value while its declared return type does not carry
    the marker. The dual of E0729: seeding trusts declared return types,
    so a plain-typed return of a tainted value makes the signature lie
    and washes the marker for every caller. Sanctioned exits: declare
    the marker-typed return (taint then travels via seeding), or unwrap
    at the return site. Authorized<T> excluded (proof marker)."""
    diags: List[Diagnostic] = []
    for marker, unwraps in _boundary_markers().items():
        src_fns = _marker_source_fns(ast, marker)
        pmask = _marker_param_mask(ast, marker)
        for d in ast.get("decls", []):
            if d.get("kind") != "FunctionDecl":
                continue
            if _is_marker_type(d.get("return_type"), marker):
                continue  # honest signature — callers taint via seeding
            tainted = _marked_tainted_names(d, marker, unwraps, src_fns, pmask)
            if not tainted and not src_fns:
                continue
            fn = d["name"]
            fpos = d.get("pos") or {"line": 0, "column": 0}
            declared = (d.get("return_type") or {}).get("name", "Unit")
            for ret in _walk_returns(d.get("body", [])):
                val = ret.get("value")
                if val is None:
                    continue
                if not _expr_leaks_marked(val, tainted, unwraps,
                                          src_fns, pmask):
                    continue
                pos = ret.get("pos") or fpos
                diags.append(Diagnostic(
                    code="E0730",
                    category="capability",
                    severity="error",
                    message=(
                        f"function {fn!r} returns a {marker}<...>-marked "
                        f"value but its declared return type "
                        f"({declared}) does not carry the marker; every "
                        f"caller receives the value with the marker "
                        f"washed off (return laundering)"
                    ),
                    position=Position(pos.get("line", 0),
                                      pos.get("column", 0)),
                    suggestion=(
                        f"declare the return type as {marker}<...> so "
                        f"taint travels to callers, or unwrap explicitly "
                        f"at the return site via one of: "
                        + ", ".join(sorted(unwraps)) + "(...)"
                    ),
                    confidence=1.0,
                    extra={"function": fn, "marker": marker,
                           "declared_return": declared},
                ))
    return diags


# ----------------------------------------------------------------------
# E0202 — non-exhaustive match on a union (unhandled variant)
# ----------------------------------------------------------------------
# Aether's `match` is exhaustive at RUNTIME (a missed variant raises). This
# lifts that to a STATIC guarantee — the architectural-integrity promise:
# the compiler refuses a match that does not handle every case of the
# scrutinee's union (or carry a wildcard/binding catch-all). A new variant
# added to a union then forces every match to be updated, at compile time.
# Conservative: only fires when the scrutinee's union type is resolvable
# from a parameter or let-binding annotation; otherwise it stays silent.

def _union_cases(ast: Dict[str, Any]) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {}
    for d in ast.get("decls", []):
        if d.get("kind") == "UnionDecl":
            out[d["name"]] = {c["name"] for c in d.get("cases", [])}
    return out


def _type_name(ty: Any) -> Optional[str]:
    if isinstance(ty, dict) and ty.get("kind") in ("TypeName", "GenericType"):
        return ty.get("name")
    return None


def _pattern_case(pat: Any) -> Optional[str]:
    """Case name a ConstructorPat covers; None if the pattern is a
    catch-all (wildcard / bare binding)."""
    if not isinstance(pat, dict):
        return None
    if pat.get("kind") == "ConstructorPat":
        path = pat.get("path") or []
        return path[-1] if path else None
    return None  # WildcardPat / BindPat → catch-all (handled by caller)


def _is_catch_all(pat: Any) -> bool:
    return isinstance(pat, dict) and pat.get("kind") in ("WildcardPat", "BindPat")


def _walk_matches(node: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(node, dict):
        if node.get("kind") in ("Match", "MatchExpr"):
            yield node
        for v in node.values():
            yield from _walk_matches(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_matches(x)


def check_exhaustiveness(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0202 diagnostics for a match that omits a union case with no
    catch-all, when the scrutinee's union type is statically resolvable."""
    unions = _union_cases(ast)
    if not unions:
        return []
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        # Name -> declared type name, from params and let bindings.
        types: Dict[str, str] = {}
        for p in d.get("params", []):
            tn = _type_name(p.get("type"))
            if tn:
                types[p["name"]] = tn

        def collect_lets(node: Any):
            if isinstance(node, dict):
                if node.get("kind") == "Let" and "name" in node:
                    tn = _type_name(node.get("type"))
                    if tn:
                        types[node["name"]] = tn
                for v in node.values():
                    collect_lets(v)
            elif isinstance(node, list):
                for x in node:
                    collect_lets(x)
        collect_lets(d.get("body", []))

        for m in _walk_matches(d.get("body", [])):
            scrut = m.get("scrutinee") or {}
            if scrut.get("kind") != "Ident":
                continue
            uname = types.get(scrut.get("name"))
            if uname not in unions:
                continue
            arms = m.get("arms") or []
            if any(_is_catch_all(a.get("pattern")) for a in arms):
                continue
            covered = {c for c in (_pattern_case(a.get("pattern")) for a in arms) if c}
            missing = unions[uname] - covered
            if not missing:
                continue
            pos = m.get("pos") or d.get("pos") or {"line": 0, "column": 0}
            diags.append(Diagnostic(
                code="E0202",
                category="type",
                severity="error",
                message=(
                    f"function {fn!r} matches on {uname!r} but does not "
                    f"handle case(s) {', '.join(sorted(missing))}; a "
                    f"non-exhaustive match traps an unhandled variant at "
                    f"runtime"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"add a case for each of {', '.join(sorted(missing))}, "
                    f"or a wildcard `case _` catch-all"
                ),
                confidence=1.0,
                extra={"function": fn, "union": uname, "missing": sorted(missing)},
            ))
    return diags


# ----------------------------------------------------------------------
# E0203 — unreachable match arm (CWE-561, dead code)
# ----------------------------------------------------------------------
# The complement of E0202: E0202 catches too FEW arms (a missed variant);
# E0203 catches redundant ones — an arm that can never execute because a
# prior wildcard/binding already catches everything, or a duplicate
# constructor case. A dead arm is a logic error (usually a mis-ordered or
# copy-pasted case). Purely about arm ordering, so it needs no type info
# and applies to every match.

def check_unreachable_arms(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0203 diagnostics for match arms that can never be reached."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        for m in _walk_matches(d.get("body", [])):
            arms = m.get("arms") or []
            mpos = m.get("pos") or d.get("pos") or {"line": 0, "column": 0}
            seen: Set[str] = set()
            catch_all = False
            for arm in arms:
                pat = arm.get("pattern")
                reason = None
                if catch_all:
                    reason = "arm follows a wildcard catch-all that already matches everything"
                elif _is_catch_all(pat):
                    catch_all = True
                else:
                    case = _pattern_case(pat)
                    if case is not None and case in seen:
                        reason = f"duplicate case {case!r} — already handled by an earlier arm"
                    elif case is not None:
                        seen.add(case)
                if reason is None:
                    continue
                pos = (pat.get("pos") if isinstance(pat, dict) else None) or mpos
                diags.append(Diagnostic(
                    code="E0203",
                    category="type",
                    severity="error",
                    message=(
                        f"function {fn!r} has an unreachable match arm "
                        f"({reason}); the code in it never runs"
                    ),
                    position=Position(pos.get("line", 0), pos.get("column", 0)),
                    suggestion=(
                        "remove the dead arm, or reorder so the specific "
                        "cases precede the wildcard"
                    ),
                    confidence=1.0,
                    extra={"function": fn, "reason": reason},
                ))
    return diags


# ----------------------------------------------------------------------
# E0204 — dead code after a terminator (CWE-561)
# ----------------------------------------------------------------------
# A statement that follows an unconditional `return` / `break` / `continue`
# in the SAME block can never execute. It is always a logic error — a
# misplaced statement, a stray early return, or a merge artifact. Purely
# structural: scan every statement list for a terminator that is not the
# last element.

_TERMINATORS = ("Return", "Break", "Continue")


def _stmt_lists(node: Any) -> Iterable[List[Any]]:
    """Yield every list that is a block of statements (its elements are
    statement dicts carrying a `kind`)."""
    if isinstance(node, dict):
        for v in node.values():
            yield from _stmt_lists(v)
    elif isinstance(node, list):
        if node and all(isinstance(x, dict) and "kind" in x for x in node):
            yield node
        for x in node:
            yield from _stmt_lists(x)


def check_dead_code(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0204 diagnostics for a statement after a terminator."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        for block in _stmt_lists(d.get("body", [])):
            for i, stmt in enumerate(block[:-1]):
                if stmt.get("kind") not in _TERMINATORS:
                    continue
                dead = block[i + 1]
                pos = dead.get("pos") or stmt.get("pos") or {"line": 0, "column": 0}
                term = stmt.get("kind").lower()
                diags.append(Diagnostic(
                    code="E0204",
                    category="type",
                    severity="error",
                    message=(
                        f"function {fn!r} has unreachable code after a "
                        f"{term}; the statement can never execute"
                    ),
                    position=Position(pos.get("line", 0), pos.get("column", 0)),
                    suggestion=(
                        f"remove the dead statement, or move it before the "
                        f"{term}"
                    ),
                    confidence=1.0,
                    extra={"function": fn, "after": term},
                ))
                break  # one diagnostic per block
    return diags


# ----------------------------------------------------------------------
# E0205 — unused let binding (dead store, CWE-563)
# ----------------------------------------------------------------------
# A `let x = ...` whose `x` is never read is a dead store — usually a bug
# (the wrong variable is used downstream, or a computation was left
# dangling). The `_`-prefix is the intentional-discard convention
# (`let _r = writeFile(...)` keeps the effect, drops the value) and is
# exempt. Detection is a use/def scan: a bound name that appears as an
# Ident nowhere in the function body is unused.

def _ident_reads(node: Any, out: Set[str]) -> None:
    if isinstance(node, dict):
        if node.get("kind") == "Ident" and isinstance(node.get("name"), str):
            out.add(node["name"])
        for v in node.values():
            _ident_reads(v, out)
    elif isinstance(node, list):
        for x in node:
            _ident_reads(x, out)


def check_unused_binding(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0205 diagnostics for a let binding whose name is never read
    (excluding the `_`-prefixed intentional-discard convention)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        body = d.get("body", [])
        reads: Set[str] = set()
        _ident_reads(body, reads)
        # Collect let bindings in source order.
        lets: List[Dict[str, Any]] = []

        def collect(node: Any):
            if isinstance(node, dict):
                if node.get("kind") == "Let" and isinstance(node.get("name"), str):
                    lets.append(node)
                for v in node.values():
                    collect(v)
            elif isinstance(node, list):
                for x in node:
                    collect(x)
        collect(body)

        for let in lets:
            name = let["name"]
            if name.startswith("_") or name in reads:
                continue
            pos = let.get("pos") or d.get("pos") or {"line": 0, "column": 0}
            diags.append(Diagnostic(
                code="E0205",
                category="type",
                severity="error",
                message=(
                    f"function {fn!r} binds {name!r} with `let` but never "
                    f"reads it; a dead store is usually a mistaken variable"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"use {name!r}, remove the binding, or — if you only "
                    f"need the value's side effect — rename it to `_{name}`"
                ),
                confidence=1.0,
                extra={"function": fn, "binding": name},
            ))
    return diags


# ----------------------------------------------------------------------
# E0206 — ignored Result / unchecked error (CWE-252)
# ----------------------------------------------------------------------
# A bare statement calling a `Result<...>`-returning function silently
# drops the error case — the classic "forgot to check the return value"
# bug (a failed writeFile that looks like it succeeded). The sanctioned
# handling is to bind the result (`let r = ...` then match it, or the
# `let _r = ...` explicit-discard convention) or `match` it inline.

_STDLIB_RESULT_FNS = {"writeFile", "readFile", "readLine", "parseInt", "parseFloat"}


def _result_returning_fns(ast: Dict[str, Any]) -> Set[str]:
    out = set(_STDLIB_RESULT_FNS)
    for d in ast.get("decls", []):
        if d.get("kind") == "FunctionDecl":
            rt = d.get("return_type") or {}
            if isinstance(rt, dict) and rt.get("name") == "Result":
                out.add(d["name"])
    return out


def check_ignored_result(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0206 diagnostics for a bare statement that discards a
    Result-returning call (an unchecked error)."""
    result_fns = _result_returning_fns(ast)
    diags: List[Diagnostic] = []

    def walk_stmts(node: Any, fn: str, fpos: Dict[str, Any]):
        if isinstance(node, dict):
            if node.get("kind") == "ExprStmt":
                expr = node.get("expr") or {}
                if expr.get("kind") == "Call" and _callee_name(expr) in result_fns:
                    callee = _callee_name(expr)
                    pos = expr.get("pos") or node.get("pos") or fpos
                    diags.append(Diagnostic(
                        code="E0206",
                        category="type",
                        severity="error",
                        message=(
                            f"function {fn!r} discards the Result of "
                            f"{callee!r}; an unchecked error (e.g. a failed "
                            f"write) is silently ignored"
                        ),
                        position=Position(pos.get("line", 0), pos.get("column", 0)),
                        suggestion=(
                            f"bind and handle it (`let r = {callee}(...)` then "
                            f"`match r`), or `let _r = ...` to discard the "
                            f"error explicitly"
                        ),
                        confidence=1.0,
                        extra={"function": fn, "callee": callee},
                    ))
            for v in node.values():
                walk_stmts(v, fn, fpos)
        elif isinstance(node, list):
            for x in node:
                walk_stmts(x, fn, fpos)

    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        walk_stmts(d.get("body", []), d["name"],
                   d.get("pos") or {"line": 0, "column": 0})
    return diags


# ----------------------------------------------------------------------
# E0207 — unsatisfiable refinement type (impossible type)
# ----------------------------------------------------------------------
# A refinement `T where P` whose predicate no value can satisfy (e.g.
# `Int where self >= 10 and self <= 5`) is a dead type — always a bounds
# typo, and every parameter of that type is uninhabitable. Light, SOUND
# interval analysis: intersect the analyzable `self OP const` clauses of a
# conjunction; flag only when that interval is provably empty. Unanalyzable
# clauses widen to (-inf, +inf), so the check never false-positives.

def _clause_bound(node: Any):
    """A `self OP const` (or `const OP self`) clause → (lo, hi) where each
    is (value, inclusive) or None. Returns None if not analyzable."""
    if not (isinstance(node, dict) and node.get("kind") == "BinOp"):
        return None
    op = node.get("op")
    left, right = node.get("left") or {}, node.get("right") or {}

    def num(n):
        if isinstance(n, dict) and n.get("kind") in ("IntLit", "FloatLit"):
            return n.get("value")
        return None

    # Normalize to `self OP const`.
    if left.get("kind") == "Ident" and left.get("name") == "self":
        c = num(right)
    elif right.get("kind") == "Ident" and right.get("name") == "self":
        c = num(left)
        op = {">=": "<=", "<=": ">=", ">": "<", "<": ">", "==": "=="}.get(op, op)
    else:
        return None
    if c is None:
        return None
    if op == ">=":
        return ((c, True), None)
    if op == ">":
        return ((c, False), None)
    if op == "<=":
        return (None, (c, True))
    if op == "<":
        return (None, (c, False))
    if op == "==":
        return ((c, True), (c, True))
    return None


def _refine_interval(pred: Any):
    """(lo, hi) bounds for a conjunction of self-clauses; each bound is
    (value, inclusive) or None (unbounded). Non-conjunction / unknown
    shapes widen to unbounded (sound)."""
    if isinstance(pred, dict) and pred.get("kind") == "BinOp" and pred.get("op") == "and":
        lo1, hi1 = _refine_interval(pred["left"])
        lo2, hi2 = _refine_interval(pred["right"])
        # tighter lower bound = larger value
        lo = lo1 if lo2 is None else lo2 if lo1 is None else (
            lo1 if lo1[0] > lo2[0] else lo2 if lo2[0] > lo1[0]
            else (lo1[0], lo1[1] and lo2[1]))
        hi = hi1 if hi2 is None else hi2 if hi1 is None else (
            hi1 if hi1[0] < hi2[0] else hi2 if hi2[0] < hi1[0]
            else (hi1[0], hi1[1] and hi2[1]))
        return (lo, hi)
    b = _clause_bound(pred)
    return b if b is not None else (None, None)


def _interval_empty(lo, hi) -> bool:
    if lo is None or hi is None:
        return False
    if lo[0] > hi[0]:
        return True
    if lo[0] == hi[0] and not (lo[1] and hi[1]):
        return True
    return False


def check_unsatisfiable_refinement(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0207 diagnostics for a refinement type no value can satisfy."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "TypeDecl":
            continue
        pred = d.get("refinement")
        if not pred:
            continue
        lo, hi = _refine_interval(pred)
        if not _interval_empty(lo, hi):
            continue
        pos = d.get("pos") or {"line": 0, "column": 0}
        diags.append(Diagnostic(
            code="E0207",
            category="type",
            severity="error",
            message=(
                f"type {d['name']!r} has an unsatisfiable refinement "
                f"(bounds [{lo[0]}, {hi[0]}] admit no value); every "
                f"parameter of this type is uninhabitable"
            ),
            position=Position(pos.get("line", 0), pos.get("column", 0)),
            suggestion="fix the bounds — the lower bound exceeds the upper",
            confidence=1.0,
            extra={"type": d["name"], "lo": lo[0], "hi": hi[0]},
        ))
    return diags


# ----------------------------------------------------------------------
# E0716 — missing authorization before a data mutation (CWE-862/863)
# ----------------------------------------------------------------------
# The bigtech auth-check-before-mutation class (Ivanti EPMM
# CVE-2023-35078 shape: an API path that mutates state with no
# authorization check on it). Every prior detector is "tainted value
# must NOT reach a sink"; this one is the inversion: a mutating sink
# REQUIRES a proof of authorization in its dataflow. `sqlExec(stmt,
# auth)` — a data-mutating statement (effect `db.exec`) — must receive,
# as its second argument, a value proven `Authorized<T>`: a direct
# `authorize(...)` guard call, an `Authorized<T>`-typed parameter
# (authorization performed by the caller and carried across the
# boundary), or a name bound only to such expressions. Anything else —
# including omitting the argument — is refused. Conservative direction:
# a proof Aether cannot see is refused (over-flag, never miss).
#
# Authorized<T> is NOMINAL: only authorize(...) mints it. Trusting an
# Authorized<T> parameter is sound only because every call site of the
# enclosing program is checked too — three companion obligations keep
# the proof from being laundered:
#   1. an argument bound to an Authorized<...> parameter of a
#      user-defined function must itself be a proof (a raw String
#      handed to a helper is rejected AT THE CALL SITE, so no unproven
#      value ever reaches a trusted parameter);
#   2. `let`/`var`/`const` with an Authorized<...> annotation must be
#      initialized with a proof (annotation cannot mint the type);
#   3. a function that takes an Authorized<...> parameter cannot be
#      used as a first-class value (an indirect call would bypass
#      obligation 1).
# Rebinding demotes: a name with ANY non-proof binding (Let, Var, or
# Assign) is disqualified by the all-bindings rule below.

_MUTATION_SINKS = ("sqlExec",)   # authorization proof required at arg index 1
_AUTH_MARKER = "Authorized"
_AUTH_GUARD = "authorize"
# Both guards mint Authorized<T>: authorizeResource is the resource-bound
# strengthening (its id-binding is E0717's job, not E0716's).
_AUTH_GUARDS = ("authorize", "authorizeResource")


def _expr_is_authorized(node: Any, authorized: Set[str],
                        minters: Set[str] = frozenset()) -> bool:
    """True iff this expression IS an authorization proof: a direct
    authorize(...)/authorizeResource(...) call, a call to a user function
    whose declared return type is Authorized<...> (its return sites are
    checked by check_authorization, so the value is proven by induction),
    or a name proven Authorized. (Allowlist — the inverse polarity of
    _expr_leaks_marked.)"""
    if not isinstance(node, dict):
        return False
    kind = node.get("kind")
    if kind == "Call":
        callee = _callee_name(node)
        if callee in _AUTH_GUARDS or callee in minters:
            return True
        return False
    if kind == "Ident" and node.get("name") in authorized:
        return True
    return False


def _minted_kind(fn_decl: Dict[str, Any]) -> str:
    """'direct' if the declared return type is Authorized<...>, 'result'
    if it is Result/Option<...> with an Authorized<...> payload, '' if the
    function does not mint proofs."""
    rt = fn_decl.get("return_type")
    if _is_marker_type(rt, _AUTH_MARKER):
        return "direct"
    if isinstance(rt, dict) and rt.get("kind") == "GenericType" \
            and rt.get("name") in ("Result", "Option") \
            and any(_is_marker_type(a, _AUTH_MARKER)
                    for a in rt.get("args", [])):
        return "result"
    return ""


def _is_result_proof_expr(node: Any, r_proven: Set[str],
                          result_minters: Set[str]) -> bool:
    """True iff this expression carries a Result/Option-wrapped proof: a
    call to a result-minting function, or a name bound only to such."""
    if not isinstance(node, dict):
        return False
    kind = node.get("kind")
    if kind == "Call" and _callee_name(node) in result_minters:
        return True
    if kind == "Ident" and node.get("name") in r_proven:
        return True
    return False


def _ok_pattern_bindings(pattern: Any) -> List[str]:
    """Names bound in payload position of an Ok(...)/Some(...) pattern —
    the only place a Result/Option-wrapped proof unwraps to a proof."""
    if not isinstance(pattern, dict) or pattern.get("kind") != "ConstructorPat":
        return []
    path = pattern.get("path") or []
    if not path or path[-1] not in ("Ok", "Some"):
        return []
    return [a["name"] for a in pattern.get("args", [])
            if isinstance(a, dict) and a.get("kind") == "BindPat"]


def _authorized_names(fn_decl: Dict[str, Any],
                      minters: Set[str] = frozenset(),
                      result_minters: Set[str] = frozenset(),
                      ) -> Tuple[Set[str], Set[str]]:
    """(authorized, result_proven): names proven to hold an Authorized<T>
    value, and names proven to hold a Result/Option-wrapped proof.

    Authorized names are: Authorized-typed params; names whose EVERY
    Let/Var/Assign binding is an authorized expression (fixpoint; one
    unproven binding disqualifies the name — the same all-bindings rule
    as _safe_path_names, inverted marker); and names bound in Ok(...)/
    Some(...) payload position of a match whose scrutinee is proven to
    carry a Result/Option-wrapped proof (and which are never rebound to
    a non-proof)."""
    authorized: Set[str] = {
        p["name"] for p in fn_decl.get("params", [])
        if _is_marker_type(p.get("type"), _AUTH_MARKER)
    }
    binds: Dict[str, List[Any]] = {}
    grants: List[Tuple[Any, List[str]]] = []  # (scrutinee, Ok/Some-bound names)

    def collect(node: Any):
        if isinstance(node, dict):
            # Let/Var carry "name"; Assign carries "target". All three are
            # bindings — missing Assign here would let `tok = raw` keep a
            # previously-proven name authorized (silent demotion miss).
            if node.get("kind") in ("Let", "Var", "Assign") and "value" in node:
                tgt = node.get("name") or node.get("target")
                if isinstance(tgt, str):
                    binds.setdefault(tgt, []).append(node["value"])
            if node.get("kind") in ("Match", "MatchExpr"):
                for arm in node.get("arms", []) or []:
                    names = _ok_pattern_bindings(arm.get("pattern"))
                    if names:
                        grants.append((node.get("scrutinee"), names))
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(fn_decl.get("body", []))
    r_proven: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, values in binds.items():
            if name not in authorized and \
                    all(_expr_is_authorized(v, authorized, minters)
                        for v in values):
                authorized.add(name)
                changed = True
            if name not in r_proven and \
                    all(_is_result_proof_expr(v, r_proven, result_minters)
                        for v in values):
                r_proven.add(name)
                changed = True
        for scrut, names in grants:
            if not _is_result_proof_expr(scrut, r_proven, result_minters):
                continue
            for n in names:
                # the pattern binding is a proof unless a Let/Var/Assign
                # elsewhere rebinds the name to a non-proof
                if n not in authorized and \
                        all(_expr_is_authorized(v, authorized, minters)
                            for v in binds.get(n, [])):
                    authorized.add(n)
                    changed = True
    return authorized, r_proven


def _authorized_param_indices(fn_decl: Dict[str, Any]) -> List[Tuple[int, str]]:
    """(index, name) of every Authorized<...>-typed parameter."""
    return [(i, p["name"]) for i, p in enumerate(fn_decl.get("params", []))
            if _is_marker_type(p.get("type"), _AUTH_MARKER)]


def _walk_returns(node: Any) -> Iterable[Dict[str, Any]]:
    """Yield every Return statement node reachable from `node`."""
    if isinstance(node, dict):
        if node.get("kind") == "Return":
            yield node
        for v in node.values():
            yield from _walk_returns(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_returns(x)


def _walk_marker_binds(node: Any) -> Iterable[Dict[str, Any]]:
    """Yield every Let/Var node annotated with the Authorized<...> marker."""
    if isinstance(node, dict):
        if node.get("kind") in ("Let", "Var") \
                and _is_marker_type(node.get("type"), _AUTH_MARKER):
            yield node
        for v in node.values():
            yield from _walk_marker_binds(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_marker_binds(x)


def _escaped_gated_idents(node: Any, gated: Set[str]) -> Iterable[str]:
    """Yield names of Authorized-gated functions referenced as VALUES —
    anywhere except as a call's direct callee. An indirect call through a
    function value would bypass the call-site obligation, so the escape
    itself is refused."""
    if isinstance(node, dict):
        if node.get("kind") == "Call":
            func = node.get("func")
            if not (isinstance(func, dict) and func.get("kind") == "Ident"):
                yield from _escaped_gated_idents(func, gated)
            for a in node.get("args") or []:
                yield from _escaped_gated_idents(a, gated)
            return
        if node.get("kind") == "Ident" and node.get("name") in gated:
            yield node["name"]
            return
        for v in node.values():
            yield from _escaped_gated_idents(v, gated)
    elif isinstance(node, list):
        for x in node:
            yield from _escaped_gated_idents(x, gated)


def _e0716(fn: str, msg: str, pos: Dict[str, Any], suggestion: str,
           extra: Dict[str, Any]) -> Diagnostic:
    return Diagnostic(
        code="E0716",
        category="capability",
        severity="error",
        message=msg,
        position=Position(pos.get("line", 0), pos.get("column", 0)),
        suggestion=suggestion,
        confidence=1.0,
        extra=dict(extra, function=fn),
    )


def check_authorization(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0716 diagnostics for a mutating sink reached without an
    authorization proof in its dataflow (missing authorization), and for
    the three laundering obligations that keep Authorized<T> nominal:
    unproven arguments to Authorized<...> parameters, Authorized<...>
    annotations initialized with non-proofs, and Authorized-gated
    functions escaping as first-class values."""
    diags: List[Diagnostic] = []
    fns = {d["name"]: d for d in ast.get("decls", [])
           if d.get("kind") == "FunctionDecl"}
    gated = {name: idxs for name, idxs in
             ((n, _authorized_param_indices(f)) for n, f in fns.items())
             if idxs}
    minters = {n for n, f in fns.items() if _minted_kind(f) == "direct"}
    result_minters = {n for n, f in fns.items()
                      if _minted_kind(f) == "result"}
    for d in ast.get("decls", []):
        if d.get("kind") == "ConstDecl" \
                and _is_marker_type(d.get("type"), _AUTH_MARKER) \
                and not _expr_is_authorized(d.get("value"), set(), minters):
            pos = d.get("pos") or {"line": 0, "column": 0}
            diags.append(_e0716(
                d.get("name", "<const>"),
                f"const {d.get('name')!r} is declared "
                f"{_AUTH_MARKER}<...> but its value is not an "
                f"{_AUTH_GUARD}(...) proof; the annotation cannot mint "
                f"the authorization type (CWE-862)",
                pos,
                f"initialize the const with {_AUTH_GUARD}(principal, action)",
                {"name": d.get("name"), "reason": "annotation coercion"},
            ))
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        authorized, r_proven = _authorized_names(d, minters, result_minters)
        body = d.get("body", [])
        # Obligation 1 — call-site proof for Authorized<...> parameters.
        # This is what makes trusting those parameters (above) sound: a
        # raw value is rejected where it enters, so it can never arrive.
        for call in _walk_calls(body):
            callee = _callee_name(call)
            idxs = gated.get(callee)
            if not idxs:
                continue
            args = call.get("args") or []
            for i, pname in idxs:
                token = args[i] if i < len(args) else None
                if token is not None and \
                        _expr_is_authorized(token, authorized, minters):
                    continue
                reason = ("no argument given for the Authorized parameter"
                          if token is None else
                          "the argument is not a proven Authorized<...> value")
                pos = call.get("pos") or fpos
                diags.append(_e0716(
                    fn,
                    f"function {fn!r} passes an unproven value to the "
                    f"{_AUTH_MARKER}<...> parameter {pname!r} of "
                    f"{callee!r} ({reason}); a helper's parameter list "
                    f"does not discharge the authorization obligation "
                    f"(CWE-862)",
                    pos,
                    f"pass {_AUTH_GUARD}(principal, action) (or a value "
                    f"proven Authorized) as argument {i} of {callee}",
                    {"callee": callee, "param": pname, "reason": reason},
                ))
        # Obligation 2 — annotation cannot mint the type.
        for b in _walk_marker_binds(body):
            if _expr_is_authorized(b.get("value"), authorized, minters):
                continue
            pos = b.get("pos") or fpos
            diags.append(_e0716(
                fn,
                f"function {fn!r} binds {b.get('name')!r} as "
                f"{_AUTH_MARKER}<...> but its value is not an "
                f"{_AUTH_GUARD}(...) proof; the annotation cannot mint "
                f"the authorization type (CWE-862)",
                pos,
                f"replace the initializer with {_AUTH_GUARD}(principal, "
                f"action), or drop the {_AUTH_MARKER} annotation",
                {"name": b.get("name"), "reason": "annotation coercion"},
            ))
        # Obligation 3 — gated functions must not escape as values.
        for gname in _escaped_gated_idents(body, set(gated)):
            diags.append(_e0716(
                fn,
                f"function {fn!r} uses the {_AUTH_MARKER}-gated function "
                f"{gname!r} as a value; an indirect call would bypass "
                f"the call-site authorization check (CWE-862)",
                fpos,
                f"call {gname} directly, or wrap it in a function that "
                f"takes the {_AUTH_MARKER}<...> proof explicitly",
                {"callee": gname, "reason": "gated function escapes"},
            ))
        # Obligation 4 — a proof-minting return type is a promise: every
        # return site must actually hand back a proof (or, for Result/
        # Option minters, an Err/None or a proof-carrying Ok/Some).
        # This is what lets _expr_is_authorized trust minter calls.
        mint = _minted_kind(d)
        if mint:
            for ret in _walk_returns(body):
                val = ret.get("value")
                ok = False
                if mint == "direct":
                    ok = _expr_is_authorized(val, authorized, minters)
                elif isinstance(val, dict):
                    if val.get("kind") == "Call":
                        cn = _callee_name(val)
                        rargs = val.get("args") or []
                        if cn in ("Err", "None"):
                            ok = True
                        elif cn in ("Ok", "Some"):
                            ok = len(rargs) == 1 and _expr_is_authorized(
                                rargs[0], authorized, minters)
                    if not ok:
                        ok = _is_result_proof_expr(val, r_proven,
                                                   result_minters)
                if not ok:
                    pos = ret.get("pos") or fpos
                    diags.append(_e0716(
                        fn,
                        f"function {fn!r} declares an "
                        f"{_AUTH_MARKER}<...>-minting return type but this "
                        f"return site does not produce an "
                        f"{_AUTH_GUARD}(...)-derived proof; the return "
                        f"type cannot mint the authorization (CWE-862)",
                        pos,
                        f"return {_AUTH_GUARD}(principal, action) (or wrap "
                        f"a proven value in Ok/Some), or change the "
                        f"declared return type",
                        {"reason": "return does not mint declared proof"},
                    ))
        for call in _walk_calls(d.get("body", [])):
            sink = _callee_name(call)
            if sink not in _MUTATION_SINKS:
                continue
            args = call.get("args") or []
            token = args[1] if len(args) > 1 else None
            if token is not None and \
                    _expr_is_authorized(token, authorized, minters):
                continue
            reason = ("no authorization argument given" if token is None else
                      "the authorization argument is not a proven "
                      "Authorized<...> value")
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0716",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} performs a data mutation via "
                    f"{sink!r} without an authorization proof ({reason}); "
                    f"a mutation reachable without an auth check is the "
                    f"missing-authorization class (CWE-862)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"pass {_AUTH_GUARD}(principal, action) as the second "
                    f"argument of {sink}, or take an "
                    f"{_AUTH_MARKER}<String> parameter so the caller's "
                    f"authorization is carried across the boundary"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": sink, "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0717 — cross-tenant data access / IDOR (CWE-639)
# ----------------------------------------------------------------------
# The resource-binding extension of E0716. E0716 proves *an*
# authorization happened on the dataflow — but not that it named the
# SAME resource the sink touches, so tenant A's perfectly valid session
# token still mutates tenant B's row (broken object-level authorization,
# OWASP API1; the Facebook photo-delete and Peloton account-data shapes).
# The resource-scoped sink `sqlByOwner(stmt, resourceId, proof)` must
# receive a proof produced by `authorizeResource(principal, action,
# resourceId)` for the SAME resource id: both id expressions must
# resolve to the same identity key — an identical literal, or the same
# *stable* name (a param or a name bound exactly once, so it denotes one
# value for the whole body; a rebound name could change between the
# guard and the sink and is refused). Conservative direction throughout:
# any relation the checker cannot prove — computed ids, rebound names,
# proofs carried across a call boundary as plain Authorized<T> params —
# is refused (over-flag, never miss).

_RESOURCE_SINK = "sqlByOwner"          # (stmt, resourceId, proof)
_RES_AUTH_GUARD = "authorizeResource"  # (principal, action, resourceId)


def _stable_names(fn_decl: Dict[str, Any]) -> Set[str]:
    """Names that denote ONE value for the whole body: params that are
    never reassigned, plus names bound exactly once. Only these can
    witness that the guard's id and the sink's id are the same value."""
    counts: Dict[str, int] = {}

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign"):
                tgt = node.get("name") or node.get("target")
                if isinstance(tgt, str):
                    counts[tgt] = counts.get(tgt, 0) + 1
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(fn_decl.get("body", []))
    params = {p["name"] for p in fn_decl.get("params", [])}
    stable = {p for p in params if counts.get(p, 0) == 0}
    stable |= {n for n, c in counts.items() if c == 1 and n not in params}
    return stable


def _id_key(node: Any, stable: Set[str]) -> Optional[Tuple[str, Any]]:
    """Canonical identity of a resource-id expression: a fixed literal or
    a stable name. None = identity unprovable (refused)."""
    if not isinstance(node, dict):
        return None
    kind = node.get("kind")
    if kind in ("StringLit", "IntLit"):
        return ("lit", node.get("value"))
    if kind == "Ident" and node.get("name") in stable:
        return ("name", node.get("name"))
    return None


def _resource_proof_ids(fn_decl: Dict[str, Any],
                        stable: Set[str]) -> Dict[str, Tuple[str, Any]]:
    """Map from stable names bound to an authorizeResource(...) call to
    the id key that call was bound to. Only stable (bound-exactly-once)
    names qualify — a rebindable proof name proves nothing."""
    out: Dict[str, Tuple[str, Any]] = {}

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                name, val = node["name"], node["value"]
                if name in stable and isinstance(val, dict) \
                        and val.get("kind") == "Call" \
                        and _callee_name(val) == _RES_AUTH_GUARD:
                    args = val.get("args") or []
                    key = _id_key(args[2], stable) if len(args) > 2 else None
                    if key is not None:
                        out[name] = key
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(fn_decl.get("body", []))
    return out


def _proof_id_key(node: Any, proof_ids: Dict[str, Tuple[str, Any]],
                  stable: Set[str]) -> Optional[Tuple[str, Any]]:
    """The resource id this proof expression is bound to: a direct
    authorizeResource(_, _, id) call, or a stable name bound to one.
    None = not a resource-bound proof."""
    if not isinstance(node, dict):
        return None
    kind = node.get("kind")
    if kind == "Call" and _callee_name(node) == _RES_AUTH_GUARD:
        args = node.get("args") or []
        return _id_key(args[2], stable) if len(args) > 2 else None
    if kind == "Ident":
        return proof_ids.get(node.get("name"))
    return None


def _fmt_id_key(key: Tuple[str, Any]) -> str:
    tag, val = key
    return repr(val) if tag == "lit" else f"name {val!r}"


def check_resource_authorization(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0717 diagnostics for a resource-scoped mutation whose
    authorization proof is missing, unbound, or bound to a DIFFERENT
    resource id than the one the sink touches (IDOR, CWE-639)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        stable = _stable_names(d)
        proof_ids = _resource_proof_ids(d, stable)
        for call in _walk_calls(d.get("body", [])):
            if _callee_name(call) != _RESOURCE_SINK:
                continue
            args = call.get("args") or []
            rid = args[1] if len(args) > 1 else None
            proof = args[2] if len(args) > 2 else None
            rid_key = _id_key(rid, stable) if rid is not None else None
            proof_key = _proof_id_key(proof, proof_ids, stable) if proof is not None else None
            if rid_key is not None and proof_key is not None and rid_key == proof_key:
                continue
            if proof is None:
                reason = "no resource-bound authorization proof given"
            elif proof_key is None:
                reason = (f"the proof is not a proven "
                          f"{_RES_AUTH_GUARD}(...) bound to a resource id")
            elif rid_key is None:
                reason = ("the sink's resource id is not a fixed literal "
                          "or a stable (never-rebound) name, so its "
                          "identity cannot be proven")
            else:
                reason = (f"the proof authorizes resource "
                          f"{_fmt_id_key(proof_key)} but the sink mutates "
                          f"resource {_fmt_id_key(rid_key)}")
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0717",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} mutates a resource via "
                    f"{_RESOURCE_SINK!r} whose authorization is not bound "
                    f"to the same resource id ({reason}); an authorized "
                    f"caller reaching ANOTHER tenant's row is the IDOR / "
                    f"cross-tenant class (CWE-639)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"authorize the SAME id the sink uses: pass "
                    f"{_RES_AUTH_GUARD}(principal, action, resourceId) as "
                    f"the third argument of {_RESOURCE_SINK} with the "
                    f"identical resourceId (a literal, or a name that is "
                    f"never rebound) as the second argument"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _RESOURCE_SINK, "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0718 — open redirect: redirect target steerable by untrusted input
# ----------------------------------------------------------------------
# CWE-601. A redirect whose target URL is attacker-controlled sends the
# user to a phishing / token-stealing site while looking like a link
# from the trusted origin. Same sink+sanitizer+literal shape as E0711:
# the `redirect` sink must receive a fixed literal target, or a
# `safeRedirect(host, path)` result (which pins the host so the target
# can only ever stay on `host`). A bare param or a concatenation is the
# open-redirect precondition and is refused.

_REDIRECT_SINK = "redirect"
_REDIRECT_SANITIZER = "safeRedirect"


def _redirect_arg_is_safe(node: Any, safe_names: Set[str]) -> Optional[str]:
    if not isinstance(node, dict):
        return "redirect target is not a fixed literal"
    kind = node.get("kind")
    if kind == "StringLit":
        return None
    if kind == "Call":
        if _callee_name(node) == _REDIRECT_SANITIZER:
            return None
        return f"target is a computed call - use {_REDIRECT_SANITIZER}(host, path)"
    if kind == "Ident" and node.get("name") in safe_names:
        return None
    if kind == "BinOp" and node.get("op") == "+":
        return f"target is built by concatenation - use {_REDIRECT_SANITIZER}(host, path)"
    return f"target is a dynamic expression - use {_REDIRECT_SANITIZER}(host, path)"


def _safe_redirect_names(body: Any) -> Set[str]:
    binds: Dict[str, List[Dict[str, Any]]] = {}

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                binds.setdefault(node["name"], []).append(node["value"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(body)
    safe: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, values in binds.items():
            if name in safe:
                continue
            if all(_redirect_arg_is_safe(v, safe) is None for v in values):
                safe.add(name)
                changed = True
    return safe


def check_open_redirect(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0718 diagnostics for a redirect fed an untrusted target."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        body = d.get("body", [])
        safe_names = _safe_redirect_names(body)
        for call in _walk_calls(body):
            if _callee_name(call) != _REDIRECT_SINK:
                continue
            args = call.get("args") or []
            if not args:
                continue
            reason = _redirect_arg_is_safe(args[0], safe_names)
            if reason is None:
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0718",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} redirects to an untrusted target "
                    f"({reason}); an open redirect sends users to an "
                    f"attacker-controlled site from a trusted link"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"redirect to a fixed literal path, or pin the host with "
                    f"{_REDIRECT_SANITIZER}(\"your-host.example\", path) so the "
                    f"target can only stay on your origin"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _REDIRECT_SINK, "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0719 — server-side template injection (SSTI) — CWE-94
# ----------------------------------------------------------------------
# The Jinja2/Flask/Handlebars SSTI shape: the TEMPLATE itself is built
# from untrusted input. When user data steers template *syntax* (not
# just fills a slot), the engine evaluates it — arbitrary code execution.
# The rule mirrors E0713 but with no sanitizer: `renderTemplate`'s first
# argument (the template) must be a fixed string literal (or a name bound
# only to literals). Untrusted data belongs in the SECOND argument (the
# data model), which the engine escapes; a dynamic template is refused.

_TEMPLATE_SINKS = ("renderTemplate",)


# The explicit-trust boundary: `trusted(x)` asserts a dynamic value comes
# from a vetted source. It is the auditable escape hatch for the two
# sink+literal checks that have NO safer sanitizer (E0719 template, E0720
# deserialize) — the dual of reveal()/redact(). Accepting it only relaxes
# those checks (strictly non-breaking).
_TRUSTED = "trusted"


def _template_expr_is_safe(node: Any, safe_names: Set[str]) -> Optional[str]:
    """None if `node` is a fixed template (literal, literal-bound name, or
    an explicit trusted(...) assertion), else a short reason it is unsafe."""
    if not isinstance(node, dict):
        return "template is not a fixed literal"
    kind = node.get("kind")
    if kind == "StringLit":
        return None
    if kind == "Call" and _callee_name(node) == _TRUSTED:
        return None  # explicit, auditable trust assertion
    if kind == "Ident" and node.get("name") in safe_names:
        return None
    if kind == "BinOp" and node.get("op") == "+":
        return "template is built by string concatenation"
    return "template is a dynamic expression, not a fixed literal"


def _safe_template_names(body: Any) -> Set[str]:
    """Names bound only to fixed templates (literal or literal-bound),
    via the same straight-line fixpoint as the SQL/path passes."""
    binds: Dict[str, List[Dict[str, Any]]] = {}

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                binds.setdefault(node["name"], []).append(node["value"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(body)
    safe: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, values in binds.items():
            if name in safe:
                continue
            if all(_template_expr_is_safe(v, safe) is None for v in values):
                safe.add(name)
                changed = True
    return safe


def check_template_injection(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0719 diagnostics for a renderTemplate call whose template
    argument is dynamic (built from untrusted input) — SSTI (CWE-94)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        body = d.get("body", [])
        safe_names = _safe_template_names(body)
        for call in _walk_calls(body):
            if _callee_name(call) not in _TEMPLATE_SINKS:
                continue
            args = call.get("args") or []
            if not args:
                continue
            reason = _template_expr_is_safe(args[0], safe_names)
            if reason is None:
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0719",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} renders a dynamic template via "
                    f"{_callee_name(call)!r} ({reason}); untrusted input in "
                    f"the template is server-side template injection (RCE)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    "keep the template a fixed string literal; pass "
                    "untrusted values as the second (data) argument, which "
                    "the engine escapes instead of evaluating"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call), "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0720 — insecure deserialization of untrusted data — CWE-502
# ----------------------------------------------------------------------
# The pickle / Java readObject / unsafe-YAML gadget class: feeding
# untrusted bytes to a decoder that can instantiate arbitrary types is
# remote code execution. Like SSTI, there is no safe way to `deserialize`
# untrusted input with an unrestricted decoder — the sanctioned form is
# `schemaDecode(schema, data)`, a decoder pinned to a fixed schema that
# can only ever produce the declared shape. E0720 refuses `deserialize`
# on any non-literal (i.e. untrusted) argument.

_DESERIALIZE_SINKS = ("deserialize",)
_SCHEMA_DECODE = "schemaDecode"


def _deser_arg_is_safe(node: Any, safe_names: Set[str]) -> Optional[str]:
    """None if `node` is a trusted-constant argument to deserialize (a
    literal or literal-bound name), else a short reason it is unsafe."""
    if not isinstance(node, dict):
        return "argument is not a fixed literal"
    kind = node.get("kind")
    if kind == "StringLit":
        return None
    if kind == "Call" and _callee_name(node) == _TRUSTED:
        return None  # explicit, auditable trust assertion
    if kind == "Ident" and node.get("name") in safe_names:
        return None
    return "argument is untrusted / dynamic data"


def check_deserialization(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0720 diagnostics for `deserialize` fed untrusted (non-
    literal) data — insecure deserialization (CWE-502)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        body = d.get("body", [])
        # A name bound only to literals is a trusted constant.
        safe_names = _safe_template_names(body)
        for call in _walk_calls(body):
            if _callee_name(call) not in _DESERIALIZE_SINKS:
                continue
            args = call.get("args") or []
            if not args:
                continue
            reason = _deser_arg_is_safe(args[0], safe_names)
            if reason is None:
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0720",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} deserializes untrusted data via "
                    f"{_callee_name(call)!r} ({reason}); an unrestricted "
                    f"decoder on attacker-controlled bytes is remote code "
                    f"execution"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    f"decode with {_SCHEMA_DECODE}(schema, data), which pins "
                    f"the output to a fixed schema and cannot instantiate "
                    f"arbitrary types"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call), "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0727 — XML external entity (XXE) — CWE-611
# ----------------------------------------------------------------------
# Parsing untrusted XML with an entity-resolving parser lets a document
# pull in <!ENTITY xxe SYSTEM "file:///etc/passwd"> (local file read) or a
# URL (SSRF / billion-laughs DoS). Like insecure deserialization, this is a
# parser-CONFIG class, not a content-escaping one: `parseXml` is the
# entity-resolving sink and is refused on untrusted (non-literal) input;
# `parseXmlSafe` is the hardened parser (external entities disabled) and is
# the sanctioned alternative.

_XXE_SINKS = ("parseXml",)


def check_xxe(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0727 diagnostics for `parseXml` fed untrusted (non-literal)
    input — XML external entity injection (CWE-611)."""
    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        fn = d["name"]
        fpos = d.get("pos") or {"line": 0, "column": 0}
        body = d.get("body", [])
        safe_names = _safe_template_names(body)
        for call in _walk_calls(body):
            if _callee_name(call) not in _XXE_SINKS:
                continue
            args = call.get("args") or []
            if not args:
                continue
            reason = _deser_arg_is_safe(args[0], safe_names)
            if reason is None:
                continue
            pos = call.get("pos") or fpos
            diags.append(Diagnostic(
                code="E0727",
                category="capability",
                severity="error",
                message=(
                    f"function {fn!r} parses untrusted XML via "
                    f"{_callee_name(call)!r} ({reason}); an entity-resolving "
                    f"parser reads local files and reaches internal URLs (XXE)"
                ),
                position=Position(pos.get("line", 0), pos.get("column", 0)),
                suggestion=(
                    "parse with parseXmlSafe(data), which disables external "
                    "entity resolution (no file read, no SSRF, no billion-"
                    "laughs)"
                ),
                confidence=1.0,
                extra={"function": fn, "sink": _callee_name(call), "reason": reason},
            ))
    return diags


# ----------------------------------------------------------------------
# E0723 — hardcoded credential in source (CWE-798)
# ----------------------------------------------------------------------
# The single most common real-world security finding (millions of keys
# leaked to public repos yearly). A secret baked into a string literal is
# in version control forever and ships in every build. This is a
# literal-content scan — a new detector family — matching high-confidence
# provider credential shapes so false positives are near zero (demo
# passwords like "hunter2" do not match; a real AKIA... key does). The fix
# is to source the secret from the environment / a secret manager, never
# a literal.

_CREDENTIAL_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"),                     "AWS access key id"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),           "GitHub token"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"),               "Google API key"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"),        "Slack token"),
    (re.compile(r"sk_live_[0-9A-Za-z]{20,}"),             "Stripe live secret key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),   "private key (PEM)"),
]


def _walk_string_lits(node: Any) -> Iterable[Dict[str, Any]]:
    """Yield every StringLit node reachable from `node`."""
    if isinstance(node, dict):
        if node.get("kind") == "StringLit":
            yield node
        for v in node.values():
            yield from _walk_string_lits(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_string_lits(x)


def check_hardcoded_secret(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0723 diagnostics for string literals that match a known
    provider-credential shape (a hardcoded secret, CWE-798)."""
    diags: List[Diagnostic] = []
    for lit in _walk_string_lits(ast):
        val = lit.get("value")
        if not isinstance(val, str):
            continue
        for pat, label in _CREDENTIAL_PATTERNS:
            if pat.search(val):
                pos = lit.get("pos") or {"line": 0, "column": 0}
                diags.append(Diagnostic(
                    code="E0723",
                    category="capability",
                    severity="error",
                    message=(
                        f"string literal contains a hardcoded {label}; a "
                        f"credential in source is committed to version "
                        f"control and shipped in every build"
                    ),
                    position=Position(pos.get("line", 0), pos.get("column", 0)),
                    suggestion=(
                        "load the secret at runtime from the environment or "
                        "a secret manager (e.g. getEnv(\"...\")), never a "
                        "string literal"
                    ),
                    confidence=1.0,
                    extra={"credential_kind": label},
                ))
                break  # one diagnostic per literal
    return diags


# ----------------------------------------------------------------------
# AST walking
# ----------------------------------------------------------------------

def _walk_calls(node: Any) -> Iterable[Dict[str, Any]]:
    """Yield every Call expression node reachable from `node`."""
    if isinstance(node, dict):
        if node.get("kind") == "Call":
            yield node
        for v in node.values():
            yield from _walk_calls(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_calls(x)


def _callee_name(call_node: Dict[str, Any]) -> Optional[str]:
    """Extract a simple name from a Call's `func` if direct/named."""
    func = call_node.get("func") or {}
    kind = func.get("kind")
    if kind == "Ident":
        return func.get("name")
    if kind == "Field":
        inner = func.get("value") or {}
        if inner.get("kind") == "Ident":
            return func.get("name")
    return None


def _format_effect(eff: EffectEntry) -> str:
    path, arg = eff
    p = ".".join(path)
    if arg is None:
        return f"'{p}'"
    return f"'{p}({arg!r})'"


def _format_effect_list(effs: List[EffectEntry]) -> str:
    if not effs:
        return "'pure'"
    return ", ".join(_format_effect(e) for e in sorted(effs))


# ----------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------

def check_effects(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return a list of E0801 diagnostics, one per call-site violation."""
    user_effects: Dict[str, List[EffectEntry]] = {}
    union_cases: Set[str] = set()
    for d in ast.get("decls", []):
        if d.get("kind") == "FunctionDecl":
            user_effects[d["name"]] = _declared_effects(d)
        elif d.get("kind") == "UnionDecl":
            for c in d.get("cases", []):
                union_cases.add(c["name"])
        elif d.get("kind") == "RecordDecl":
            user_effects[d["name"]] = []

    for name in ("Some", "None", "Ok", "Err"):
        union_cases.add(name)

    diags: List[Diagnostic] = []
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        caller_name = d["name"]
        caller_effects = _declared_effects(d)
        pos = d.get("pos") or {"line": 0, "column": 0}

        for call in _walk_calls(d.get("body", [])):
            callee = _callee_name(call)
            if callee is None or callee in union_cases:
                continue
            if callee in user_effects:
                callee_effects = user_effects[callee]
            elif callee in _STDLIB_EFFECTS:
                callee_effects = _STDLIB_EFFECTS[callee]
            elif callee.endswith("?") or callee.endswith("!"):
                callee_effects = _STDLIB_EFFECTS.get(callee, [])
            else:
                continue

            for callee_eff in callee_effects:
                if _effect_covered(caller_effects, callee_eff):
                    continue
                missing_pretty = _format_effect(callee_eff)
                caller_pretty = _format_effect_list(caller_effects)
                diags.append(Diagnostic(
                    code="E0801",
                    category="effect",
                    severity="error",
                    message=(
                        f"function {caller_name!r} (effects {caller_pretty}) "
                        f"calls {callee!r} which has effect {missing_pretty} "
                        f"not covered by the caller"
                    ),
                    position=Position(pos.get("line", 0), pos.get("column", 0)),
                    suggestion=(
                        f"add {missing_pretty} to {caller_name}'s effects "
                        f"clause, or change the call site"
                    ),
                    confidence=1.0,
                    extra={
                        "caller": caller_name,
                        "callee": callee,
                        "caller_effects": [
                            [list(p), a] for p, a in caller_effects
                        ],
                        "missing_effect": [list(callee_eff[0]), callee_eff[1]],
                    },
                ))
    return diags
