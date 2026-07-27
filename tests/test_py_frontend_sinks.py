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


def test_with_statement_open_is_seen():
    """`with open(path) as f:` is THE idiomatic Python file access.
    Missing it made the benign-corpus false-positive count look good for
    the wrong reason: most file opens were simply invisible."""
    src = ('def load(base, name):\n'
           '    with open(base + "/" + name) as f:\n'
           '        return f.read()\n')
    assert "E0711" in _codes(src), \
        "a with-statement open must reach the path rule"
    print("sinks: with-statement open is translated")


def test_string_literal_carries_a_position():
    """E0723 anchors on the literal itself. A finding with no line is
    useless to a fix-loop, so StringLit must carry `pos`."""
    src = 'def f():\n\n\n    k = "AKIAIOSFODNN7EXAMPLE"\n'
    ast_dict, _u, _m = py_to_ir(src)
    diags = [d for d in analyze_flat(ast_dict, skip=PY_SKIP_STAGES)
             if d.code == "E0723"]
    assert diags, "a hardcoded AWS key literal must be reported"
    assert diags[0].position.line == 4, \
        f"E0723 must anchor on the literal's real line, got {diags[0].position.line}"
    print("sinks: E0723 anchors on the literal's line")


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


# --- guard-bound-elsewhere: an unresolved guard means SINK ---------------
# These gates decide safety from something other than the argument the
# rule judges. All three shipped defaulting the unknown case to "safe",
# which produced three false accepts (BUGS.md BUG-004). q5's rule applies
# to values exactly as it does to names: never clear on weak evidence.

def test_yaml_unsafe_loader_is_still_a_sink():
    """`Loader=yaml.Loader` is the RCE. Verified by execution on PyYAML
    6.0.3: yaml.Loader constructs !!python/object/apply. Adding Loader=
    to silence the deprecation warning is the commonest wrong fix."""
    src = "import yaml\ndef f(raw):\n    yaml.load(raw, Loader=yaml.Loader)\n"
    assert "E0720" in _codes(src), "yaml.Loader is the unsafe loader"
    print("guard: yaml.Loader still flagged")


def test_yaml_unsafe_loader_named_elsewhere_is_still_a_sink():
    src = ("import yaml\ndef f(raw):\n"
           "    loader = yaml.Loader\n"
           "    yaml.load(raw, Loader=loader)\n")
    assert "E0720" in _codes(src), \
        "a loader bound elsewhere must not clear the sink"
    print("guard: loader bound elsewhere still flagged")


def test_yaml_safe_loader_stays_clean():
    src = "import yaml\ndef f(raw):\n    yaml.load(raw, Loader=yaml.SafeLoader)\n"
    assert "E0720" not in _codes(src), "SafeLoader is the documented fix"
    print("guard: SafeLoader stays clean")


def test_yaml_full_loader_is_not_sanctioned():
    """FullLoader refused this plan's probe payload but has its own
    bypass CVEs (CVE-2020-1747, CVE-2020-14343). Over-flag."""
    src = "import yaml\ndef f(raw):\n    yaml.load(raw, Loader=yaml.FullLoader)\n"
    assert "E0720" in _codes(src), \
        "FullLoader is deliberately not sanctioned - it has bypass CVEs"
    print("guard: FullLoader deliberately not sanctioned")


def test_shell_true_bound_elsewhere_is_still_a_sink():
    src = ("import subprocess\ndef f(cmd):\n"
           "    sh = True\n"
           "    subprocess.run('x ' + cmd, shell=sh)\n")
    assert "E0714" in _codes(src), \
        "shell= whose value is not provably False must be treated as a shell"
    print("guard: shell bound elsewhere still flagged")


