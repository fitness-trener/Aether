# Python Frontend — Sink Detectors on Unmodified Python Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Aether's seven annotation-free security detectors fire on **unmodified Python** — no rewrite, no type hints, no `.aeth` port — and measure the result honestly against bandit and against a benign-code false-positive corpus.

**Architecture:** `tools/py_frontend.py` already translates Python into the Aether dict-AST that the passes consume, but it throws the **function body away**: it emits `body=[]` plus local-call stubs with `args: []`. That is why 21 of 30 detectors see nothing. This plan adds an expression translator (`_expr`) and an auditable Python-sink→Aether-sink mapping table, so `cursor.execute("... " + name)` reaches `check_injection` as `sqlQuery(BinOp +)` and the existing, untouched detector does the proving. Then a new `aether check-py` subcommand and a differential bench decide, by measurement, which rows are default-on.

**Tech Stack:** Python 3 stdlib only (`ast` module). Aether transpiler passes (unchanged). bandit is a **bench-only optional** — never a runtime dependency.

## Global Constraints

- **Windows.** Use `python` (never `python3`). Run Python through PowerShell; use the Bash tool for `grep`/`sed`. Ignore PowerShell `NativeCommandError` wrapper lines on native-exe stderr — check the real exit code. PowerShell here-strings have mis-parsed in this repo; write multi-line commit messages to a scratch file and use `git commit -F <file>`.
- **Full gate:** `python -B scripts/run_all.py` must exit 0 after every task.
- **Ratchet:** `tests/ratchet_baseline.json` stays at `min_emitted_codes: 54`, `min_gated_detectors: 30`. This plan adds **no** new diagnostic code and **no** new detector pass — it gives existing detectors a new input language. Do NOT change the baseline.
- **Zero runtime dependencies.** `tests/test_packaging.py` asserts it (`H.B.1 deps: zero runtime`). bandit is imported **only** inside the bench script, which must skip cleanly with a printed reason when it is absent — the same contract `tests/test_llm_fix_demo.py` uses ("cleanly skips with exit 2 + reason") and `passes/smt.py` uses for z3.
- **Never weaken py_frontend's existing soundness discipline.** A call whose capability surface cannot be determined stays UNPROVABLE. `PURE_METHODS` is deleted and is never coming back (`tools/py_frontend.py:187-192`). This plan only ADDS a sink surface; it must not clear anything that is UNPROVABLE today.
- **Honesty rules (CLAUDE.md).** These passes are syntactic and intraprocedural — "over-flag, never miss *within the modeled surface*", never "sound". Never invent diagnostic codes, effects, keywords, or capabilities. Never describe Aether as "better than bandit" without the qualifier and the metric.
- **Every measured number in a report cites the command that produced it.**

---

## Confirmed Gap (probe result — do not re-derive)

`tools/py_frontend.py` at commit `1d77a16`, driven through the full `aether.passes.analyze_flat` registry (all 30 detectors) on a file containing five textbook vulnerabilities:

```python
def get_user(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE name = '" + name + "'")   # SQLi
def ping(host):
    return subprocess.run("ping -c 1 " + host, shell=True)            # cmd injection
def read_upload(base, entry):
    return open(base + "/" + entry).read()                            # path traversal
def load_session(blob):
    return pickle.loads(blob)                                         # insecure deser
def run_it(cmd):
    return os.system("sh -c " + cmd)                                  # cmd injection
```

Measured output:

```
get_user      effects=[]                     body=[]
ping          effects=[{'path': ['process','run']}]   body=[]
read_upload   effects=[{'path': ['fs','open']}]       body=[]
load_session  effects=[]                     body=[]
run_it        effects=[{'path': ['process','system']}] body=[]

diagnostics: 3  — all E0701 (capability), zero security findings
```

**Zero of five vulnerabilities found.** The three findings are capability facts ("this function touches `process`/`fs`") that `grep -r "import subprocess"` also produces. The body is discarded, so no sink call, no argument expression, and no detector input exists.

The acceptance criterion for Tasks 1-3 is that this same file yields **E0713, E0714 ×2, E0711, E0720**.

---

## File Structure

**Modified:**
- `tools/py_frontend.py` — the only Python-specific logic. Gains `_expr` (Python expression → Aether expression node), the `SINK_BY_*` / `SANITIZER_BY_*` tables, and body emission. Keeps every existing capability table and the UNPROVABLE discipline untouched.
- `transpiler/aether/cli.py` — a `check-py` subcommand (`cmd_check_py` + its subparser).
- `tools/py_surface.py` — unchanged in behaviour, but its module docstring's claim about which passes run must be updated once sinks exist.
- `SECURITY_POSTURE.md`, `PYTHON_VIABILITY.md` — the reach and the measured numbers.

**Created:**
- `tests/test_py_frontend_sinks.py` — the translation and detection tests (new file: `tests/test_py_soundness.py` owns the capability-table soundness contract and should stay focused on it).
- `bench/py_frontend/run_bench.py`, `bench/py_frontend/LABELS.json`, `bench/py_frontend/REPORT.md`
- `bench/py_frontend/corpus/` — the four repro files the existing bench lacks (SQLi, path traversal, open redirect, hardcoded secret).
- `vault/wiki/questions/q4-sink-matching-vs-purity-matching.md`

---

### Task 1: Translate Python expressions into Aether expression nodes

The detectors judge argument *shapes*. This task produces those shapes and nothing else — no sinks yet, so no diagnostic changes and no gate risk.

**Files:**
- Modify: `tools/py_frontend.py` (add `_expr` and `_stmt_body`; extend `_FnVisitor` to collect statements)
- Test: `tests/test_py_frontend_sinks.py` (create)

