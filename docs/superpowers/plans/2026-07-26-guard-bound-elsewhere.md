# Guard-Bound-Elsewhere Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three probe-confirmed FALSE ACCEPTS in the Python sink gates, and make "the guard could not be resolved" mean **sink**, not **safe**.

**Architecture:** `tools/py_frontend.py` gates three sinks on something other than the argument the rule judges: `yaml.load`'s `Loader=`, `subprocess.*`'s `shell=`, and `etree.fromstring`'s parser object. Each gate was written ad hoc, and two of them default the *unresolvable* case to "not a sink" — the wrong direction. Task 1 replaces them with one declarative `SINK_GUARDS` table whose default is **sink**, restoring soundness at some precision cost. Task 2 adds conservative local-constant resolution to win the precision back for the cases that are actually decidable. Task 3 measures the cost and records it.

**Tech Stack:** Python 3 stdlib only (`ast`). No Aether pass changes — the detectors are correct; the frontend was feeding them a wrong answer.

## Global Constraints

- **Windows.** `python`, not `python3`. PowerShell for running Python, Bash tool for `grep`/`sed`. **Never** put a multi-line commit message in a PowerShell here-string — it mis-parses and git reads the remainder as pathspecs. Write the message to a scratch file and use `git commit -F <file> -- <paths>`.
- **Full gate:** `python -B scripts/run_all.py` must exit 0 after every task.
- **Ratchet:** `tests/ratchet_baseline.json` stays at 54 codes / 30 detectors. No new code, no new detector.
- **This is a soundness fix, and soundness beats precision at every fork.** CLAUDE.md: over-flag rather than miss. A MISS inside the modeled surface is the contract-breach class — the same class as BUG-001 and BUG-002. Where Task 1 and Task 2 disagree, Task 1 wins.
- **Never present these passes as sound.** Syntactic, intraprocedural, over-flag-never-miss *within the modeled surface*.
- **Cite every security claim.** The loader-safety classification below was verified by execution, not from memory — keep it that way for anything added.

---

## Confirmed Gaps (probe results — do not re-derive)

`bench/py_frontend/run_bench.py`'s pipeline, stages `effects`/`semantic`/`capability` skipped, on commit `3cc82a1`:

| # | Shape | Now | Wanted |
|---|---|---|---|
| **G1** | `yaml.load(raw, Loader=yaml.Loader)` | **SILENT** | E0720 |
| **G2** | `loader = yaml.Loader` … `yaml.load(raw, Loader=loader)` | **SILENT** | E0720 |
| **G3** | `sh = True` … `subprocess.run('x ' + cmd, shell=sh)` | **SILENT** | E0714 |
| **G4** | `cur.execute('SELECT * FROM t WHERE n=' + name, extra)` | **SILENT** | E0713 |
| C2 | `subprocess.run('x ' + cmd, shell=True)` | E0714 | unchanged (control) |
| F | parser rebound to `resolve_entities=True` after a safe binding | E0727 | unchanged (control) |
| A2 | `yaml.load(raw, Loader=yaml.SafeLoader)` | SILENT | **must stay silent** |

**G1 is the serious one.** It is not even "bound elsewhere" — the unsafe value is written directly at the call site. `_sink_name` reads `if _has_kw(call, "Loader"): return None`, i.e. *any* `Loader=` means safe. Adding `Loader=yaml.Loader` is the single most common wrong fix for PyYAML's deprecation warning, and it is the RCE.

**Loader safety, verified by execution** (PyYAML 6.0.3, payload `!!python/object/apply:os.system [...]`):

| Loader | Result |
|---|---|
| `yaml.Loader` | **CONSTRUCTED — arbitrary object construction ran** |
| `yaml.UnsafeLoader` | **CONSTRUCTED** |
| `yaml.FullLoader` | refused (`ConstructorError`) |
| `yaml.SafeLoader` | refused (`ConstructorError`) |

`FullLoader` refused this payload but is **deliberately NOT sanctioned** by this plan: CVE-2020-1747 and CVE-2020-14343 are FullLoader bypasses. Over-flag direction, and the reason is citable.

