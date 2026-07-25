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
from typing import Any, Dict, Iterator, Optional


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