**Interfaces:**
- Produces: `_expr(node: _pyast.AST, imports: _Imports) -> Dict[str, Any]` — always returns a dict node, never `None`. Task 2 calls it for sink arguments.
- Produces: the `FunctionDecl["body"]` of `py_to_ir` output is now a list of `Let` and `Call` statement nodes instead of `[]`.

**Node shapes the Aether passes require** (read off `_arg_reason` in `transpiler/aether/passes/detector_specs.py` and `callee_name` in `passes/ast_walk.py` — do not invent others):

| Aether node | Shape | Python source |
|---|---|---|
| `StringLit` | `{"kind":"StringLit","value":str}` | `ast.Constant` holding a `str` |
| `Ident` | `{"kind":"Ident","name":str}` | `ast.Name` |
| `BinOp` + | `{"kind":"BinOp","op":"+","left":…,"right":…}` | `ast.BinOp` with `ast.Add`; also f-strings and `%`/`.format` (see below) |
| `Call` | `{"kind":"Call","func":{"kind":"Ident","name":…},"args":[…],"pos":…}` | `ast.Call` |
| `Let` | `{"kind":"Let","name":str,"value":…,"pos":…}` | `ast.Assign` to a single `ast.Name` |

Anything else translates to `{"kind": "PyExpr", "py": "<ast class name>"}`. That kind is unknown to every rule, so `_arg_reason` falls through to `rule.default` — flagged, not cleared. That is the correct direction and it is why no new rule branch is needed.

**f-strings are the point of this task.** `f"SELECT * FROM t WHERE id={uid}"` is the dominant modern injection shape and Python's AST models it as `JoinedStr`. Translate a `JoinedStr` containing **at least one** `FormattedValue` into a left-nested `BinOp "+"` tree over its parts; a `JoinedStr` of only constants becomes a single `StringLit`. `_arg_reason` then reports it through the existing `rule.concat` reason, with no rule change. Same treatment for `"..." % x` (`ast.BinOp` with `ast.Mod` and a `str` left operand) and `"...".format(x)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_py_frontend_sinks.py`:

```python
"""Python frontend — expression translation and sink detection.

`tests/test_py_soundness.py` owns the capability-table soundness contract
(nothing here may weaken it). This file owns the other half: that a Python
function BODY reaches the Aether detectors as judgeable expression shapes,
and that the sink mapping fires the right existing detector.

Run: python -B tests/test_py_frontend_sinks.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from tools.py_frontend import py_to_ir                    # noqa: E402
from aether.passes import analyze_flat                    # noqa: E402
from aether.passes.ast_walk import walk                   # noqa: E402


def _fn(src: str, name: str):
    ast_dict, _unp, _meta = py_to_ir(src)
    for d in ast_dict["decls"]:
        if d.get("kind") == "FunctionDecl" and d["name"] == name:
            return d
    raise AssertionError(f"no FunctionDecl named {name!r}")


def _codes(src: str):
    ast_dict, _unp, _meta = py_to_ir(src)
    return sorted(d.code for d in analyze_flat(ast_dict))


# --- expression translation ---------------------------------------------

def test_body_is_no_longer_discarded():
    d = _fn("def f(a):\n    x = a + 'b'\n    return x\n", "f")
    assert d["body"], "the function body must reach the IR, not be dropped"
    print("body: statements reach the IR")


def test_assign_becomes_let():
    d = _fn("def f(a):\n    x = 'lit'\n", "f")
    lets = [n for n in walk(d["body"], "Let")]
    assert len(lets) == 1 and lets[0]["name"] == "x", \
        "a single-target assignment must become a Let the safe-name pass can read"
    assert lets[0]["value"]["kind"] == "StringLit", "a str constant is a StringLit"
    print("Let: assignment translated with a StringLit value")


def test_concat_becomes_binop_plus():
    d = _fn("def f(a):\n    x = 'p/' + a\n", "f")
    lets = [n for n in walk(d["body"], "Let")]
    v = lets[0]["value"]
    assert v["kind"] == "BinOp" and v["op"] == "+", \
        "string concatenation must reach the rules as BinOp '+'"
    print("BinOp: '+' concatenation translated")


def test_fstring_becomes_concat():
    d = _fn("def f(uid):\n    x = f'id={uid}'\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "BinOp" and v["op"] == "+", \
        "an f-string with an interpolation is a concatenation, not a literal"
    print("BinOp: f-string with interpolation translated as concat")


def test_constant_only_fstring_is_a_literal():
    d = _fn("def f():\n    x = f'no interpolation here'\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "StringLit", \
        "an f-string with no FormattedValue is a fixed literal"
    print("StringLit: constant-only f-string translated as a literal")


def test_percent_format_becomes_concat():
    d = _fn("def f(a):\n    x = 'id=%s' % a\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "BinOp" and v["op"] == "+", \
        "%-formatting builds a dynamic string - same shape as concat"
    print("BinOp: %-formatting translated as concat")


def test_unmodeled_expression_is_not_cleared():
    d = _fn("def f(xs):\n    x = [i for i in xs]\n", "f")
    v = [n for n in walk(d["body"], "Let")][0]["value"]
    assert v["kind"] == "PyExpr", \
        "an unmodeled expression must be opaque, never silently a literal"
    print("PyExpr: unmodeled expression stays opaque (flag-more direction)")


if __name__ == "__main__":
    test_body_is_no_longer_discarded()
    test_assign_becomes_let()
    test_concat_becomes_binop_plus()
    test_fstring_becomes_concat()
    test_constant_only_fstring_is_a_literal()
    test_percent_format_becomes_concat()
    test_unmodeled_expression_is_not_cleared()
    print("PY FRONTEND: ALL TESTS PASS")
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: FAIL on `test_body_is_no_longer_discarded` with `AssertionError: the function body must reach the IR, not be dropped`.

- [ ] **Step 3: Add the expression translator**

In `tools/py_frontend.py`, insert after `_const_str` (currently line 231-234):

```python
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


