"""The recursive descent over the AST, written once.

Six generators across `passes/` were the same eleven lines with one
`kind` string changed, and a dozen more inlined the same recursion in a
local `collect()`. `walk(node, *kinds)` replaces them all: it yields
every dict node reachable from `node` — descending through dict values
and list elements — whose `"kind"` is in `kinds`. With no kinds it
yields every dict node.

Order is pre-order and follows dict insertion order, which is source
order for parser output. A matching node is yielded AND descended into,
so a Call nested in a Call yields both. Both properties are load-bearing:
`tests/test_corpus.py` pins the exact multiplicity every corpus program
reports, so a walk that visits a node twice or skips a branch fails the
gate rather than passing quietly.

`callee_name` lives here because every caller of `walk(node, "Call")`
immediately needs it, and it was the same clone in the same three files.

Deliberately NOT unified: `patch_target.py`'s `_walk_calls_with_path` /
`_walk_returns_with_path`. They thread a structural path prefix through
the descent and skip the `kind`/`pos`/`name`/`op` fields, to build the
anchor a fix-loop splices a patch against — a different traversal with a
different return type, pinned by `tests/test_alsp_corpus.py`'s H.A.1.b
anchor contract. Nor are the passes that PRUNE (`_expr_leaks_marked`,
`_escaped_gated_idents`): a walk that stops early is not this walk.
"""

from __future__ import annotations
from typing import Any, Dict, Iterator, List, NamedTuple, Optional


def walk(node: Any, *kinds: str) -> Iterator[Dict[str, Any]]:
    """Yield every dict node reachable from `node` whose `kind` is in
    `kinds` (every dict node if `kinds` is empty)."""
    if isinstance(node, dict):
        if not kinds or node.get("kind") in kinds:
            yield node
        for v in node.values():
            yield from walk(v, *kinds)
    elif isinstance(node, list):
        for x in node:
            yield from walk(x, *kinds)


def fn_exprs(decl: Dict[str, Any]) -> List[Any]:
    """Everything a function EVALUATES: its body AND its `requires` /
    `ensures` clauses. Every pass that asks "what does this function do"
    walks this, never `decl["body"]` alone — a `requires
    isOk?(writeFile(...))` runs at call entry, so walking only the body
    let a `pure` function write files and a `requires shellExec("rm -rf "
    + n)` escape E0801 and E0714 together (audit 2026-09-24 A1)."""
    return [decl.get("body", []), decl.get("requires", []),
            decl.get("ensures", [])]


def contexts(ast: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Every evaluation context of a program, as function-shaped dicts:
    each `FunctionDecl`, plus one synthetic PURE context per refinement
    predicate (`type T = B where <pred>`, run at every boundary check,
    with `self` as its one parameter) and per `const` initializer (run
    once at module load). Neither declares effects, so any effect in
    them is E0801, and under a module E0701 (audit 2026-09-24 A1).

    The synthetic contexts carry `"synthetic"` and a `name` no user
    function can have (`<const X>` / `<type T where>`), so a pass that
    keys a SIGNATURE table by function name must keep reading real
    `FunctionDecl`s; only the per-body scans iterate this."""
    for d in ast.get("decls", []):
        k = d.get("kind")
        if k == "FunctionDecl":
            yield d
        elif k == "TypeDecl" and d.get("refinement") is not None:
            yield {"kind": "FunctionDecl", "synthetic": "refinement",
                   "name": f"<type {d.get('name')} where>",
                   "params": [{"name": "self", "type": d.get("base")}],
                   "effects": [], "body": [d["refinement"]],
                   "pos": d.get("pos")}
        elif k == "ConstDecl" and d.get("value") is not None:
            yield {"kind": "FunctionDecl", "synthetic": "const",
                   "name": f"<const {d.get('name')}>", "params": [],
                   "effects": [], "body": [d["value"]], "pos": d.get("pos")}


class Binder(NamedTuple):
    """One place a name gets a value inside a function.

    `value` is the bound expression, or None for a VALUE-LESS binder: a
    `for` loop variable or a `match` pattern binding, whose value is
    some element of `source` (the iterable / the scrutinee). A pass that
    PROVES something about a name (safe literal, stable id, authorized
    proof) must treat a value-less binder as disqualifying; a taint pass
    propagates through `source`."""
    name: str
    value: Optional[Dict[str, Any]]
    kind: str
    node: Dict[str, Any]
    source: Optional[Dict[str, Any]]


def binders(decl: Dict[str, Any]) -> Iterator[Binder]:
    """Every binding in a function: its parameters (kind `Param`, value
    None), then in body and contracts `let`, `var`, assignment, `for`
    loop variable, and each `BindPat` / `AsPat` name of every `match`
    statement AND match expression arm.

    The ONE binding iterator. Six fixpoints each walked their own subset
    and five of them knew only Let/Var/Assign, so `let s = "SELECT 1";
    for s in xs do sqlQuery(s) end` was proven a literal (audit
    2026-09-24 A5; the BUG-013/014 class, closed here at the root rather
    than walker by walker). `Let`/`Var` carry `name`, `Assign` carries
    `target` (the Python frontend's `Assign` carries `name`)."""
    for p in decl.get("params") or []:
        if isinstance(p.get("name"), str):
            # A parameter is a binder too: a value the body did not choose.
            # Without it `p = "lit"` after `readFile(p)` proved `p` a literal.
            yield Binder(p["name"], None, "Param", p, None)
    for n in walk(fn_exprs(decl)):
        k = n.get("kind")
        if k in ("Let", "Var", "Assign"):
            tgt = n.get("name") or n.get("target")
            if isinstance(tgt, str):
                yield Binder(tgt, n.get("value"), k, n, None)
        elif k == "For":
            if isinstance(n.get("var"), str):
                yield Binder(n["var"], None, k, n, n.get("iter"))
        elif k in ("Match", "MatchExpr"):
            for arm in n.get("arms") or []:
                for p in walk(arm.get("pattern"), "BindPat", "AsPat"):
                    if isinstance(p.get("name"), str):
                        yield Binder(p["name"], None, p["kind"], p,
                                     n.get("scrutinee"))


def callee_name(call_node: Dict[str, Any]) -> Optional[str]:
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
