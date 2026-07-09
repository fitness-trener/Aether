"""Monotonic ratchet — Aether may only improve.

The self-teaching loop edits the compiler autonomously. This gate makes the
improvement one-directional:

  1. Detector count never drops. The number of distinct diagnostic codes
     the transpiler emits, and the number of detector passes folded into
     the CLI gate, must meet or exceed a committed FLOOR
     (`ratchet_baseline.json`). Removing a detector — even if its code,
     doc, and test are all deleted together so the rest of the suite stays
     green — drops the count below the floor and turns THIS gate red.

  2. Gains get locked. When an iteration adds a detector, this test prints
     a reminder to raise the floor in the same commit, so the addition can
     never be silently removed later.

  3. Fixed bugs stay fixed. Every `[FIXED ...]` entry in BUGS.md must name
     a regression test that still exists, so a repaired bug cannot quietly
     reappear.

Run: python3 tests/test_ratchet.py   (exit 0 = pass)
"""
from __future__ import annotations
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_REL = "tests/ratchet_baseline.json"


def _emitted_codes() -> set:
    """Distinct Exxxx codes the transpiler emits (same enumeration as the
    D.2 catalog test)."""
    codes = set()
    tdir = os.path.join(ROOT, "transpiler")
    for dp, _, files in os.walk(tdir):
        if "__pycache__" in dp:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(dp, fn), encoding="utf-8") as f:
                text = f.read()
            for m in re.finditer(r'(?:code="|"code":\s*")(E\d+)"', text):
                codes.add(m.group(1))
    return codes


def _gated_detectors() -> set:
    """Detector check_* functions folded into the CLI check pipeline."""
    with open(os.path.join(ROOT, "transpiler", "aether", "cli.py"),
              encoding="utf-8") as f:
        text = f.read()
    return set(re.findall(r'(check_[a-z_]+)\(ast\)', text))


def _baseline() -> dict:
    with open(os.path.join(ROOT, "tests", "ratchet_baseline.json"),
              encoding="utf-8") as f:
        return json.load(f)


def test_detector_count_ratchet():
    base = _baseline()
    codes = len(_emitted_codes())
    dets = len(_gated_detectors())
    floor_c = base["min_emitted_codes"]
    floor_d = base["min_gated_detectors"]

    assert codes >= floor_c, (
        f"RATCHET REGRESSION: emitted diagnostic codes dropped to {codes}, "
        f"below the floor {floor_c}. A detector was removed — the ratchet "
        f"forbids it. Restore it or explain in BUGS.md why it is unsound.")
    assert dets >= floor_d, (
        f"RATCHET REGRESSION: gated detector passes dropped to {dets}, below "
        f"the floor {floor_d}. Restore the removed check_* pass.")

    if codes > floor_c or dets > floor_d:
        print(f"  NOTE: ratchet gain not locked — raise ratchet_baseline.json "
              f"to min_emitted_codes={codes}, min_gated_detectors={dets} in "
              f"this commit so the gain is permanent.")
    print(f"ratchet: {codes} codes >= floor {floor_c}, "
          f"{dets} detectors >= floor {floor_d}")


def _detector_codes() -> list:
    """Documented codes the self-teaching loop owns: the security range
    (E07xx) and the static-semantic range (E02xx, excluding the parse code
    E0201). These are the codes the ratchet's legitimacy guard protects."""
    docs = open(os.path.join(ROOT, "grammar", "diagnostics.md"),
                encoding="utf-8").read()
    documented = set(re.findall(r'\*\*(E\d{4})\*\*', docs))
    return sorted(c for c in documented
                  if c.startswith("E07") or (c.startswith("E02") and c != "E0201"))