def _expr(node: Any, imp: "_Imports") -> Dict[str, Any]:
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
                    "left": _expr(node.left, imp), "right": _expr(node.right, imp)}
        if isinstance(node.op, _pyast.Mod) and _const_str(node.left) is not None:
            return _concat([_expr(node.left, imp), _expr(node.right, imp)])
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
                parts.append(_expr(v.value, imp))
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
        return _call_expr(node, imp)
    return {"kind": "PyExpr", "py": type(node).__name__}
```

`_call_expr` is defined in Task 2 — for THIS task, add a placeholder immediately below `_expr` that names the callee generically so the tests here pass:

```python
def _call_expr(node: _pyast.Call, imp: "_Imports") -> Dict[str, Any]:
    """A Python call as an Aether Call node. Task 2 maps the callee to an
    Aether SINK name; until then every call is named by its Python spelling,
    which matches no sink and no wrapper — the refused direction."""
    name = _callee_spelling(node.func, imp) or "<expr>"
    return {"kind": "Call",
            "func": {"kind": "Ident", "name": name},
            "args": [_expr(a, imp) for a in node.args],
            "pos": _pos(node)}


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
```

- [ ] **Step 4: Emit statement bodies**

In `_FnVisitor.__init__`, add one more accumulator next to `self.local_calls`:

```python
        self.stmts: List[Dict[str, Any]] = []
```

Add this method to `_FnVisitor`:

```python
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
                                   "value": _expr(stmt.value, self.imp),
                                   "pos": _pos(stmt, self.fn_line)})
            return
        if isinstance(stmt, _pyast.Expr) and isinstance(stmt.value, _pyast.Call):
            self.stmts.append(_expr(stmt.value, self.imp))
            return
        if isinstance(stmt, _pyast.Return) and stmt.value is not None:
            self.stmts.append({"kind": "Return", "value": _expr(stmt.value, self.imp),
                               "pos": _pos(stmt, self.fn_line)})
```

Then in `py_to_ir`, replace the walk-and-build block (currently lines 428-434):

```python
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
```

and use `body` in the `decls.append({... "body": body ...})` below it.

Note the two separate `_pyast.walk` passes are deliberate: `visit_call` drives the untouched capability/UNPROVABLE analysis over EVERY call anywhere in the function (including inside comprehensions and nested calls), while `visit_stmt` builds the shape the detectors judge. Merging them would change what the capability pass sees, and this plan must not.

- [ ] **Step 5: Run to verify they pass**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: PASS, ending with `PY FRONTEND: ALL TESTS PASS`.

- [ ] **Step 6: Verify nothing that was UNPROVABLE became clean**

```bash
python -B tests/test_py_soundness.py
```

Expected: PASS. This is the non-regression gate for the existing soundness contract — if it goes red, the change touched the capability surface and must be reverted, not patched.

- [ ] **Step 7: Full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0.

- [ ] **Step 8: Commit**

Write the message to a scratch file, then:

```bash
git commit -F <msgfile> -- tools/py_frontend.py tests/test_py_frontend_sinks.py
```

Message subject: `feat(py): translate Python expressions into judgeable Aether nodes`. Body must state that no detector output changed yet (no sinks are mapped), and that unmodeled expressions become `PyExpr` — refused, never cleared.

---

### Task 2: Map Python sinks to Aether sinks

Now the detectors fire. This is the task that closes the confirmed gap.

**Files:**
- Modify: `tools/py_frontend.py` (`SINK_BY_QUALIFIED`, `SINK_BY_METHOD`, `SINK_BY_BUILTIN`, gating helpers; `_call_expr` resolves through them; `mapping_table()` exposes them)
- Test: `tests/test_py_frontend_sinks.py`

**Interfaces:**
- Consumes: `_expr`, `_call_expr`, `_callee_spelling` from Task 1.
- Produces: `_sink_name(func, call, imp) -> Optional[str]` — the Aether sink name for a Python call, or `None`.
- Produces: `mapping_table()` gains keys `sink_by_qualified`, `sink_by_method`, `sink_by_builtin` (the `/pymap` audit endpoint and `tests/test_py_soundness.py`'s mapping-table test both read this dict).

**The doctrine that makes method-name matching legitimate — put this in the module docstring, it is the intellectual content of the task:**

> `py_frontend` deleted its `PURE_METHODS` allowlist as unsound: clearing `obj.append()` as pure from the method NAME, with no proof of the receiver's type, certified a capability-using module clean (`tools/py_frontend.py:187-192`).
> Sink matching is the same operation with the **opposite** consequence. Treating `cursor.execute(...)` as a SQL sink from the method name alone, with no proof of the receiver's type, can only ever produce a finding on code that was not a sink — an over-flag. The one rule covers both: **never assume clean from a name; freely assume dangerous from a name.** The asymmetry is not a double standard, it is the direction of the error.

**The mapping table.** Sink names must be exactly the strings in `LITERAL_OR_WRAPPER_SPECS` (`transpiler/aether/passes/detector_specs.py`): `writeFile`, `readFile`, `sqlQuery`, `sqlExec`, `sqlByOwner`, `shellExec`, `redirect`, `renderTemplate`, `deserialize`, `parseXml`. Do not invent a sink name — an unmapped string matches no row and silently does nothing.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_py_frontend_sinks.py`, before the `if __name__` block:

