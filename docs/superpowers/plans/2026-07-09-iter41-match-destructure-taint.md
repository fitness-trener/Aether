# Iteration 41 — Match-Destructure Taint (miss fix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close a confirmed **false accept** (the contract-breach class — over-flag-never-miss violated inside the modeled surface): a `match` arm binding destructured from a tainted scrutinee carries no taint, so `case Some(v) do print(v)` leaks a wrapped Secret (repro exit 0 today). Also record the iteration-40 residual correction: "stdlib transform propagation" is PHANTOM — generic leak-walk recursion already over-flags `print(trim(pw))`, `let t = trim(pw)`, and returns (probe: both prints fire E0712).

**Architecture:** Extend the shared fixpoint `_marked_tainted_names` in `transpiler/aether/passes/effects.py`: collect every `Match` node's `(pattern-bound names, scrutinee)`; in the fixpoint, when the scrutinee leaks the marker, all arm-pattern `BindPat` names become tainted (conservative: every arm, every binding — over-flag by design). One fix widens all eight sharing passes (E0712/E0715/E0724/E0725/E0726/E0728/E0729/E0730). No new diagnostic code; `Authorized` (E0716/E0717) uses the separate `_authorized_names` machinery and is untouched.

**Tech Stack:** Python stdlib only. AST shapes confirmed: `Match {"kind": "Match", "scrutinee": <expr>, "arms": [{"pattern": ..., "body": [...]}]}`; patterns `ConstructorPat {"path": [...], "args": [...]}` with `BindPat {"name": ...}` leaves. Match syntax: `match o do case Some(v) do ... end case None() do ... end end`.

## Global Constraints

