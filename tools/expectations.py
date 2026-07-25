"""`// expect:` headers — the one parser.

A hand-authored `.aeth` states its own claim in a header comment:

    // expect: E0710x3          static codes from analyze(), sorted multiset
    // expect: E0713, E0719     several codes, one each
    // expect: clean            no static diagnostics
    // expect-run: E0304        code raised at execution (optional)

Multiplicity is part of the claim: a detector regressing from three sites
to one is exactly what a set comparison would miss.

Two consumers, one grammar. `tests/test_corpus.py` asserts every in-scope
file HAS a header and MEETS it. `tools/scan.py --expect` gates CI on the
DIFFERENCE between findings and what the tree declares — which is what
makes a repo full of deliberately-vulnerable demos scannable at all. That
workflow ran `tools.scan` over the whole repo and failed on any finding,
so it could not pass and carried no signal from 2026-07-09 onward.

Scope is `demos/**` + `playground/examples/**` per ADR-0003. `bench/`
(generated tasks, graded on whether the fix-loop repairs them) and
`reference/` (driven by `cli test`, which runs no static passes per
ADR-0001) stay out, as do the fixture trees under `tests/`, `runs/`,
`validation/` and `outreach/`.
"""

from __future__ import annotations
import collections
import glob
import os
import re
from typing import List, Optional, Tuple

# The corpus roots. `tests/test_corpus.py` globs these; the aether-scan
# workflow passes the same two paths to `tools.scan --expect`. Change one,
# change the other.
CORPUS_ROOTS = ("demos", os.path.join("playground", "examples"))

_HEADER = re.compile(r'^//\s*expect(-run)?:\s*(.+?)\s*$', re.M)
_ENTRY = re.compile(r'^(E\d{4})(?:x(\d+))?$')

Spec = collections.Counter


def render(codes) -> str:
    """Codes -> the canonical `// expect:` spec. Inverse of parse_spec, so
    a failure message can print the line a human would paste."""
    counts = collections.Counter(codes)
    if not counts:
        return "clean"
    return ", ".join(f"{c}x{n}" if n > 1 else c for c, n in sorted(counts.items()))


def parse_spec(spec: str, where: str) -> Spec:
    if spec.strip() == "clean":
        return collections.Counter()
    counts: Spec = collections.Counter()
    for tok in spec.split(","):
        m = _ENTRY.match(tok.strip())
        if not m:
            raise ValueError(f"{where}: bad expectation entry {tok.strip()!r} "
                             f"(want `E0710`, `E0710x3`, or `clean`)")
        counts[m.group(1)] += int(m.group(2) or 1)
    return counts


def parse_header(src: str, where: str) -> Tuple[Optional[Spec], Optional[Spec]]:
    """Return (static_spec|None, run_spec|None) from the file's header.
    None means the file makes no claim on that axis."""
    static = run = None
    for is_run, spec in _HEADER.findall(src):
        if is_run:
            run = parse_spec(spec, where)
        else:
            static = parse_spec(spec, where)
    return static, run


def corpus_files(root: str) -> List[str]:
    """Hand-authored `.aeth` under the in-scope roots.

    `<source>.fixed.aeth` is excluded: that is the output filename
    `demos/payment_workflow/fix_loop.py` writes, and
    `tests/test_fix_loop_demo.py` regenerates it on every gate run — a
    header written into it would be silently overwritten. Generated files
    make no compliance claim, same reason `bench/` is out of scope
    (ADR-0003). The hand-authored case-study `fixed.aeth` files do NOT
    match this suffix and stay in.
    """
    files: List[str] = []
    for sub in CORPUS_ROOTS:
        files += glob.glob(os.path.join(root, sub, "**", "*.aeth"), recursive=True)
    return sorted(f for f in set(files)
                  if not os.path.basename(f).endswith(".fixed.aeth"))
