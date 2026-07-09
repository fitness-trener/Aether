"""Diff ingester (Phase 0, P0.3).

Turns a change-set into the set of changed functions/regions with their
enclosing scope. This is the front half of differential capability analysis:
the delta analyzer (tools.cap_delta) only ever looks at what this module marks
as changed.

Inputs supported:
  * two source strings           -> changed_regions(base_src, head_src)
  * a unified diff + both sources -> changed_regions_from_unified_diff(...)
  * git refs                      -> changed_regions_from_git(repo, base, head, path)

Output: a ChangeSet with, per Python function (qualified name incl. class):
    kind         : "added" | "deleted" | "modified"
    head_line    : def line in head (None if deleted)
    base_line    : def line in base (None if added)
    enclosing    : "<module>" or the enclosing class qualname
    changed_head_lines / changed_base_lines : the specific lines that moved
Plus `module_scope_changed`: True if any import-time / top-level statement
changed (module-level capability surface can shift without any function
changing — e.g. a new module-level `requests.get(...)`).

SOUNDNESS NOTE: when in doubt, a region is reported as changed. Over-reporting
changed regions is safe (it can only make the delta analyzer look at MORE code);
under-reporting would let a capability slip in unanalyzed. We never trade that.
"""
from __future__ import annotations
import ast as _ast
import difflib
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class FnSpan:
    name: str
    lineno: int
    end_lineno: int
    enclosing: str           # "<module>" or class qualname


@dataclass
class ChangedFn:
    name: str
    kind: str                # added | deleted | modified
    head_line: Optional[int]
    base_line: Optional[int]
    enclosing: str
    changed_head_lines: List[int] = field(default_factory=list)
    changed_base_lines: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "kind": self.kind,
            "head_line": self.head_line, "base_line": self.base_line,
            "enclosing": self.enclosing,
            "changed_head_lines": sorted(self.changed_head_lines),
            "changed_base_lines": sorted(self.changed_base_lines),
        }


@dataclass
class ChangeSet:
    changed_fns: List[ChangedFn]
    module_scope_changed: bool
    parse_ok: bool = True
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "changed_functions": [c.to_dict() for c in self.changed_fns],
            "module_scope_changed": self.module_scope_changed,
            "parse_ok": self.parse_ok,
            "note": self.note,
        }


def _fn_spans(source: str) -> Tuple[Optional[List[FnSpan]], Set[int]]:
    """All function spans + the set of line numbers that belong to module
    scope (top-level statements that are NOT inside any function)."""
    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return None, set()
    spans: List[FnSpan] = []

    def walk(node, enclosing: str):
        for child in getattr(node, "body", []):
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                qual = child.name if enclosing == "<module>" else enclosing + "." + child.name
                end = getattr(child, "end_lineno", child.lineno)
                spans.append(FnSpan(qual, child.lineno, end, enclosing))
                walk(child, qual)               # nested defs
            elif isinstance(child, _ast.ClassDef):
                qual = child.name if enclosing == "<module>" else enclosing + "." + child.name
                walk(child, qual)
    walk(tree, "<module>")

    # module-scope lines = top-level statements not covered by any top-level fn
    n_lines = source.count("\n") + 1
    covered = set()
    for s in spans:
        if s.enclosing == "<module>":
            covered.update(range(s.lineno, s.end_lineno + 1))
    module_lines = set(range(1, n_lines + 1)) - covered
    return spans, module_lines


def _innermost(spans: List[FnSpan], line: int) -> Optional[FnSpan]:
    best: Optional[FnSpan] = None
    for s in spans:
        if s.lineno <= line <= s.end_lineno:
            if best is None or (s.end_lineno - s.lineno) < (best.end_lineno - best.lineno):
                best = s
    return best


def _changed_lines(base_src: str, head_src: str) -> Tuple[Set[int], Set[int]]:
    """Return (changed_base_lines, changed_head_lines) via line diff."""
    b = base_src.splitlines()
    h = head_src.splitlines()
    sm = difflib.SequenceMatcher(a=b, b=h, autojunk=False)
    base_changed: Set[int] = set()
    head_changed: Set[int] = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        base_changed.update(range(i1 + 1, i2 + 1))   # 1-based
        head_changed.update(range(j1 + 1, j2 + 1))
    return base_changed, head_changed