**G4 needs no new machinery — it needs a deletion.** `_is_parameterized_query` clears *any* two-argument `execute`. It was never necessary: `_SQL_RULE` has no `literal_bans`, so `cur.execute("... id = ?", (uid,))` is already clean because argument 0 is a `StringLit`. The recognizer only ever added a false accept.

---

## File Structure

**Modified:**
- `tools/py_frontend.py` — `SINK_GUARDS` table + `_guard_verdict`; `_sink_name` reads the table; `_is_parameterized_query` deleted; `_safe_xml_parser_names` folded in (Task 2).
- `tests/test_py_frontend_sinks.py` — the four gap probes as tests, plus the three controls that must not move.
- `BUGS.md` — BUG-004.
- `bench/py_frontend/REPORT.md`, `vault/wiki/questions/q5-sink-matching-vs-purity-matching.md`, `vault/wiki/log.md`, `demos/case_studies/LOOP_LOG.md`.

**No new files.**

---

### Task 1: Unresolvable guard means SINK

Closes G1, G3, G4 outright, and G2 by over-flagging (Task 2 recovers the precision).

**Files:**
- Modify: `tools/py_frontend.py`
- Test: `tests/test_py_frontend_sinks.py`

**Interfaces:**
- Produces: `SINK_GUARDS: Dict[str, Guard]` and `_guard_verdict(call, guard, imp, resolver=None) -> bool` (True = this call IS a sink).
- Removes: `_is_parameterized_query`, `_has_kw`, `_has_kw_true`. Grep for each before deleting; `_has_kw_true` has no other caller.

**The doctrine, to be written into the module** — this is the same rule as q5, applied one level down:

> q5 settled that a NAME may not clear a call. A VALUE may not either. Every guard here answers "is this call safe?", and the answer is only accepted when the value is positively identified as one of the sanctioned forms. Unrecognized, computed, unresolvable, or absent — all mean **sink**. The three gates this replaces defaulted the unknown case to "safe" and produced three false accepts, one of them an RCE written literally at the call site.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_py_frontend_sinks.py`, before the CLI section:

```python
# --- guard-bound-elsewhere: an unresolved guard means SINK ---------------
# These gates decide safety from something other than the argument the
# rule judges. All three shipped defaulting the unknown case to "safe",
# which produced three false accepts (BUGS.md BUG-004). q5's rule applies
# to values exactly as it does to names: never clear on weak evidence.

def test_yaml_unsafe_loader_is_still_a_sink():
    """`Loader=yaml.Loader` is the RCE. Verified by execution on PyYAML
    6.0.3: yaml.Loader constructs !!python/object/apply. Adding Loader=
    to silence the deprecation warning is the commonest wrong fix."""
    src = "import yaml\ndef f(raw):\n    yaml.load(raw, Loader=yaml.Loader)\n"
    assert "E0720" in _codes(src), "yaml.Loader is the unsafe loader"
    print("guard: yaml.Loader still flagged")


def test_yaml_unsafe_loader_named_elsewhere_is_still_a_sink():
    src = ("import yaml\ndef f(raw):\n"
           "    loader = yaml.Loader\n"
           "    yaml.load(raw, Loader=loader)\n")
    assert "E0720" in _codes(src), \
        "a loader bound elsewhere must not clear the sink"
    print("guard: loader bound elsewhere still flagged")


def test_yaml_safe_loader_stays_clean():
    src = "import yaml\ndef f(raw):\n    yaml.load(raw, Loader=yaml.SafeLoader)\n"
    assert "E0720" not in _codes(src), "SafeLoader is the documented fix"
    print("guard: SafeLoader stays clean")


def test_yaml_full_loader_is_not_sanctioned():
    """FullLoader refused this plan's probe payload but has its own
    bypass CVEs (CVE-2020-1747, CVE-2020-14343). Over-flag."""
    src = "import yaml\ndef f(raw):\n    yaml.load(raw, Loader=yaml.FullLoader)\n"
    assert "E0720" in _codes(src), \
        "FullLoader is deliberately not sanctioned - it has bypass CVEs"
    print("guard: FullLoader deliberately not sanctioned")