def test_concatenated_sql_with_params_is_still_a_sink():
    """A second argument does not launder a concatenated query. The
    parameterized form is already clean because argument 0 is a literal -
    the recognizer was unnecessary AND wrong."""
    src = ("def f(cur, name, extra):\n"
           "    cur.execute('SELECT * FROM t WHERE n=' + name, extra)\n")
    assert "E0713" in _codes(src), \
        "params do not save a query built by concatenation"
    print("guard: concatenated SQL with params still flagged")


def test_attribute_read_of_a_call_result_is_not_lost():
    """`subprocess.run(...).returncode` is an attribute READ of a call
    result — not a call, so the call inside it used to vanish. Found by
    the bench, not by a hand-written test: the same shape without
    `.returncode` was flagged, so the unit tests all passed."""
    src = ("import subprocess\ndef f(cmd):\n"
           "    return subprocess.run('x ' + cmd, shell=True).returncode\n")
    assert "E0714" in _codes(src), \
        "a sink call under an attribute read must still be seen"
    print("guard: attribute read of a call result is translated")


def test_safe_loader_bound_elsewhere_is_clean():
    src = ("import yaml\ndef f(raw):\n"
           "    loader = yaml.SafeLoader\n"
           "    yaml.load(raw, Loader=loader)\n")
    assert "E0720" not in _codes(src), \
        "a name bound once to a sanctioned loader is resolvable"
    print("guard: SafeLoader bound elsewhere resolves clean")


def test_rebound_loader_is_still_a_sink():
    src = ("import yaml\ndef f(raw, flag):\n"
           "    loader = yaml.SafeLoader\n"
           "    loader = yaml.Loader\n"
           "    yaml.load(raw, Loader=loader)\n")
    assert "E0720" in _codes(src), \
        "a name with disagreeing bindings must not resolve to safe"
    print("guard: rebound loader stays flagged")


def test_shell_false_bound_elsewhere_is_clean():
    src = ("import subprocess\ndef f(cmd):\n"
           "    sh = False\n"
           "    subprocess.run(['x', cmd], shell=sh)\n")
    assert "E0714" not in _codes(src), \
        "shell provably False is not a shell sink"
    print("guard: shell=False bound elsewhere resolves clean")


