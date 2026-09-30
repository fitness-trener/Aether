"""Run the fromisoformat example/failure lists of a datetimetester.py against
a given _pydatetime.py (both from the fix/<side>/ tree)."""
import ast, importlib.util, sys, types

side = sys.argv[1]
spec = importlib.util.spec_from_file_location("_pyd", f"fix/{side}/Lib/_pydatetime.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
tree = ast.parse(open(f"fix/{side}/Lib/test/datetimetester.py", encoding="utf-8").read())

CASES = {  # test function -> class under test
    "test_fromisoformat_date_examples": None, "test_fromisoformat_fails": None,
    "test_fromisoformat_datetime_examples": m.datetime, "test_fromisoformat_fails_datetime": m.datetime,
    "test_fromisoformat_time_examples": m.time,
}
fails = 0
for cls_node in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
    for fn in [n for n in cls_node.body if isinstance(n, ast.FunctionDef) and n.name in CASES]:
        cls = CASES[fn.name] or (m.date if cls_node.name == "TestDate" else
                                 m.time if cls_node.name == "TestTime" else None)
        if cls is None:
            continue
        for st in fn.body:
            if isinstance(st, ast.Assign) and st.targets[0].id in ("examples", "bad_strs"):
                ns = dict(self=types.SimpleNamespace(theclass=cls), timezone=m.timezone,
                          timedelta=m.timedelta, UTC=m.timezone.utc,
                          BST=m.timezone(m.timedelta(hours=1), 'BST'),
                          EST=m.timezone(m.timedelta(hours=-5), 'EST'),
                          EDT=m.timezone(m.timedelta(hours=-4), 'EDT'))
                vals = eval(compile(ast.Expression(st.value), "t", "eval"), ns)
                for v in vals:
                    if st.targets[0].id == "examples":
                        s, want = v
                        try:
                            ok = cls.fromisoformat(s) == want
                        except Exception as e:
                            ok = False
                    else:
                        s = v
                        try:
                            cls.fromisoformat(s)
                            ok = False
                        except ValueError:
                            ok = True
                        except Exception:
                            ok = False
                    if not ok:
                        fails += 1
                        print(f"  {side} {cls_node.name}.{fn.name}: {s!r} FAILS")
                print(f"{side} {cls_node.name}.{fn.name} {st.targets[0].id}: {len(vals)} cases")
print(f"{side}: {fails} failing cases")
