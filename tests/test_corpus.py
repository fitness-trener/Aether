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
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)          # sdk.run reaches bench.harness for its timeout

from aether.parser import parse                        # noqa: E402
from aether.passes import analyze_flat                 # noqa: E402

_HEADER = re.compile(r'^//\s*expect(-run)?:\s*(.+?)\s*$', re.M)
_ENTRY = re.compile(r'^(E\d{4})(?:x(\d+))?$')


def _corpus() -> list:
    """Hand-authored `.aeth` under the two in-scope roots.

    `<source>.fixed.aeth` is excluded: that is the output filename
    `demos/payment_workflow/fix_loop.py` writes, and
    `tests/test_fix_loop_demo.py` regenerates it on every gate run — a
    header written into it would be silently overwritten. Generated
    files make no compliance claim, same reason `bench/` is out of scope
    (ADR-0003). The hand-authored case-study `fixed.aeth` files do NOT
    match this suffix and stay in.
    """
    files = glob.glob(os.path.join(ROOT, "demos", "**", "*.aeth"), recursive=True)
    files += glob.glob(os.path.join(ROOT, "playground", "examples", "**", "*.aeth"),
                       recursive=True)
    return sorted(f for f in set(files)
                  if not os.path.basename(f).endswith(".fixed.aeth"))


def _render(codes) -> str:
    """Codes -> the canonical `// expect:` spec. Inverse of _parse_spec, so
    a failure message can print the line a human would paste."""
    counts = collections.Counter(codes)
    if not counts:
        return "clean"
    return ", ".join(f"{c}x{n}" if n > 1 else c for c, n in sorted(counts.items()))


def _parse_spec(spec: str, where: str) -> collections.Counter:
    if spec.strip() == "clean":
        return collections.Counter()
    counts: collections.Counter = collections.Counter()
    for tok in spec.split(","):
        m = _ENTRY.match(tok.strip())
        if not m:
            raise ValueError(f"{where}: bad expectation entry {tok.strip()!r} "
                             f"(want `E0710`, `E0710x3`, or `clean`)")
        counts[m.group(1)] += int(m.group(2) or 1)
    return counts


def _headers(src: str, where: str):
    """Return (static_spec|None, run_spec|None) from the file's header."""
    static = run = None
    for is_run, spec in _HEADER.findall(src):
        if is_run:
            run = _parse_spec(spec, where)
        else:
            static = _parse_spec(spec, where)
    return static, run


def _runtime_codes(path: str, src: str) -> collections.Counter:
    from aether import sdk
    rr = sdk.run(src, deterministic=True, filename=path)
    return collections.Counter([rr.diagnostic.code] if rr.diagnostic else [])


def test_corpus_states_its_expectations():
    corpus = _corpus()
    assert corpus, "corpus is empty — glob found nothing"
    failures = []
    ran = 0
    for path in corpus:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        want, want_run = _headers(src, rel)
        if want is None:
            failures.append(
                f"{rel}: no `// expect:` header. Every corpus file states its "
                f"own claim — add `// expect: {_render([])}` (or the codes it "
                f"demonstrates) as the first line.")
            continue
        got = collections.Counter(d.code for d in analyze_flat(parse(src, path)))
        if got != want:
            failures.append(
                f"{rel}: static expectation mismatch\n"
                f"    declared: // expect: {_render(want.elements())}\n"
                f"    actual:   // expect: {_render(got.elements())}")
        if want_run is not None:
            ran += 1
            got_run = _runtime_codes(path, src)
            if got_run != want_run:
                failures.append(
                    f"{rel}: runtime expectation mismatch\n"
                    f"    declared: // expect-run: {_render(want_run.elements())}\n"
                    f"    actual:   // expect-run: {_render(got_run.elements())}")
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
