import ast, json, sys, os, collections
S, SRC = sys.argv[1], sys.argv[2]
t = open(os.path.join(S,'fw.json'),encoding='utf-8').read(); d = json.loads(t[t.index('{\n'):])
cache={}
def tree(p):
    if p not in cache:
        try: cache[p]=ast.parse(open(p,encoding='utf-8',errors='replace').read())
        except Exception: cache[p]=None
    return cache[p]
def kind_of_value(v):
    if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id in ('self','cls'): return 'self.attr'
    if isinstance(v, ast.Name) and v.id.isupper(): return 'CONST'
    if isinstance(v, ast.Name): return 'name'
    if isinstance(v, ast.Call): return 'call'
    if isinstance(v, ast.Attribute): return 'attr'
    if isinstance(v, ast.Subscript): return 'subscript'
    return type(v).__name__
c=collections.Counter(); interp=collections.Counter()
for f in d['findings']:
    if f['code']!='E0713': continue
    tr=tree(os.path.join(SRC,f['dist'],f['file']))
    if tr is None: continue
    calls=[n for n in ast.walk(tr) if isinstance(n,ast.Call) and n.lineno<=f['line']<=(n.end_lineno or n.lineno)]
    fs=[a for cl in calls for a in cl.args if isinstance(a,ast.JoinedStr)]
    if fs:
        kinds={kind_of_value(v.value) for j in fs for v in j.values if isinstance(v,ast.FormattedValue)}
        for k in kinds: interp[k]+=1
        c['fstring-arg']+=1
    else:
        c['no-fstring-at-site']+=1
print(c); print('interpolated value kinds (per finding):', interp.most_common())