def _build_changeset(base_src: str, head_src: str,
                     base_changed: Set[int], head_changed: Set[int]) -> ChangeSet:
    base_spans, base_modlines = _fn_spans(base_src)
    head_spans, head_modlines = _fn_spans(head_src)
    if base_spans is None or head_spans is None:
        return ChangeSet([], True, parse_ok=False,
                         note="base or head did not parse; treat entire change-set as UNPROVABLE")

    base_by_name = {s.name: s for s in base_spans}
    head_by_name = {s.name: s for s in head_spans}

    # attribute changed lines to enclosing functions
    head_hits: Dict[str, Set[int]] = {}
    head_module_touched = False
    for ln in head_changed:
        fn = _innermost(head_spans, ln)
        if fn is None:
            if ln in head_modlines:
                head_module_touched = True
        else:
            head_hits.setdefault(fn.name, set()).add(ln)

    base_hits: Dict[str, Set[int]] = {}
    base_module_touched = False
    for ln in base_changed:
        fn = _innermost(base_spans, ln)
        if fn is None:
            if ln in base_modlines:
                base_module_touched = True
        else:
            base_hits.setdefault(fn.name, set()).add(ln)

    changed: List[ChangedFn] = []
    seen: Set[str] = set()

    for name, hspan in head_by_name.items():
        if name not in base_by_name:
            changed.append(ChangedFn(name, "added", hspan.lineno, None, hspan.enclosing,
                                     changed_head_lines=sorted(head_hits.get(name, set()
                                          ) or set(range(hspan.lineno, hspan.end_lineno + 1)))))
            seen.add(name)
        elif name in head_hits or name in base_hits:
            changed.append(ChangedFn(name, "modified", hspan.lineno, base_by_name[name].lineno,
                                     hspan.enclosing,
                                     changed_head_lines=sorted(head_hits.get(name, set())),
                                     changed_base_lines=sorted(base_hits.get(name, set()))))
            seen.add(name)

    for name, bspan in base_by_name.items():
        if name not in head_by_name and name not in seen:
            changed.append(ChangedFn(name, "deleted", None, bspan.lineno, bspan.enclosing,
                                     changed_base_lines=sorted(base_hits.get(name, set()
                                          ) or set(range(bspan.lineno, bspan.end_lineno + 1)))))

    return ChangeSet(changed, head_module_touched or base_module_touched)


def changed_regions(base_src: str, head_src: str) -> ChangeSet:
    """Primary entry point: diff two full sources."""
    base_changed, head_changed = _changed_lines(base_src, head_src)
    return _build_changeset(base_src, head_src, base_changed, head_changed)


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def changed_regions_from_unified_diff(diff_text: str, base_src: str, head_src: str) -> ChangeSet:
    """Use an explicit unified diff to compute changed line numbers, then map
    to functions. base_src/head_src are still needed to resolve enclosing
    scopes. Falls back to source diff if the patch has no parseable hunks."""
    base_changed: Set[int] = set()
    head_changed: Set[int] = set()
    bln = hln = 0
    saw_hunk = False
    for raw in diff_text.splitlines():
        m = _HUNK.match(raw)
        if m:
            saw_hunk = True
            bln = int(m.group(1))
            hln = int(m.group(3))
            continue
        if not saw_hunk or raw.startswith(("---", "+++")):
            continue
        if raw.startswith("+"):
            head_changed.add(hln); hln += 1
        elif raw.startswith("-"):
            base_changed.add(bln); bln += 1
        elif raw.startswith(" ") or raw == "":
            bln += 1; hln += 1
    if not saw_hunk:
        return changed_regions(base_src, head_src)
    return _build_changeset(base_src, head_src, base_changed, head_changed)


def changed_regions_from_git(repo: str, base_ref: str, head_ref: str, path: str) -> ChangeSet:
    """Diff one file across two git refs. Read-only; never mutates the repo."""
    def show(ref: str) -> str:
        try:
            return subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"],
                                  capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            return ""   # file absent at that ref (whole-file add/delete)
    return changed_regions(show(base_ref), show(head_ref))
