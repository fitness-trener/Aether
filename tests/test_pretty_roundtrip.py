"""C.1 regression tests for the canonical pretty-printer.

The contract under test is the round-trip property:

    parse(pretty(parse(src))) ≡ parse(src)  (modulo position metadata)

across every program in the reference corpus, the benchmark reference
solutions, and the architectural-integrity demo corpus. If the
round-trip ever drops below the full corpus, the pretty-printer has
lost faithfulness for some AST shape and must be fixed before the
formatter (C.4) or the agent SDK's structural-edit tooling (C.2) is
shipped.

Three tests:
  1. Round-trip every file in the union corpus.
  2. Re-pretty is idempotent (`pretty(parse(pretty(parse(src))))` ==
     `pretty(parse(src))`), so the formatter has a stable fixed point.
  3. `asts_equal_ignoring_pos` actually ignores position metadata.
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse  # noqa: E402
from aether.pretty import pretty, asts_equal_ignoring_pos  # noqa: E402


def _collect_corpus():
    """EVERY `.aeth` in the repository that parses — not a sample. The old
    sample (reference/, bench/tasks/, architectural-integrity/) missed
    `playground/examples/32_function_typed_param.aeth`, on which `pretty`
    crashed (`KeyError: 'ret'`, audit 2026-09-24 A9). Files that do not
    parse are the malformed-input fixtures; they have no AST to print."""
    paths = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith(".") and d != "_work")
        for f in sorted(filenames):
            if not f.endswith(".aeth"):
                continue
            p = os.path.join(dirpath, f)
            try:
                parse(open(p, encoding="utf-8-sig").read(), p)
            except Exception:
                continue
            paths.append(p)
    assert any(p.endswith("32_function_typed_param.aeth") for p in paths)
    return paths


def test_roundtrip_full_corpus():
    corpus = _collect_corpus()
    assert len(corpus) >= 400, f"expected >=400 files, found {len(corpus)}"
    failures = []
    for path in corpus:
        try:
            src = open(path, encoding="utf-8-sig").read()
            ast1 = parse(src, path)
            rendered = pretty(ast1)
            ast2 = parse(rendered, path)
            if not asts_equal_ignoring_pos(ast1, ast2):
                failures.append((path, "AST mismatch after round-trip"))
            # With comments kept (fmt, fix-loop): same AST, and a fixed point.
            kept = pretty(ast1, src)
            if not asts_equal_ignoring_pos(ast1, parse(kept, path)):
                failures.append((path, "AST mismatch with comments kept"))
            elif pretty(parse(kept, path), kept) != kept:
                failures.append((path, "comment-keeping pretty not idempotent"))
        except Exception as e:
            failures.append((path, f"{type(e).__name__}: {e}"))
    assert not failures, failures
    print(f"C.1 roundtrip: {len(corpus)} files parse + pretty + reparse to same AST")


def test_pretty_is_idempotent():
    corpus = _collect_corpus()
    failures = []
    for path in corpus:
        src = open(path, encoding="utf-8-sig").read()
        once = pretty(parse(src, path))
        twice = pretty(parse(once, path))
        if once != twice:
            failures.append(path)
    assert not failures, f"pretty not idempotent on {len(failures)} files: {failures[:3]}"
    print(f"C.1 idempotence: pretty stable as a fixed point across {len(corpus)} files")


def test_function_types_print_as_parsed():
    """A9: FunctionType is `{params, returns}` in the parser and prints
    as `function(<params>) returns <T>`."""
    src = ("function apply(f: function(Int, String) returns Bool, x: Int) returns Bool\n"
           "  effects pure\ndo\n  return f(x, \"a\")\nend\n")
    assert pretty(parse(src, "<ft>")) == src, pretty(parse(src, "<ft>"))
    print("C.1 function types: printed from params/returns")


def test_asts_equal_ignoring_pos_strips_pos_metadata():
    a = {"kind": "Ident", "name": "x", "pos": {"line": 1, "column": 1}}
    b = {"kind": "Ident", "name": "x", "pos": {"line": 99, "column": 5}}
    assert asts_equal_ignoring_pos(a, b)
    # but a real structural difference is still caught
    c = {"kind": "Ident", "name": "y", "pos": {"line": 1, "column": 1}}
    assert not asts_equal_ignoring_pos(a, c)
    # nested 'position' as well
    a2 = {"kind": "Foo", "position": {"line": 1, "column": 1}, "children": [a]}
    b2 = {"kind": "Foo", "position": {"line": 7, "column": 2}, "children": [b]}
    assert asts_equal_ignoring_pos(a2, b2)
    print("C.1 oracle: asts_equal_ignoring_pos strips pos + position metadata")


def test_string_escapes_print_escaped():
    """BUG-104: `expr_StringLit` escaped only `\\` and `"`, so `\\n` `\\r`
    `\\t` `\\0` were printed as raw characters. A raw CR broke the
    comment re-attachment on the next pass (a `// ...` line was lost), so
    comment-keeping `fmt` was not a fixed point."""
    for lit in ("\\n", "\\r", "\\t", "\\0", "\\\\", '\\"'):
        src = ('function f() returns String\n  effects pure\ndo\n  return "%s"\nend\n\n'
               "// one\n// two\nfunction g() returns Int\n  effects pure\ndo\n  return 1\nend\n") % lit
        once = pretty(parse(src, "<r>"), src)
        twice = pretty(parse(once, "<r>"), once)
        assert f'return "{lit}"' in once, (lit, once)
        assert once == twice, f"fmt not a fixed point for {lit!r}"
        assert "// one" in twice and "// two" in twice, f"comment lost for {lit!r}"
        assert asts_equal_ignoring_pos(parse(once, "<r>"), parse(src, "<r>")), lit
    print("BUG-104: string escapes print escaped; comment-keeping fmt is a fixed point")


def test_pattern_literals_and_unicode_line_breaks_keep_comments():
    """BUG-105: the `match` literal-pattern printer had the same narrow
    escaping as BUG-104, and `_comment_blocks` split lines with
    `splitlines()`, which also breaks on U+2028/U+0085/VT/FF while the
    lexer counts only "\\n" — a raw U+2028 inside a string literal shifted
    every later comment anchor and a comment line was dropped per pass."""
    tail = ("\n// one\n// two\nfunction g() returns Int\n  effects pure\ndo\n"
            "  return 1\nend\n")
    cases = [
        # a string literal pattern with an escape
        'function f(s: String) returns Int\n  effects pure\ndo\n'
        '  match s do\n    case "\\n" do\n      return 1\n    end\n'
        '    case _ do\n      return 0\n    end\n  end\nend\n',
        # a raw U+2028 inside a string literal
        'function f() returns String\n  effects pure\ndo\n  return "a b"\nend\n',
    ]
    for head in cases:
        src = head + tail
        once = pretty(parse(src, "<r>"), src)
        twice = pretty(parse(once, "<r>"), once)
        assert once == twice, f"fmt not a fixed point:\n{once!r}"
        assert "// one" in twice and "// two" in twice, f"comment lost:\n{twice!r}"
        assert asts_equal_ignoring_pos(parse(once, "<r>"), parse(src, "<r>"))
    once = pretty(parse(cases[0] + tail, "<r>"), cases[0] + tail)
    assert 'case "\\n" do' in once, f"pattern literal printed raw:\n{once!r}"
    print("BUG-105: pattern literals escape; a Unicode line separator keeps comment anchors")


if __name__ == "__main__":
    test_string_escapes_print_escaped()
    test_pattern_literals_and_unicode_line_breaks_keep_comments()
    test_roundtrip_full_corpus()
    test_pretty_is_idempotent()
    test_function_types_print_as_parsed()
    test_asts_equal_ignoring_pos_strips_pos_metadata()
    print("C.1 ALL PRETTY-ROUNDTRIP TESTS PASS")
