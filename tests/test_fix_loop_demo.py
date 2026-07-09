"""F.2 regression test for the SDK-driven fix-loop demo.

The contract under test: given the broken candidate at
`demos/payment_workflow/broken.aeth` (which violates B.1 and B.3 at
once), the fix-loop driver mechanically resolves both diagnostics
using only structured `extra` info, in two iterations, and the
result passes every default-on pass.

Two tests:
  1. The fix-loop transcript shows exactly the expected sequence of
     (diagnostic-code, transformer) tuples and ends with "clean".
  2. The resulting source passes `aether check` (exit 0, no
     diagnostics).
"""
from __future__ import annotations
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)


DEMO_DIR = os.path.join(ROOT, "demos", "payment_workflow")
BROKEN = os.path.join(DEMO_DIR, "broken.aeth")
DRIVER = os.path.join(DEMO_DIR, "fix_loop.py")


def test_fix_loop_resolves_broken_candidate():
    r = subprocess.run(
        [sys.executable, "-B", DRIVER, BROKEN, "--quiet"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r
    transcript_path = BROKEN.replace(".aeth", ".transcript.json")
    with open(transcript_path) as f:
        transcript = json.load(f)
    # Expect: 2 fix entries + 1 clean entry
    fixes = [t for t in transcript if "diagnostic" in t]
    assert len(fixes) == 2, transcript
    codes = [t["diagnostic"]["code"] for t in fixes]
    assert "E0801" in codes, codes
    assert "E0701" in codes, codes
    # Last entry is the "clean" marker
    assert transcript[-1].get("status") == "clean", transcript[-1]
    print(f"F.2 fix-loop: {len(fixes)} mechanical fixes, final state clean")


def test_fixed_source_passes_full_check():
    fixed_path = BROKEN.replace(".aeth", ".fixed.aeth")
    r = subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", "check", fixed_path],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r
    print("F.2 fixed source: passes aether check with exit 0")


def test_payment_workflow_aether_runs_cleanly():
    """F.1 — the architecturally-correct reference must check + run."""
    src = os.path.join(DEMO_DIR, "aether", "main.aeth")
    chk = subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", "check", src],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert chk.returncode == 0, chk
    run = subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", "run", src],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert run.returncode == 0, run
    out = run.stdout
    assert "DONE rcpt-8500-USD" in out, out
    print("F.1 payment workflow Aether: check + run both clean")


def test_payment_workflow_python_runs_cleanly():
    src = os.path.join(DEMO_DIR, "python", "main.py")
    r = subprocess.run([sys.executable, "-B", src],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r
    assert "DONE rcpt-8500-USD" in r.stdout, r.stdout
    print("F.1 payment workflow Python: runs cleanly with matching output")


if __name__ == "__main__":
    test_payment_workflow_aether_runs_cleanly()
    test_payment_workflow_python_runs_cleanly()
    test_fix_loop_resolves_broken_candidate()
    test_fixed_source_passes_full_check()
    print("F ALL DEMO TESTS PASS")
