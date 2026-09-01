# Aether upstream bug list

Bugs found by agents using Aether in other projects on this PC.
Entries appended automatically per prompt/upstream-bug-report.md.

## Fix protocol
Run fix sessions from this repo with the most capable Claude model
currently available (today: Fable 5 / `claude-fable-5`; use whatever
supersedes it). Per session: pick [OPEN] entries, reproduce first, fix
root cause, add regression test, run `python -B scripts/run_all.py`,
then mark entry `[FIXED <commit>]` AND add a `test: tests/<file>.py`
line to the entry naming the regression test that keeps it fixed.

The ratchet (`tests/test_ratchet.py`, in the gate) enforces that every
real `[FIXED <commit>]` entry names an existing `test:` file — so a
repaired bug can never silently reappear, and Aether only moves forward.
Entry shape:

    ### BUG-NNN  <one-line title>          [FIXED <commit>]
    test: tests/test_regressions.py
    <repro + root-cause notes>

---

### BUG-001  match-arm bindings dropped taint (false accept)  [FIXED 8d928d9]
test: tests/test_effect_scope.py

Found 2026-07-09 (iter-41 gap probe, this repo). Repro: `case Some(v) do
print(v) end` over an `Option<Secret<String>>` checked CLEAN (exit 0) —
a genuine MISS inside the modeled surface, violating the
over-flag-never-miss contract of every confidentiality-marker pass
(E0712/E0715/E0724/E0725/E0726/E0728/E0729/E0730). Root cause: the
shared fixpoint `_marked_tainted_names` collected only Let/Assign
bindings; match-pattern `BindPat` names were fresh, untainted names.
Fix: destructure propagation — every arm-pattern binding over a leaking
scrutinee is tainted (all arms, conservative). Regression tests:
`test_match_destructured_secret_rejected` and 4 siblings in
tests/test_effect_scope.py.

### BUG-002  function aliases laundered the taint boundary (false accept)  [FIXED f6b8bf3]
test: tests/test_effect_scope.py

Found 2026-07-09 (iter-42 probes, this repo). Two repros, both exit 0:
`let f = logIt; f(password)` bypassed E0729's callee lookup (callee
name "f" is not a declared function), and `let f = getToken; f()`
defeated return-type seeding (source set keyed by declared names).
Root cause: every boundary mechanism resolved callees by literal name
only. Fix: per-function alias map (`_fn_aliases`, straight-line bare-
Ident bindings, chains followed, union on rebinding) applied FLAG-MORE
only — aliases join the source set, single-target aliases extend the
sanctioned-crossing mask, E0729 checks every alias target; an aliased
unwrapper (`let r = reveal`) is deliberately NOT honored (documented
over-flag). Regression tests: `test_fn_alias_launder_rejected` and 5
siblings in tests/test_effect_scope.py.

### BUG-003  mixed-arg effect list crashed the effect check (compiler crash)  [FIXED 27abede]
test: tests/test_effect_scope.py

Found 2026-07-26 (Python-frontend work, this repo). Repro — 16 lines of
legal Aether, `python -B -m transpiler.aether.cli check`:

    function helper() returns Unit
      effects fs.write
    do
      let _r: Result<Unit, String> = writeFile("/tmp/x", "y")
    end

    function go() returns Unit
      effects net.fetch, net.fetch("https://api.example.com/x")
    do
      helper()
    end

-> `TypeError: '<' not supported between instances of 'str' and
'NoneType'`, uncaught, from `_format_effect_list`. The compiler DIES
instead of emitting the E0801 it had already decided to emit.

Root cause: `EffectEntry = Tuple[Tuple[str, ...], Optional[str]]` and
the formatter called `sorted(effs)` on the entries themselves. Two
effects that share a path but differ in arg presence — `net.fetch` and
`net.fetch("https://...")`, a legal and meaningful pair — make tuple
comparison fall through to the arg slot and compare `None` with `str`.
Only reachable on the DIAGNOSTIC path (the caller list is formatted
solely when a violation is being reported), which is why the corpus
never hit it: every corpus program with mixed args is otherwise clean.

Surfaced by `tools/py_frontend.py`, which synthesizes exactly this shape
(`_add_effect` records the first constant string argument, or None), but
the bug is in the Aether pass and reproduces with no Python involved.

