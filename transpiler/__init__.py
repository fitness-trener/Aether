"""Source root for the Aether toolchain. NOT part of the distribution.

The library is `aether`, and that is what the wheel ships:
`[tool.setuptools] package-dir = {"" = "transpiler"}` remaps this
directory to the package root, so an installed user writes
`from aether import sdk` — the same spelling every file in this repo
uses. (It used to ship `transpiler`, which made that documented import
fail for everyone who installed rather than cloned: BUGS.md BUG-009.)

This file stays because the CHECKOUT needs it: roughly twenty call sites
across `tests/`, `bench/`, `demos/`, `scripts/` and `playground/` invoke
the CLI as `python -B -m transpiler.aether.cli` from the repo root,
without installing anything. Those keep working; the module simply never
reaches site-packages.
"""