```python
# --- sink mapping: the detectors fire on unmodified Python --------------

VULN_SRC = """
import os
import subprocess
import pickle


def get_user(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE name = '" + name + "'")


def ping(host):
    subprocess.run("ping -c 1 " + host, shell=True)


def read_upload(base, entry):
    open(base + "/" + entry)


def load_session(blob):
    pickle.loads(blob)


def run_it(cmd):
    os.system("sh -c " + cmd)
"""


def test_the_five_vulnerabilities_are_found():
    codes = _codes(VULN_SRC)
    assert codes.count("E0713") == 1, f"SQL injection via concat must fire: {codes}"
    assert codes.count("E0714") == 2, f"both command injections must fire: {codes}"
    assert codes.count("E0711") == 1, f"path traversal via concat must fire: {codes}"
    assert codes.count("E0720") == 1, f"pickle.loads must fire: {codes}"
    print("sinks: all five vulnerabilities found on unmodified Python")


def test_fstring_sql_injection_found():
    src = "def q(cur, uid):\n    cur.execute(f'SELECT * FROM t WHERE id={uid}')\n"
    assert "E0713" in _codes(src), "an f-string query is a dynamic query"
    print("sinks: f-string SQL injection found")


def test_literal_query_is_clean():
    src = "def q(cur):\n    cur.execute('SELECT 1')\n"
    assert "E0713" not in _codes(src), "a fixed literal query is not an injection"
    print("sinks: literal query stays clean")


def test_shell_false_is_not_a_shell_sink():
    src = ("import subprocess\n"
           "def r(name):\n    subprocess.run(['convert', name])\n")
    assert "E0714" not in _codes(src), \
        "an argv list without shell=True never reaches a shell"
    print("sinks: subprocess without shell=True is not a shell sink")


def test_yaml_load_with_safe_loader_is_not_a_sink():
    src = ("import yaml\n"
           "def load(raw):\n    yaml.load(raw, Loader=yaml.SafeLoader)\n")
    assert "E0720" not in _codes(src), \
        "an explicit safe Loader is the documented safe form of yaml.load"
    print("sinks: yaml.load with SafeLoader is not a deserialization sink")


def test_sink_tables_are_auditable():
    from tools.py_frontend import mapping_table
    t = mapping_table()
    for key in ("sink_by_qualified", "sink_by_method", "sink_by_builtin"):
        assert key in t and t[key], f"{key} must be exposed for audit"
    print("sinks: mapping tables exposed via mapping_table()")
```

and register the six new calls in the `__main__` block.

- [ ] **Step 2: Run to verify they fail**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: FAIL on `test_the_five_vulnerabilities_are_found` — the count assertions report `[]` or only `E0701` entries.

- [ ] **Step 3: Add the sink tables**

In `tools/py_frontend.py`, insert after `CAP_BY_BUILTIN` (currently ends line 110):

```python
# ----------------------------------------------------------------------
# THE AUDITABLE SINK MAPPING TABLE
# ----------------------------------------------------------------------
# Python call -> the Aether SINK NAME the existing detectors already know.
# Every value here must be a sink string that appears in
# `aether.passes.detector_specs.LITERAL_OR_WRAPPER_SPECS`; an unmapped
# string matches no row and would silently do nothing.
#
# Matching by method NAME on an unresolved receiver is deliberate and is
# NOT the unsound `PURE_METHODS` allowlist returning (see the note at the
# bottom of the capability tables). Clearing from a name hides a real
# capability; flagging from a name can only over-flag. Same rule, opposite
# direction of error.

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
```

- [ ] **Step 4: Resolve calls through the tables**

Replace the Task 1 placeholder `_call_expr` with:

```python
def _has_kw_true(call: _pyast.Call, name: str) -> bool:
    for kw in call.keywords or []:
        if kw.arg == name and isinstance(kw.value, _pyast.Constant) \
                and kw.value.value is True:
            return True
    return False


def _has_kw(call: _pyast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in call.keywords or [])


def _sink_name(call: _pyast.Call, imp: "_Imports") -> Optional[str]:
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
    if dotted in SINK_BY_QUALIFIED:
        return SINK_BY_QUALIFIED[dotted]
    if dotted in SINK_BY_BUILTIN:
        return SINK_BY_BUILTIN[dotted]
    # Method on an unresolved receiver: over-flag by name (see doctrine note).
    if isinstance(call.func, _pyast.Attribute):
        return SINK_BY_METHOD.get(call.func.attr)
    return None


def _call_expr(node: _pyast.Call, imp: "_Imports") -> Dict[str, Any]:
    """A Python call as an Aether Call node, named so the existing
    detectors recognize it: the Aether SINK name when it maps to one, the
    Aether WRAPPER name when it is a sanctioned exit, otherwise its Python
    spelling (which matches neither, so an argument that is one of these
    calls is refused — the flag-more direction)."""
    dotted = _callee_spelling(node.func, imp)
    name = (_sink_name(node, imp)
            or SANITIZER_BY_QUALIFIED.get(dotted or "")
            or dotted or "<expr>")
    return {"kind": "Call",
            "func": {"kind": "Ident", "name": name},
            "args": [_expr(a, imp) for a in node.args],
            "pos": _pos(node)}
```

- [ ] **Step 5: Expose the tables for audit**

In `mapping_table()`, add before the closing brace:

```python
        "sink_by_qualified": SINK_BY_QUALIFIED,
        "sink_by_method": SINK_BY_METHOD,
        "sink_by_builtin": SINK_BY_BUILTIN,
        "sink_gated": {"subprocess_shell_true": sorted(SINK_GATED_SUBPROCESS),
                       "yaml_without_loader": sorted(SINK_GATED_YAML)},
        "sanitizer_by_qualified": SANITIZER_BY_QUALIFIED,
```

- [ ] **Step 6: Run to verify they pass**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: PASS.

- [ ] **Step 7: Re-run the probe from the Confirmed Gap section**

Recreate the five-vulnerability file and drive it through the full registry:

```bash
python -B -c "import sys,os; sys.path.insert(0,'transpiler'); sys.path.insert(0,'.'); from tools.py_frontend import py_to_ir; from aether.passes import analyze_flat; a,_,_=py_to_ir(open(sys.argv[1],encoding='utf-8').read()); [print(d.code, d.message[:70]) for d in analyze_flat(a)]" <path-to-vuln.py>
```

