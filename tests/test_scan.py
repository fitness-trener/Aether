"""tools/scan.py — the reusable corpus scanner.

Verifies the scanner (the product-shape of Aether's phase-2 story: point it
at a directory of AI-generated code, get a findings report) reports clean
code as clean and flags a known vulnerability.

Run: python3 tests/test_scan.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import scan  # noqa: E402


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


if __name__ == "__main__":
    test_clean_file_no_findings()
    test_vulnerable_file_flagged()
    test_fixed_file_clean()
    test_sarif_output_wellformed()
    print("SCAN TOOL: all tests pass")
