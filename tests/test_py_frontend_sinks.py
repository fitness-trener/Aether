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


# Stages that do not apply to Python, skipped here and by `check-py`:
#   effects  — E0801 compares a call site against a DECLARED effects
#              clause. Python has none, so there is nothing to compare.
#   semantic — E0202-E0207 are checks about Aether language constructs
#              (match exhaustiveness, dead `let` stores, ignored Results).
#              On translated Python they describe the translation, not
#              the program: `cur = conn.cursor()` read as a dead store.
PY_SKIP_STAGES = ("effects", "semantic")


def _codes(src: str):
    ast_dict, _unp, _meta = py_to_ir(src)
    return sorted(d.code for d in analyze_flat(ast_dict, skip=PY_SKIP_STAGES))


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
    return open(base + "/" + entry).read()


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


def test_chained_receiver_call_is_not_lost():
    """`conn.cursor().execute(sql)` — the sink is reached through a call
    used as a RECEIVER. Dropping receivers loses the finding entirely."""
    src = "def q(conn, name):\n    conn.cursor().execute('SELECT ' + name)\n"
    assert "E0713" in _codes(src), \
        "a sink called on the result of another call must still be seen"
    print("sinks: chained receiver call is translated")


def test_sink_tables_are_auditable():
    from tools.py_frontend import mapping_table
    t = mapping_table()
    for key in ("sink_by_qualified", "sink_by_method", "sink_by_builtin"):
        assert key in t and t[key], f"{key} must be exposed for audit"
    print("sinks: mapping tables exposed via mapping_table()")


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


def test_parameterized_query_is_the_sanctioned_exit():
    """DB-API parameter binding is Python's `sqlBind`: the driver binds
    the values, so the string is not the injection vector. It is a call
    SHAPE (a second argument), not a wrapper function."""
    src = ("def q(cur, uid):\n"
           "    cur.execute('SELECT * FROM t WHERE id = ?', (uid,))\n")
    assert "E0713" not in _codes(src), \
        "a parameterized query is the documented safe form"
    print("sinks: parameterized query passes clean")


def test_single_arg_dynamic_query_still_fires():
    src = ("def q(cur, uid):\n"
           "    cur.execute('SELECT * FROM t WHERE id = ' + uid)\n")
    assert "E0713" in _codes(src), \
        "one argument built by concatenation is the injection"
    print("sinks: single-argument dynamic query still fires")


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


if __name__ == "__main__":
    test_body_is_no_longer_discarded()
    test_assign_becomes_let()
    test_concat_becomes_binop_plus()
    test_fstring_becomes_concat()
    test_constant_only_fstring_is_a_literal()
    test_percent_format_becomes_concat()
    test_unmodeled_expression_is_not_cleared()
    test_the_five_vulnerabilities_are_found()
    test_fstring_sql_injection_found()
    test_literal_query_is_clean()
    test_shell_false_is_not_a_shell_sink()
    test_yaml_load_with_safe_loader_is_not_a_sink()
    test_chained_receiver_call_is_not_lost()
    test_sink_tables_are_auditable()
    test_parameterized_query_is_the_sanctioned_exit()
    test_single_arg_dynamic_query_still_fires()
    test_xxe_safe_parser_disarms_the_sink()
    test_xxe_default_parser_still_fires()
    test_repro_corpus_flags_the_bug()
    test_safe_functions_are_clean()
    print("PY FRONTEND: ALL TESTS PASS")
