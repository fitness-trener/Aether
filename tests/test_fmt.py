"""C.4 regression tests for `aether fmt`.

Three contracts:
  1. `fmt --check` returns exit 0 on canonically-formatted source and
     exit 1 on unformatted source.
  2. `fmt` (no flags) writes canonical Aether source to stdout that
     parses to the same AST.
  3. `fmt --write` overwrites the file in place; running it twice in a
     row leaves the file unchanged (idempotent fixed point).
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse  # noqa: E402
from aether.pretty import asts_equal_ignoring_pos  # noqa: E402


UNFORMATTED = """function    main()    returns Unit
       effects log
   do
print(   "hello"   )
end
"""

CANONICAL = """function main() returns Unit
  effects log
do
  print("hello")
end
"""


def _run(*args):
    return subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_fmt_check_unformatted_exits_1():
    fd, path = tempfile.mkstemp(prefix="aether_c4_check_", suffix=".aeth", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(UNFORMATTED)
        r = _run("fmt", "--check", path)
        assert r.returncode == 1, r
        assert "would reformat" in r.stderr, r.stderr
        print("C.4 --check: exits 1 + 'would reformat' on stderr")
    finally:
        try: os.remove(path)
        except OSError: pass


def test_fmt_check_canonical_exits_0():
    fd, path = tempfile.mkstemp(prefix="aether_c4_canon_", suffix=".aeth", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(CANONICAL)
        r = _run("fmt", "--check", path)
        assert r.returncode == 0, r
        print("C.4 --check: exits 0 on already-canonical source")
    finally:
        try: os.remove(path)
        except OSError: pass


def test_fmt_default_writes_canonical_to_stdout():
    fd, path = tempfile.mkstemp(prefix="aether_c4_stdout_", suffix=".aeth", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(UNFORMATTED)
        r = _run("fmt", path)
        assert r.returncode == 0, r
        # The stdout source must parse to the same AST as the original.
        a = parse(UNFORMATTED, "<orig>")
        b = parse(r.stdout, "<fmt>")
        assert asts_equal_ignoring_pos(a, b)
        print("C.4 fmt: stdout output parses to same AST as input")
    finally:
        try: os.remove(path)
        except OSError: pass


def test_fmt_write_is_idempotent():
    fd, path = tempfile.mkstemp(prefix="aether_c4_write_", suffix=".aeth", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(UNFORMATTED)
        # First write — file must change.
        r = _run("fmt", "--write", path)
        assert r.returncode == 0, r
        after1 = open(path).read()
        assert after1 != UNFORMATTED, "fmt --write didn't change unformatted source"
        # Second write — file must NOT change (canonical fixed point).
        r = _run("fmt", "--write", path)
        assert r.returncode == 0, r
        after2 = open(path).read()
        assert after2 == after1, "fmt --write is not idempotent"
        # And `--check` agrees we're formatted now.
        r = _run("fmt", "--check", path)
        assert r.returncode == 0, r
        print("C.4 --write: in-place rewrite reaches canonical fixed point")
    finally:
        try: os.remove(path)
        except OSError: pass


if __name__ == "__main__":
    test_fmt_check_unformatted_exits_1()
    test_fmt_check_canonical_exits_0()
    test_fmt_default_writes_canonical_to_stdout()
    test_fmt_write_is_idempotent()
    print("C.4 ALL FORMATTER TESTS PASS")
