"""E0713 shape census over a scan json (scan.py output).
usage: python census.py <scan.json> [--examples KIND]
       HYPO=quote_db_identifier python census.py ...   (what-if: treat that call as a sanitizer)
A bench/pypi_scan/run_scan.py --json file works too (no column: located by line + method name).

For every E0713 finding: locate the sink Call, take the judged argument,
classify its top shape, and ask a STRONGER literal-only evaluator whether
the argument can only ever be a string literal. Each extra power the
evaluator uses is recorded as a feature, so a finding cleared only with
feature F is attributed to F. Aggregate counts only."""
import ast, json, os, sys, collections

SRC = os.environ.get("FW_SRC", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "bench", "framework_scan", "_work", "src"))
d = json.load(open(sys.argv[1], encoding="utf-8"))
HYPO = set(os.environ.get("HYPO", "").split(",")) - {""}
EX = sys.argv[sys.argv.index("--examples") + 1] if "--examples" in sys.argv else None


SINKM = {"execute","executemany","executescript","raw","exec_driver_sql","exec","fetch","fetchrow","fetchval",
         "fetch_all","fetch_one","fetch_val","mogrify","execute_sql","sql","extra","read_sql","read_sql_query",
         "text","RawSQL","query","where","filter","having","literal_column","raw_sql","run_sql"}
def path_of(f):
    return os.path.join(d["root"], f["file"]) if "root" in d else os.path.join(SRC, f["dist"], f["file"])
def locate(tree, f):
    cs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and n.lineno == f["line"]
          and ("col" not in f or n.col_offset + 1 == f["col"])]
    if not cs: return None
    if "col" not in f:
        nm = lambda c: c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "")
        good = [c for c in cs if nm(c) in SINKM and (c.args or c.keywords)]
        cs = good or cs
    cs.sort(key=lambda c: (c.end_lineno, c.end_col_offset))
    return next((c for c in cs if c.args or c.keywords), cs[0])
cache = {}
def mod(p):
    if p not in cache:
        try:
            cache[p] = ast.parse(open(p, encoding="utf-8", errors="replace").read())
            for n in ast.walk(cache[p]):
                for c in ast.iter_child_nodes(n):
                    c._parent = n
        except Exception:
            cache[p] = None
    return cache[p]

def enclosing(node, kinds):
    n = getattr(node, "_parent", None)
    while n is not None and not isinstance(n, kinds):
        n = getattr(n, "_parent", None)
    return n

FN = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)

def scope_walk(root):
    """Nodes of `root`'s own scope (no nested def/class/lambda bodies)."""
    stack = list(ast.iter_child_nodes(root))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, SCOPE):
            # decorators / defaults belong to outer scope; ignore (conservative: nested def binds its name)
            continue
        stack.extend(ast.iter_child_nodes(n))

def target_names(t):
    if isinstance(t, ast.Name): return [t.id]
    if isinstance(t, (ast.Tuple, ast.List)): return [x for e in t.elts for x in target_names(e)]
    if isinstance(t, ast.Starred): return target_names(t.value)
    return []

def bindings(root, name):
    """All bindings of `name` in root's own scope: list of value-or-None
    (None = a binding whose value is unknown). ('aug', v) for +=."""
    out = []
    if isinstance(root, FN):
        a = root.args
        for p in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
            if p is not None and p.arg == name: out.append(None)
    for n in scope_walk(root):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == name: out.append(n.value)
                elif name in target_names(t): out.append(None)
        elif isinstance(n, ast.AnnAssign):
            if isinstance(n.target, ast.Name) and n.target.id == name and n.value is not None:
                out.append(n.value)
        elif isinstance(n, ast.AugAssign):
            if isinstance(n.target, ast.Name) and n.target.id == name:
                out.append(("aug", n.op, n.value))
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            if name in target_names(n.target): out.append(None)
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for it in n.items:
                if it.optional_vars is not None and name in target_names(it.optional_vars): out.append(None)
        elif isinstance(n, ast.ExceptHandler):
            if n.name == name: out.append(None)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                if (al.asname or al.name.split(".")[0]) == name: out.append(None)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if n.name == name: out.append(None)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            if name in n.names: out.append(("global",))
        elif isinstance(n, ast.NamedExpr):
            if n.target.id == name: out.append(n.value)
        elif isinstance(n, ast.Delete):
            pass
        elif hasattr(ast, "MatchAs") and isinstance(n, (ast.MatchAs, ast.MatchStar)):
            if getattr(n, "name", None) == name: out.append(None)
    return out