def _tests_text() -> str:
    out = []
    for f in glob.glob(os.path.join(ROOT, "tests", "**", "*.py"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            out.append(fh.read())
    return "\n".join(out)


def test_detectors_legitimately_checked():
    """An improvement must be REAL, not a bumped number. Every protected
    detector code must be (1) actually emitted by the transpiler, and
    (2) asserted by a test that proves it fires. This blocks inflating the
    ratchet with a documented-but-dead `code=` string or a phantom
    detector: to raise the count you must ship a wired, tested detector."""
    detector = _detector_codes()
    emitted = _emitted_codes()
    tests_text = _tests_text()

    not_emitted = [c for c in detector if c not in emitted]
    assert not not_emitted, (
        "LEGITIMACY: these documented detector codes are not emitted by any "
        "transpiler pass (a doc row without a real detector):\n  "
        + ", ".join(not_emitted))

    not_tested = [c for c in detector if c not in tests_text]
    assert not not_tested, (
        "LEGITIMACY: these detector codes have no test asserting they fire "
        "(an untested/unverifiable detector cannot count toward the "
        "ratchet — add a test that triggers it):\n  " + ", ".join(not_tested))

    print(f"legitimacy: all {len(detector)} detector codes are emitted AND "
          f"proven by a test")


def _git_show(ref: str) -> str | None:
    try:
        r = subprocess.run(["git", "show", ref], cwd=ROOT,
                           capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    except (FileNotFoundError, OSError):
        return None


def test_baseline_never_lowered():
    """The one edit the count-floor can't catch itself: lowering a number
    in the baseline. Compare the working-tree baseline against the last
    COMMITTED baseline; every number must be >= its committed value. This
    makes the ratchet monotonic across git history — you can raise the
    floor, never lower it. Skips cleanly if there is no committed baseline
    yet (first commit) or git is unavailable."""
    committed = _git_show(f"HEAD:{BASELINE_REL}")
    if committed is None:
        print("ratchet: no committed baseline to compare (first commit / no git)")
        return
    prev = json.loads(committed)
    cur = _baseline()
    lowered = [k for k in ("min_emitted_codes", "min_gated_detectors")
               if k in prev and cur.get(k, 0) < prev[k]]
    assert not lowered, (
        "RATCHET REGRESSION: the baseline was LOWERED for "
        + ", ".join(f"{k} ({prev[k]} -> {cur[k]})" for k in lowered)
        + ". The ratchet is one-directional — a baseline number may only be "
          "raised. Restore it; Aether does not lose ground.")
    print("ratchet: baseline >= last committed (never lowered)")


def test_fixed_bugs_stay_fixed():
    """Every BUGS.md [FIXED] entry must reference an existing regression
    test, so a repaired bug cannot silently reappear."""
    bugs_path = os.path.join(ROOT, "BUGS.md")
    if not os.path.isfile(bugs_path):
        print("ratchet: no BUGS.md — nothing to enforce")
        return
    with open(bugs_path, encoding="utf-8") as f:
        text = f.read()
    # A real FIXED marker carries a commit hash: `[FIXED 0f356e1]`. The
    # `[FIXED <commit>]` placeholder in the Fix-protocol instructions is not
    # a real entry and is deliberately not matched.
    marker = re.compile(r'\[FIXED\s+[0-9a-f]{6,}\]')
    fixed = marker.findall(text)
    missing = []
    for block in re.split(r'(?=^#{1,3}\s)', text, flags=re.M):
        # The "Fix protocol" section is documentation (it contains a format
        # example), not a real entry — skip it.
        if block.lstrip().lower().startswith("## fix protocol"):
            continue
        if not marker.search(block):
            continue
        m = re.search(r'test:\s*(\S+)', block)
        if not m:
            missing.append(block.strip().splitlines()[0] if block.strip() else "?")
            continue
        ref = m.group(1)
        # a file path under the repo, or a pytest-style path::marker
        path = ref.split("::", 1)[0]
        if not os.path.isfile(os.path.join(ROOT, path)):
            missing.append(f"{ref} (missing file)")
    assert not missing, (
        "RATCHET: these [FIXED] BUGS.md entries lack an existing regression "
        "test (add `test: tests/....py` to each):\n  " + "\n  ".join(missing))
    print(f"ratchet: {len(fixed)} FIXED bug(s), all with a live regression test")


if __name__ == "__main__":
    test_detector_count_ratchet()
    test_detectors_legitimately_checked()
    test_baseline_never_lowered()
    test_fixed_bugs_stay_fixed()
    print("RATCHET: Aether only moves forward")