def test_pypi_scan_row_set_matches_cli():
    """The PyPI scan claims to measure exactly what `check-py` prints. If
    the CLI's row set drifts, the scan's headline number silently stops
    describing the shipped tool."""
    import importlib.util
    from transpiler.aether import cli
    spec = importlib.util.spec_from_file_location(
        "pypi_scan", os.path.join(ROOT, "bench", "pypi_scan", "run_scan.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.SKIP_STRICT == cli._PY_SKIP_STAGES, \
        f"scan {m.SKIP_STRICT} vs cli {cli._PY_SKIP_STAGES}"
    assert m.SKIP_DEFAULT == cli._PY_SKIP_STAGES + ("capability",), \
        f"scan default stages drifted: {m.SKIP_DEFAULT}"
    assert m.STRICT_ONLY == cli._PY_STRICT_ONLY_CODES, \
        f"scan {m.STRICT_ONLY} vs cli {cli._PY_STRICT_ONLY_CODES}"
    print("scan: row set matches the CLI's")


def test_unmapped_call_cannot_collide_with_an_aether_sink_name():
    """An unmapped Python call keeps its spelling under a `py:` prefix, so
    a method merely SPELLED like an Aether sink cannot become one without
    passing through the mapping table. Found by the PyPI scan: before the
    prefix, `self.redirect(uri)` fired E0718 and `self.renderTemplate(x)`
    fired E0719 on the name collision alone."""
    src = ("class H:\n"
           "    def go(self, uri):\n"
           "        self.redirect(uri)\n"
           "    def w(self, x):\n"
           "        self.renderTemplate(x)\n"
           "    def d(self, b):\n"
           "        self.deserialize(b)\n")
    codes = _codes(src)
    assert codes == [], \
        f"a name collision must not create an unmapped sink: {codes}"
    print("sinks: unmapped calls cannot collide with Aether sink names")


def test_real_mapped_sinks_still_fire_after_prefixing():
    """The prefix must not cost a mapped sink. Control for the test above."""
    src = ("import os\nfrom flask import redirect\n"
           "def a(cmd):\n    os.system('sh ' + cmd)\n"
           "def b(nxt):\n    redirect(nxt)\n")
    codes = _codes(src)
    assert "E0714" in codes and "E0718" in codes, \
        f"mapped sinks must still fire: {codes}"
    print("sinks: mapped sinks unaffected by the py: prefix")


# --- CLI ----------------------------------------------------------------
# `_emit_error` writes diagnostics to STDERR and the summary to STDOUT,
# so these assert against the combined output.

def _run_check_py(src: str, *flags):
    import subprocess as sp
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(src)
        r = sp.run([sys.executable, "-B", "-m", "transpiler.aether.cli",
                    "check-py", p, *flags], cwd=ROOT,
                   capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


_OPEN_PARAM_SRC = 'def load(path):\n    with open(path) as f:\n        return f.read()\n'


def test_e0711_is_held_back_by_default():
    """Measured on 76 benign modules: E0711 fired 11 times, 8 of them
    `open(path_param)`. Real, but at a ratio that buries the other rows."""
    rc, out = _run_check_py(_OPEN_PARAM_SRC)
    # "[E0711]" is the diagnostic form; the banner mentions the bare code
    # when it explains what --strict adds, and that must not count.
    assert "[E0711]" not in out, f"E0711 must not be reported by default: {out}"
    assert rc == 0, f"default run on this shape must be clean: {out}"
    print("cli: E0711 held back by default")


def test_e0711_appears_under_strict():
    rc, out = _run_check_py(_OPEN_PARAM_SRC, "--strict")
    assert "[E0711]" in out, f"--strict must report E0711: {out}"
    assert rc == 2, "a finding must exit 2"
    print("cli: --strict reports E0711")


def test_check_py_cli_reports_and_exits_2():
    rc, out = _run_check_py("import subprocess\n"
                            "def r(host):\n"
                            "    subprocess.run('ping ' + host, shell=True)\n")
    assert rc == 2, f"a finding must exit 2, got {rc}: {out}"
    assert "E0714" in out, out
    assert "not checked" in out.lower(), \
        "the reduced guarantee set must be stated on the output, not implied"
    print("cli: check-py reports E0714 and states its limits")


def test_check_py_clean_exits_0():
    rc, out = _run_check_py("def add(a, b):\n    return a + b\n")
    assert rc == 0, f"clean file must exit 0: {out}"
    print("cli: check-py on a clean file exits 0")


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
    test_with_statement_open_is_seen()
    test_string_literal_carries_a_position()
    test_xxe_safe_parser_disarms_the_sink()
    test_xxe_default_parser_still_fires()
    test_repro_corpus_flags_the_bug()
    test_safe_functions_are_clean()
    test_yaml_unsafe_loader_is_still_a_sink()
    test_yaml_unsafe_loader_named_elsewhere_is_still_a_sink()
    test_yaml_safe_loader_stays_clean()
    test_yaml_full_loader_is_not_sanctioned()
    test_shell_true_bound_elsewhere_is_still_a_sink()
    test_concatenated_sql_with_params_is_still_a_sink()
    test_attribute_read_of_a_call_result_is_not_lost()
    test_safe_loader_bound_elsewhere_is_clean()
    test_rebound_loader_is_still_a_sink()
    test_shell_false_bound_elsewhere_is_clean()
    test_pypi_scan_row_set_matches_cli()
    test_unmapped_call_cannot_collide_with_an_aether_sink_name()
    test_real_mapped_sinks_still_fire_after_prefixing()
    test_check_py_cli_reports_and_exits_2()
    test_check_py_clean_exits_0()
    test_e0711_is_held_back_by_default()
    test_e0711_appears_under_strict()
    print("PY FRONTEND: ALL TESTS PASS")
