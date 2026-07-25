"""Expectation corpus — every hand-authored `.aeth` states its own claim.

83 files under `demos/**` and `playground/examples/**` are named for what
they demonstrate (`14_sql_injection.aeth`, `vulnerable.aeth`,
`fixed.aeth`). Nothing read those names. This suite makes the claim
machine-checkable by putting it in the file:

    // expect: E0710x3            static codes from analyze(), sorted multiset
    // expect: E0713, E0719       several codes, one each
    // expect: clean              no static diagnostics
    // expect-run: E0304          code raised at execution (optional)

Multiplicity is part of the claim — a detector regressing from three
sites to one is exactly the failure the ratchet exists to catch, and a
set comparison would not see it. No line numbers: they turn whitespace
edits into test edits.

Scope is `demos/**` + `playground/examples/**` per ADR-0003. `bench/`
(generated tasks, graded on whether the fix-loop repairs them) and
`reference/` (driven by `cli test`, which runs no static passes per
ADR-0001) stay out. `tests/test_false_positive_corpus.py` survives
rather than being subsumed: its glob reaches `bench/**/fixed.aeth`,
which this does not.

A file in scope with no `// expect:` line is a FAILURE, not a skip —
that is the whole enforcement. A new detector ships its corpus pair, and
the pair states what it claims.

`// expect-run:` is opt-in and only the files that declare it are
executed. This suite does not sweep the corpus for runtime behaviour;
`tests/test_runtime_enforcement.py` owns that axis.

Run: python -B tests/test_corpus.py   (exit 0 = pass)
"""
from __future__ import annotations
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)          # sdk.run reaches bench.harness for its timeout

from aether.parser import parse                        # noqa: E402
from aether.passes import analyze_flat                 # noqa: E402
# The header grammar and the corpus scope live in tools/expectations.py so
# that `tools.scan --expect` — the aether-scan CI gate — judges files by
# exactly the claim this suite enforces.
from tools.expectations import (                       # noqa: E402
    corpus_files, parse_header, render,
)


def _runtime_codes(path: str, src: str) -> collections.Counter:
    from aether import sdk
    rr = sdk.run(src, deterministic=True, filename=path)
    return collections.Counter([rr.diagnostic.code] if rr.diagnostic else [])


def test_corpus_states_its_expectations():
    corpus = corpus_files(ROOT)
    assert corpus, "corpus is empty — glob found nothing"
    failures = []
    ran = 0
    for path in corpus:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        want, want_run = parse_header(src, rel)
        if want is None:
            failures.append(
                f"{rel}: no `// expect:` header. Every corpus file states its "
                f"own claim — add `// expect: {render([])}` (or the codes it "
                f"demonstrates) as the first line.")
            continue
        got = collections.Counter(d.code for d in analyze_flat(parse(src, path)))
        if got != want:
            failures.append(
                f"{rel}: static expectation mismatch\n"
                f"    declared: // expect: {render(want.elements())}\n"
                f"    actual:   // expect: {render(got.elements())}")
        if want_run is not None:
            ran += 1
            got_run = _runtime_codes(path, src)
            if got_run != want_run:
                failures.append(
                    f"{rel}: runtime expectation mismatch\n"
                    f"    declared: // expect-run: {render(want_run.elements())}\n"
                    f"    actual:   // expect-run: {render(got_run.elements())}")
    assert not failures, (
        f"{len(failures)} corpus expectation(s) unmet:\n\n"
        + "\n".join(failures)
        + "\n\nIf the new behaviour is CORRECT, update the header. If it is "
          "not, the detector regressed — fix the detector.")
    print(f"corpus: {len(corpus)} programs state their expectation and meet it "
          f"({ran} also checked at runtime)")


if __name__ == "__main__":
    test_corpus_states_its_expectations()
    print("CORPUS: every claim holds")
