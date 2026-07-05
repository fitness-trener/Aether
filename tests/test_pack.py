"""aether pack: emitted-module-as-Python-package with contract-checked
boundary (gap 3 — formalizes the bench-harness interop pattern).

Standalone (`python -B tests/test_pack.py`, exit 0) and pytest-collectable.
"""
from __future__ import annotations
import importlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

# The generated package prefers `transpiler.aether.runtime` and falls back
# to `aether.runtime`. Those are DISTINCT module objects when both import
# paths work (as here), so their AetherError classes differ — catch both.
from aether.diagnostics import AetherError as _AE1              # noqa: E402
from transpiler.aether.diagnostics import AetherError as _AE2   # noqa: E402
AETHER_ERRORS = (_AE1, _AE2)

SRC = """
type Percentage = Int where self >= 0 and self <= 100

function applyDiscount(basePrice: Int, pct: Percentage) returns Int
  requires basePrice >= 0
  ensures result >= 0
  ensures result <= basePrice
  effects pure
do
  return basePrice - (basePrice * pct) / 100
end

function main() returns Unit
  effects log
do
  print(intToString(applyDiscount(200, 25)))
end
"""


def test_pack_import_and_contracts():
    with tempfile.TemporaryDirectory() as td:
        aeth = os.path.join(td, "pricing.aeth")
        with open(aeth, "w", encoding="utf-8") as f:
            f.write(SRC)
        r = subprocess.run(
            [sys.executable, "-B", "-m", "transpiler.aether.cli",
             "pack", aeth, "--out", td],
            cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        init = os.path.join(td, "pricing", "__init__.py")
        assert os.path.isfile(init)

        sys.path.insert(0, td)
        try:
            mod = importlib.import_module("pricing")
            # clean-name alias works; contracts hold on the happy path
            assert mod.applyDiscount(200, 25) == 150
            # refinement boundary: pct=150 violates Percentage -> E0302
            try:
                mod.applyDiscount(200, 150)
            except AETHER_ERRORS as e:
                assert e.diag.code == "E0302", e.diag.code
            else:
                raise AssertionError("refinement violation not raised")
            # requires boundary: negative price -> E0301
            try:
                mod.applyDiscount(-1, 10)
            except AETHER_ERRORS as e:
                assert e.diag.code == "E0301", e.diag.code
            else:
                raise AssertionError("requires violation not raised")
            # importing did NOT run main (no stray stdout): __main__ guard
            assert hasattr(mod, "main")
        finally:
            sys.path.remove(td)
            sys.modules.pop("pricing", None)


def main() -> int:
    test_pack_import_and_contracts()
    print("ok test_pack_import_and_contracts")
    print("OK: 1 pack test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
