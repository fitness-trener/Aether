"""False-positive gate — legitimate code must stay clean.

A security checker that over-flags is worse than useless: developers turn
it off. This suite is the counterweight to the positive (violation-caught)
tests. It runs EVERY reach-scope detector (E0710-E0726) over a corpus of
programs that use the guarded sinks CORRECTLY — every `fixed.aeth` across
the repo plus the clean playground examples — and asserts ZERO diagnostics.

Together the three suites form the credibility triangle:
  - test_effect_scope        : bad code is caught          (catch rate)
  - test_false_positive_corpus: good code stays clean       (this file)
  - test_runtime_enforcement : the fix defangs at runtime  (not theater)

Run: python3 tests/test_false_positive_corpus.py   (exit 0 = pass)
"""
from __future__ import annotations
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from aether.parser import parse                       # noqa: E402
from aether.passes.effects import (                   # noqa: E402
    check_effect_scope, check_fs_path_safety, check_secret_flow,
    check_injection, check_command_injection, check_pii_flow,
    check_authorization, check_resource_authorization, check_open_redirect,
    check_template_injection, check_deserialization, check_cleartext_transmission,
    check_metadata_fetch, check_hardcoded_secret, check_log_injection,
    check_reflected_xss, check_header_injection,
)

_ALL_CHECKS = [
    check_effect_scope, check_fs_path_safety, check_secret_flow,
    check_injection, check_command_injection, check_pii_flow,
    check_authorization, check_resource_authorization, check_open_redirect,
    check_template_injection, check_deserialization, check_cleartext_transmission,
    check_metadata_fetch, check_hardcoded_secret, check_log_injection,
    check_reflected_xss, check_header_injection,
]

# Clean playground examples (the non-violation ones — the violation demos
# 02/03/04/05/10/13.. are SUPPOSED to be flagged and are excluded).
_CLEAN_PLAYGROUND = [
    "01_clean_pure_function.aeth",
    "06_payment_pipeline.aeth",
    "07_rate_limiter.aeth",
    "08_order_saga.aeth",
    "09_feature_flags.aeth",
]


def _corpus():
    files = []
    files += glob.glob(os.path.join(ROOT, "bench", "**", "fixed.aeth"), recursive=True)
    files += glob.glob(os.path.join(ROOT, "demos", "**", "fixed.aeth"), recursive=True)
    for name in _CLEAN_PLAYGROUND:
        p = os.path.join(ROOT, "playground", "examples", name)
        if os.path.isfile(p):
            files.append(p)
    return sorted(set(files))


def test_no_false_positives():
    corpus = _corpus()
    assert corpus, "corpus is empty — glob found nothing"
    offenders = []
    for path in corpus:
        with open(path, encoding="utf-8") as f:
            ast = parse(f.read(), path)
        codes = []
        for chk in _ALL_CHECKS:
            codes += [d.code for d in chk(ast)]
        if codes:
            offenders.append((os.path.relpath(path, ROOT), sorted(set(codes))))
    assert not offenders, "legitimate code flagged (false positives):\n" + \
        "\n".join(f"  {p}: {c}" for p, c in offenders)
    print(f"false-positive gate: {len(corpus)} legitimate programs, 0 diagnostics")


if __name__ == "__main__":
    test_no_false_positives()
    print("FALSE-POSITIVE CORPUS: all clean")
