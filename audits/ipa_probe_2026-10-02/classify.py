import ast, json, sys, os, collections, re
S, SRC = sys.argv[1], sys.argv[2]
t = open(os.path.join(S, 'fw.json'), encoding='utf-8').read(); d = json.loads(t[t.index('{\n'):])
cache = {}
def mod(path):
    if path not in cache:
        try: cache[path] = ast.parse(open(path, encoding='utf-8', errors='replace').read())
        except Exception: cache[path] = None
    return cache[path]
def enclosing(tree, line):
    best = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= line <= (n.end_lineno or n.lineno):
            if best is None or n.lineno > best.lineno: best = n
    return best
def lit(e):
    if isinstance(e, ast.Constant): return True
    if isinstance(e, ast.JoinedStr): return all(isinstance(v, ast.Constant) for v in e.values)
    if isinstance(e, ast.BinOp): return lit(e.left) and lit(e.right)
    if isinstance(e, (ast.List, ast.Tuple)): return all(lit(x) for x in e.elts)
    return False
def local_defs(tree):
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): out.setdefault(n.name, []).append(n)
    return out
def returns_literal(fn):
    rs = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    return bool(rs) and all(r.value is not None and lit(r.value) for r in rs)
cls = collections.Counter(); ex = collections.defaultdict(list)
for f in d['findings']:
    path = os.path.join(SRC, f['dist'], f['file']); tree = mod(path)
    if tree is None: cls['unparsed'] += 1; continue
    fn = enclosing(tree, f['line'])
    calls = [n for n in ast.walk(fn or tree) if isinstance(n, ast.Call) and n.lineno <= f['line'] <= (n.end_lineno or n.lineno)]
    args = [a for c in calls for a in c.args[:2]] + [k.value for c in calls for k in c.keywords]
    params = set()
    if fn: params = {a.arg for a in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs}
    defs = local_defs(tree)
    kind = 'other'
    for a in args:
        if isinstance(a, ast.Name) and a.id in params: kind = 'param'; break
        if isinstance(a, ast.Call):
            fnm = a.func.id if isinstance(a.func, ast.Name) else (a.func.attr if isinstance(a.func, ast.Attribute) and isinstance(a.func.value, ast.Name) and a.func.value.id in ('self','cls') else None)
            if fnm in defs:
                kind = 'local-call:' + ('returns-literal' if all(returns_literal(x) for x in defs[fnm]) else 'computed'); break
    if kind == 'param' and fn:
        # call sites of fn in same module
        pname = next(a.id for a in args if isinstance(a, ast.Name) and a.id in params)
        idx = [x.arg for x in fn.args.args].index(pname) if pname in [x.arg for x in fn.args.args] else None
        sites = [c for c in ast.walk(tree) if isinstance(c, ast.Call) and ((isinstance(c.func, ast.Name) and c.func.id == fn.name) or (isinstance(c.func, ast.Attribute) and c.func.attr == fn.name))]
        if not sites: kind = 'param:no-local-callers'
        else:
            vals = []
            for c in sites:
                v = next((k.value for k in c.keywords if k.arg == pname), None)
                if v is None and idx is not None:
                    off = 1 if fn.args.args and fn.args.args[0].arg in ('self','cls') and isinstance(c.func, ast.Attribute) else 0
                    if idx - off < len(c.args) and idx - off >= 0: v = c.args[idx - off]
                vals.append(v)
            kind = 'param:all-local-callers-literal' if all(v is not None and lit(v) for v in vals) else 'param:some-caller-nonliteral'
    cls[kind] += 1; ex[kind].append(f"{f['code']} {f['file']}:{f['line']}")
tot = sum(cls.values())
for k, v in cls.most_common(): print(f"{k:38s} {v:4d}  {100*v/tot:5.1f}%")
print('total', tot)
for k in ('param:all-local-callers-literal', 'local-call:returns-literal'):
    print('\n', k, ex[k][:8])
by = collections.Counter((f['code']) for f in d['findings']); print('\nby code', by.most_common())