Fix: sort on an explicit ordering key, `(path, arg or "")`, so the arg
slot is always str-vs-str. Regression test:
`test_mixed_arg_effect_list_does_not_crash` in tests/test_effect_scope.py.

### BUG-004  three sink guards defaulted "unknown" to "safe" (false accepts)  [FIXED 6606fe1]
test: tests/test_py_frontend_sinks.py

Found 2026-07-26, probing the guard-bound-elsewhere residual recorded in
`vault/wiki/questions/q5`. Expected a precision gap; found three MISSES
inside the modeled surface — the contract-breach class, same as BUG-001
and BUG-002. All three are one mistake: the unknown case defaulted to
"not a sink".

Repros, all SILENT before the fix (stages effects/semantic/capability
skipped, as `aether check-py` runs them):

1.  yaml.load(raw, Loader=yaml.Loader)                    -> expected E0720
2.  loader = yaml.Loader; yaml.load(raw, Loader=loader)   -> expected E0720
3.  sh = True; subprocess.run('x ' + cmd, shell=sh)       -> expected E0714
4.  cur.execute('SELECT * FROM t WHERE n=' + name, extra) -> expected E0713

(1) is the worst and is not "bound elsewhere" at all: the unsafe value is
written at the call site. The old gate read `if _has_kw(call, "Loader"):
return None` — ANY Loader= meant safe. Adding `Loader=` is the commonest
wrong fix for PyYAML's deprecation warning, and `yaml.Loader` is the RCE.

Loader safety verified by EXECUTION on PyYAML 6.0.3, payload
`!!python/object/apply:os.system [...]`:
    yaml.Loader     -> CONSTRUCTED (unsafe)
    yaml.UnsafeLoader -> CONSTRUCTED (unsafe)
    yaml.FullLoader -> refused (ConstructorError)
    yaml.SafeLoader -> refused (ConstructorError)
FullLoader is deliberately NOT sanctioned regardless: CVE-2020-1747 and
CVE-2020-14343 are FullLoader bypasses.

(3) `_has_kw_true` required a literal `True` Constant, so a shell flag
held in a variable was read as "no shell".

(4) `_is_parameterized_query` cleared ANY two-argument execute. It was
never needed: `_SQL_RULE` has no literal_bans, so
`cur.execute("... id = ?", (uid,))` is already clean because argument 0
is a StringLit. The recognizer only ever added a false accept, and the
fix is its deletion.

Fix: one declarative `SINK_GUARDS` table whose contract is that a guard
clears a call ONLY when its value is positively identified as sanctioned.
Unrecognized, computed, unresolvable, or absent all mean SINK. This is
q5's rule ("never assume clean from a name") applied to values.
Regression tests: `test_yaml_unsafe_loader_is_still_a_sink` and 5 siblings
in tests/test_py_frontend_sinks.py.

### BUG-005  a UTF-8 BOM made a file invisible to the scanner (silent false negative)  [FIXED 70f0793]
test: tests/test_py_frontend_sinks.py


Found 2026-09-01, while testing the new `check-py` directory walk against
a tree written by PowerShell (which emits UTF-8 **with BOM** by default).
Repro — a file whose only difference from a flagged one is three leading
bytes:

    printf '\xef\xbb\xbfimport subprocess\ndef r(h):\n    subprocess.run("ping " + h, shell=True)\n' > bom.py
    aether check-py bom.py

Before: `SyntaxError`. Over a directory the walk counted it "unparseable"
and moved on, so a file containing a live command injection was reported
in a summary line as skipped — and in the tree summary that line is easy
to read as "nothing here".

Root cause: `_read` in `transpiler/aether/cli.py` opened every source with
`encoding="utf-8"`, under which a BOM survives decoding as U+FEFF at
offset 0. Python's own tokenizer strips it; `ast.parse` on the decoded
string does not, because by then it is an ordinary non-printable
character.

Severity is the point, not the parse error. A checker that cannot read a
file must not resolve that to *clean*. The single-file path failed loudly
(traceback), so the bug only became dangerous when the directory walk
turned "cannot read" into a counted, easily-skimmed line.

Fix: read with `utf-8-sig`, which strips a BOM if present and is identical
to `utf-8` when it is not. Applied in `_read`, the one function every
subcommand routes through, so `.aeth` sources get the same repair —
a BOM'd `.aeth` file previously died in the lexer for the same reason.
The walk additionally reports the unparseable count on its own line rather
than folding it into the file total. Regression test:
`test_utf8_bom_file_is_scanned_not_silently_skipped`, plus
`test_unparseable_file_does_not_abort_the_walk` in
tests/test_py_frontend_sinks.py.