def test_shell_true_bound_elsewhere_is_still_a_sink():
    src = ("import subprocess\ndef f(cmd):\n"
           "    sh = True\n"
           "    subprocess.run('x ' + cmd, shell=sh)\n")
    assert "E0714" in _codes(src), \
        "shell= whose value is not provably False must be treated as a shell"
    print("guard: shell bound elsewhere still flagged")


def test_concatenated_sql_with_params_is_still_a_sink():
    """A second argument does not launder a concatenated query. The
    parameterized form is already clean because argument 0 is a literal -
    the recognizer was unnecessary AND wrong."""
    src = ("def f(cur, name, extra):\n"
           "    cur.execute('SELECT * FROM t WHERE n=' + name, extra)\n")
    assert "E0713" in _codes(src), \
        "params do not save a query built by concatenation"
    print("guard: concatenated SQL with params still flagged")
```

Register all six in `__main__`, and keep the existing
`test_parameterized_query_is_the_sanctioned_exit`,
`test_yaml_load_with_safe_loader_is_not_a_sink`,
`test_shell_false_is_not_a_shell_sink`,
`test_xxe_safe_parser_disarms_the_sink` and
`test_xxe_default_parser_still_fires` — those are the controls that must not move.

- [ ] **Step 2: Run to verify they fail**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: FAIL on `test_yaml_unsafe_loader_is_still_a_sink`. Confirm the other five new tests fail too (comment out the first temporarily if the runner short-circuits, or run them individually) — each is a separate false accept, and seeing all six red is the point.

- [ ] **Step 3: Add the guard table**

In `tools/py_frontend.py`, replace the `SINK_GATED_SUBPROCESS` / `SINK_GATED_YAML` block with:

```python
# ----------------------------------------------------------------------
# SINK GUARDS — when safety lives somewhere other than the judged argument
# ----------------------------------------------------------------------
# q5 settled that a NAME may not clear a call. A VALUE may not either.
# Each guard answers "is this call safe?", and the answer is accepted only
# when the value is positively identified as one of the sanctioned forms.
# Unrecognized, computed, unresolvable, or absent all mean SINK.
#
# The three ad-hoc gates this replaces defaulted the unknown case to
# "safe" and produced three false accepts (BUGS.md BUG-004), one of them
# an RCE written literally at the call site:
# `yaml.load(raw, Loader=yaml.Loader)` was silent.

class Guard:
    """One sink's safety condition.

    sink_name     — the Aether sink this call becomes when the guard says
                    SINK. Lives here because the guarded callables are not
                    in SINK_BY_QUALIFIED — the guard owns them entirely.
    keyword       — the keyword argument that decides, or None for a
                    positional slot (`arg_index`).
    safe_values   — dotted spellings that make the call SAFE. Empty means
                    no value is sanctioned; presence alone never is.
    sink_values   — dotted spellings that make it a SINK. Used where the
                    absent case is safe (`shell=` absent means no shell).
    absent_is_sink— verdict when the keyword is not present at all.
    """
    def __init__(self, sink_name, keyword=None, arg_index=None,
                 safe_values=(), sink_values=(), absent_is_sink=True):
        self.sink_name = sink_name
        self.keyword = keyword
        self.arg_index = arg_index
        self.safe_values = frozenset(safe_values)
        self.sink_values = frozenset(sink_values)
        self.absent_is_sink = absent_is_sink


# Loader safety verified by EXECUTION on PyYAML 6.0.3 with the payload
# `!!python/object/apply:os.system [...]`:
#   yaml.Loader       -> CONSTRUCTED (unsafe)   yaml.UnsafeLoader -> CONSTRUCTED
#   yaml.FullLoader   -> refused                yaml.SafeLoader   -> refused
# FullLoader is deliberately NOT sanctioned: CVE-2020-1747 and
# CVE-2020-14343 are FullLoader bypasses. Over-flag direction.
_YAML_SAFE_LOADERS = ("yaml.SafeLoader", "yaml.CSafeLoader",
                      "yaml.BaseLoader", "yaml.CBaseLoader")