def module_rebinds_global(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names: return True
    return False

class Ctx:
    def __init__(self, tree, fn, cls):
        self.tree, self.fn, self.cls = tree, fn, cls

def lit(e, ctx, scope, seen, feats):
    """True if e can only evaluate to str/int/float literal text."""
    if isinstance(e, ast.Constant):
        if isinstance(e.value, str): return True
        if isinstance(e.value, (int, float)) and not isinstance(e.value, bool):
            feats.add("num-const"); return True
        return False
    if isinstance(e, ast.JoinedStr):
        for v in e.values:
            if isinstance(v, ast.FormattedValue):
                if not lit(v.value, ctx, scope, seen, feats): return False
                if v.format_spec is not None and not lit(v.format_spec, ctx, scope, seen, feats): return False
            elif not lit(v, ctx, scope, seen, feats): return False
        return True
    if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Add, ast.Mod)):
        if isinstance(e.op, ast.Mod): feats.add("pct")
        return lit(e.left, ctx, scope, seen, feats) and lit(e.right, ctx, scope, seen, feats)
    if isinstance(e, ast.Tuple):  # rhs of %
        return all(lit(x, ctx, scope, seen, feats) for x in e.elts)
    if isinstance(e, ast.IfExp):
        feats.add("ifexp")
        return lit(e.body, ctx, scope, seen, feats) and lit(e.orelse, ctx, scope, seen, feats)
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and isinstance(e.func.value, ast.Constant) \
            and isinstance(e.func.value.value, str):
        if e.func.attr == "format" and not e.keywords:
            feats.add("dot-format")
            return all(lit(a, ctx, scope, seen, feats) for a in e.args)
        if e.func.attr == "join" and len(e.args) == 1 and isinstance(e.args[0], (ast.List, ast.Tuple)):
            feats.add("join-lits")
            return all(lit(a, ctx, scope, seen, feats) for a in e.args[0].elts)
        return False
    if HYPO and isinstance(e, ast.Call):
        f = e.func; nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if nm in HYPO:
            feats.add("HYPO:" + nm); return True
    if isinstance(e, ast.Name):
        return name_lit(e.id, ctx, scope, seen, feats)
    if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id in ("self", "cls") \
            and ctx.cls is not None:
        return attr_lit(e.attr, ctx, seen, feats)
    return False

def name_lit(name, ctx, scope, seen, feats):
    key = (id(scope), name)
    if key in seen: return True  # cycle: judged by the other bindings
    seen = seen | {key}
    if scope is not None and scope is not ctx.tree:
        bs = bindings(scope, name)
        if any(isinstance(b, tuple) and b[0] == "global" for b in bs):
            return False
        if bs:
            if len(bs) > 1: feats.add("local-multi")
            for b in bs:
                if b is None: return False
                if isinstance(b, tuple):
                    if not isinstance(b[1], ast.Add): return False
                    feats.add("local-aug")
                    if not lit(b[2], ctx, scope, seen, feats): return False
                elif not lit(b, ctx, scope, seen, feats): return False
            feats.add("local")
            return True
        # free variable: enclosing function scopes, then module
        outer = enclosing(scope, FN)
        if outer is not None:
            feats.add("closure")
            return name_lit(name, ctx, outer, seen, feats)
    # module scope
    if module_rebinds_global(ctx.tree, name): return False
    bs = bindings(ctx.tree, name)
    if not bs: return False   # builtin / star import / unknown
    feats.add("module" if len(bs) == 1 else "module-multi")
    for b in bs:
        if b is None or isinstance(b, tuple): return False
        if not lit(b, ctx, ctx.tree, seen, feats): return False
    return True

def attr_lit(attr, ctx, seen, feats):
    """self.attr / cls.attr: every assignment of `.attr` (any receiver) in
    the module, and every class-body binding of `attr` in any class of the
    module, is literal-only; no setattr/property/def of that name."""
    key = ("attr", attr)
    if key in seen: return True
    seen = seen | {key}
    vals = []
    for n in ast.walk(ctx.tree):
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            tgts = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in tgts:
                for s in ast.walk(t):
                    if isinstance(s, ast.Attribute) and s.attr == attr and isinstance(s.ctx, ast.Store):
                        if s is not t or isinstance(n, ast.AugAssign): return False
                        if n.value is None: continue
                        vals.append((n.value, enclosing(n, FN)))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "setattr":
            return False
        elif isinstance(n, ast.ClassDef):
            for b in bindings(n, attr):
                if b is None or isinstance(b, tuple): return False
                vals.append((b, n))
    if not vals: return False
    feats.add("self-attr")
    if attr.isupper(): feats.add("self-attr-UPPER")
    for v, sc in vals:
        if not lit(v, ctx, sc, seen, feats): return False
    return True