### BUG-006  `pip install .` failed outright on current setuptools  [FIXED 70f0793]
test: tests/test_packaging.py


Found 2026-09-01, building a wheel to check BUG-007. Repro, setuptools
84.0.0, a clean venv:

    python -m pip install .
    ValueError: invalid pyproject.toml config: `project.license`.
    configuration error: `project.license` must be string

Root cause: `license = { text = "BUSL-1.1" }`, the PEP 621 table form,
which PEP 639 deprecated and setuptools >= 77 rejects. Removing it then
surfaced the second half: an SPDX `license` string may not coexist with a
`License ::` trove classifier, so the build failed again on
`License :: Other/Proprietary License`.

The gate did not catch this because `tests/test_packaging.py` reads
pyproject.toml with a hand-rolled mini-parser that has a branch
specifically for the inline-table license form, and asserts against the
parsed values. It never built a wheel, so it validated the config it could
read rather than the config setuptools accepts.

Fix: `license = "BUSL-1.1"` (string form, accepted by both old and new
setuptools) and drop the license classifier. Also corrected
`Operating System :: POSIX` to `OS Independent` — the CLI is developed and
run on Windows, and the POSIX-only caveat belongs to the bench harness's
SIGALRM timeout, not to the package.

Verified by building and installing the wheel into a fresh venv, not by
re-reading the config.

### BUG-007  `aether check-py` was broken in every installed copy  [FIXED 70f0793]
test: tests/test_packaging.py


Found 2026-09-01, immediately after BUG-006 let a wheel build for the
first time. Repro — install the wheel into a venv and run the headline
feature from any directory that is not the source checkout:

    aether check-py some_file.py
    ModuleNotFoundError: No module named 'tools'

Root cause: `cmd_check_py` imported the Python frontend as
`from tools.py_frontend import py_to_ir`, reaching it through a
`sys.path.insert` of the checkout root. `[tool.setuptools.packages.find]`
has `include = ["transpiler*"]`, so `tools/` is not in the wheel. From a
source checkout the import resolved and every test passed; from a wheel it
could never resolve. The gate runs from the checkout, so it saw the
working case only.

This is the whole Python story failing in exactly the configuration a user
installs, and it was invisible for as long as nobody built a wheel.

Fix: move the frontend to `transpiler/aether/py_frontend.py` — library
code the CLI depends on belongs in the library — and import it relatively
(`from .py_frontend import py_to_ir`), so no `sys.path` surgery is
involved and the installed package name (`transpiler.aether`) is
irrelevant. The nine `tools.py_frontend` import sites in bench scripts,
tools and tests were updated to `aether.py_frontend`; they already put
`transpiler/` on `sys.path`. Packaging `tools*` was the alternative and
was rejected: `tools` is far too generic a name to occupy in a user's
site-packages, and most of that directory is not library code.

Verified end to end: `pip install .` into a clean venv, then
`aether check-py` run from an unrelated working directory, reporting the
two expected E0713 findings.

### BUG-008  `sdk.run` / `sdk.grade` fail on every installed copy, and report it as your program failing  [FIXED 70f0793]
test: tests/test_sdk.py


Found 2026-09-01 by the regression test written for BUG-007
(`test_the_package_never_imports_an_unpackaged_top_level_module`) — the
same class, a second site, found on the first run.

`transpiler/aether/sdk.py:208` does `from bench.harness import
compile_and_run`, and `bench/` is excluded from the wheel by
`[tool.setuptools.packages.find]`. The import sits inside a bare
`except Exception` whose handler returns

    RunResult(ok=False, stderr="sdk.run error: ModuleNotFoundError: ...")

so in an installed copy **every** `sdk.run()` and `sdk.grade()` returns a
failed run. That is worse than the BUG-007 crash: a caller grading
candidates sees every candidate fail, and a failed run is exactly what a
bad candidate looks like. The docstring says the helper is used "where
available", which describes a fallback that does not exist.

Not blocking the scanner: `check-py`, `tools/scan.py` and the CLI do not
route through `sdk.run`. Listed in that test's `KNOWN_OPEN` set — listed,
not waived, and the test fails if the entry goes stale.