- Windows: `python` (never `python3`), always `-B`. Full gate: `python -B scripts/run_all.py` exit 0.
- Non-breaking on gated corpus (false_positive gate: fixed.aeth + clean examples). alsp corpus has zero marker files; new taint applies only when a scrutinee already leaks a marker.
- No new diagnostic code → ratchet floors unchanged (40/30 remain satisfied); NO baseline edit.
- This is a fixed BUG in shipped detectors → append a `[FIXED <commit>]` entry to `BUGS.md` with a `test:` line (the ratchet's fixed-bugs-stay-fixed layer enforces the reference exists).
- Honesty wording unchanged: syntactic + intraprocedural with signature-level enforcement; the destructure fix removes a known false-accept, it does not make the pass "sound".
- Repro (exit 0 today): scratchpad `gap_d_match_destructure.aeth`. Phantom-probe (already flags): scratchpad `probe_stdlib_transform.aeth`.

## Interfaces produced

- `_pattern_bind_names(pat) -> Set[str]` — recursive `BindPat` name collector.
- `_marked_tainted_names` — same signature, now also propagates through match destructuring (behavior widened, callers unchanged).

---

### Task 1: Red tests

**Files:**
- Modify: `tests/test_effect_scope.py` — append tests before `if __name__`; register in runner (no banner change — codes unchanged).

**Interfaces:**
- Consumes: existing helpers `_sec_codes`, `_li_codes`, `_rl_codes`; `parse` imported.

- [ ] **Step 1: Write the failing tests**

```python
# --- Iter 41: taint through match-arm destructuring ----------------------
# A binding introduced by a match pattern over a tainted scrutinee must
# be tainted. Pre-fix this was a FALSE ACCEPT (the contract-breach
# class): case Some(v) do print(v) leaked a wrapped Secret at exit 0.

MATCH_LEAK_SRC = """
function f(pw: Secret<String>) returns Unit
  effects log
do
  let o: Option<Secret<String>> = Some(pw)
  match o do
    case Some(v) do
      print(v)
    end
    case None() do
      print("none")
    end
  end
end
"""


def test_match_destructured_secret_rejected():
    assert _sec_codes(MATCH_LEAK_SRC) == ["E0712"], \
        "a binding destructured from a tainted scrutinee must be tainted"
    print("E0712: match-destructured secret rejected")


def test_match_destructured_untrusted_rejected():
    src = """
function f(q: Untrusted<String>) returns Unit
  effects log
do
  let o: Option<Untrusted<String>> = Some(q)
  match o do
    case Some(v) do
      print(v)
    end
    case None() do
      print("none")
    end
  end
end
"""
    assert _li_codes(src) == ["E0724"], \
        "untrusted destructured from a tainted Option must stay untrusted"
    print("E0724: match-destructured untrusted rejected")


def test_match_clean_scrutinee_clean():
    src = """
function f() returns Unit
  effects log
do
  let o: Option<String> = Some("plain")
  match o do
    case Some(v) do
      print(v)
    end
    case None() do
      print("none")
    end
  end
end
"""
    assert _sec_codes(src) == [] and _li_codes(src) == [], \
        "destructuring an untainted scrutinee must not taint the binding"
    print("E0712/E0724: clean scrutinee destructure passes clean")


def test_match_revealed_arm_clean():
    src = """
function f(pw: Secret<String>) returns Unit
  effects log
do
  let o: Option<Secret<String>> = Some(pw)
  match o do
    case Some(v) do
      print(reveal(v))
    end
    case None() do
      print("none")
    end
  end
end
"""
    assert _sec_codes(src) == [], \
        "reveal() of the destructured binding is the sanctioned exit"
    print("E0712: reveal() of destructured binding passes clean")


def test_match_destructured_return_laundered_rejected():
    src = """
function f(pw: Secret<String>) returns String
  effects pure
do
  let o: Option<Secret<String>> = Some(pw)
  match o do
    case Some(v) do
      return v
    end
    case None() do
      return "none"
    end
  end
end
"""
    assert _rl_codes(src) == ["E0730"], \
        "returning a destructured tainted binding under a plain type launders"
    print("E0730: match-destructured return laundering rejected")
```

Register the 5 names in the runner after `test_unit_function_clean()` (banner stays `E0710..E0730`).

- [ ] **Step 2: Run to verify failure**

Run: `python -B tests/test_effect_scope.py`
Expected: FAIL at `test_match_destructured_secret_rejected` — `[] != ["E0712"]`. All pre-existing tests pass first.

- [ ] **Step 3: Commit red**

```bash
git add tests/test_effect_scope.py
git commit -m "test: iter-41 red tests - match-destructure taint miss"
```

---

### Task 2: Fix the shared fixpoint

**Files:**
- Modify: `transpiler/aether/passes/effects.py` — `_marked_tainted_names` (line ~556) + new `_pattern_bind_names` directly above it.

**Interfaces:**
- Produces: `_pattern_bind_names(pat) -> Set[str]`; widened `_marked_tainted_names` (same signature).

- [ ] **Step 1: Add the pattern-bind collector** (insert directly above `_marked_tainted_names`)

```python
def _pattern_bind_names(pat: Any) -> Set[str]:
    """Names bound by a match pattern (BindPat leaves, recursively —
    nested constructor patterns included)."""
    out: Set[str] = set()
    if isinstance(pat, dict):
        if pat.get("kind") == "BindPat" and "name" in pat:
            out.add(pat["name"])
        for v in pat.values():
            out |= _pattern_bind_names(v)
    elif isinstance(pat, list):
        for x in pat:
            out |= _pattern_bind_names(x)
    return out
```

- [ ] **Step 2: Widen the fixpoint.** In `_marked_tainted_names`: extend `collect` to also gather match destructures, and the fixpoint to propagate through them. Replace the body after the seed line with:

```python
    binds: List[Tuple[str, Any]] = []
    destructures: List[Tuple[Set[str], Any]] = []  # (arm-bound names, scrutinee)

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node and "value" in node:
                binds.append((node["name"], node["value"]))
            if node.get("kind") == "Match" and "scrutinee" in node:
                names: Set[str] = set()
                for arm in node.get("arms", []):
                    names |= _pattern_bind_names(arm.get("pattern"))
                if names:
                    destructures.append((names, node["scrutinee"]))
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(fn_decl.get("body", []))
    changed = True
    while changed:
        changed = False
        for name, value in binds:
            if name not in tainted and _expr_leaks_marked(value, tainted, unwrap, source_fns, param_mask):
                tainted.add(name)
                changed = True
        for names, scrut in destructures:
            if not names <= tainted and _expr_leaks_marked(scrut, tainted, unwrap, source_fns, param_mask):
                tainted |= names
                changed = True
    return tainted
```

Update the docstring to add: "Match-arm pattern bindings over a tainted scrutinee are tainted (every arm, every binding — conservative)."

- [ ] **Step 3: Suite green**

Run: `python -B tests/test_effect_scope.py`
Expected: PASS, banner `E0710..E0730 ALL REACH-SCOPE TESTS PASS`.

- [ ] **Step 4: Repro refuses; full gate**

Run: `python -B -m transpiler.aether.cli check "<scratchpad>\gap_d_match_destructure.aeth"`
Expected: nonzero, `E0712`.
Run: `python -B scripts/run_all.py`
Expected: exit 0 (ratchet still `40 codes >= floor 40, 30 detectors >= floor 30`; false_positive gate green — the propagation only fires on already-tainted scrutinees).

- [ ] **Step 5: Commit**

```bash
git add transpiler/aether/passes/effects.py
git commit -m "fix: taint match-arm bindings destructured from a tainted scrutinee (iter 41)"
```

---

### Task 3: BUGS.md entry, doc prose, playground example

**Files:**
- Modify: `BUGS.md` — append a `[FIXED <commit-of-task-2>]` entry (read the file's entry format first and mirror it; the entry MUST contain a `test: tests/test_effect_scope.py` line — the ratchet's fixed-bugs layer verifies the file exists)
- Modify: `grammar/diagnostics.md` — extend the iteration-39/40 marker-flow prose paragraph
- Create: `playground/examples/26_match_destructure_leak.aeth`

**Interfaces:**
- Consumes: Task 2's commit hash (from `git log --oneline -1` after Task 2).

- [ ] **Step 1: BUGS.md entry** (mirror the file's existing entry structure; content:)

```markdown
## B<next-number>: match-arm bindings dropped taint (false accept) [FIXED <task-2-commit>]

- **Found:** 2026-07-09, iter-41 gap probe. `case Some(v) do print(v) end`
  over `Option<Secret<String>>` checked clean (exit 0) — a genuine MISS
  inside the modeled surface, violating the over-flag-never-miss
  contract of every confidentiality-marker pass (E0712/E0715/E0724/
  E0725/E0726/E0728/E0729/E0730).
- **Cause:** the shared fixpoint `_marked_tainted_names` collected only
  Let/Assign bindings; match-pattern `BindPat` names were fresh,
  untainted names.
- **Fix:** destructure propagation — every arm-pattern binding over a
  leaking scrutinee is tainted (conservative, all arms).
- test: tests/test_effect_scope.py
```

- [ ] **Step 2: Doc prose** — in `grammar/diagnostics.md`, append to the marker-flow paragraph (after the iteration-40 E0730 sentence):

```markdown
Iteration 41 fixed a false accept in the shared dataflow: `match`-arm
pattern bindings destructured from a tainted scrutinee are now tainted
(every arm, every binding — conservative), so wrapping a marked value
in `Some(...)`/`Ok(...)` and unwrapping it via `match` no longer washes
the marker.
```

- [ ] **Step 3: Playground example** — `playground/examples/26_match_destructure_leak.aeth`:

```
// Example 26 — Match-destructure leak (iter 41). The Secret is wrapped
// in an Option and unwrapped via match: the arm binding `v` is a fresh
// name, and before iteration 41 it silently dropped the marker - this
// exact program checked CLEAN (a false accept, the one failure the
// over-flag contract forbids). Now the destructured binding stays
// tainted: [E0712]. The sanctioned exit is reveal(v) inside the arm.

module TokenCache
  requires capability log
  exports main
end

function main(pw: Secret<String>) returns Unit
  effects log
do
  let o: Option<Secret<String>> = Some(pw)
  match o do
    case Some(v) do
      print(v)
    end
    case None() do
      print("none")
    end
  end
end
```

Verify: `python -B -m transpiler.aether.cli check playground/examples/26_match_destructure_leak.aeth` → nonzero, `E0712`.

- [ ] **Step 4: Full gate** (the ratchet fixed-bugs layer now checks the BUGS.md `test:` reference)

Run: `python -B scripts/run_all.py`
Expected: exit 0, ratchet line includes `1 FIXED bug(s), all with a live regression test` (or increments the existing count).

- [ ] **Step 5: Commit**

```bash
git add BUGS.md grammar/diagnostics.md playground/examples/26_match_destructure_leak.aeth
git commit -m "docs: BUGS.md fixed entry, prose, playground example 26 (iter 41)"
```

---

### Task 4: Record & compound (including the phantom-residual correction)

**Files:**
- Modify: `demos/case_studies/LOOP_LOG.md` — `## Iteration 41 — match-destructure taint (a false accept, found and fixed)` before the `## Infra` section
- Modify: `vault/wiki/questions/q1-taint-marker-soundness-boundary.md` — two Evidence rows (miss closed; phantom correction), rescope Recommended Actions
- Modify: `vault/wiki/log.md` — prepend entry

**Interfaces:**
- Consumes: probe results (this plan's Global Constraints), Task 2/3 commits.

- [ ] **Step 1: LOOP_LOG block** containing: how the gap was found (probing the recorded stdlib residual first, per method step 2 — the probe PROVED THE RESIDUAL PHANTOM: `print(trim(pw))` and `let t = trim(pw); print(t)` both already fire E0712 via generic leak-walk recursion; no-op iteration avoided); the real gap found in the same probe session (match destructure, exit 0, a FALSE ACCEPT — the contract-breach class, strictly worse than any missing detector); the fix (destructure propagation in the shared fixpoint — one edit widens 8 passes; `Authorized` untouched, separate machinery); BUGS.md `[FIXED]` entry with ratchet-locked regression test; no new code → floors unchanged at 40/30; **TYPE gap surfaced for next iter:** E0717 value-equality/alias reasoning for resource ids (the last big q1 remaining item) — currently over-flag-only (`let id2 = id1` refused), a *precision* target, plus HOF/function-typed callees (still skipped by E0729) as the remaining miss-side surface.

- [ ] **Step 2: q1 update** — Evidence rows: (a) "Match-destructure MISS found & closed (iter 41): arm bindings over a tainted scrutinee were fresh untainted names — a genuine false accept inside the modeled surface (the contract breach); fixed by conservative all-arm propagation in `_marked_tainted_names`; BUGS.md entry with ratchet-locked test"; (b) "CORRECTION: iter-40's 'stdlib transform propagation' residual was PHANTOM — the leak walk's generic recursion into unmodeled calls already over-flags `trim(secret)` at sinks, bindings, and returns; probe recorded 2026-07-09. Lesson: residuals must be probe-confirmed before entering the backlog, same as gaps." Rescope Recommended Actions remaining list to: E0717 value-equality/alias reasoning, HOF/function-typed callees, boundary-sanitizer coarseness. `last_updated` stays 2026-07-09.

- [ ] **Step 3: vault log** — prepend: `[2026-07-09] iter 41 | match-destructure false accept fixed; stdlib-transform residual proven phantom` with two-line summary and the lesson (probe residuals like gaps).

- [ ] **Step 4: Final gate + commit**

Run: `python -B scripts/run_all.py`
Expected: exit 0.

```bash
git add demos/case_studies/LOOP_LOG.md vault/wiki/questions/q1-taint-marker-soundness-boundary.md vault/wiki/log.md
git commit -m "record: iter-41 LOOP_LOG, q1 miss-closed + phantom-residual correction"
```
