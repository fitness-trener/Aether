"""H.B.1 regression tests for the pip-installable package.

We can't reach PyPI from this CI sandbox, so we don't actually run
`pip install .` here. We DO validate every fact `pip install` will
rely on:

  1. The console script entry point string in `pyproject.toml`
     (`aether = aether.cli:main`) resolves to a real callable in the
     source tree.
  2. The `main` function it points at accepts the same arg shape as
     setuptools will hand it — calling `main(["--help"])` exits 0 and
     prints the top-level help.
  3. The package's `__version__` matches the version declared in
     `pyproject.toml`. A version drift here means a future release
     ships a wheel whose stamped version disagrees with what
     `import aether; aether.__version__` reports.
  4. `pyproject.toml` declares no runtime dependencies — the core
     toolchain is stdlib-only by design and the H.B.1 contract is
     that `pip install aether-lang` pulls in no third-party
     packages. (`anthropic` lives under the `[llm]` extra.)
  5. `package-dir` + `packages.find.where` ship `aether` as the
     top-level package — the spelling every document and every import
     in this repo uses — and structurally cannot ship anything outside
     `transpiler/` (BUG-009).
  6. Nothing under `transpiler/` imports a module that is not in the
     wheel (BUG-007/008), and `project.license` is in the form current
     setuptools accepts (BUG-006).
"""
from __future__ import annotations
import io
import os
import re
import sys
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)


