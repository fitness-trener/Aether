"""Which diagnostic codes does this tree actually construct?

One scanner, one answer. `tests/test_diagnostic_catalog.py` asks it to
check every constructed code is documented in `grammar/diagnostics.md`;
`tests/test_ratchet.py` asks it for the floor that stops a code being
removed. Both used to carry their own copy of the same regex over
different roots, while the ratchet's docstring claimed they were "the
same enumeration" — they were not, and the catalog test's promise that
"every diagnostic code the toolchain can emit is documented" was false
and green. See `docs/adr/0002-diagnostics-md-stays-hand-written.md`.

Three construction FORMS exist in the tree, and the old regex saw only
the first two:

  1. a keyword argument or a local assignment — `Diagnostic(code=...)`,
     and the `code` local that runtime.py's requires/ensures split
     assigns before passing it on (E0301 vs E0304);
  2. a dict-shaped diagnostic — `{"code": ..., "message": ...}` — used by
     the SDK, `bench/harness.py`, and `tools/py_surface.py`;
  3. the code as the FIRST POSITIONAL argument to a constructing helper —
     `lexer.py`'s `_err("E01xx", msg, pos)` and
     `passes/imports.py`'s `_diag("E07xx", msg, pos)`.

Form 3 is why E0101–E0106, E0705 and E0706 were invisible, and why
E0705/E0706 were live, tested, and documented nowhere.

**Residual, per ADR-0002.** A code assembled at runtime — an f-string, a
module constant, a lookup — stays invisible to this scanner too. It is
text matching, not reachability analysis. Do NOT describe the catalog as
provably complete; the honest claim is "every code constructed in one of
the three literal forms above is documented". ADR-0002 records the
stronger fix (a `CATALOG` plus a `diag(code, pos, **fmt)` constructor,
which makes an undocumented code unconstructible) and the condition for
reopening it: when diagnostic prose gets reused.

Examples above use `E01xx`/`E07xx` placeholders on purpose — a real code
in this docstring would match form 3 and count itself. For the same
reason the form-coverage self-check lives in
`tests/test_diagnostic_catalog.py`, which this scanner does not walk.
"""

from __future__ import annotations
import os
import re
from typing import Iterable, Set

# `tools/` is scanned as well as `transpiler/` and `bench/`: it holds
# `scan.py` and `py_surface.py`, which construct diagnostics a user sees.
# It contributes no code the transpiler does not already construct today —
# it is here so that the first one it adds is not invisible.
ROOTS = ("transpiler", "tools", "bench")

_FORMS = (
    re.compile(r'code\s*=\s*"(E\d{4})"'),
    re.compile(r'"code"\s*:\s*"(E\d{4})"'),
    re.compile(r'\b\w*(?:err|diag)\w*\(\s*"(E\d{4})"', re.I),
)


def constructed_codes(root: str, subdirs: Iterable[str] = ROOTS) -> Set[str]:
    """Every diagnostic code constructed under `root`/`subdirs`, in any of
    the three forms above. `root` is the repo root."""
    codes: Set[str] = set()
    for sub in subdirs:
        for dirpath, _, files in os.walk(os.path.join(root, sub)):
            if "__pycache__" in dirpath:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                    text = f.read()
                for form in _FORMS:
                    codes.update(form.findall(text))
    return codes


def codes_in(text: str) -> Set[str]:
    """Codes constructed in one blob of source. Exposed so the catalog
    test can pin form coverage without writing real codes into a file
    this scanner walks."""
    return {c for form in _FORMS for c in form.findall(text)}
