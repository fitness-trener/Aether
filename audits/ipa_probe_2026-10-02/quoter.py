"""Side measurement: how many findings hinge on a HAND-WRITTEN identifier
quoter in the distribution — a helper whose every return is
`Q{x}Q` with `x = <param>.replace(Q, QQ)`, Q one of `"` and a backtick?

Recognising such a helper is a sanitizer-recognition question, not an
interprocedural one: its result is quoted whatever its argument is. So the
argument at the sink clears when every OTHER leaf is literal or IPA-safe.

Run (repo root): python -B audits/ipa_probe_2026-10-02/quoter.py <fw_full.json> <SRC> [--site]
"""
import ast
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pkg_ipa as P  # noqa: E402


def _blocks(node):
    for n in ast.walk(node):
        for field in ("body", "orelse", "finalbody"):
            b = getattr(n, field, None)
            if isinstance(b, list) and b and isinstance(b[0], ast.stmt):
                yield b


def is_quoter(g):
    """Each `return` is checked against the binding of its name in the SAME
    statement list, just before it (the backtick branch must escape
    backticks); the name must not be rebound between the two."""
    if not g.returns or g.gen:
        return False
    rets = 0
    for block in _blocks(g.node):
        for i, st in enumerate(block):
            if not isinstance(st, ast.Return):
                continue
            rets += 1
            rv = st.value
            if not (isinstance(rv, ast.JoinedStr) and len(rv.values) == 3):
                return False
            a, m, b = rv.values
            if not (isinstance(a, ast.Constant) and isinstance(b, ast.Constant)
                    and a.value == b.value and a.value in ('"', "`")):
                return False
            if not (isinstance(m, ast.FormattedValue) and isinstance(m.value, ast.Name)
                    and m.conversion == -1 and m.format_spec is None):
                return False
            prev = [s for s in block[:i] if isinstance(s, ast.Assign) and len(s.targets) == 1
                    and isinstance(s.targets[0], ast.Name) and s.targets[0].id == m.value.id]
            if len(prev) != 1 or block.index(prev[0]) != i - 1:
                return False
            c = prev[0].value
            if not isinstance(c, ast.Call):
                return False
            if not (isinstance(c.func, ast.Attribute) and c.func.attr == "replace" and len(c.args) == 2
                    and all(isinstance(x, ast.Constant) for x in c.args)
                    and c.args[0].value == a.value and c.args[1].value == a.value * 2):
                return False
    return rets == len(g.returns)


_orig = P.Analyzer.safe_leaf


def safe_leaf(s, lf, env, stack):
    if lf[0] == "pkgcall" and is_quoter(lf[2]):
        return P.SOUND, [("pkgcall", lf[1])]
    return _orig(s, lf, env, stack)


def main():
    P.Analyzer.safe_leaf = safe_leaf
    rows = json.load(open(sys.argv[1], encoding="utf-8"))["findings"]
    src = sys.argv[2]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["dist"]].append(r)
    n_q = n_clear = 0
    quoters, blockers = set(), collections.Counter()
    for dist, fs in sorted(by.items()):
        pkg = P.Package(os.path.join(src, dist), dist if "--site" in sys.argv else "")
        quoters |= {g.qual() for g in pkg.fns if is_quoter(g)}
        an = P.Analyzer(pkg, fields=False, summaries=True)
        for f in fs:
            mod = next((m for m in pkg.mods.values() if m.path == f["file"]), None)
            if not mod:
                continue
            fn = P.fn_at(pkg, mod, f["line"])
            call = P.sink_call(mod.tree, f["line"], f["col"], f["extra"].get("callee"))
            arg = P.sink_arg(call) if call else None
            if arg is None:
                continue
            lv = an.leaves(arg, mod, fn, frozenset())
            if not any(l[0] == "pkgcall" and is_quoter(l[2]) for l in lv):
                continue
            n_q += 1
            if an.safe_expr(arg, mod, fn, {}, frozenset()) is not None:
                n_clear += 1
            else:
                for k in {l[0] for l in lv if an.safe_leaf(l, {}, frozenset()) is None}:
                    blockers[k] += 1
    print("quoter-shaped helpers:", sorted(quoters))
    print("findings with a quoter call in the judged argument:", n_q)
    print("  every other leaf literal or IPA-safe (would clear):", n_clear)
    print("  blocking leaf kinds in the rest (per finding):", blockers.most_common())


if __name__ == "__main__":
    main()
