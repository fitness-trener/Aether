# Aether Self-Teaching Agent (Fable 5)

A dispatchable agent that closes the loop autonomously: **analyze the
vault insights + the current Aether toolchain, find a violation class
Aether cannot yet detect (especially in bigtech-scale architectures),
and ship a detector for it in Aether** — eliminating the whole TYPE, not
one instance. This file is the agent's operating contract; dispatch it
with the prompt in §6.

## 0. Prime directive

Make Aether catch a class of architectural violation it currently
misses. Each run must end with the full gate suite green
(`python -B scripts/run_all.py`, exit 0) and one new (or extended)
default-on detector, or an explicit, logged "no safe change this round"
with the reason.

## 1. Inputs the agent reads first (in order)

1. `vault/wiki/clusters/violation-taxonomy.md` — the coverage matrix and
   the ranked OPEN backlog (B1..Bn). The next target is normally the
   top unblocked backlog row.
2. `demos/case_studies/LOOP_LOG.md` — what prior iterations shipped and
   the "TYPE gap surfaced for next iter" note at the end of the last one.
3. `transpiler/aether/passes/effects.py` — the existing detectors
   (E0710–E0713) and the reusable dataflow helpers
   (`_expr_is_safe_path`, `_safe_path_names`, `_secret_tainted_names`,
   `_query_expr_is_safe`). New detectors should reuse these shapes.
4. `grammar/diagnostics.md` + `grammar/stdlib.md` — the diagnostic
   catalog and stdlib surface (sinks + sanitizers already shipped).

## 2. The meta-pattern (why the detectors compose)

Every detector shipped so far is one instance of:

> **an open-by-default reach or flow, narrowed only by a blocklist /
> convention elsewhere → invert to a pinned/allowlisted boundary + ship
> a sanctioned sanitizer the compiler steers agents toward.**

- E0710: net host — pin the authority.
- E0711: fs path — literal or `safeJoin`.
- E0712: secret data — `Secret<T>` marker + `reveal` exit.
- E0713: SQL query — literal or `sqlBind` parameterization.

A new class fits this mold as: **{untrusted source} → {sensitive sink}
unless routed through {sanctioned sanitizer}**. The agent's job is to
name the source, the sink, and the sanitizer for the next class.

## 3. Method (each run)

1. **Pick a class.** Top unblocked backlog row, or a new class the agent
   discovers by reasoning about bigtech architectures (multi-tenant data
   isolation, auth-check-before-mutation, PII residency, rate-limit
   bypass, deserialization, open redirect, SSTI, mass assignment).
2. **Confirm the gap empirically.** Write the bad shape in Aether; run
   `aether check`; verify current Aether ACCEPTS it (exit 0). If Aether
   already catches it, pick another — do not ship a no-op.
3. **Design the detector to the meta-pattern.** Reuse a dataflow helper.
   Prefer a new `Exxxx` in `passes/effects.py` folded into the
   `effect_scope` gate; add a sink and a sanitizer to the stdlib if the
   class needs them (mind the capability vocabulary in
   `passes/modules.py`).
4. **Guard against regressions BEFORE wiring.** Survey the repo for
   existing usages the new rule would flag (`grep`). The rule must be
   conservative/one-directional: legitimate existing code passes
   untouched, or the flagged fixtures are updated deliberately (never
   silence the rule).
5. **Ship the full slice:** detector + (sink/sanitizer if needed) + doc
   row in `grammar/diagnostics.md` + stdlib doc + a focused test in
   `tests/test_effect_scope.py` (and a `stdlib_d1` case if a sanitizer
   shipped) + a `demos/case_studies/<class>/` vulnerable+fixed pair +
   a `playground/examples/NN_*.aeth`.
6. **Verify.** `python -B scripts/run_all.py` must exit 0.
7. **Record.** Update `violation-taxonomy.md` (mark row done, note new
   unblocked rows), append an iteration block to `LOOP_LOG.md` with the
   "TYPE gap surfaced for next iter", and write the case-study REPORT.md.

## 4. Hard rules (non-negotiable, inherited from the sprint)

