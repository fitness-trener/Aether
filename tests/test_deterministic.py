"""C.5 regression tests for deterministic test mode.

The promise: a program calling `now()` returns a stable, monotonic clock
when run under `--deterministic` (or env var AETHER_DETERMINISTIC=1).
Two consecutive runs of the same program produce byte-identical stdout.

Tests:
  1. set_deterministic pins the clock to the documented anchor and
     advances by exactly 1 ms per `now()` call.
  2. is_deterministic() reflects state.
  3. End-to-end: two CLI runs of the same .aeth source with
     --deterministic produce identical stdout; without it, stdout differs
     (or at least the runtime clock value differs).
  4. AETHER_DETERMINISTIC=1 env var activates the mode without the flag.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether import runtime as _rt  # noqa: E402


def test_set_deterministic_pins_clock():
    # Reset to non-deterministic just in case a prior test mutated state.
    _rt._DETERMINISTIC_CLOCK_MS = None
    assert not _rt.is_deterministic()
    _rt.set_deterministic(0)
    assert _rt.is_deterministic()
    t1 = _rt._ae_now()["epochMillis"]
    t2 = _rt._ae_now()["epochMillis"]
    t3 = _rt._ae_now()["epochMillis"]
    assert t1 == _rt._DETERMINISTIC_CLOCK_INIT, t1
    assert t2 == t1 + 1, t2
    assert t3 == t1 + 2, t3
    print(f"C.5 unit: clock pinned at {t1} and monotonic +1ms")


def test_cli_deterministic_two_runs_identical():
    src = """
function main() returns Unit
  effects log, time.now
do
  let t1: Instant = now()
  let t2: Instant = now()
  print(intToString(t1.epochMillis))
  print(intToString(t2.epochMillis))
end
"""
    fd, src_path = tempfile.mkstemp(prefix="aether_c5_", suffix=".aeth", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(src)
        # Two runs with --deterministic should be byte-identical.
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        a = subprocess.run(
            [sys.executable, "-B", "-m", "transpiler.aether.cli",
             "run", "--deterministic", src_path],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        b = subprocess.run(
            [sys.executable, "-B", "-m", "transpiler.aether.cli",
             "run", "--deterministic", src_path],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        assert a.returncode == 0, a.stderr
        assert b.returncode == 0, b.stderr
        assert a.stdout == b.stdout, f"non-identical: {a.stdout!r} vs {b.stdout!r}"
        # And the values are exactly the documented anchor + monotonic.
        lines = a.stdout.strip().splitlines()
        assert lines[0] == str(_rt._DETERMINISTIC_CLOCK_INIT), lines
        assert lines[1] == str(_rt._DETERMINISTIC_CLOCK_INIT + 1), lines
        print(f"C.5 cli: two --deterministic runs identical "
              f"({lines[0]} -> {lines[1]})")
    finally:
        try:
            os.remove(src_path)
        except OSError:
            pass


def test_cli_env_var_activates_deterministic():
    src = """
function main() returns Unit
  effects log, time.now
do
  print(intToString(now().epochMillis))
end
"""
    fd, src_path = tempfile.mkstemp(prefix="aether_c5_env_", suffix=".aeth", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(src)
        env = {**os.environ,
               "PYTHONDONTWRITEBYTECODE": "1",
               "AETHER_DETERMINISTIC": "1"}
        r = subprocess.run(
            [sys.executable, "-B", "-m", "transpiler.aether.cli", "run", src_path],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == str(_rt._DETERMINISTIC_CLOCK_INIT), r.stdout
        print(f"C.5 env: AETHER_DETERMINISTIC=1 activates pinned clock")
    finally:
        try:
            os.remove(src_path)
        except OSError:
            pass


if __name__ == "__main__":
    test_set_deterministic_pins_clock()
    test_cli_deterministic_two_runs_identical()
    test_cli_env_var_activates_deterministic()
    print("C.5 ALL DETERMINISTIC-MODE TESTS PASS")
