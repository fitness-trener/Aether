# Calling Aether from Python (`aether pack`)

`aether pack` turns an `.aeth` file into an importable Python package whose
public functions keep their Aether contracts at the call boundary — a
contract-hardened drop-in for the equivalent hand-written Python.

    aether pack pricing.aeth --out dist
    # -> dist/pricing/__init__.py

    import sys; sys.path.insert(0, "dist")
    import pricing
    pricing.applyDiscount(200, 25)    # -> 150
    pricing.applyDiscount(200, 150)   # raises AetherError [E0302]:
                                      # 150 fails refinement Percentage

What holds at the boundary:

- `requires` clauses -> AetherError E0301 on violation
- refinement types on parameters -> AetherError E0302
- `ensures` clauses -> AetherError E0304 (implementation bug surfaced)
- effect frames run as in `aether run` (strict mode off by default)

Requirements: the `aether-lang` package must be importable
(`pip install -e .` from the repo, or the repo root on `sys.path`).
The generated package imports its runtime from `transpiler.aether.runtime`
(falling back to `aether.runtime`).

Catching violations: import `AetherError` from the SAME path the package
resolved its runtime through. If both `transpiler.aether` and `aether` are
importable in your environment they are distinct module objects with
distinct exception classes; when unsure, catch both:

    try:
        from transpiler.aether.diagnostics import AetherError
    except ImportError:
        from aether.diagnostics import AetherError

Function name mapping: Aether `valid?` / `save!` become Python `valid_q` /
`save_e` (Python identifiers cannot contain `?` or `!`).

Limitations (v1, deliberate):
- one package per entry file (multi-file imports are resolved and inlined)
- no type stubs (.pyi) yet
- the reverse direction (Aether calling Python) does not exist
