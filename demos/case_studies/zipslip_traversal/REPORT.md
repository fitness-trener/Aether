# Case Study + Aether Improvement: Path traversal / Zip-Slip

**Date:** 2026-07-04
**Loop iteration:** 2
**Target:** the Zip-Slip class (Snyk 2018 disclosure; thousands of
downstream CVEs across archive extractors, and the same shape in
avatar-upload / "download to path" arbitrary-file-write bugs).
CWE-22 (path traversal) / CWE-434 (unrestricted upload).

## 1. The failure class (TYPE, not instance)

Every path-traversal bug has one precondition: a filesystem read/write
whose **path is derived from untrusted input without a containment
guarantee**. A malicious archive entry named `../../../../etc/cron.d/evil`
climbs out of the intended directory and overwrites an arbitrary file.
A fixed literal path cannot be steered; a path routed through a
containment helper cannot escape. Everything else is the precondition.

## 2. The gap this exposed in Aether (before this iteration)

Aether modeled fs effects as bare `fs.read` / `fs.write` with **no path
scope at all** — `record_effect("fs","write")` carried nothing. So a
crawler/extractor that wrote `writeFile(baseDir + entryName, body)`
passed every gate: the effect was declared, the capability was granted,
and there was no notion of the path being dangerous.

## 3. The improvement — eliminates the TYPE

New default-on diagnostic **E0711** (`check_fs_path_safety` in
`passes/effects.py`): a `readFile`/`writeFile` call whose path argument
is neither a fixed string literal nor a `safeJoin(...)`-sanitized value
is a compile error. Plus a new stdlib sanitizer **`safeJoin(base, rel)`**
(pure) that strips `..`, `.`, absolute roots, and drive/backslash
prefixes so the result is guaranteed to stay under `base` — the
sanctioned repair the compiler steers every agent toward.

Detection includes a lightweight **per-function dataflow**: a variable
bound only to literals or `safeJoin` results is treated as a safe path,
so the idiomatic fix `let p = safeJoin(dir, name); writeFile(p, body)`
is accepted (no false positive on the real fix shape).

| Path expression at a fs sink | Verdict |
|---|---|
| `writeFile("/tmp/fixed.log", x)` | ALLOW (literal) |
| `writeFile("../secrets/x", x)` | REJECT (literal escapes) |
| `writeFile(base + "/" + name, x)` | REJECT (dynamic/steerable) |
| `writeFile(name, x)` | REJECT (bare untrusted param) |
| `writeFile(safeJoin(base, name), x)` | ALLOW (sanitized) |
| `let p = safeJoin(base, name); writeFile(p, x)` | ALLOW (dataflow) |

Because it targets the *shape of the sink call*, the same rule
forecloses Zip-Slip in any archive extractor, avatar-upload traversal,
and "download to user path" arbitrary-write — not just this extractor.
Opt-out: `--no-scope-check` (shared umbrella with E0710).

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0711] error (capability) at line 24: function 'writeEntry' calls
  'writeFile' with an unsafe path (path is a dynamic expression - route
  it through safeJoin()); a path traversal here can read or overwrite
  arbitrary files
exit 2

$ aether check aether/fixed.aeth
OK (4 decls)
```

`safeJoin` verified to neutralize traversal at runtime:
```
safeJoin("uploads", "../../etc/passwd")  -> uploads/etc/passwd
safeJoin("uploads", "/etc/shadow")       -> uploads/etc/shadow
safeJoin("uploads", "a/../../../b")      -> uploads/a/b
```

## 5. Regression posture

- Surveyed every `writeFile`/`readFile` call in the repo first: **all
  use string literals**, so E0711 fires zero times on the existing
  corpus — non-breaking by construction.
- New `safeJoin` added to the stdlib registry (auto-exported `_ae_`
  name), documented in `grammar/stdlib.md`, covered by a new
  `stdlib_d1` case + unit assertion.
- E0711 folded into the existing `effect_scope` gate; full suite is
  **24/24 green** (unchanged gate count — E0710 and E0711 share the
  reach-scope gate). E0711 documented in `grammar/diagnostics.md`; D.2
  catalog test stays green.
- Playground example 12 added (demoable).

## 6. Honesty

- Same modeling caveat as prior studies: a faithful model of the class,
  not a scan of a specific extractor's source.
- E0711 detects the **static** precondition (dynamic path into a sink).
  It does not model symlink-following or a `safeJoin` base that is
  itself attacker-controlled; those are runtime/config concerns. The
  claim is "removes the untrusted-path-into-sink precondition, and ships
  the containment primitive," which is what the class relies on.
- Dataflow is straight-line and forward (a name defined before use). A
  name used before its safe binding, or reassigned across a loop back-
  edge, may be over-flagged (false positive, never a missed vuln) — the
  safe direction to err.

## 7. Files

```
aether/vulnerable.aeth   dynamic extractor path   -> E0711
aether/fixed.aeth        safeJoin-contained path  -> OK
```
Playground: `playground/examples/12_path_traversal.aeth`.
Insight backlog: `vault/wiki/clusters/violation-taxonomy.md`.