SINK_GUARDS: Dict[str, Guard] = {}
for _fn in ("yaml.load", "yaml.full_load", "yaml.unsafe_load"):
    # Absent Loader= is a sink (that is the classic yaml.load(x) RCE);
    # a SANCTIONED loader clears it; anything else does not.
    SINK_GUARDS[_fn] = Guard("deserialize", keyword="Loader",
                             safe_values=_YAML_SAFE_LOADERS,
                             absent_is_sink=True)
for _fn in ("subprocess.run", "subprocess.call", "subprocess.check_call",
            "subprocess.check_output", "subprocess.Popen"):
    # No shell= means no shell — the argv form, which IS the documented
    # fix — so absence is SAFE here. But a shell= we cannot resolve to a
    # literal False is treated as a shell.
    SINK_GUARDS[_fn] = Guard("shellExec", keyword="shell",
                             safe_values=("False",), absent_is_sink=False)
```

- [ ] **Step 4: Add the verdict function**

```python
def _dotted_of(node: Any, imp: "_Imports",
               resolver: Optional[Any] = None) -> Optional[str]:
    """The dotted spelling of a VALUE expression, or None if it cannot be
    positively identified. `resolver` (Task 2) maps a local name to the
    single value bound to it; without one, a bare Name is unresolved —
    which, per the guard contract, means unsafe."""
    if isinstance(node, _pyast.Constant):
        return repr(node.value) if node.value is None else str(node.value)
    if isinstance(node, _pyast.Attribute) and isinstance(node.value, _pyast.Name):
        return imp.resolve_attr(node.value.id, node.attr) or \
            (node.value.id + "." + node.attr)
    if isinstance(node, _pyast.Name):
        if resolver is not None:
            return resolver(node.id)
        return None
    return None


def _guard_verdict(call: _pyast.Call, guard: "Guard", imp: "_Imports",
                   resolver: Optional[Any] = None) -> bool:
    """True if this call IS a sink under `guard`."""
    node = None
    for kw in call.keywords or []:
        if kw.arg == guard.keyword:
            node = kw.value
            break
    if node is None and guard.arg_index is not None \
            and len(call.args) > guard.arg_index:
        node = call.args[guard.arg_index]
    if node is None:
        return guard.absent_is_sink
    dotted = _dotted_of(node, imp, resolver)
    if dotted is None:
        return True                      # unresolved -> sink, never safe
    if dotted in guard.safe_values:
        return False
    if guard.sink_values:
        return dotted in guard.sink_values
    return True                          # not positively sanctioned -> sink
```

- [ ] **Step 5: Read the table from `_sink_name`, and delete the recognizer**

Replace the `SINK_GATED_*` branches at the top of `_sink_name` with:

```python
    guard = SINK_GUARDS.get(dotted)
    if guard is not None:
        return guard.sink_name if _guard_verdict(call, guard, imp, resolver) \
            else None
```

The guarded callables are deliberately absent from `SINK_BY_QUALIFIED` —
the guard owns them, and `Guard.sink_name` is the single place their sink
name is written. Thread a `resolver=None` parameter through `_sink_name`
and `_call_expr` now, so Task 2 has one call site to change and no
signatures to churn.

Note the from-import limit while you are here: `from yaml import SafeLoader`
then `Loader=SafeLoader` reaches `_dotted_of` as a bare `Name`, which is
unresolved and therefore a SINK until Task 2's resolver sees the binding —
and a from-imported name has no local binding, so it stays an over-flag.
Correct direction; record it in Task 3's report rather than fixing it here.

Then **delete `_is_parameterized_query` and its call site** in `_sink_name`:

```python
    if isinstance(call.func, _pyast.Attribute):
        return SINK_BY_METHOD.get(call.func.attr)