Expected: `E0713` ×1, `E0714` ×2, `E0711` ×1, `E0720` ×1, alongside the pre-existing `E0701` capability findings. Before this task: zero security findings.

- [ ] **Step 8: Soundness non-regression + full gate**

```bash
python -B tests/test_py_soundness.py
```

```bash
python -B scripts/run_all.py
```

Expected: both exit 0.

- [ ] **Step 9: Commit**

Subject: `feat(py): map Python sinks onto Aether's sink names`. The body must carry the doctrine note (clearing from a name is unsound, flagging from a name over-flags) and name the two gated mappings (`shell=True`, `Loader=`).

---

### Task 3: The safe halves stay clean

A detector that flags the fix as loudly as the bug is worthless. `bench/realworld_*/**_repro.py` each contain a vulnerable function AND the documented safe one; this task makes the safe halves silent.

**Files:**
- Modify: `tools/py_frontend.py` (extend `SANITIZER_BY_QUALIFIED` and the parameterized-query recognizer as the corpus demands)
- Test: `tests/test_py_frontend_sinks.py`

**Interfaces:** consumes everything from Task 2; produces no new symbol.

**The corpus (already in the repo — read each before changing code):**

| File | Vulnerable fn | Safe fn | Expected code |
|---|---|---|---|
| `bench/realworld_subprocess_cmdi/subprocess_repro.py` | `make_thumbnail` | `make_thumbnail_safe` | E0714 |
| `bench/realworld_pyyaml/pyyaml_repro.py` | `load_config` | `load_config_safe` | E0720 |
| `bench/realworld_flask_ssti/flask_repro.py` | `greeting` | `greeting_safe` | E0719 — the safe form passes a fixed literal template with the value as a keyword argument, so `_arg_reason` already reads it as `StringLit`; expected to need no new mapping |
| `bench/realworld_xxe/lxml_repro.py` | `load_config` | `load_config_safe` | E0727 — **see the known offender below; this one cannot be closed with a wrapper mapping** |
| `bench/realworld_requests_ssrf/requests_repro.py` | (read the file) | (read the file) | — SSRF is effect-string, out of this plan's scope; assert only that the file produces no *sink-family* false positive |
| `bench/realworld_metadata_ssrf/capitalone_repro.py` | (read the file) | (read the file) | — same |
| `bench/realworld_jwt/pyjwt_repro.py` | (read the file) | (read the file) | — E0716 needs `Authorized<T>`; out of scope, assert no sink-family false positive |

- [ ] **Step 1: Write the failing test**

Append to `tests/test_py_frontend_sinks.py`:

```python
# --- the fix must be silent ---------------------------------------------
# Each bench repro carries the vulnerable shape AND the documented fix.
# A checker that flags both is noise, not a checker.

import glob                                                      # noqa: E402

SINK_CODES = {"E0711", "E0713", "E0714", "E0718", "E0719", "E0720", "E0727"}


def _repro_files():
    return sorted(glob.glob(os.path.join(ROOT, "bench", "realworld_*", "*_repro.py")))


def test_repro_corpus_flags_the_bug():
    files = _repro_files()
    assert files, "bench repro corpus is empty - glob found nothing"
    hits = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            codes = set(_codes(f.read())) & SINK_CODES
        hits[os.path.basename(path)] = sorted(codes)
    # The four sink-family repros must each produce their code.
    assert "E0714" in hits.get("subprocess_repro.py", []), hits
    assert "E0720" in hits.get("pyyaml_repro.py", []), hits
    print("repro corpus: sink-family bugs found ->", hits)


def test_safe_functions_are_clean():
    """Per-function: the documented fix must produce no sink-family code."""
    import ast as pyast
    offenders = []
    for path in _repro_files():
        with open(path, encoding="utf-8") as f:
            src = f.read()
        for node in pyast.parse(src).body:
            if not isinstance(node, (pyast.FunctionDef, pyast.AsyncFunctionDef)):
                continue
            if not node.name.endswith("_safe"):
                continue
            fn_src = pyast.get_source_segment(src, node) or ""
            header = "\n".join(l for l in src.splitlines()
                               if l.startswith("import ") or l.startswith("from "))
            codes = set(_codes(header + "\n\n" + fn_src)) & SINK_CODES
            if codes:
                offenders.append((os.path.basename(path), node.name, sorted(codes)))
    assert not offenders, \
        "the documented FIX must not be flagged - that is noise: " + repr(offenders)
    print("repro corpus: every *_safe function is clean")
```

Register both in `__main__`.

- [ ] **Step 2: Run to see the real failure set**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: FAIL. **Read the offender list carefully — it is the specification for Step 3.** Do not guess at mappings before seeing it. If a `*_safe` function is flagged, one of exactly two things is true, and they need opposite fixes:
- Python's documented fix has no entry in `SANITIZER_BY_QUALIFIED` → add it.
- The safe form is a *shape*, not a call (e.g. `cursor.execute("... ?", params)` is safe because of the placeholder + second argument, not because of a wrapper) → that needs a recognizer, written in Step 3.

- [ ] **Step 3a: Close the known offender — XXE, where both call sites are identical**

`bench/realworld_xxe/lxml_repro.py` will fail, and no wrapper mapping can fix it. Read it: the vulnerable and safe call sites are **byte-identical**.

```python
def load_config(raw: bytes):
    parser = etree.XMLParser(resolve_entities=True)
    return etree.fromstring(raw, parser)              # CWE-611

def load_config_safe(raw: bytes):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, ...)
    return etree.fromstring(raw, parser)              # identical call
```