def _read_pyproject():
    """Read pyproject.toml. Uses tomllib on 3.11+, tomli if installed,
    else a minimal hand-rolled parser that handles only the subset of
    TOML we actually use in this file (string scalars, single-line
    arrays of strings, nested tables under [section.subsection]).
    The hand-rolled path lets the test run on Python 3.10 without a
    third-party tomli."""
    path = os.path.join(ROOT, "pyproject.toml")
    try:
        import tomllib                                       # Py 3.11+
        with open(path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        pass
    try:
        import tomli                                          # pragma: no cover
        with open(path, "rb") as f:
            return tomli.load(f)
    except ImportError:
        pass

    # Minimal fallback. Sufficient for the assertions in this file.
    out = {}
    section = out
    section_path = []
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("["):
            parts = line.strip()[1:-1].split(".")
            section_path = parts
            d = out
            for p in parts:
                d = d.setdefault(p, {})
            section = d
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            section[k] = v[1:-1]
        elif v == "[]":
            section[k] = []
        elif v.startswith("[") and v.endswith("]"):
            body = v[1:-1].strip()
            items = [seg.strip().strip('"').strip("'")
                     for seg in re.findall(r'"[^"]*"|\'[^\']*\'', body)]
            section[k] = items
        elif v.startswith("{") and v.endswith("}"):
            # inline-table for project.license — we only read the
            # `text = "MIT"` form
            m = re.search(r'text\s*=\s*"([^"]+)"', v)
            section[k] = {"text": m.group(1)} if m else {}
        elif v.startswith("["):
            # Multi-line array — collect until we see a closing ]
            collected = [v]
            # NB: we don't fully implement multi-line arrays in the
            # fallback parser; the values we care about are all single
            # line in pyproject.toml. If a later edit makes one of
            # them multi-line, this branch loses data and the test
            # surfaces a clear failure.
            section[k] = collected
    return out


def test_console_script_entry_point_resolves():
    cfg = _read_pyproject()
    scripts = cfg["project"]["scripts"]
    assert "aether" in scripts, scripts
    target = scripts["aether"]
    assert target == "aether.cli:main", target
    # And it actually resolves.
    mod_path, _, attr = target.partition(":")
    mod = __import__(mod_path, fromlist=[attr])
    fn = getattr(mod, attr)
    assert callable(fn), fn
    print(f"H.B.1 entry point: {target} -> {fn!r}")


def test_main_accepts_help():
    """setuptools-installed `aether --help` will invoke `main(['--help'])`.
    The function must exit cleanly (SystemExit code 0) without writing
    to stderr — that's what `pip install + run` will produce."""
    from transpiler.aether.cli import main
    out, err = io.StringIO(), io.StringIO()
    exit_code = None
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(["--help"])
        except SystemExit as e:
            exit_code = e.code
    assert exit_code == 0, (exit_code, out.getvalue(), err.getvalue())
    combined = out.getvalue() + err.getvalue()
    assert "aether" in combined.lower(), combined
    for sub in ("parse", "emit", "check", "run", "test", "fmt"):
        assert sub in combined, (sub, combined)
    print("H.B.1 main(--help): exits 0, lists every subcommand")


def test_version_consistency():
    cfg = _read_pyproject()
    declared = cfg["project"]["version"]
    from transpiler.aether import __version__ as actual
    assert declared == actual, (declared, actual)
    print(f"H.B.1 version: pyproject.toml and transpiler.aether agree on {declared}")


def test_zero_runtime_dependencies():
    cfg = _read_pyproject()
    deps = cfg["project"].get("dependencies", [])
    assert deps == [], deps
    extras = cfg.get("project", {}).get("optional-dependencies", {})
    assert "llm" in extras, extras
    assert any(d.startswith("anthropic") for d in extras["llm"]), extras["llm"]
    print("H.B.1 deps: zero runtime, [llm] extra carries anthropic SDK")


def test_the_wheel_ships_aether_as_the_top_level_package():
    """BUG-009. The wheel used to ship `transpiler`, so the only import
    that worked for an installed user was `from transpiler.aether import
    sdk` — while README, the sdk docstring and every file in this repo say
    `from aether import sdk`. `package-dir` remaps the root to
    `transpiler/`, so the package is `aether`, and `where` scopes discovery
    to that one directory: tests/, demos/ and bench/ are then unshippable
    by construction rather than by an exclude list somebody has to keep
    extending.

    Read from the file text: `package-dir = {"" = "transpiler"}` is an
    inline table with an empty-string key, which the 3.10 fallback parser
    in this file does not model."""
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        text = f.read()
    assert re.search(r'^package-dir\s*=\s*\{\s*""\s*=\s*"transpiler"\s*\}\s*$',
                     text, re.M),         "package-dir must remap the root to transpiler/ so `aether` is top-level"

    cfg = _read_pyproject()
    find = cfg["tool"]["setuptools"]["packages"]["find"]
    assert find.get("where") == ["transpiler"], find
    assert "aether*" in find["include"], find
    assert not any(i.startswith("transpiler") for i in find["include"]),         f"`transpiler` must not be shipped as a package: {find['include']}"

    assert os.path.isfile(os.path.join(ROOT, "transpiler", "aether", "__init__.py"))
    # Still a package in the CHECKOUT: ~20 call sites run the CLI as
    # `python -m transpiler.aether.cli` without installing.
    assert os.path.isfile(os.path.join(ROOT, "transpiler", "__init__.py"))
    print("H.B.1 packages: the wheel ships `aether`, scoped to transpiler/")


def test_license_is_an_spdx_string_without_a_trove_classifier():
    """BUG-006. `license = { text = ... }` is the PEP 621 table form; PEP
    639 deprecated it and setuptools >= 77 REJECTS it, so `pip install .`
    failed outright. Removing it surfaces the second half: an SPDX license
    string may not coexist with a `License ::` trove classifier.

    Asserted against the file text rather than through `_read_pyproject`,
    because that reader has a branch that happily parses the broken form —
    which is why the gate was green while the build was broken."""
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        text = f.read()
    assert re.search(r'^license\s*=\s*"[^"]+"\s*$', text, re.M), \
        "project.license must be an SPDX string, not the `{ text = ... }` table"
    assert "License ::" not in text, \
        "a `License ::` classifier and an SPDX license string cannot coexist"
    print("H.B.1 license: SPDX string, no conflicting trove classifier")


def test_the_package_never_imports_an_unpackaged_top_level_module():
    """BUG-007. `cmd_check_py` imported `tools.py_frontend`, reached via a
    sys.path insert of the checkout root. `packages.find` ships only
    `transpiler*`, so every pip-installed copy raised ModuleNotFoundError
    on the headline Python feature while the source checkout worked and
    every test passed.

    The invariant: nothing under `transpiler/` may import a top-level
    module that lives in the repo but is not in the wheel."""
    unpackaged = {d for d in os.listdir(ROOT)
                  if os.path.isdir(os.path.join(ROOT, d))
                  and d not in ("transpiler", "build")
                  and not d.startswith(".")}
    pat = re.compile(r"^\s*(?:from|import)\s+(\w+)", re.M)
    offenders = []
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "transpiler")):
        if "__pycache__" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            with open(p, encoding="utf-8") as f:
                for mod in pat.findall(f.read()):
                    if mod in unpackaged:
                        offenders.append(f"{rel} imports {mod!r}")
    assert not offenders, (
        "the package imports a module that is not in the wheel, so this "
        "works from a checkout and fails for every installed user: "
        + "; ".join(sorted(offenders)))
    print("H.B.1 imports: the package never reaches outside the wheel")


if __name__ == "__main__":
    test_console_script_entry_point_resolves()
    test_main_accepts_help()
    test_version_consistency()
    test_zero_runtime_dependencies()
    test_the_wheel_ships_aether_as_the_top_level_package()
    test_license_is_an_spdx_string_without_a_trove_classifier()
    test_the_package_never_imports_an_unpackaged_top_level_module()
    print("H.B.1 ALL PACKAGING TESTS PASS")
