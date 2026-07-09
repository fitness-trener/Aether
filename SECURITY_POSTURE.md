# Aether Security Posture — the architectural-violation classes the compiler refuses

Aether's compiler refuses to emit code that composes an architecturally
unsound program. Beyond the base passes (effect locality E0801, capability
scope E0701–E0704, refinement boundaries E0301/E0302/E0305), a default-on
**reach-scope** pass refuses 14 concrete security-violation classes. All
are opt-out with `--no-scope-check`; all emit structured, machine-readable
diagnostics an agent fix-loop acts on; the full catalog is in
`grammar/diagnostics.md`.

## The 14 classes (built by the self-teaching loop, iters 1–19)

| Code | Class | CWE | Family | Sanctioned repair |
|------|-------|-----|--------|-------------------|
| E0710 | SSRF — unpinned fetch scope | 918 | effect-string | pin the host |
| E0711 | Path traversal / Zip-Slip | 22 | sink+literal | `safeJoin` |
| E0712 | Secret exfil to log/disk | 532 | taint | `reveal` |
| E0713 | SQL injection | 89 | sink+literal | `sqlBind` |
| E0714 | Command injection | 78 | sink+literal | `shellArg` |
| E0715 | PII egress (GDPR) | 359 | taint | `redact` |
| E0716 | Missing authorization | 862/863 | taint (inverted) | `authorize` |
| E0717 | Cross-tenant / IDOR | 639 | taint (resource-bound) | `authorizeResource` |
| E0718 | Open redirect | 601 | sink+literal | `safeRedirect` |
| E0719 | Template injection / SSTI | 94 | sink+literal | fixed template / `trusted` |
| E0720 | Insecure deserialization | 502 | sink+literal | `schemaDecode` / `trusted` |
| E0721 | Cleartext transmission | 319 | effect-string | `https://` |
| E0722 | SSRF to cloud metadata (IMDS) | 918 | effect-string | use the credential provider |
| E0723 | Hardcoded credential | 798 | literal-content | source from env / secret manager |

## Four detector families (the reusable shapes)

1. **sink+literal** — a dangerous sink (`sqlQuery`, `shellExec`,
   `writeFile`, `renderTemplate`, `deserialize`, `redirect`) must receive a
   fixed literal or a sanctioned sanitizer; a concatenation / untrusted
   expression is refused.
2. **taint** — a marker type (`Secret<T>`, `PII<T>`, `Authorized<T>`)
   whose value must not reach a sink (E0712/E0715) or, inverted, whose
   proof a sink *requires* (E0716/E0717). Straight-line, intraprocedural,
   over-flag-never-miss (see `vault/wiki/questions/q1`).
3. **effect-string** — a property read straight off the declared
   `net.fetch` effect annotation: host pinning (E0710), scheme (E0721),
   destination range (E0722).
4. **literal-content** — a scan of string literals for credential shapes
   (E0723) — a secret scanner built into the compiler.

## The credibility triangle (three gated suites)

A security checker is only trustworthy if it catches bad code, leaves good
code alone, AND its fixes actually work at runtime. All three are gated:

| Property | Suite | Evidence |
|----------|-------|----------|
| **Catches bad** | `test_effect_scope.py` | every E07xx fires on its violation |
| **Passes good** | `test_false_positive_corpus.py` | 31 legitimate programs, **0** diagnostics |
| **Not theater** | `test_runtime_enforcement.py` | 8 sanitizers defang a real payload end-to-end |

The false-positive corpus is every `fixed.aeth` across the repo plus the
clean playground examples — if any detector ever over-flags legitimate
use of a guarded sink, that gate goes red.

## Composition is verified

`demos/case_studies/composition_kitchen_sink/aether/multi_violation.aeth`
is one module with seven independent violations; `aether check` emits all
seven diagnostics at once. `tests/test_effect_scope.py::
test_detectors_compose_additively` asserts this — the passes accumulate,
none masks another.

## Real-world validation

`bench/REALWORLD_VALIDATION.md` shows the detectors firing on the
documented vulnerable shapes of five hundred-million-scale projects /
incidents (requests, subprocess, Flask, PyYAML, the Capital One 2019
breach). Honestly scoped: faithful models with auditable 1:1 maps, not a
live-repo scan.

## What is deliberately NOT covered (honest boundary)

- **Provenance / source-taint** — taint originates at marker-typed params,
  not from `readFile`/network reads. The standing structural investment
  (`vault/wiki/questions/q3`), repeatedly surfaced by the loop.
- **Noisy-inference classes** — div-by-zero / index-OOB preconditions
  (B3), TOCTOU (B4), unbounded-resource DoS (B5) are parked until a clean
  static signal exists.
- **Runtime vs static** — refinement/capability guarantees that fire at
  runtime are runtime guarantees, never presented as static proof.

## Reproduce everything

    python -B scripts/run_all.py            # full gate, exit 0 = green
    python -B tests/test_effect_scope.py    # the 14-class reach-scope suite