The safety lives in a **different statement**, in the keyword argument of the parser bound to `parser`. E0727's `arg_index` is 0, so `_arg_reason` inspects `raw` and never sees the parser at all — the Aether pass structurally cannot resolve this, and it must not be changed to try. The `.aeth` port sidestepped it by hand-mapping the two shapes to `parseXml` and `parseXmlSafe` (`bench/realworld_xxe/lxml_repro.py:26-27`).

This is exactly the Python-specific knowledge `py_frontend` exists to hold ("that is the only Python-specific logic", module docstring). Resolve it in the frontend, per function:

```python
_XML_PARSER_CTORS = {"lxml.etree.XMLParser", "xml.sax.make_parser"}


def _safe_xml_parser_names(fn_node: Any, imp: "_Imports") -> Set[str]:
    """Names bound to an XML parser constructed with entity resolution
    OFF. Passing one of these disarms the XXE sink — the guard is on the
    PARSER, in a different statement from the parse call, so no
    argument-shape rule can see it.

    Conservative: a name is safe only when EVERY binding to it in this
    function is an explicit `resolve_entities=False`. Anything else —
    rebound, computed, no keyword, unknown — is not safe."""
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
```

Thread the resulting set into `_FnVisitor` (compute it once per function in `py_to_ir`, store it on the visitor as `self.safe_xml`), and in `_sink_name` return `None` for a `parseXml` hit whose parser argument is one of those names:

```python
    sink = SINK_BY_QUALIFIED.get(dotted)
    if sink == "parseXml":
        for a in call.args[1:]:
            if isinstance(a, _pyast.Name) and a.id in safe_xml:
                return None      # entity resolution explicitly disabled
    return sink
```

Add a test pinning **both** directions — the disarmed parser is clean, and a parser with `resolve_entities=True` (or no keyword at all) still fires:

```python
def test_xxe_safe_parser_disarms_the_sink():
    src = ("from lxml import etree\n"
           "def load(raw):\n"
           "    parser = etree.XMLParser(resolve_entities=False)\n"
           "    etree.fromstring(raw, parser)\n")
    assert "E0727" not in _codes(src), \
        "resolve_entities=False is lxml's documented XXE fix"
    print("sinks: XML parser with entities off is not an XXE sink")


def test_xxe_default_parser_still_fires():
    src = ("from lxml import etree\n"
           "def load(raw):\n"
           "    parser = etree.XMLParser(resolve_entities=True)\n"
           "    etree.fromstring(raw, parser)\n")
    assert "E0727" in _codes(src), \
        "entity resolution left ON is the vulnerability"
    print("sinks: XML parser with entities on still fires")
```

- [ ] **Step 3b: Close the remaining offenders**

For the parameterized-query shape, add to `tools/py_frontend.py` and call it from `_call_expr` before the sink lookup:

```python
def _is_parameterized_query(call: _pyast.Call) -> bool:
    """`cursor.execute(sql, params)` with a second argument is the DB-API
    parameterized form — the driver binds the values, so the string is not
    the injection vector. This is Python's `sqlBind`, expressed as a call
    SHAPE rather than as a wrapper function."""
    return len(call.args) >= 2
```

Then in `_sink_name`, before returning a `SINK_BY_METHOD` hit:

```python
    if isinstance(call.func, _pyast.Attribute):
        sink = SINK_BY_METHOD.get(call.func.attr)
        if sink is not None and _is_parameterized_query(call):
            return None      # DB-API parameter binding — the sanctioned exit
        return sink
```

Add any further `SANITIZER_BY_QUALIFIED` entries the offender list demands, **one per offender, each with a comment naming the upstream documentation that calls it the fix.** Do not add a mapping the corpus did not ask for.

- [ ] **Step 4: Run to verify they pass**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: PASS.

- [ ] **Step 5: Full gate + commit**

```bash
python -B scripts/run_all.py
```

Subject: `feat(py): recognize Python's sanctioned exits so the documented fix is clean`.

---

### Task 4: `aether check-py`

A CLI door, with the reduced guarantee set stated on it rather than buried.

**Files:**
- Modify: `transpiler/aether/cli.py` (add `cmd_check_py`; add the subparser; wire it into the dispatch table)
- Test: `tests/test_py_frontend_sinks.py`

**Interfaces:** consumes `py_to_ir` and `aether.passes.analyze_flat`. Produces the `check-py` subcommand.

**Why a separate subcommand and not `aether check foo.py`:** `cmd_check` runs parse → **emit → compile** → analysis → SMT (`transpiler/aether/cli.py:227-267`). Emitting Python from Python and SMT-proving contracts that do not exist are both meaningless here, and the guarantees genuinely differ — E0801 needs a declared `effects` clause Python does not have. A separate door that names its own guarantees is honest; overloading `check` would quietly imply parity.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_py_frontend_sinks.py`:

```python
# --- CLI --------------------------------------------------------------

