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

### BUG-004  three sink guards defaulted "unknown" to "safe" (false accepts)  [FIXED PENDING]
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