```

Also delete `_has_kw` and `_has_kw_true` — grep first to confirm no other caller.

- [ ] **Step 6: Run to verify they pass**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: PASS, all controls included.

- [ ] **Step 7: Re-run the gap probe**

Re-run the seven-case probe from the Confirmed Gaps table. Expected after this task: G1, G3, G4 report their code; **G2 also reports** (by over-flagging — the loader name is unresolved, which now means sink); A2/C2/F unchanged.

- [ ] **Step 8: Full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0. If `bench/py_frontend` labels now disagree, that is a real change — fix the code or the label deliberately, never by loosening a guard.

- [ ] **Step 9: Add BUG-004 and commit**

Append to `BUGS.md`, following the shape of BUG-003 (`[FIXED <commit>]` + a `test:` line — `tests/test_ratchet.py` enforces that the named file exists). Title: `three sink guards defaulted "unknown" to "safe" (false accepts)`. Record all four repros, the loader execution table, and that G1 needed no "elsewhere" at all.

Commit message to a scratch file, then `git commit -F`.

---

### Task 2: Win the precision back — conservative local resolution

Task 1 makes `Loader=loader` a sink even when `loader = yaml.SafeLoader`. That is sound and annoying. This task resolves a local name to its value **only when every binding in the function agrees**, mirroring the discipline `_safe_xml_parser_names` already uses (`flags and all(flags)`) and `_fn_aliases` uses in `detector_specs.py` (single target only; ambiguity over-flags).

**Files:**
- Modify: `tools/py_frontend.py`
- Test: `tests/test_py_frontend_sinks.py`

**Interfaces:**
- Produces: `_local_constants(fn_node, imp) -> Dict[str, str]` — local name → the single dotted value bound to it, omitting any name bound more than once to different values.
- Consumes: the `resolver` parameter threaded in Task 1 Step 5.

- [ ] **Step 1: Write the failing tests**

```python
def test_safe_loader_bound_elsewhere_is_clean():
    src = ("import yaml\ndef f(raw):\n"
           "    loader = yaml.SafeLoader\n"
           "    yaml.load(raw, Loader=loader)\n")
    assert "E0720" not in _codes(src), \
        "a name bound once to a sanctioned loader is resolvable"
    print("guard: SafeLoader bound elsewhere resolves clean")


def test_rebound_loader_is_still_a_sink():
    src = ("import yaml\ndef f(raw, flag):\n"
           "    loader = yaml.SafeLoader\n"
           "    loader = yaml.Loader\n"
           "    yaml.load(raw, Loader=loader)\n")
    assert "E0720" in _codes(src), \
        "a name with disagreeing bindings must not resolve to safe"
    print("guard: rebound loader stays flagged")


def test_shell_false_bound_elsewhere_is_clean():
    src = ("import subprocess\ndef f(cmd):\n"
           "    sh = False\n"
           "    subprocess.run(['x', cmd], shell=sh)\n")
    assert "E0714" not in _codes(src), \
        "shell provably False is not a shell sink"
    print("guard: shell=False bound elsewhere resolves clean")
```

Register in `__main__`.

- [ ] **Step 2: Run to verify the first and third fail**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: FAIL on `test_safe_loader_bound_elsewhere_is_clean` (Task 1 deliberately over-flags it). `test_rebound_loader_is_still_a_sink` already passes and is the pin that must survive Step 3.

- [ ] **Step 3: Add the resolver**

```python
def _local_constants(fn_node: Any, imp: "_Imports") -> Dict[str, str]:
    """local name -> the single dotted value bound to it in this function.

    A name bound more than once to DIFFERENT values is omitted: ambiguity
    must over-flag, never resolve. Straight-line only; no control flow is
    modeled, so a name assigned in one branch and read in another is
    treated as agreeing — which is why this only ever runs against
    `safe_values`, where being wrong costs a missed clear, not a missed
    finding... except that it does not: a WRONG resolution to a safe value
    IS a false accept. Hence: single unique binding, or nothing."""
    seen: Dict[str, Set[str]] = {}
    for stmt in _pyast.walk(fn_node):
        if not isinstance(stmt, _pyast.Assign) or len(stmt.targets) != 1:
            continue
        tgt = stmt.targets[0]
        if not isinstance(tgt, _pyast.Name):
            continue
        val = _dotted_of(stmt.value, imp, None)
        seen.setdefault(tgt.id, set()).add(val if val is not None else "<unresolved>")
    return {n: next(iter(vs)) for n, vs in seen.items()
            if len(vs) == 1 and "<unresolved>" not in vs}