Fixed 2026-09-01 (the same move BUG-007 got, and the third instance of
this one architectural mistake — library code living outside the library):
`compile_and_run`, its timeout machinery and `format_diag_as_stderr` moved
to `transpiler/aether/runner.py`. `bench/harness.py` re-exports them under
their original names, so all six `from bench.harness import
compile_and_run` call sites are unchanged. `sdk.run` imports it at module
level, so an ImportError can no longer be swallowed by the function's own
`except Exception`.

The SIGALRM caveat was the part that needed care — it is POSIX-only and a
no-op on Windows, and moving it into the package would have made the SDK
promise a timeout it cannot keep. So the fact is now reported instead of
documented in a file nobody reads: `runner.TIMEOUT_ENFORCED`,
re-exported as `sdk.TIMEOUT_ENFORCED`, and `timeout_enforced` on every
result dict and every `RunResult`. "No timeout fired" and "this platform
has no timer" are now distinguishable by the caller.

Regression tests: `test_run_works_without_bench_importable` (runs `sdk.run`
in a subprocess with the repo root off `sys.path`, asserting `bench` is
genuinely unimportable first, so the test cannot pass vacuously) and
`test_run_reports_whether_the_timeout_was_actually_armed`, both in
tests/test_sdk.py. `test_the_package_never_imports_an_unpackaged_top_level_module`
in tests/test_packaging.py now passes with no exemptions.

Verified from a wheel installed into a clean venv, `bench` not importable:
`sdk.run` returns ok=True with the program's stdout, `sdk.grade` ok=True.

### BUG-009  the documented SDK import `from aether import sdk` does not work when installed  [FIXED 70f0793]
test: tests/test_packaging.py


Found 2026-09-01, verifying the BUG-008 fix from an installed wheel. The
wheel's top-level package is **`transpiler`** (`packages.find` has
`include = ["transpiler*"]`), so an installed user must write

    from transpiler.aether import sdk        # works
    from aether import sdk                   # ModuleNotFoundError

The second spelling is what `README.md`, `transpiler/aether/sdk.py`'s own
docstring, and every file in the repo use — it works from a checkout only
because `bench/`, `tests/` and `tools/` each `sys.path.insert` the
`transpiler/` directory. The docs describe the checkout layout, not the
installed one. Same theme as BUG-006/007/008.

`transpiler` is also a poor name to occupy at top level in someone's
site-packages, for the same reason packaging `tools*` was rejected in
BUG-007.

Fixed 2026-09-01. `[tool.setuptools] package-dir = {"" = "transpiler"}`
remaps the root, and `[tool.setuptools.packages.find] where =
["transpiler"], include = ["aether*"]` scopes discovery to it, so the
wheel ships `aether` and nothing else. The `[project.scripts]` entry point
became `aether.cli:main`. `transpiler/__init__.py` stays in the checkout —
roughly twenty call sites run `python -B -m transpiler.aether.cli` without
installing — but is no longer part of the distribution. The dual-spelling
header `cmd_pack` emits already tried both, so it needed no change.

`where` also replaced a fourteen-entry `exclude` list of top-level
directories. That list was a promise to remember every new directory
somebody adds; scoping discovery to `transpiler/` makes tests/, demos/ and
bench/ unshippable by construction.

**A second bug surfaced during the fix, and it is the reason the first
attempt looked like it worked.** After the pyproject change the wheel
shipped BOTH `aether` and `transpiler` — two full copies of the same code
in site-packages. The cause was a stale `build/lib/transpiler/` left by an
earlier build: setuptools packs what it finds under `build/lib`, so a
directory deleted from the config lives on in every subsequent wheel until
`build/` is cleared. `build/` and `UNKNOWN.egg-info/` are gitignored and
were removed; a clean rebuild ships `aether` alone. Worth knowing before
the first PyPI upload, because `python -m build` has the same failure mode
and the result is silently a superset of what was intended.

Regression test: `test_the_wheel_ships_aether_as_the_top_level_package`
in tests/test_packaging.py — asserts `package-dir` from the file text (the
3.10 fallback parser cannot model an inline table with an empty-string
key), `where == ["transpiler"]`, `aether*` in `include`, and that nothing
starting with `transpiler` is in `include`.

Verified in a clean venv: `transpiler` NOT importable, `from aether import
sdk` works, `sdk.run` and `sdk.grade` return ok, and the `aether check-py`
console script reports E0723 on the hardcoded-credential repro.
