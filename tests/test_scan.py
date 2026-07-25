"""tools/scan.py — the reusable corpus scanner.

Verifies the scanner (the product-shape of Aether's phase-2 story: point it
at a directory of AI-generated code, get a findings report) reports clean
code as clean and flags a known vulnerability.

Run: python3 tests/test_scan.py   (exit 0 = pass)
"""
from __future__ import annotations
import io
import os
import sys
from collections import Counter
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import scan  # noqa: E402
from tools.expectations import CORPUS_ROOTS  # noqa: E402


def test_clean_file_no_findings():
    p = os.path.join(ROOT, "reference", "01_hello", "program.aeth")
    r = scan.scan_file(p)
    assert r["findings"] == [], f"clean file should have no findings: {r}"
    assert "parse_error" not in r, r
    print("scan: clean reference file reports no findings")


def test_vulnerable_file_flagged():
    p = os.path.join(ROOT, "demos", "case_studies", "sql_injection",
                     "aether", "vulnerable.aeth")
    r = scan.scan_file(p)
    codes = {f["code"] for f in r["findings"]}
    assert "E0713" in codes, f"SQL-injection demo should flag E0713: {codes}"
    print("scan: vulnerable file flags E0713")


def test_fixed_file_clean():
    p = os.path.join(ROOT, "demos", "case_studies", "sql_injection",
                     "aether", "fixed.aeth")
    r = scan.scan_file(p)
    assert r["findings"] == [], f"fixed form should be clean: {r}"
    print("scan: fixed file reports no findings")


def test_sarif_output_wellformed():
    p = os.path.join(ROOT, "demos", "case_studies", "sql_injection",
                     "aether", "vulnerable.aeth")
    doc = scan.to_sarif([scan.scan_file(p)])
    assert doc["version"] == "2.1.0", doc
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "aether-scan"
    ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert "E0713" in ids, ids
    res = run["results"][0]
    assert res["ruleId"] == "E0713"
    loc = res["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"].endswith("vulnerable.aeth")
    assert loc["region"]["startLine"] >= 1
    print("scan: SARIF output is well-formed (GitHub Code Scanning-ready)")


def test_expect_mode_gates_on_the_difference():
    """`--expect` is what makes the aether-scan workflow able to pass at
    all: this repo deliberately contains vulnerable files, so "fail on any
    finding" is red by construction. Both directions of the difference
    must fail — a finding nobody declared, and a declared finding that
    stopped firing (a detector regression, which the old gate could never
    see because it only ever counted findings upward)."""
    vuln = os.path.join(ROOT, "demos", "case_studies", "sql_injection",
                        "aether", "vulnerable.aeth")
    base = scan.scan_file(vuln)
    assert {f["code"] for f in base["findings"]} == {"E0713"}, base

    declared = scan.diff_expected(base)
    assert declared["unexpected"] == [], declared
    assert declared["missing"] == [], declared

    # No header -> held to `clean`, so the finding is unexpected.
    undeclared = scan.diff_expected(dict(base, declared=None))
    assert [f["code"] for f in undeclared["unexpected"]] == ["E0713"], undeclared

    # Declares a code it does not produce -> the regression direction.
    overstated = scan.diff_expected({"path": vuln, "findings": [],
                                     "declared": Counter({"E0713": 1})})
    assert overstated["missing"] == [("E0713", 1)], overstated
    assert overstated["unexpected"] == [], overstated

    # Multiplicity is part of the claim: 2 sites declared, 1 reported.
    two = dict(base, declared=Counter({"E0713": 2}))
    assert scan.diff_expected(two)["missing"] == [("E0713", 1)], two
    print("scan: --expect gates on the difference, both directions")


def test_expect_mode_clean_over_the_corpus():
    """The end state the workflow depends on: every corpus file matches
    what it declares, so the gate is green and any drift turns it red."""
    argv = [os.path.join(ROOT, sub) for sub in CORPUS_ROOTS] + ["--expect"]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = scan.main(argv)
    assert rc == 0, ("corpus does not match its declared expectations:\n"
                     + buf.getvalue())
    print("scan: --expect is green over the whole expectation corpus")


if __name__ == "__main__":
    test_clean_file_no_findings()
    test_vulnerable_file_flagged()
    test_fixed_file_clean()
    test_sarif_output_wellformed()
    test_expect_mode_gates_on_the_difference()
    test_expect_mode_clean_over_the_corpus()
    print("SCAN TOOL: all tests pass")
