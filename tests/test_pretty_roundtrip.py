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
    paths = []
    refdir = os.path.join(ROOT, "reference")
    if os.path.isdir(refdir):
        for d in sorted(os.listdir(refdir)):
            p = os.path.join(refdir, d, "program.aeth")
            if os.path.isfile(p):
                paths.append(p)
    bench = os.path.join(ROOT, "bench", "tasks")
    if os.path.isdir(bench):
        for d in sorted(os.listdir(bench)):
            p = os.path.join(bench, d, "reference.aeth")
            if os.path.isfile(p):
                paths.append(p)
    demos = os.path.join(ROOT, "demos", "architectural-integrity")
    if os.path.isdir(demos):
        for d in sorted(os.listdir(demos)):
            p = os.path.join(demos, d, "aether", "main.aeth")
            if os.path.isfile(p):
                paths.append(p)
    return paths


def test_roundtrip_full_corpus():
    corpus = _collect_corpus()
    assert len(corpus) >= 20, f"expected >=20 files, found {len(corpus)}"
    failures = []
    for path in corpus:
        try:
            src = open(path).read()
            ast1 = parse(src, path)
            rendered = pretty(ast1)
            ast2 = parse(rendered, path)
            if not asts_equal_ignoring_pos(ast1, ast2):
                failures.append((path, "AST mismatch after round-trip"))
        except Exception as e:
            failures.append((path, f"{type(e).__name__}: {e}"))
    assert not failures, failures
    print(f"C.1 roundtrip: {len(corpus)} files parse + pretty + reparse to same AST")


def test_pretty_is_idempotent():
    corpus = _collect_corpus()
    failures = []
    for path in corpus:
        src = open(path).read()
        once = pretty(parse(src, path))
        twice = pretty(parse(once, path))
        if once != twice:
            failures.append(path)
    assert not failures, f"pretty not idempotent on {len(failures)} files: {failures[:3]}"
    print(f"C.1 idempotence: pretty stable as a fixed point across {len(corpus)} files")


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


if __name__ == "__main__":
    test_roundtrip_full_corpus()
    test_pretty_is_idempotent()
    test_asts_equal_ignoring_pos_strips_pos_metadata()
    print("C.1 ALL PRETTY-ROUNDTRIP TESTS PASS")