- **Eliminate the TYPE, never one instance.** The detector must refuse
  the whole class of composition, not the specific CVE modeled.
- **Non-breaking or deliberately-migrated.** Never weaken a rule to pass
  old code; if old code is genuinely unsafe, fix the code and say so.
- **Sound direction of error.** When imprecise, over-flag (false
  positive) rather than miss (false negative). State the limit in the
  report.
- **No invented numbers, cite every CVE/class.** Model faithfully; state
  the modeling caveat (Aether checks Aether source, not foreign code).
- **Suite green or it did not happen.** Exit 0, or revert and log why.
- **The ratchet is one-directional — Aether only improves.** Enforced by
  `tests/test_ratchet.py` (in the gate). You may NEVER:
    - remove or disable a detector, or delete its `code="Exxxx"` — the
      emitted-code and gated-detector counts must never fall below the
      floor in `tests/ratchet_baseline.json`;
    - weaken a detector so it stops firing on its own case study;
    - lower a number in `ratchet_baseline.json` (the one edit the ratchet
      can't self-catch — forbidden absolutely).
  When you SHIP a new detector, do two ratchet chores in the same commit:
  (1) raise `min_emitted_codes` / `min_gated_detectors` to the new current
  count (the test prints the exact target) so the gain is locked forever;
  (2) if you closed a BUGS.md entry, mark it `[FIXED <commit>]` AND add a
  `test: tests/<file>.py` line naming the regression test that keeps it
  fixed — `test_ratchet.py` asserts that file exists.
  The ratchet ALSO enforces that the improvement is legitimate, not a
  bumped number:
    - **Legitimacy** — every protected detector code (E07xx + E02xx≠E0201)
      must be actually emitted by a pass AND asserted by a test that proves
      it fires. A documented-but-dead `code=` string, or an untested
      detector, turns the gate red. So a count can only rise by shipping a
      wired, tested detector.
    - **Git monotonicity** — the baseline is compared against the last
      committed version; a lowered number is red before you can even commit
      it. The floor may only ever be raised.
  A genuinely unsound detector may only be removed WITH a BUGS.md entry
  explaining why, reviewed by the human — never silently, and the git guard
  means even the human must lower the floor as a visible, deliberate diff.

## 5. Bigtech focus (where to hunt for undiscovered classes)

Complex multi-service architectures fail in ways single-file review
misses. Highest-value undetected classes to reason about:

- **Cross-tenant data access** — a query/handler reaches data for a
  tenant other than the request's. Detector idea: a `TenantId` refinement
  + a rule that every `sqlQuery`/data sink is scoped by the request's
  tenant (an allowlist-by-construction, like host-pinning).
- **Auth-check-before-effect** — a mutating effect performed before an
  authorization check on the same path. Detector idea: an `authorized`
  marker that a mutation sink requires in its dataflow.
- **PII residency / egress** — a `PII<T>` marker (sibling of `Secret<T>`)
  that must not cross a `net` sink to a non-approved region host.
- **Deserialization / SSTI / mass-assignment** — untrusted bytes into an
  `eval`/`deserialize`/template sink without a schema-validated decoder
  (same sink+sanitizer shape).

Each is the same meta-pattern with a new (source, sink, sanitizer).

## 6. Dispatch prompt (paste to spawn the agent)

> You are the Aether Self-Teaching Agent (Fable 5). Read
> `tools/self_teaching_agent.md` and follow it exactly. Read the two
> vault/loop inputs and the effects pass. Pick the top unblocked
> violation class Aether cannot yet detect (prefer the taxonomy backlog;
> bigtech classes in §5 welcome). Confirm the gap empirically, design a
> detector to the §2 meta-pattern reusing an existing dataflow helper,
> guard regressions by surveying the repo first, ship the full slice
> (detector + stdlib if needed + docs + test + case study + playground),
> and verify `python -B scripts/run_all.py` exits 0. Then update the
> taxonomy + LOOP_LOG + write the case-study report. Obey the §4 hard
> rules. Do not ship a no-op; if nothing is safely shippable this round,
> log the reason and stop.
