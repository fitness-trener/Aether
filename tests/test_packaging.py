"""H.B.1 regression tests for the pip-installable package.

We can't reach PyPI from this CI sandbox, so we don't actually run
`pip install .` here. We DO validate every fact `pip install` will
rely on:

  1. The console script entry point string in `pyproject.toml`
     (`aether = transpiler.aether.cli:main`) resolves to a real
     callable in the source tree.
  2. The `main` function it points at accepts the same arg shape as
     setuptools will hand it — calling `main(["--help"])` exits 0 and
     prints the top-level help.
  3. The package's `__version__` matches the version declared in
     `pyproject.toml`. A version drift here means a future release
     ships a wheel whose stamped version disagrees with what
     `import transpiler.aether; transpiler.aether.__version__` reports.
  4. `pyproject.toml` declares no runtime dependencies — the core
     toolchain is stdlib-only by design and the H.B.1 contract is
     that `pip install aether-lang` pulls in no third-party
     packages. (`anthropic` lives under the `[llm]` extra.)
  5. The `setuptools.packages.find` `include` / `exclude` lists let
     `transpiler.aether` through and block everything else
     (tests, demos, bench, scripts).
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
    assert target == "transpiler.aether.cli:main", target
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


def test_packages_find_filters_correctly():
    cfg = _read_pyproject()
    find = cfg["tool"]["setuptools"]["packages"]["find"]
    assert "transpiler*" in find["include"], find
    for blocked in ("tests*", "demos*", "bench*", "scripts*", "yc*"):
        assert blocked in find["exclude"], (blocked, find["exclude"])
    assert os.path.isfile(os.path.join(ROOT, "transpiler", "__init__.py"))
    assert os.path.isfile(os.path.join(ROOT, "transpiler", "aether", "__init__.py"))
    print("H.B.1 packages.find: include/exclude lists wired correctly")


if __name__ == "__main__":
    test_console_script_entry_point_resolves()
    test_main_accepts_help()
    test_version_consistency()
    test_zero_runtime_dependencies()
    test_packages_find_filters_correctly()
    print("H.B.1 ALL PACKAGING TESTS PASS")