def test_check_py_cli_reports_and_exits_2(tmpdir=None):
    import subprocess as sp
    import tempfile
    src = ("import subprocess\n"
           "def r(host):\n    subprocess.run('ping ' + host, shell=True)\n")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(src)
        r = sp.run([sys.executable, "-B", "-m", "transpiler.aether.cli",
                    "check-py", p], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2, f"a finding must exit 2, got {r.returncode}: {r.stdout}"
    assert "E0714" in r.stdout, r.stdout
    assert "not checked" in r.stdout.lower(), \
        "the reduced guarantee set must be stated on the output, not implied"
    print("cli: check-py reports E0714 and states its limits")


def test_check_py_clean_exits_0():
    import subprocess as sp
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "y.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    return a + b\n")
        r = sp.run([sys.executable, "-B", "-m", "transpiler.aether.cli",
                    "check-py", p], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"clean file must exit 0: {r.stdout} {r.stderr}"
    print("cli: check-py on a clean file exits 0")
```

Register both in `__main__`.

- [ ] **Step 2: Run to verify they fail**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: FAIL — `invalid choice: 'check-py'`.

- [ ] **Step 3: Add the command**

In `transpiler/aether/cli.py`, add next to the other `cmd_*` functions:

```python
def cmd_check_py(args) -> int:
    """Run the language-independent detectors over a Python file.

    Python has no declared `effects` clause and no marker types, so the
    guarantee set is genuinely smaller than `check` on a .aeth file. That
    is printed, not implied: a tool that quietly offers less than it looks
    like it offers is worse than one that offers less out loud."""
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    from tools.py_frontend import py_to_ir
    from .passes import analyze_flat

    src = _read(args.file)
    ast, unprovable, meta = py_to_ir(src)
    diags = analyze_flat(ast)

    for d in diags:
        _emit_error(d, args.json)
    if args.json:
        json.dump({"ok": not diags, "lang": "python",
                   "diagnostics": [d.to_dict() for d in diags],
                   "unprovable": unprovable, "meta": meta}, sys.stdout)
        sys.stdout.write("\n")
        return 2 if diags else 0

    n_unp = sum(len(v) for v in unprovable.values())
    print(f"\n{len(diags)} finding(s) in {meta['n_functions']} function(s); "
          f"{n_unp} unprovable region(s) in {len(unprovable)} function(s).")
    print("NOT checked on Python (no declared effects clause, no marker "
          "types): E0801 effect composition, and the taint-marker family "
          "(E0712/E0715/E0716/E0717/E0724). Sink and capability checks "
          "only. See PYTHON_VIABILITY.md for measured coverage.")
    return 2 if diags else 0
```

Add the subparser next to the `check` one:

```python
    sp = sub.add_parser("check-py",
                        help="run the language-independent detectors over a "
                             "Python file (sinks + capability; no effect "
                             "composition, no marker taint)")
    sp.add_argument("file")
```

and add the dispatch line. `main` uses an `if args.cmd == "..."` ladder at `transpiler/aether/cli.py:579-586`; insert immediately after the `check` line, keeping the column alignment of its neighbours:

```python
        if args.cmd == "check-py": return cmd_check_py(args)
```

- [ ] **Step 4: Run to verify they pass**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: PASS.

- [ ] **Step 5: Wire the test file into the gate**

Add a line for `tests/test_py_frontend_sinks.py` in `scripts/run_all.py`, following the pattern of the neighbouring entries (grep for `test_py_soundness` and mirror it). A test file not in the gate does not exist.

- [ ] **Step 6: Full gate + commit**

```bash
python -B scripts/run_all.py
```

Expected: exit 0, with the new suite listed in the output.

Subject: `feat(py): aether check-py, with its reduced guarantee set printed`.

---

### Task 5: Measure it — differential bench, false-positive corpus, and the record

Without this task the claim "Aether checks Python too" is unbacked, and an unbacked claim on Semgrep/Bandit's turf **lowers** technical legitimacy rather than raising it.

**Files:**
- Create: `bench/py_frontend/run_bench.py`, `bench/py_frontend/LABELS.json`, `bench/py_frontend/REPORT.md`, `bench/py_frontend/corpus/*.py`
- Modify: `PYTHON_VIABILITY.md`, `SECURITY_POSTURE.md`, `demos/case_studies/LOOP_LOG.md`
- Create: `vault/wiki/questions/q4-sink-matching-vs-purity-matching.md`
- Modify: `vault/wiki/index.md`, `vault/wiki/log.md`, `vault/wiki/clusters/violation-taxonomy.md`

**Interfaces:** consumes the frontend from Tasks 1-4. Produces `bench/py_frontend/run_bench.py`, runnable standalone.

- [ ] **Step 1: Write the four missing corpus files**

The bench repro corpus covers cmdi, deser, SSTI, and XXE. Write `bench/py_frontend/corpus/` files in the same house style as `bench/realworld_subprocess_cmdi/subprocess_repro.py` — a header comment naming the real CVE/class, a vulnerable function, and a `*_safe` function that is the documented fix — for the four sink rows it does not cover:

- `sqli_repro.py` — CWE-89. Model it on the shape already ported at `bench/realworld_cve/cve_2026_1312_django_orderby_vulnerable.aeth`; the safe form is DB-API parameter binding, `cur.execute("... WHERE id = ?", (uid,))`.
- `path_traversal_repro.py` — CWE-22. Model on `bench/realworld_cve/cve_2007_4559_tarfile_vulnerable.aeth`; the safe form is `werkzeug.utils.secure_filename` (or an explicit containment check).
- `open_redirect_repro.py` — CWE-601. Model on `bench/realworld_cve/cve_2018_14574_django_redirect_vulnerable.aeth`; the safe form is a fixed literal target or an allowlist lookup.
- `hardcoded_secret_repro.py` — CWE-798, E0723. The safe form is `os.environ["..."]`.

- [ ] **Step 2: Write the ground truth**

`bench/py_frontend/LABELS.json`, keyed by `<file>::<function>`, valued with the expected code or `"clean"`. Include a `_meta` block matching the style of `tools/py_corpus2/LABELS.json`: the method used, and the **independence caveat** (author-established ground truth). Cover every function in `bench/py_frontend/corpus/*.py` **and** every function in `bench/realworld_*/**_repro.py`.

- [ ] **Step 3: Write the bench**

`bench/py_frontend/run_bench.py` must produce three measurements. Structure it so each is a separate function returning a dict, and `main()` prints all three plus a machine-readable JSON blob.

1. **Detection vs ground truth.** For each labelled function: expected code vs codes Aether produced. Report true positives, false negatives, false positives.
2. **Differential vs bandit.** Run `python -m bandit -f json -q <file>` over the same corpus. Report per-file: found-by-both, Aether-only, bandit-only. **The bandit-only column is required output, not optional** — a differential that only shows the wins is marketing. If `import bandit` fails, print `SKIP: bandit not installed (pip install bandit); differential column unavailable` and continue with measurements 1 and 3. Exit code must not depend on bandit's presence.
3. **False-positive rate on benign code.** Run the frontend over all 77 modules in `tools/py_corpus/` (26) and `tools/py_corpus2/` (51) and count sink-family findings per row. These modules were written for the capability experiment, not as vulnerabilities; a sink-family finding there is a false-positive candidate that must be inspected and reported by code.

- [ ] **Step 4: Run the bench and read measurement 3 before writing anything else**

```bash
python -B bench/py_frontend/run_bench.py
```

**This is a decision point, not a formality.** E0711 (`readFile`/`writeFile` path must be a literal or `safeJoin`) is the row most likely to fire on ordinary `open(path)` across benign code. If a row's finding count on the benign corpus is high relative to its true positives, do **not** ship it default-on and do not quietly delete it either. Instead:

- keep the row out of `cmd_check_py`'s default set,
- add a `--strict` flag to `check-py` that enables it,
- and state the measured number and the decision in `REPORT.md`.

Rows whose benign-corpus count is 0 or near it ship default-on. Let the measurement decide; record the measurement either way.

- [ ] **Step 5: Write `bench/py_frontend/REPORT.md`**

Lead with the weakest number, per the house style of `PYTHON_RESULTS.md` ("This report leads with the thesis-critical metric — false negatives — per the experiment's own success criterion. A bad result reported honestly is the goal."). Required sections:

1. **What this measures and what it does not.** Sink family only. No marker taint on Python (no annotations), no E0801 (no declared effects), no SSRF/cleartext (effect-string family reads a declared annotation Python does not have).
2. **Detection table** — per row: true positives, false negatives, false positives, each citing the command.
3. **False-positive rate on 77 benign modules** — per row, with the default-on/`--strict` decision from Step 4 stated as a consequence of the number.
4. **Differential vs bandit** — including **what bandit catches that Aether does not**, named individually. If bandit was unavailable, say so instead of omitting the section.
5. **Limits.** Intraprocedural. Sink-by-method-name over-flags. No cross-file resolution. A `VIOLATION` is a sound positive, not a complete inventory (reuse the exact caveat from `PYTHON_VIABILITY.md`). Name the **guard-bound-elsewhere** class explicitly, using XXE as the worked example: when the safety of a call lives in a *different statement* (a parser object, a session, a config flag) rather than in the argument shape, no argument-shape rule can see it and the frontend must resolve it per-sink by hand. `resolve_entities=False` is handled (Task 3 Step 3a); every other member of that class is unhandled. That is a residual, not a solved problem — say so, and file it in q4.

- [ ] **Step 6: Write the q4 question page**

`vault/wiki/questions/q4-sink-matching-vs-purity-matching.md`, following the `question_page` contract in `vault/templates/page-contracts.md` and the YAML frontmatter schema in `vault/CLAUDE.md` (`type`, `status`, `confidence`, `last_updated`, `tags`).

**Question:** *Why may the Python frontend match sinks by method name when it was unsound to match purity by method name?*

**Answer:** the direction of the error. `PURE_METHODS` cleared `obj.append()` from the name with no proof of the receiver's type and thereby certified a capability-using module clean — a silent false negative, the contract-breach class (`tools/py_frontend.py:187-192`, and `trap_04` in `PYTHON_RESULTS.md`). Matching `cursor.execute(...)` as a SQL sink from the name, with the same absence of proof, can only produce a finding on code that was not a sink — an over-flag. One rule covers both: never assume clean from a name; freely assume dangerous from a name.

Cite with valid source markers only — `source_name` must be one of `README | keywords | effects | types | diagnostics` (`vault/CLAUDE.md`, Data Model). Link `[[q1-taint-marker-soundness-boundary]]` and `[[../clusters/violation-taxonomy]]` (the ≥2-wikilink rule), add the page to `vault/wiki/index.md` so it is not an orphan, and prepend an entry to `vault/wiki/log.md`.

- [ ] **Step 7: Update the measured claims**

- `PYTHON_VIABILITY.md` — add a section for the sink experiment with the real numbers from Step 4. Do not touch the existing capability numbers; they measured a different thing.
- `SECURITY_POSTURE.md` — state which rows run on Python and which do not, with the reason for each exclusion.
- `demos/case_studies/LOOP_LOG.md` — append an iteration block in the established shape: target, gap confirmed empirically (the 0-of-5 probe), improvement, wiring, ratchet unchanged, report path, TYPE gap surfaced next, suite result.

- [ ] **Step 8: Full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0.

- [ ] **Step 9: Commit**

Two commits: `bench(py): differential vs bandit + false-positive corpus` and `docs(py): q4 sink-vs-purity doctrine, measured Python reach`.

---

## Out of scope (deliberate)

- **Marker taint on Python** (E0712/E0715/E0724 via `typing.Annotated`). Requires users to annotate, which is the same adoption tax as a new language — the objection this plan exists to remove. Revisit only if the sink family lands and someone asks for it.
- **E0716/E0717 authorization.** Needs `Authorized<T>`; no annotation-free Python equivalent exists.
- **The effect-string family (E0710/E0721/E0722).** Reads a declared `net.fetch(...)` annotation. `py_frontend` synthesizes an effect with the first constant string argument, so a partial mapping may be possible — but it is a different mechanism from the sink family and belongs in its own plan with its own probe.
- **Cross-file / whole-repo resolution.** Single-file only, matching `py_frontend` today.
- **Control flow.** Neither the Aether passes nor this frontend model branches or loops; adding it here would make the Python path stronger than the Aether path, which is backwards.