def top_shape(a):
    if isinstance(a, ast.Constant): return "const"
    if isinstance(a, ast.JoinedStr): return "fstring"
    if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Add): return "concat"
    if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Mod): return "pct-format"
    if isinstance(a, ast.Name): return "name"
    if isinstance(a, ast.Attribute):
        return "self.attr" if isinstance(a.value, ast.Name) and a.value.id in ("self", "cls") else "attr"
    if isinstance(a, ast.Call):
        f = a.func
        if isinstance(f, ast.Attribute) and f.attr == "format": return "call:.format"
        if isinstance(f, ast.Attribute) and f.attr == "join": return "call:.join"
        nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "?")
        return "call:" + nm
    return type(a).__name__

def name_origin(a, fn, tree):
    """For a Name argument: what its local bindings are."""
    if fn is None: return "module-code"
    bs = bindings(fn, a.id)
    if not bs:
        return "free/module"
    kinds = set()
    for b in bs:
        if b is None:
            ps = [p.arg for p in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
            kinds.add("param" if a.id in ps else "unknown-binding")
        elif isinstance(b, tuple): kinds.add("aug" if b[0] == "aug" else "global")
        else: kinds.add(top_shape(b))
    return "+".join(sorted(kinds))

SANITIZERS = ("quoted_name", "Identifier", "identifier_preparer", "quote_identifier",
              "escape_identifier", "sql.SQL", "quote_ident", "_quote", "quote(")

shape = collections.Counter(); verdict = collections.Counter(); featc = collections.Counter()
only_feat = collections.Counter(); sanit = collections.Counter(); name_or = collections.Counter()
interp = collections.Counter(); exs = collections.defaultdict(list); unlocated = 0
for f in d["findings"]:
    if f["code"] != "E0713": continue
    tree = mod(path_of(f))
    if tree is None: unlocated += 1; continue
    call = locate(tree, f)
    if call is None: unlocated += 1; continue
    a = call.args[0] if call.args else (call.keywords[0].value if call.keywords else None)
    # a raw entry nested inside: text(...) as the arg -> judge text's arg
    if isinstance(a, ast.Call) and ((isinstance(a.func, ast.Name) and a.func.id in ("text", "literal_column"))
                                    or (isinstance(a.func, ast.Attribute) and a.func.attr in ("text", "literal_column"))) and a.args:
        a = a.args[0]
    if a is None: unlocated += 1; continue
    fn = enclosing(call, FN); cls = enclosing(call, (ast.ClassDef,))
    sh = top_shape(a)
    shape[sh] += 1
    if sh == "name": name_or[name_origin(a, fn, tree)] += 1
    if sh == "fstring":
        for v in a.values:
            if isinstance(v, ast.FormattedValue):
                k = top_shape(v.value)
                if k == "name": k = "name:" + name_origin(v.value, fn, tree)
                interp[k] += 1
    src = ast.unparse(a)
    for s in SANITIZERS:
        if s in src: sanit[s] += 1
    feats = set()
    ok = lit(a, Ctx(tree, fn, cls), fn if fn is not None else tree, frozenset(), feats)
    verdict["literal-only" if ok else "not-provable"] += 1
    key = f"{sh}"
    if ok:
        for ft in feats: featc[ft] += 1
        only_feat[",".join(sorted(feats))] += 1
    tag = ("LIT:" if ok else "NO:") + sh
    exs[tag].append(f"{f['dist']}/{f['file']}:{f['line']}  {src[:140]}")
    for ft in feats:
        if ok: exs["feat:" + ft].append(f"{f['dist']}/{f['file']}:{f['line']}  {src[:140]}")

print("unlocated", unlocated)
print("\nTOP SHAPE of judged arg:"); [print(f"  {v:4d} {k}") for k, v in shape.most_common()]
print("\nNAME arg, local binding kinds:"); [print(f"  {v:4d} {k}") for k, v in name_or.most_common(25)]
print("\nF-STRING interpolated value kinds (per value):"); [print(f"  {v:4d} {k}") for k, v in interp.most_common(25)]
print("\nVERDICT (stronger evaluator):", dict(verdict))
print("\nfeatures used by literal-only findings:"); [print(f"  {v:4d} {k}") for k, v in featc.most_common()]
print("\nfeature SETS of literal-only findings:"); [print(f"  {v:4d} {k}") for k, v in only_feat.most_common()]
print("\nsanitizer substrings in judged arg:"); [print(f"  {v:4d} {k}") for k, v in sanit.most_common()]
lit_by_shape = collections.Counter(k.split(":",1)[1] for k, v in exs.items() if k.startswith("LIT:") for _ in v)
print("\nliteral-only by top shape:", lit_by_shape.most_common())
if EX:
    for e in exs.get(EX, [])[:40]: print("  ", e)

# ---- exclusive buckets by dynamic leaves --------------------------------
SQLA = {"select", "insert", "update", "delete", "where", "limit", "offset", "order_by", "group_by",
        "values", "returning", "on_conflict_do_update", "on_conflict_do_nothing", "filter", "join",
        "outerjoin", "having", "distinct", "with_only_columns", "subquery", "cte", "union", "union_all",
        "select_from", "execution_options", "params", "bindparams", "columns", "scalar_subquery"}
def leaves(e, fn, tree, seen, out):
    if isinstance(e, ast.Constant): return
    if isinstance(e, ast.JoinedStr):
        for v in e.values:
            if isinstance(v, ast.FormattedValue): leaves(v.value, fn, tree, seen, out)
        return
    if isinstance(e, ast.BinOp): leaves(e.left, fn, tree, seen, out); leaves(e.right, fn, tree, seen, out); return
    if isinstance(e, (ast.Tuple, ast.List)):
        for x in e.elts: leaves(x, fn, tree, seen, out)
        return
    if isinstance(e, ast.IfExp): leaves(e.body, fn, tree, seen, out); leaves(e.orelse, fn, tree, seen, out); return
    if isinstance(e, ast.Name):
        if e.id in seen: return
        seen.add(e.id)
        bs = bindings(fn, e.id) if fn is not None else []
        if not bs:
            mb = bindings(tree, e.id)
            out.append("module-name" if mb else "free-name"); return
        ps = [p.arg for p in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
        for b in bs:
            if b is None: out.append("param" if e.id in ps else "loop/with/unpack-var")
            elif isinstance(b, tuple):
                if b[0] == "aug": leaves(b[2], fn, tree, seen, out)
                else: out.append("global")
            else: leaves(b, fn, tree, seen, out)
        return
    if isinstance(e, ast.Attribute):
        if isinstance(e.value, ast.Name) and e.value.id in ("self", "cls"): out.append("self.attr"); return
        out.append("attr"); return
    if isinstance(e, ast.Call):
        f = e.func
        nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "?")
        if nm == "quote_db_identifier": out.append("call:quote_db_identifier"); return
        if nm in SQLA: out.append("sqla-chain"); return
        if nm in ("format", "join") and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Constant):
            for a in list(e.args) + [k.value for k in e.keywords]: leaves(a, fn, tree, seen, out)
            return
        if nm in ("format", "join") and isinstance(f, ast.Attribute) and "SQL" in ast.unparse(f.value)[:12]:
            out.append("psycopg-composition"); return
        out.append("call:other"); return
    if isinstance(e, ast.Subscript): out.append("subscript"); return
    out.append(type(e).__name__)

