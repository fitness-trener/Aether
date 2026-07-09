"""Differential: Aether PEP 440 port vs packaging 26.2.

Generates a corpus of canonical PEP 440 version strings, then for EVERY
ordered pair compares:
  - packaging.version.Version(a) <=> Version(b)   (the oracle)
  - Aether versionCompare(a, b)                    (the port)

A single ordering divergence would mean a resolver using this logic could
select a different release than pip does. Also checks that sorting the whole
corpus with the Aether key agrees with packaging's sort.

Exit 0 iff zero unattributed divergences.
"""

from __future__ import annotations

import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
PKGLIBS = os.environ.get("PACKAGING_PYLIBS")
if PKGLIBS:
    sys.path.insert(0, PKGLIBS)

from packaging import version as pv  # noqa: E402
import packaging  # noqa: E402

from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402


def load_aether(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_pep440"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


def gen_corpus() -> list[str]:
    """Canonical PEP 440 forms across the epoch/release/pre/post/dev space."""
    releases = [
        "0", "1", "2", "10", "1.0", "1.1", "1.0.0", "1.2.3", "1.2.10",
        "2.0", "1.0.1", "0.9", "1.11", "1.2", "9.0", "10.0.0", "1.0.0.0",
    ]
    out: set[str] = set()
    for rel in releases:
        for epoch in ("", "1!"):
            base = f"{epoch}{rel}"
            pres = ["", "a0", "a1", "b0", "b1", "rc0", "rc1", "rc2"]
            posts = ["", ".post0", ".post1", ".post2"]
            devs = ["", ".dev0", ".dev1"]
            for pre in pres:
                for post in posts:
                    for dev in devs:
                        out.add(f"{base}{pre}{post}{dev}")
    # Curated PEP 440 example ladder (the canonical ordering from the spec).
    out.update([
        "1.0.dev456", "1.0a1", "1.0a2.dev456", "1.0a12.dev456", "1.0a12",
        "1.0b1.dev456", "1.0b2", "1.0b2.post345.dev456", "1.0b2.post345",
        "1.0rc1.dev456", "1.0rc1", "1.0", "1.0.post456.dev34", "1.0.post456",
        "1.1.dev1", "1!1.0", "1!1.1", "2!1.0",
    ])
    # Keep only strings the port's canonical grammar is claimed to cover and
    # that packaging accepts; normalize through packaging so both sides see the
    # identical canonical string.
    corpus: set[str] = set()
    for s in out:
        try:
            corpus.add(str(pv.Version(s)))
        except pv.InvalidVersion:
            pass
    return sorted(corpus)


def main() -> int:
    g = load_aether(os.path.join(HERE, "pep440.aeth"))
    ae_cmp = g["_ae_versionCompare"]

    corpus = gen_corpus()
    print(f"packaging version under test: {packaging.__version__}")
    print(f"python: {sys.version.split()[0]}")
    print(f"corpus: {len(corpus)} distinct canonical versions")
    print(f"ordered pairs: {len(corpus) * len(corpus)}")
    print()

    def oracle(a: str, b: str) -> int:
        va, vb = pv.Version(a), pv.Version(b)
        return -1 if va < vb else (1 if va > vb else 0)

    mismatches = []
    parse_fail = []
    total = 0
    for a, b in itertools.product(corpus, repeat=2):
        total += 1
        want = oracle(a, b)
        got = ae_cmp(a, b)
        if got != want:
            # Distinguish a real ordering disagreement from a parse gap: if the
            # port and oracle agree on every OTHER pairing of a and b, a lone
            # 0-vs-nonzero here means the port failed to parse one operand.
            mismatches.append((a, b, want, got))

    # Sort agreement: does the Aether key induce packaging's total order?
    import functools
    ae_sorted = sorted(corpus, key=functools.cmp_to_key(ae_cmp))
    pk_sorted = sorted(corpus, key=functools.cmp_to_key(oracle))
    sort_ok = ae_sorted == pk_sorted

    rate = 100.0 * (total - len(mismatches)) / total
    print(f"pairwise ordering: {total - len(mismatches)}/{total} match ({rate:.6f}%)")
    print(f"full-corpus sort agrees with packaging: {sort_ok}")
    for a, b, want, got in mismatches[:30]:
        print(f"  MISMATCH cmp({a!r}, {b!r}): packaging={want} aether={got}")
    if len(mismatches) > 30:
        print(f"  ... and {len(mismatches) - 30} more")

    # Equality-consistency: a==b under the port iff canonical strings equal.
    eq_bugs = 0
    for a in corpus:
        if ae_cmp(a, a) != 0:
            eq_bugs += 1
    print(f"reflexive cmp(a,a)==0 failures: {eq_bugs}")

    print()
    ok = not mismatches and sort_ok and eq_bugs == 0
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
