"""H.A.1.e — ALSP corpus regression.

Discovers every .aeth in `tests/alsp_corpus/`, pairs each with its
`<name>.expected.json`, and asserts:

  (a) the diagnostic codes from `sdk.check` (plus `sdk.run` for runtime
      codes that only fire at execution) match the expected list, in
      order;
  (b) for each diagnostic, walking `compute_patch_target(ast, diag)` to
      the leaf via `resolve_path_kind` returns the expected
      `patch_target_kind` string (None for lex/parse errors);
  (c) clean programs (empty diagnostics) additionally pass `sdk.run`.

Exits 0 on full pass; prints a clear failure summary and exits 1
otherwise. Mirrors the style of `tests/test_regressions.py`.

Why some codes are read from `sdk.run`
--------------------------------------
The static `check` pass surfaces E0801 / E0701 / E0201 (and the lex
codes when the SDK reraises). The contract codes E0301 (requires),
E0302 (refinement boundary), E0304 (ensures), E0305 (stdlib
precondition) only fire at run time. The corpus test transparently
falls back to `sdk.run` for those, since the patch_target pass operates
on the parsed AST either way.
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether import sdk                                       # noqa: E402
from aether.diagnostics import AetherError                   # noqa: E402
from aether.passes.patch_target import (                     # noqa: E402
    compute_patch_target, resolve_path_kind,
)


CORPUS_DIR = os.path.join(HERE, "alsp_corpus")


def _gather_diagnostics(src: str):
    """Return (diagnostics, ast). Reraises nothing — catches AetherError
    from the lexer/parser and falls through to sdk.run when sdk.check
    returns clean, so runtime codes can be observed."""
    try:
        result = sdk.check(src, filename="<corpus>")
        diags = list(result.diagnostics)
        ast = result.ast
    except AetherError as e:
        diags = list(e.diagnostics)
        ast = None
    if not diags:
        try:
            rr = sdk.run(src, deterministic=True, filename="<corpus>")
        except Exception:
            rr = None
        if rr is not None and rr.diagnostic is not None:
            diags = [rr.diagnostic]
            if ast is None:
                try:
                    ast = sdk.parse(src, filename="<corpus>").ast
                except Exception:
                    ast = None
    return diags, ast


def _load_expected(aeth_path: str) -> dict:
    json_path = aeth_path.replace(".aeth", ".expected.json")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_one(program: str) -> list:
    """Return a list of failure strings for `program`. Empty list = pass."""
    failures = []
    with open(program, "r", encoding="utf-8") as f:
        src = f.read()
    exp = _load_expected(program)
    expected_diags = exp.get("diagnostics", []) or []

    diags, ast = _gather_diagnostics(src)

    # (a) codes match in order
    actual_codes = [d.code for d in diags]
    expected_codes = [e["code"] for e in expected_diags]
    if actual_codes != expected_codes:
        failures.append(
            f"  codes mismatch: actual={actual_codes} expected={expected_codes}"
        )
        # Don't try to compare patch_target_kind when the lengths differ.
        return failures

    # (b) each patch_target_kind matches
    for i, (diag, exp_entry) in enumerate(zip(diags, expected_diags)):
        path = compute_patch_target(ast, diag)
        kind = resolve_path_kind(ast, path)
        want_kind = exp_entry.get("patch_target_kind")
        if kind != want_kind:
            failures.append(
                f"  diag #{i} {diag.code}: patch_target_kind={kind!r} "
                f"expected={want_kind!r} (path={path})"
            )

    # (c) clean programs must also `run` successfully
    if not expected_diags:
        try:
            rr = sdk.run(src, deterministic=True, filename="<corpus>")
        except Exception as e:
            failures.append(f"  clean program failed sdk.run: {e!r}")
            return failures
        if not rr.ok:
            failures.append(
                f"  clean program sdk.run not ok (exit={rr.exit_code}, "
                f"stderr={rr.stderr[:120]!r})"
            )
    return failures


def main() -> int:
    if not os.path.isdir(CORPUS_DIR):
        print(f"[fail] corpus dir missing: {CORPUS_DIR}", file=sys.stderr)
        return 1
    programs = sorted(
        os.path.join(CORPUS_DIR, f)
        for f in os.listdir(CORPUS_DIR)
        if f.endswith(".aeth")
    )
    if not programs:
        print(f"[fail] no .aeth files in {CORPUS_DIR}", file=sys.stderr)
        return 1

    total = len(programs)
    passed = 0
    failures = {}
    for p in programs:
        fs = _check_one(p)
        if fs:
            failures[os.path.basename(p)] = fs
        else:
            passed += 1

    print(f"H.A.1 alsp_corpus: {passed}/{total}")
    if failures:
        print(f"--- {len(failures)} failure(s) ---")
        for fn, fs in failures.items():
            print(f"FAIL {fn}")
            for line in fs:
                print(line)
        return 1
    print("H.A.1 alsp_corpus: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
