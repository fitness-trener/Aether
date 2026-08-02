"""Risk ratings — the triage axis.

Every diagnostic code the tree can emit must carry a security risk
rating. Risk is orthogonal to `Diagnostic.severity`: severity decides
whether the compiler refuses the program, risk decides what a human
reading a 1.19M-line scan looks at first. A new code with no rating is
a scan row that sorts silently to the bottom, so the coverage check
below is a gate, not a nicety.

Run: python -B tests/test_risk.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from aether.risk import (RISK, ORDER, SECURITY_SEVERITY,      # noqa: E402
                         risk_of, rank, at_or_above)
from tools.diagnostic_codes import constructed_codes          # noqa: E402


def test_every_emitted_code_rated():
    emitted = constructed_codes(ROOT)
    missing = sorted(emitted - set(RISK))
    assert not missing, (
        f"codes with no risk rating: {missing}. Add a row to "
        f"transpiler/aether/risk.py. A rated code is how the scanner "
        f"sorts and how SARIF sets security-severity.")
    print(f"risk: all {len(emitted)} emitted codes rated")


def test_no_phantom_codes_rated():
    emitted = constructed_codes(ROOT)
    phantom = sorted(set(RISK) - emitted)
    assert not phantom, (
        f"risk table rates codes the tree never emits: {phantom}. "
        f"Remove them — an invented code is the one thing the honesty "
        f"rules forbid outright.")
    print("risk: no phantom codes rated")


def test_ratings_are_legal_values():
    bad = sorted((c, v) for c, v in RISK.items() if v not in ORDER)
    assert not bad, f"illegal rating values: {bad}; legal: {sorted(ORDER)}"
    assert set(SECURITY_SEVERITY) == set(ORDER), (
        SECURITY_SEVERITY, ORDER)
    print("risk: all ratings legal, severity map complete")


def test_rank_orders_worst_first():
    assert rank("E0714") > rank("E0725"), "critical must outrank high"
    assert rank("E0725") > rank("E0728"), "high must outrank medium"
    assert rank("E0728") > rank("E0205"), "medium must outrank low"
    assert rank("E0205") > rank("E0201"), "low must outrank info"
    print("risk: rank orders critical > high > medium > low > info")


def test_unknown_code_is_info_not_a_crash():
    assert risk_of("E9999") == "info", (
        "an unrated code must degrade to info, not raise — the scanner "
        "renders output on a tree the table may lag behind; "
        "test_every_emitted_code_rated is what catches the lag")
    print("risk: unknown code degrades to info")


def test_at_or_above_filters():
    assert at_or_above("E0714", "high") is True
    assert at_or_above("E0725", "high") is True
    assert at_or_above("E0728", "high") is False
    assert at_or_above("E0201", "info") is True
    print("risk: at_or_above filters on the floor")


if __name__ == "__main__":
    test_every_emitted_code_rated()
    test_no_phantom_codes_rated()
    test_ratings_are_legal_values()
    test_rank_orders_worst_first()
    test_unknown_code_is_info_not_a_crash()
    test_at_or_above_filters()
    print("\nrisk: 6/6 pass")
