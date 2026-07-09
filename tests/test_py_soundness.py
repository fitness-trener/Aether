"""P0 soundness regressions for the Python capability frontend.

These lock in the two defects fixed in Phase 0:

  * trap_02 (pprint): `pprint.pprint` writes to stdout. It used to be silently
    certified PROVEN_CLEAN because `pprint` sat in PURE_MODULES. It must now be
    VIOLATION or UNPROVABLE — NEVER PROVEN_CLEAN — at every granularity.
  * trap_04 (pure-method override): `AuditLog.append()` opens a file and writes
    to disk. Pragmatic mode used to certify the caller `record()` PROVEN_CLEAN by
    trusting the method NAME `.append`. Pragmatic mode is deleted; no function in
    this module that reaches the disk write may be PROVEN_CLEAN.

Soundness contract: a module/function with a real capability is NEVER reported
PROVEN_CLEAN. When the engine cannot resolve the surface it must degrade to
UNPROVABLE, never to a silent clean.

Run: python3 tests/test_py_soundness.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from tools.py_surface import build_surface_py          # noqa: E402
from tools.py_frontend import PURE_MODULES, CAP_BY_QUALIFIED, mapping_table  # noqa: E402

FORBIDDEN = "PROVEN_CLEAN"


def _all_states(surface):
    """Every state in the surface: module roll-ups + each function."""
    states = []
    for m in surface["modules"]:
        states.append(("module:" + m["module"], m["state"]))
        for f in m["functions"]:
            states.append(("fn:" + f["name"], f["state"]))
    for f in surface.get("ungoverned", {}).get("functions", []):
        states.append(("free:" + f["name"], f["state"]))
    return states


def _check_never_clean(name, source):
    surface = build_surface_py(source)
    states = _all_states(surface)
    clean = [n for n, s in states if s == FORBIDDEN]
    # The capability-carrying function specifically must not be clean.
    return states, clean


def test_trap02_pprint_never_clean():
    src = "import pprint\n\ndef dump_state(state):\n    pprint.pprint(state)\n    return len(state)\n"
    states, clean = _check_never_clean("trap_02", src)
    # dump_state carries a log effect; it must not be PROVEN_CLEAN.
    dump = dict(states).get("fn:dump_state") or dict(states).get("free:dump_state")
    assert dump != FORBIDDEN, f"trap_02 dump_state was {dump} (silent false negative!)"
    assert dump in ("VIOLATION", "UNPROVABLE"), f"unexpected state {dump}"
    print(f"  [ok] trap_02 dump_state = {dump} (not PROVEN_CLEAN)")


def test_trap04_disk_append_never_clean():
    src = ('class AuditLog:\n'
           '    def __init__(self, path):\n'
           '        self.path = path\n\n'
           '    def append(self, entry):\n'
           '        with open(self.path, "a") as fh:\n'
           '            fh.write(entry + "\\n")\n\n'
           'def record(audit, event):\n'
           '    audit.append(event)\n')
    states, clean = _check_never_clean("trap_04", src)
    d = dict(states)
    appended = d.get("fn:AuditLog.append")
    record = d.get("fn:record") or d.get("free:record")
    assert appended == "VIOLATION", f"AuditLog.append must be VIOLATION (fs), got {appended}"
    # record() reaches disk via .append on an untyped object -> must NOT be clean.
    assert record != FORBIDDEN, f"trap_04 record() was {record} (pragmatic false-clean!)"
    assert record == "UNPROVABLE", f"record() should degrade to UNPROVABLE, got {record}"
    print(f"  [ok] trap_04 append={appended}, record={record} (no false-clean)")


def test_pure_modules_have_no_io_offenders():
    for offender in ("pprint", "warnings", "codecs", "dataclass"):
        assert offender not in PURE_MODULES, f"{offender} must not be in PURE_MODULES"
    # the I/O verbs are now positively mapped
    assert CAP_BY_QUALIFIED.get("pprint.pprint") == "log"
    assert CAP_BY_QUALIFIED.get("warnings.warn") == "log"
    assert CAP_BY_QUALIFIED.get("codecs.open") == "fs"
    # every remaining pure module carries a citation
    cites = mapping_table()["pure_module_citations"]
    missing = [m for m in PURE_MODULES if not cites.get(m)]
    assert not missing, f"pure modules without purity citation: {missing}"
    print(f"  [ok] PURE_MODULES audited: {len(PURE_MODULES)} entries, all cited, no I/O offenders")


def test_pragmatic_mode_is_gone():
    import tools.py_frontend as pf
    assert not hasattr(pf, "PURE_METHODS"), "PURE_METHODS allowlist must be deleted"
    assert not hasattr(pf, "_FnVisitor") or "strict" not in pf._FnVisitor.__init__.__code__.co_varnames, \
        "_FnVisitor must not take a strict flag"
    import inspect
    assert "strict" not in inspect.signature(pf.py_to_ir).parameters, "py_to_ir must not take strict"
    print("  [ok] pragmatic mode fully removed (no PURE_METHODS, no strict flag)")


def main():
    tests = [
        test_trap02_pprint_never_clean,
        test_trap04_disk_append_never_clean,
        test_pure_modules_have_no_io_offenders,
        test_pragmatic_mode_is_gone,
    ]
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failures += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\n{len(tests)-failures}/{len(tests)} soundness regressions passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