ORDER = ["param", "self.attr", "attr", "loop/with/unpack-var", "subscript", "global", "free-name",
         "module-name", "call:other", "psycopg-composition", "sqla-chain", "call:quote_db_identifier"]
bucket = collections.Counter(); leafc = collections.Counter()
for f in d["findings"]:
    if f["code"] != "E0713": continue
    tree = mod(path_of(f))
    call = locate(tree, f) if tree is not None else None
    if call is None: continue
    a = call.args[0] if call.args else (call.keywords[0].value if call.keywords else None)
    if isinstance(a, ast.Call) and getattr(a.func, "attr", getattr(a.func, "id", "")) in ("text", "literal_column") and a.args: a = a.args[0]
    out = []
    leaves(a, enclosing(call, FN), tree, set(), out)
    ks = set(out)
    for k in ks: leafc[k] += 1
    if not ks: bucket["no dynamic leaf"] += 1; continue
    worst = min(ks, key=lambda k: ORDER.index(k) if k in ORDER else -1)
    bucket[worst] += 1
print("\nEXCLUSIVE bucket (worst dynamic leaf):"); [print(f"  {v:4d} {k}") for k, v in bucket.most_common()]
print("\nfindings containing leaf kind:"); [print(f"  {v:4d} {k}") for k, v in leafc.most_common()]