```

Build it once per function in `py_to_ir` (beside `_safe_xml_parser_names`), store it on the visitor, and pass `resolver=self.consts.get` down through `_expr` → `_call_expr` → `_sink_name`.

- [ ] **Step 4: Run to verify they pass**

```bash
python -B tests/test_py_frontend_sinks.py
```

Expected: PASS, including `test_rebound_loader_is_still_a_sink` and every Task 1 test.

- [ ] **Step 5: Fold `_safe_xml_parser_names` onto the same resolver**

`_safe_xml_parser_names` is the same idea written earlier and separately. Leave its behaviour identical — both XXE controls must still pass — but note in its docstring that it is the parser-shaped instance of `_local_constants`' discipline, so a future reader sees one pattern instead of two. **Do not merge them if the merge changes any test outcome**; a green refactor is worth less than a correct guard.

- [ ] **Step 6: Full gate + commit**

```bash
python -B scripts/run_all.py
```

---

### Task 3: Measure the cost and record it

**Files:**
- Modify: `bench/py_frontend/REPORT.md`, `vault/wiki/questions/q5-sink-matching-vs-purity-matching.md`, `vault/wiki/log.md`, `demos/case_studies/LOOP_LOG.md`

- [ ] **Step 1: Re-run the bench**

```bash
python -B bench/py_frontend/run_bench.py
```

Record all three measurements again. The benign-corpus counts are the number that matters: Task 1 made guards stricter, so E0720 and E0714 may now fire more on `tools/py_corpus{,2}`. Apply the same rule as before — a row whose benign count swamps its true positives goes behind `--strict` with its number published, and the decision is stated as a consequence of the number.

- [ ] **Step 2: Update `bench/py_frontend/REPORT.md`**

Add a section for this iteration. It must state plainly that the previous run's numbers were produced by a build with three false accepts, so the earlier "0 false negatives" line was measured against a corpus that did not contain these shapes. Do not quietly overwrite the old numbers — show both, and say why they differ.

- [ ] **Step 3: Update q5**

Extend `vault/wiki/questions/q5-sink-matching-vs-purity-matching.md`. The question generalizes: q5 answered "a NAME may not clear a call"; this iteration establishes the same for a VALUE, and shows the cost of getting the default backwards — three false accepts, one an RCE at the call site. Move guard-bound-elsewhere out of the Residual section and into Evidence, with what remains (object state mutated after construction, e.g. `session.verify = False`; import-time configuration) named as the surviving residual.

Keep source markers valid: `source_name` must be one of `README | keywords | effects | types | diagnostics` (`vault/CLAUDE.md`).

- [ ] **Step 4: Prepend to `vault/wiki/log.md` and append to `demos/case_studies/LOOP_LOG.md`**

LOOP_LOG entry in the established shape. The "gap confirmed empirically" line is the seven-case probe; the "TYPE gap surfaced" line is the surviving residual from Step 3.

- [ ] **Step 5: Full gate + commit**

```bash
python -B scripts/run_all.py
```

---

## Out of scope (deliberate)

- **`session.verify = False` (E-case in the probe).** Probed: silent — but for a different reason. Aether has **no detector that models TLS verification at all**, so there is nothing to gate. That is a missing-detector backlog item for the loop's normal q3 selection, not a guard bug. Do not add a detector inside this plan.
- **Import-time / module-scope configuration.** `_local_constants` is per-function by design. Module-level state needs a different traversal and its own probe.
- **Control flow.** A name bound differently in two branches is treated as disagreeing, which over-flags. Correct direction; modeling branches is out of scope for both this frontend and the Aether passes.
- **Positional guards.** `Guard.arg_index` exists and is exercised by no row today. It is two lines and the XXE parser is positional-or-keyword, so it is cheaper to have than to retrofit — but do not add rows that use it without a probe.
