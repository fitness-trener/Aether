# Aether Improvement Loop — Log

Autonomous loop: find a real OSS program with an architecture-class
bug, run Aether on a faithful model, then improve Aether to eliminate
the *TYPE* of problem (not the single instance) so it won't repeat on
similar programs. Each iteration builds on the previous report.

State carried forward: the full gate suite must stay green
(`python -B scripts/run_all.py`, exit 0) after every iteration.

---

## Iteration 0 (seed) — Log4Shell (CVE-2021-44228)

- **Target:** Apache Log4j 2 JNDI RCE. A `void log(String)` that opened
  a socket via message-lookup substitution.
- **Aether result:** the composition does not compile — E0801 (effect
  leak) then E0701 (capability) on the lazy fix. Python + `mypy --strict`
  accept it.
- **Report:** `demos/case_studies/log4shell/REPORT.md`.
- **TYPE gap surfaced:** enforcement is only as deep as the declared
  scope; a broad declared scope is a hole. → drove iteration 1.
- **Suite:** 23/23 green.

## Iteration 1 — SSRF via unpinned fetch scope (crawl4ai CVE-2026-53754)

- **Target:** crawl4ai SSRF (incomplete CIDR blocklist → cloud metadata
  169.254.169.254; fixed 0.8.8 by host allowlisting). Siblings: FlaskBB
  CVE-2026-46556, OpenCTI CVE-2026-21887.
- **Gap confirmed empirically:** current Aether accepted `net.fetch("*")`
  reaching 169.254.169.254 (exit 0). Both existing gates satisfied by a
  wildcard scope.
- **Improvement (eliminates TYPE):** new default-on pass + diagnostic
  **E0710** (`check_effect_scope` in `passes/effects.py`) — a `net.fetch`
  whose host/authority is unpinned is a compile error. Path/query
  wildcards and `*.subdomain` pins still allowed. Closes the
  open-by-default fetch-scope precondition for ALL programs, not just
  the crawler. Opt-out `--no-scope-check`.
- **Wiring:** cmd_check + cmd_run; doc row in `grammar/diagnostics.md`;
  test `tests/test_effect_scope.py`; gate line in `scripts/run_all.py`;
  playground example 11.
- **Report:** `demos/case_studies/crawl4ai_ssrf/REPORT.md`.
- **TYPE gap surfaced for next iter:** the filesystem sibling —
  `fs.read`/`fs.write` with an unpinned / absolute / `..`-bearing path
  is the path-traversal (Zip-Slip / arbitrary-file-write) precondition.
  Currently stdlib fs effects carry NO path arg at all (`(("fs","write"),
  None)`), so there is no scope to pin yet. Candidate next target:
  a real path-traversal CVE (e.g. a tar/zip extractor or a static-file
  server) → give fs effects a path scope + an E0711-style pin check.
- **Suite:** 24/24 green.

## Iteration 2 — Path traversal / Zip-Slip (Snyk 2018 class, CWE-22/434)

- **Target:** archive-extractor / upload path traversal. `writeFile(baseDir
  + entryName, ...)` where entryName is `../../../../etc/...`.
- **Gap confirmed:** fs effects carried NO path scope; a dynamic path
  into writeFile/readFile passed every gate.
- **Improvement (eliminates TYPE):** new diagnostic **E0711**
  (`check_fs_path_safety`) — a fs sink path that is not a literal or a
  `safeJoin(...)` result is a compile error. New stdlib **`safeJoin`**
  (pure sanitizer, strips `..`/absolute roots) is the sanctioned repair.
  Lightweight per-function dataflow recognizes `let p = safeJoin(...)`.
- **Wiring:** folded into the `effect_scope` gate (shared `--no-scope-check`);
  doc rows in `grammar/diagnostics.md` + `grammar/stdlib.md`; tests in
  `tests/test_effect_scope.py` + `tests/test_stdlib_d1.py`; playground
  example 12.
- **Vault:** created `vault/wiki/clusters/violation-taxonomy.md` — the
  coverage matrix + OPEN backlog (B1..B8) the loop now pulls from.
- **Report:** `demos/case_studies/zipslip_traversal/REPORT.md`.
- **TYPE gap surfaced for next iter:** taxonomy backlog says the highest-
  leverage next addition is a **taint-lite provenance pass** (untrusted-
  source → sensitive-sink flow), which unlocks B1 (secret/PII exfil via
  log, CWE-532) and B2 (injection: SQL/command, CWE-89/78) together.
  Cheaper reuse-of-E0711-shape wins: B7 open-redirect, B2 injection
  (sink + sanitizer + pin).
- **Suite:** 24/24 green.

## Iteration 3 — Secret/PII exfil into logs (CWE-532, backlog B1)

- **Target:** the "accidentally logged the password/token" class.
- **Gap confirmed:** Aether had no notion of *sensitive data*; every pass
  reasoned about operations, none about the data flowing into them.
- **Improvement (eliminates TYPE):** Aether's first **taint-lite pass**.
  New marker type **`Secret<T>`** (erased at runtime), stdlib
  **`classify`** (wrap) + **`reveal`** (sanctioned unwrap), diagnostic
  **E0712** — a Secret value reaching `print` without `reveal` is a
  compile error. Param-origin taint, straight-line dataflow (reuses the
  E0711 skeleton), log sink only.
- **Wiring:** folded into `effect_scope` gate; docs in diagnostics.md +
  stdlib.md; tests in test_effect_scope.py; playground example 13.
- **Vault:** taxonomy B1 marked DONE; noted the taint pass now lowers the
  cost of B2 (injection) and the B1 extensions (net/fs sinks, source-side
  taint).
- **Report:** `demos/case_studies/secret_in_logs/REPORT.md`.
- **TYPE gap surfaced for next iter:** two cheap reuses now unlocked —
  (a) extend E0712 taint to the `writeFile`/network sinks and to
  `readFile`/network *sources* (secret-to-disk, untrusted-in); (b) B2
  injection (SQL/command) = the same taint dataflow + a modeled
  `db.query`/`exec` sink + a `param()`/`shellQuote()` sanitizer, mirroring
  safeJoin→E0711.
- **Suite:** 24/24 green.

## Iteration 4 — SQL injection (CWE-89, backlog B2)

- **Target:** untrusted parameter concatenated into a SQL query.
- **Gap confirmed:** no db sink existed; concatenated query was just a
  String, invisible to every pass (checked clean before).
- **Improvement (eliminates TYPE):** **E0713** (`check_injection`) — a
  `sqlQuery` arg that is raw concatenation, not a literal or
  `sqlBind(...)`, is a compile error. New stdlib `sqlQuery` sink (effect
  `db.query`) + `sqlBind` parameterizing sanitizer. Reuses the
  sink+sanitizer+literal dataflow shape.
- **Wiring:** effect + capability registries, folded into `effect_scope`
  gate; docs; tests; `stdlib_d1` escaping assertion; case study;
  playground 14. Non-breaking (`db` cap already known; no code calls
  sqlQuery). Suite 24/24 green.
- **Self-teaching agent established:** `tools/self_teaching_agent.md` —
  operating contract + dispatch prompt for a Fable-5 agent that reads the
  vault + toolchain, picks an undetected class, and ships a detector to
  the meta-pattern. Iteration 5 onward can be run by dispatching it.
- **Report:** `demos/case_studies/sql_injection/REPORT.md`.
- **TYPE gaps surfaced for next iter:** (a) command injection = clone the
  E0713 slice for a `shellExec` sink + `shellArg` (add `exec` to the
  capability vocab in `passes/modules.py`); (b) bigtech classes in the
  agent's §5 — cross-tenant data access, auth-before-mutation, PII
  egress/residency — each the same (source, sink, sanitizer) meta-pattern.
- **Suite:** 24/24 green.

## Iteration 5 — Command injection (CWE-78, backlog B2 remainder) — first self-teaching-agent run

- **Target:** untrusted input concatenated into a shell command line
  (OpenSSL c_rehash CVE-2022-1292 shape, CVSS 9.8: certificate file
  names concatenated into shell commands).
- **Gap confirmed empirically:** no exec sink existed; the concatenated
  `shellExec("convert " + filename + " out.png")` shape checked clean
  (exit 0) before this iteration.
- **Improvement (eliminates TYPE):** **E0714** (`check_command_injection`
  in `passes/effects.py`) — a `shellExec` arg that is raw concatenation
  (or any dynamic expression), not a literal or `shellArg(...)`, is a
  compile error. New stdlib `shellExec` sink (effect `exec.run`) +
  `shellArg` quoting sanitizer (POSIX single-quote, binds into `?` as
  ONE argument). New **`exec`** capability in the E0704 vocabulary.
  E0713 slice cloned exactly (sink+sanitizer+literal + straight-line
  dataflow).
- **Wiring:** effect + capability registries (`passes/effects.py`,
  `passes/capability.py`), `exec` in `passes/modules.py`, runtime funcs,
  folded into the `effect_scope` gate in `cli.py`; docs in
  `grammar/{diagnostics,stdlib}.md`; tests in `test_effect_scope.py` +
  `stdlib_d1` quoting assertions; case study
  `demos/case_studies/command_injection/`; playground example 15.
  Non-breaking (surveyed first: nothing in the repo used
  `shellExec`/`shellArg`/`exec`).
- **Report:** `demos/case_studies/command_injection/REPORT.md`.
- **TYPE gap surfaced for next iter:** B2's last remainder is
  template injection / SSTI (needs a template-render sink first). The
  higher-value hunt is the bigtech §5 classes, now that the marker-type
  pattern (`Secret<T>`) is proven: (a) **PII egress** — a `PII<T>`
  sibling of `Secret<T>` that must not reach a `net`/`fs.write` sink,
  which also delivers the B1 extension (secret-to-disk/wire) with the
  same machinery; (b) **auth-check-before-mutation** — an `Authorized<T>`
  marker a mutating sink requires in its dataflow. Both reuse
  `_secret_tainted_names` nearly verbatim.
- **Suite:** green, exit 0.

## Iteration 6 — PII egress (GDPR / data-residency)

- **Target:** personal data (email/name/device id) logged or persisted
  to disk in the clear — the bigtech privacy-postmortem class.
- **Gap confirmed:** the iter-3 taint pass covered only `Secret`→`print`;
  a `PII<String>` value logged + written to disk checked clean before.
- **Improvement (eliminates TYPE):** **generalized the taint core** —
  `_marked_tainted_names(fn, marker, unwrap)` + `_expr_leaks_marked`
  now back both detectors (`Secret`/E0712 became thin wrappers,
  behavior unchanged). Added **`PII<T>`** marker + `classifyPII` +
  masking **`redact`**, and **E0715** (`check_pii_flow`): a PII value
  reaching `print` or `writeFile` **contents** (arg 1 only) without
  `redact(...)` is refused.
- **Wiring:** folded into `effect_scope` gate; docs in diagnostics.md +
  stdlib.md; tests in test_effect_scope.py (+ redact `stdlib_d1`
  assertions); case study `pii_egress/`; playground example 16.
  Non-breaking (no `PII<>` in corpus). Suite 24/24 green.
- **Report:** `demos/case_studies/pii_egress/REPORT.md`.
- **TYPE gaps surfaced for next iter:** (a) the taint core is now generic
  — **auth-check-before-mutation** via an `Authorized<T>` marker that a
  mutating sink (e.g. `sqlExec`/`writeFile`) requires in scope is the
  next high-value bigtech class, near-verbatim reuse; (b) **cross-tenant
  data access** — a `TenantScoped<T>` marker requiring every data sink be
  bound to the request tenant; (c) template/SSTI = clone the injection
  slice once a template-render sink exists; (d) secret→disk/net sinks +
  source-side taint (readFile/network reads).
- **Suite:** 24/24 green, exit 0.

## Iteration 7 — missing authorization before mutation (CWE-862/863)

- **Target:** a data-mutating operation reachable with no authorization
  check on its path — the bigtech broken-authorization class (OWASP
  API1/API5; Ivanti EPMM CVE-2023-35078 shape: an unauthenticated
  mutating API path). Survives review because every function is locally
  fine; the missing guard is an *absence*, invisible locally.
- **Gap confirmed:** an unauthorized `sqlExec` mutation — effect
  declared, capability granted, query parameterized with `sqlBind` —
  checked clean (exit 0) before this iteration.
- **Improvement (eliminates TYPE):** the taint core **inverted**: every
  prior detector says "a marked value must NOT reach a sink"; **E0716**
  (`check_authorization`) says "a mutating sink REQUIRES a marked value
  in its dataflow". New stdlib mutating sink **`sqlExec(stmt, auth)`**
  (effect `db.exec`, existing `db` capability), new marker
  **`Authorized<T>`**, new guard **`authorize(principal, action)`**.
  The proof is accepted as a direct `authorize(...)` call, an
  `Authorized<T>` param (caller's proof crossing the boundary), or a
  name bound only to those (allowlist fixpoint, `_safe_path_names`
  shape + `_is_marker_type`). Absent/unproven → refused (over-flag,
  never miss). `sqlExec`'s query arg also joined `_SQL_SINKS`, so
  E0713 covers injection on the new write sink.
- **Wiring:** folded into the `effect_scope` gate in `cli.py`; registries
  in `passes/effects.py` + `passes/capability.py`; runtime
  `sqlExec`/`authorize`; docs in `grammar/{diagnostics,stdlib}.md`;
  6 tests in `test_effect_scope.py` + `stdlib_d1` runtime assertions;
  case study `demos/case_studies/missing_authorization/`; playground
  example 17. Non-breaking (surveyed first: nothing in the repo used
  `sqlExec`/`authorize`/`Authorized`; no new capability).
- **Report:** `demos/case_studies/missing_authorization/REPORT.md`.
- **TYPE gaps surfaced for next iter:** (a) **cross-tenant / object-level
  authorization (IDOR, CWE-639)** — E0716 proves *an* authorization on
  the path, not that it names the SAME resource being mutated; bind the
  proof to the resource (`TenantScoped<T>` or an
  `authorize(principal, action, resourceId)` triple matched against the
  query's id) — added as taxonomy backlog B9; (b) template/SSTI = clone
  the injection slice once a template-render sink exists (B2 remainder);
  (c) secret→disk/net sinks + source-side taint (B1 remainder); (d) a
  body-carrying net sink would unlock PII network egress AND a second
  E0716 mutation sink at once.
- **Suite:** green, exit 0 (D.2 catalog: 22 codes, all documented).

---

## Iteration 8 — cross-tenant data access / IDOR (CWE-639)

- **Target:** taxonomy backlog **B9** — broken object-level
  authorization: an authenticated, action-authorized caller mutating a
  resource that belongs to ANOTHER tenant (OWASP API1, the #1 API risk;
  the Facebook "delete any photo" / Peloton account-data shapes). The
  resource-binding extension the iter-7 report surfaced.
- **Gap confirmed:** a handler calling `authorizeResource(user,
  "docs:edit", requestedId)` then mutating a DIFFERENT `victimId`
  checked clean (exit 0) before this iteration — E0716 only proves *an*
  authorization is on the path, not that it named the mutated resource.
- **Improvement (eliminates TYPE):** **E0717** (`check_resource_
  authorization`) — the resource-binding extension of E0716. New
  resource-scoped sink **`sqlByOwner(stmt, resourceId, proof)`** (effect
  `db.exec`, existing `db` capability) requires its `proof` to be an
  **`authorizeResource(principal, action, resourceId)`** call (direct,
  or a name bound exactly once to one) whose id resolves to the SAME
  identity as the sink's `resourceId`: an identical literal, or the same
  *stable* name (a param or name bound exactly once — a `_stable_names`
  helper). Mismatched id, unbound proof (a resource-less
  `authorize(...)`), rebound/computed id, or absent proof → refused
  (over-flag, never miss). `sqlByOwner`'s stmt arg also joined the
  E0713 `_SQL_SINKS` list.
- **Wiring:** folded into the `effect_scope` gate in `cli.py`;
  registries in `passes/effects.py` (`_STDLIB_EFFECTS`) +
  `passes/capability.py` (`_STDLIB_EFFECT_PATHS`); runtime
  `sqlByOwner`/`authorizeResource` (auto-exported via `_ae_` prefix);
  docs in `grammar/{diagnostics,stdlib}.md`; 8 tests in
  `test_effect_scope.py` + `stdlib_d1` runtime assertions; case study
  `demos/case_studies/idor_cross_tenant/`; playground example 18.
  Non-breaking (surveyed: nothing used `sqlByOwner`/`authorizeResource`;
  no new capability).
- **Report:** `demos/case_studies/idor_cross_tenant/REPORT.md`.
- **TYPE gaps surfaced for next iter:** (a) **id identity is syntactic**
  — E0717 relates ids only by identical literal or same never-rebound
  name; two differently-named params holding the same value, or an id
  threaded through string/arithmetic ops, are refused as unprovable.
  A light **value-equality / alias pass** would widen this from
  over-flag to precise — highest-leverage next addition, reused by
  several backlog rows; (b) template/SSTI = clone the injection slice
  once a template-render sink exists (B2 remainder); (c) secret→disk/net
  sinks + source-side taint (B1 remainder); (d) a body-carrying net sink
  would unlock PII network egress AND a second resource/mutation sink at
  once.
- **Suite:** green, exit 0.

## Iteration 9 — Open redirect (CWE-601, backlog B7)

- **Target:** login/OAuth `returnTo` used as an unconstrained redirect
  target → off-site phishing from a trusted link.
- **Gap confirmed:** no redirect sink existed; with one added, the
  dynamic-target form checked clean under `--no-scope-check` (exit 0).
- **Improvement (eliminates TYPE):** **E0718** (`check_open_redirect`) —
  a `redirect` target that is not a literal or `safeRedirect(...)` result
  is refused. New `redirect` sink (effect `net.redirect`) + `safeRedirect`
  host-pinning sanitizer (strips scheme/authority/leading-slash; defeats
  absolute + `//evil` protocol-relative). Reuses the E0711 dataflow shape.
- **Wiring:** effect + capability registries; folded into `effect_scope`
  gate; docs in diagnostics.md + stdlib.md; tests in test_effect_scope.py
  + safeRedirect `stdlib_d1` assertions; case study `open_redirect/`;
  playground example 19. Non-breaking (`net` cap known; no code calls
  redirect). Suite 24/24 green.
- **Report:** `demos/case_studies/open_redirect/REPORT.md`.
- **TYPE gaps surfaced for next iter:** (a) **template injection / SSTI**
  (CWE-1336) — a `renderTemplate(tmpl, data)` sink requiring a literal
  template, same slice; (b) **deserialization of untrusted data** (B6,
  CWE-502) — untrusted bytes into a `deserialize` sink without a
  schema-validated decoder; (c) **alias/value-equality id matching** to
  widen E0717 beyond syntactic identity (the iter-8 residual); (d)
  scoped capabilities (B8) — `capability net to "host/*"`.
- **Suite:** 24/24 green, exit 0.

---

## Iteration 10 — server-side template injection / SSTI (CWE-94)

- **Author:** main thread (Fable 5). The subagent pool hit its session
  limit mid-iteration-10; the main thread carried it.
- **Class / target:** backlog B2 remainder — template injection. The
  Jinja2/Flask `{{7*7}}`→RCE shape: untrusted input concatenated into the
  *template* string, which the engine evaluates.
- **Gap confirmed first:** `renderTemplate("Hi " + userInput, "")` passed
  `aether check` at exit 0 before this iteration.
- **New diagnostic: E0719.** `check_template_injection` in
  `passes/effects.py`, folded into `_run_effect_scope_check`
  (`--no-scope-check` opt-out). Rule: `renderTemplate`'s first (template)
  arg must be a fixed string literal or a name bound only to literals.
  **No sanitizer** — the leanest injection member; SSTI has no safe way to
  build a template from user input. Untrusted value must move to the
  second (data) arg, which the engine escapes.
- **New stdlib:** `renderTemplate(template, data)` (pure — no new effect
  or capability; `_ae_renderTemplate` substitutes the first `{}` with
  escaped data).
- **Before → after:** vulnerable.aeth exit 0 → **E0719 exit 2**; fixed.aeth
  (`renderTemplate("<h1>Hello {}</h1>", userName)`) check+run exit 0, and
  `run` prints `<h1>Hello {{7*7}}</h1>` — payload inert, never evaluated.
- **Non-breaking:** surveyed first — zero prior uses of `renderTemplate`;
  E0719 fires zero times on the existing corpus.
- **Files:** `passes/effects.py`, `cli.py`, `runtime.py`,
  `grammar/diagnostics.md` (+D.2 catalog now 24 codes), `grammar/stdlib.md`,
  `tests/test_effect_scope.py` (4 new tests),
  `demos/case_studies/template_injection/{aether/vulnerable,aether/fixed,REPORT}.md`,
  `playground/examples/20_template_injection.aeth`, this log, taxonomy.
- **TYPE gap surfaced for next iter:** E0719 refuses templates read from
  files/DB too (correct for untrusted stores, over-strict for trusted
  bundles). A `TrustedTemplate<T>` provenance marker — the dual of the
  taint markers — would admit vetted template sources. Also still open:
  B3 (missing precondition div-by-zero/index-OOB), B5 (unbounded
  resource/DoS), B6 (deserialization), value-equality id matching (iter-8
  residual), scoped capabilities (B8).
- **Suite:** exit 0 (all gates PASS; reach-scope tests E0710..E0719).

---

## Iteration 11 — Secret exfil to disk (E0712 sink widening, CWE-532)

- **Author:** main thread (Fable 5).
- **Class / target:** the E0712 residual surfaced back in iter 3 and
  recorded in q1 — a `Secret<T>` reaching a *persistence* sink, not just a
  log sink. Picked via q3 (cheapest reuse: no new marker, no new machinery).
- **Gap confirmed first:** `writeFile("/tmp/creds", "t=" + token)` with a
  `Secret<String>` param passed `aether check` at exit 0.
- **Change (no new code E-number):** widened E0712's sink set from
  `_LOG_SINKS = ("print",)` to a sink-spec dict
  `_SECRET_SINKS = {"print": None, "writeFile": (1,)}` — mirrors E0715's
  `_PII_SINKS`. Only the `writeFile` *contents* arg (index 1) is a sink;
  the path arg is not. The marker + dataflow core was untouched.
- **Before → after:** secret→writeFile exit 0 → **E0712 exit 2**;
  secret→print still caught; `reveal(token)` into writeFile still clean.
- **Non-breaking:** message text changed ("logs"→"logs/persists") but all
  tests assert codes not messages; E0712 still fires only where a secret
  actually reaches a sink. Two new tests (disk-rejected, path-arg-clean).
- **Files:** `passes/effects.py` (sink-spec dict + loop), `grammar/diagnostics.md`
  (row + prose), `tests/test_effect_scope.py` (+2 tests), `vault` q1 +
  taxonomy (B1 remaining narrowed), this log.
- **Compounded:** appended the sink-coverage row to
  `vault/wiki/questions/q1-taint-marker-soundness-boundary.md` — sink
  coverage is a cheap per-marker list, distinct from the (harder)
  dataflow-soundness axis.
- **TYPE gap surfaced for next iter:** the two remaining B1 items —
  taint *origin* from `readFile`/network reads (not just marker-typed
  params), which needs source-marking, and network-body egress (needs a
  body-carrying net sink). Both are bigger than a sink-list edit.
- **Suite:** exit 0 (reach-scope tests E0710..E0719, all green).

---

## Iteration 12 — insecure deserialization (E0720, CWE-502)

- **Author:** main thread (Fable 5). Target picked via q3 (cheap
  sink+literal reuse; high-prevalence RCE class).
- **Class:** pickle / Java `readObject` / unsafe-YAML gadget class —
  untrusted bytes to an unrestricted decoder = RCE.
- **Gap confirmed first:** `deserialize(raw)` on a `String` param passed
  `aether check` at exit 0.
- **New diagnostic: E0720.** `check_deserialization` in
  `passes/effects.py`, folded into `_run_effect_scope_check`. SSTI-shaped:
  `deserialize` on any non-literal argument is refused; **no sanitizer** —
  the repair is a sibling function `schemaDecode(schema, data)` pinned to
  a fixed schema. New pure stdlib: `deserialize`, `schemaDecode`.
- **Before → after:** exit 0 → **E0720 exit 2**; `schemaDecode(...)`
  check+run exit 0, gadget payload rendered inert under the schema.
- **Non-breaking:** zero prior uses of `deserialize`/`schemaDecode`;
  E0720 fires 0× on the corpus. 4 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `runtime.py`,
  `grammar/diagnostics.md` (D.2 catalog now 25 codes), `grammar/stdlib.md`,
  `tests/test_effect_scope.py`, `demos/case_studies/insecure_deserialization/`,
  `playground/examples/21_insecure_deserialization.aeth`, taxonomy (B6 done),
  q3, this log.
- **CONVERGENT SIGNAL (compounded into q3):** iters 10, 11-residual, and
  12 all surfaced the same residual — the pass over-flags a *trusted
  dynamic source* because it can't distinguish trusted-dynamic from
  untrusted-dynamic. **A taint-origin / provenance pass is now the top
  structural investment** — it closes all three residuals + relaxes E0717.
  The cheap-clone well for new classes is nearly dry (B2/B6/B7 done).
- **TYPE gap surfaced for next iter:** build the provenance pass
  (source-marking: `readFile`/network reads → tainted; a `trusted(...)`
  boundary clears). This is the mechanism three iterations have asked for.
- **Suite:** exit 0 (reach-scope tests E0710..E0720).

---

## Iteration 13 — trusted() trust boundary (closes the convergent residual)

- **Author:** main thread (Fable 5). Target = the convergent signal q3
  recorded across iters 10/11/12: passes over-flag a *trusted dynamic
  source*.
- **Decision:** a full provenance/taint-origin pass (auto-mark
  `readFile`/network reads) would ADD violations and risk breaking the
  corpus — wrong shape for a clean closing iteration. Instead shipped the
  minimal primitive that resolves the residual: an explicit `trusted(x)`
  boundary (the dual of `reveal`/`redact`).
- **Change:** new pure stdlib `trusted<T>(x) returns T` (identity at
  runtime). `_template_expr_is_safe` (E0719) and `_deser_arg_is_safe`
  (E0720) now accept a `trusted(...)` call. Narrow by design — only the
  two no-sanitizer sinks honor it.
- **Strictly non-breaking:** the change only RELAXES two checks (more
  programs pass, never fewer) — zero corpus risk by construction.
- **Before → after:** `renderTemplate(trusted(bundleTmpl), data)` and
  `deserialize(trusted(configBlob))` now pass; `renderTemplate("Hi "+u, d)`
  and `deserialize(cookie)` still E0719/E0720. Verified: in a function with
  both, only the untrusted call is flagged.
- **Files:** `runtime.py` (`_ae_trusted`), `passes/effects.py` (`_TRUSTED`
  + two predicate arms), `grammar/diagnostics.md`, `grammar/stdlib.md`
  (Trust boundary section), `tests/test_effect_scope.py` (+2 tests),
  q1 + q3 + taxonomy (residual RESOLVED), this log.
- **Honest scope note:** `trusted()` is an *assertion*, not *inference* —
  it documents trust, it does not prove it. Real source-taint (auto-mark
  untrusted reads, so the human never has to remember to NOT wrap attacker
  input) remains the open structural investment. `trusted()` misused on
  attacker input is the one failure mode, visible in review by design.
- **Suite:** exit 0 (reach-scope tests E0710..E0720).

---

## Iteration 14 — real-world validation (loop phase 2)

- **Author:** main thread (Fable 5). First **phase-2** iteration: the loop
  directive "implement Aether into programs that have a lot of users to
  find their current issues" — never exercised across iters 1–13 (all
  phase-1 detector-building).
- **What:** took the documented vulnerable *shape* of two very-high-user
  OSS projects and showed Aether refuses the composition each real
  toolchain accepted:
  - **PyYAML** `yaml.load` (~300M downloads/mo), insecure deserialization
    (CWE-502, CVE-2017-18342 precedent) → **E0720**. `bench/realworld_pyyaml/`.
  - **Flask/Jinja2** `render_template_string` (~30M/mo), SSTI (CWE-94) →
    **E0719**. `bench/realworld_flask_ssti/`.
  - Both: `<project>_repro.py` states the real call + the 1:1 Aether map;
    `vulnerable.aeth` refused, `fixed.aeth` passes + runs the payload inert.
  - Summary: `bench/REALWORLD_VALIDATION.md`.
- **Honesty (stated in the summary):** Aether checks Aether source, so
  these are faithful MODELS of the real shape, not literal transpilations
  of upstream internals, and NOT a live-repo scan producing new CVEs. The
  claim is scoped: the architecture-class maps 1:1 and the detector fires
  on the real-world shape.
- **No transpiler code changed** — validation artifacts only (bench/*.aeth,
  *.py, *.md). Suite unaffected; re-ran to confirm exit 0.
- **TYPE gap surfaced (the real phase-2 limit):** model-not-live-scan. To
  find LIVE issues in real code, need either an in-language port of a real
  module, or the source-taint provenance pass (q3 convergent signal) so a
  Python→Aether importer can auto-flag untrusted-read→sink flows. (b) is
  the standing structural investment.
- **Suite:** exit 0.

---

## Iteration 15 — real-world validation, broadened (loop phase 2)

- **Author:** main thread (Fable 5). Continued phase 2; chose breadth of
  evidence over the risky provenance pass (which mainly cuts annotation
  burden, not new bugs, and risks corpus regressions — deferred, honestly).
- **Added two more high-user classes** to `bench/REALWORLD_VALIDATION.md`:
  - **requests** `get(user_url)` (~500M/mo), SSRF (CWE-918) → **E0710**
    on the unpinned `net.fetch("*")` scope. `bench/realworld_requests_ssrf/`.
  - **subprocess** `call(..., shell=True)` (stdlib, universal), command
    injection (CWE-78, CVE-2022-1292 shape) → **E0714**.
    `bench/realworld_subprocess_cmdi/`.
  - Validation table now spans 4 projects / 4 detectors (E0710, E0714,
    E0719, E0720); each has `<project>_repro.py` with the 1:1 map,
    `vulnerable.aeth` refused, `fixed.aeth` passing + payload inert.
- **Same honesty scope as iter 14:** faithful models of the real shapes,
  not literal transpilations nor a live-repo scan.
- **No transpiler code changed** — validation artifacts only.
- **Incidental gate fix:** the D.2 catalog walk (scans `transpiler` + `bench`)
  surfaced a latent `E9999` in an untracked, agent-created harness
  `bench/aetherbench/run.py` (absent when iter 14 was green). It was a
  "CLI produced no parseable diagnostic" fallback masquerading as a
  compiler code. Fixed to a non-E sentinel `NO_DIAGNOSTIC`, consistent
  with the file's existing `WRONG_OUTPUT` marker — the E-space now again
  means "real, documented compiler diagnostic". This is the D.2 invariant
  doing its job: it caught a fabricated code before it spread.
- **TYPE gap unchanged:** the model-vs-live-scan limit persists; the
  source-taint provenance pass remains the standing structural investment
  to move from "fires on the shape" to "finds live issues in ported code".
- **Suite:** exit 0.

---

## Iteration 16 — cleartext transmission (E0721, CWE-319)

- **Author:** main thread (Fable 5). Back to phase 1 (a new TYPE) after the
  cheap-clone sink families ran dry — found an *orthogonal* cheap class
  the effect annotation already carries the signal for.
- **Class:** cleartext transmission — a `net.fetch` scope over `http://`
  ships credentials/PII unencrypted. E0710 checks host *pinning*; a pinned
  `http://` host passes E0710 yet is still cleartext. Orthogonal, uncovered.
- **Gap confirmed first:** `net.fetch("http://api.corp.example/ingest/*")`
  passed at exit 0.
- **New diagnostic: E0721.** `check_cleartext_transmission` in
  `passes/effects.py`, folded into `_run_effect_scope_check`. Reuses
  `_declared_effects` + authority parsing; flags `http://` non-loopback
  schemes. **Loopback exempt** (`localhost`/`127.0.0.0/8`/`::1`/`0.0.0.0`)
  — that traffic never leaves the host. No new stdlib (pure effect-string
  check).
- **Before → after:** exit 0 → **E0721 exit 2**; `https://` clean;
  loopback `http://127.0.0.1`/`localhost` clean.
- **Non-breaking:** the corpus's only `http://` net.fetch is
  `demos/capability-firewall` on `127.0.0.1` (loopback, exempt) —
  confirmed E0721 fires 0× there. 3 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `grammar/diagnostics.md`
  (D.2 catalog now 26 codes), `tests/test_effect_scope.py`,
  `playground/examples/22_cleartext_transmission.aeth`, taxonomy, this log.
- **Note:** first covered class that is NEITHER a sink+literal NOR a taint
  member — a pure declared-effect-string check, the cheapest shape yet.
  Suggests a small remaining vein: other properties readable straight off
  the effect annotation (e.g. a `net.fetch` to a raw IP literal, or a
  known-bad port).
- **TYPE gap surfaced:** provenance pass still the big one; smaller vein =
  effect-annotation string properties (raw-IP host, non-TLS ports).
- **Suite:** exit 0 (reach-scope tests E0710..E0721).

---

## Iteration 17 — SSRF to cloud metadata / IMDS (E0722, CWE-918)

- **Author:** main thread (Fable 5). Worked the effect-string vein E0721
  opened.
- **Class:** server-side fetch pinned to the link-local range
  169.254.0.0/16 — the cloud metadata endpoint (169.254.169.254, AWS/GCP/
  Azure IMDS), the crown-jewel SSRF target for IAM-credential theft.
- **The blind spot it closes:** E0710 refuses *unpinned* scopes; a metadata
  IP is host-*pinned*, so E0710 (and E0721, if https) pass it. E0722 refuses
  the pinned link-local reach directly.
- **Gap confirmed first:** `net.fetch("https://169.254.169.254/latest/meta-data/iam/*")`
  passed at exit 0.
- **New diagnostic: E0722.** `check_metadata_fetch` in `passes/effects.py`,
  folded into `_run_effect_scope_check`. Reuses the authority parser;
  flags host `169.254.*`. RFC-1918 private ranges deliberately NOT flagged
  (legit in service meshes) — link-local IMDS is the non-noisy high-signal
  case. No new stdlib.
- **Non-breaking:** corpus `169.254` refs are all comments / runtime
  `crawl(...)` args, never `net.fetch` effect annotations — E0722 fires 0×.
  3 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `grammar/diagnostics.md`
  (D.2 catalog now 27 codes), `tests/test_effect_scope.py`, taxonomy,
  this log.
- **Residual (honest):** IPv6 IMDS (`fd00:ec2::254`) and DNS names that
  resolve to link-local are not covered (static string check only).
- **TYPE gap surfaced:** effect-string vein has ~1-2 more (raw-IP host in
  general as a warning, non-standard ports); then it too is dry and the
  provenance pass remains the big structural investment.
- **Suite:** exit 0 (reach-scope tests E0710..E0722).

---

## Iteration 18 — phase-2 validation of E0721/E0722 (Capital One SSRF)

- **Author:** main thread (Fable 5). Chose a clean phase-2 validation over
  forcing a hardcoded-secret detector: `classify("literal")` → CWE-798
  would flag 7+ existing demos that legitimately use `classify("hunter2")`
  to illustrate secret flow — not non-breaking without heavy migration.
  Recorded that decision honestly rather than churn the corpus.
- **What:** validated the two newest detectors (E0721 cleartext, E0722
  metadata) against the **Capital One 2019 breach** (~100M records) — the
  canonical real SSRF-to-IMDS incident. `bench/realworld_metadata_ssrf/`.
  The pinned `http://169.254.169.254/...` scope fires **both** E0722
  (metadata reach) and E0721 (cleartext) on one line; the https
  non-metadata fix is clean.
- **Point made:** this is the incident that motivated E0722 — host
  *pinning* is not enough when the pinned destination is the crown jewel.
  A wildcard-only allowlist (and E0710 alone) accepts it; E0722 does not.
- **Validation table now 5 projects / 5 detectors** (E0710, E0714, E0719,
  E0720, +E0721/E0722), `bench/REALWORLD_VALIDATION.md`.
- **Same honesty scope:** faithful model, not a live-repo scan.
- **No transpiler code changed** — validation artifacts only. Suite green.
- **TYPE gap unchanged:** provenance pass still the big structural
  investment; hardcoded-secret (CWE-798) is a real open class but needs a
  credential-pattern heuristic or corpus migration to land non-breaking.
- **Suite:** exit 0.

---

## Iteration 19 — hardcoded credential in source (E0723, CWE-798)

- **Author:** main thread (Fable 5). Revisited the class deferred in iter
  18 with the fix noted there: a **credential-pattern heuristic** instead
  of flagging all `classify(literal)`.
- **Class:** hardcoded secret in source — the #1 real-world security
  finding (millions of keys leaked to public repos yearly).
- **Why it's now non-breaking:** high-confidence provider shapes only
  (AWS `AKIA…`, GitHub `ghp_…`, Google `AIza…`, Slack `xox…`, Stripe
  `sk_live_…`, PEM private key). Whole-corpus grep for these = ZERO hits,
  so the demo secrets (`hunter2`, `s3cr3t-pg-pw`, `tok_live_abc123`) all
  stay clean. Confirmed empirically before wiring.
- **New diagnostic: E0723**, and a NEW detector family — a **literal-
  content scan** (`check_hardcoded_secret` walks every StringLit and
  regex-matches), distinct from the sink+literal, taint, and effect-string
  families. Essentially a secret scanner built into the compiler.
- **Before → after:** `return "AKIAIOSFODNN7EXAMPLE"` exit 0 → **E0723
  exit 2**; `classify("hunter2")` and env-sourced `Secret` params clean.
- **Files:** `passes/effects.py` (new family + `_walk_string_lits`),
  `cli.py`, `grammar/diagnostics.md` (D.2 catalog now 28 codes),
  `tests/test_effect_scope.py` (4 tests),
  `playground/examples/23_hardcoded_secret.aeth`, taxonomy, this log.
- **Residual (honest):** pattern list, not entropy analysis — a generic
  high-entropy secret or a non-listed provider is missed. Adding an
  entropy heuristic would broaden coverage at some false-positive cost;
  deferred (the narrow list is the non-noisy choice for now).
- **Suite:** exit 0 (reach-scope tests E0710..E0723).

---

## Iteration 20 — consolidation checkpoint (composition + posture)

- **Author:** main thread (Fable 5). Milestone iteration: instead of a 15th
  narrow detector, consolidated 19 iterations into verified, coherent
  artifacts.
- **Composition verified (a real, previously-untested correctness
  property):** one kitchen-sink module with SEVEN independent violations
  (`demos/case_studies/composition_kitchen_sink/`) — `aether check` emits
  all seven (E0712/13/19/20/21/22/23) at once. New regression test
  `test_detectors_compose_additively` asserts the passes accumulate and
  none masks another.
- **Security posture summary:** `SECURITY_POSTURE.md` — the 14 classes with
  CWE + family + repair, the four reusable detector families
  (sink+literal / taint / effect-string / literal-content), the
  composition guarantee, the real-world validation pointer, and the honest
  not-covered boundary. This is the single-page artifact a reviewer or new
  contributor needs.
- **No transpiler code changed** — a demo, a composition test, a summary
  doc. Suite green.
- **Trajectory note (honest):** the cheap-clone veins across all four
  families are now largely worked out; further NEW classes increasingly
  need real machinery (provenance, entropy analysis, loop/recursion
  analysis). The loop is reaching the point where the next high-value move
  is the deferred **provenance pass**, not another narrow detector — the
  loop's own signal that phase-1 breadth is maturing.
- **Suite:** exit 0.

---

## Iteration 21 — log injection + the Untrusted<T> marker (E0724, CWE-117)

- **Author:** main thread (Fable 5). Committed to the "provenance" move
  from iter 20 — but did it the SOUND way.
- **Key decision:** provenance-by-inference (auto-taint from `readFile`/
  network reads) is risky and mostly cuts annotation burden, not bugs.
  Instead introduced `Untrusted<T>` — an EXPLICIT taint-SOURCE marker (the
  dual of Secret/PII), applied at the trust boundary. This is the sound
  provenance story: mark, don't infer. Compounded into q3.
- **New class it unlocks: log injection (CWE-117)** — an Untrusted value
  logged raw lets embedded CR/LF forge fake log lines (audit/SIEM
  poisoning). Genuinely NOT caught before (logging dynamic values is
  normal; only *untrusted* ones are dangerous — which needed the marker).
- **New diagnostic: E0724.** `check_log_injection` reuses the generalized
  taint machinery (`_marked_tainted_names`/`_expr_leaks_marked`); marker
  `Untrusted<T>`, sanitizer `sanitizeLog` (strips CR/LF), sink `print`.
  New stdlib `classifyUntrusted` + `sanitizeLog`.
- **Before → after:** `print("req: " + userInput)` with an Untrusted param
  exit 0 → **E0724 exit 2**; `sanitizeLog(userInput)` clean, and at runtime
  strips the `\n` so a forged `[ADMIN]` payload stays on one line.
- **Non-breaking:** zero prior `Untrusted`/`sanitizeLog` uses; E0724 fires
  0× on the corpus. 3 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `runtime.py`,
  `grammar/diagnostics.md` (D.2 catalog now 29 codes), `grammar/stdlib.md`,
  `tests/test_effect_scope.py`, taxonomy, q3, this log.
- **Why this matters beyond one class:** `Untrusted<T>` is reusable — any
  future sink can require it sanitized (untrusted → path, → header, →
  redirect target). The provenance investment is now paying out
  incrementally and soundly, one sink at a time.
- **Suite:** exit 0 (reach-scope tests E0710..E0724).

---

## Iteration 22 — reflected XSS, second Untrusted<T> sink (E0725, CWE-79)

- **Author:** main thread (Fable 5). Cashed in the `Untrusted<T>` marker
  from iter 21 on the highest-value web sink.
- **Class:** reflected XSS (OWASP #2) — an untrusted value written into an
  HTML response without escaping runs `<script>` in the victim's browser.
- **New diagnostic: E0725.** `check_reflected_xss` reuses the taint
  machinery; marker `Untrusted<T>`, sink `htmlResponse`, sanitizer
  `htmlEscape`. New pure stdlib `htmlResponse` + `htmlEscape`.
- **Key soundness property established — PER-SINK sanitizers:** the E0725
  exit is `htmlEscape`, and it is sink-specific. `sanitizeLog` (which
  clears E0724 log injection) does NOT clear E0725 — stripping CR/LF does
  not neutralize HTML. Verified by test: `htmlResponse(sanitizeLog(u))` is
  still flagged E0725. The right exit for one sink is the wrong exit for
  another; the taint machinery models this correctly because the unwrap
  name is a per-check parameter.
- **Before → after:** `htmlResponse("<div>" + userInput + "</div>")` with
  an Untrusted param exit 0 → **E0725 exit 2**; `htmlEscape(userInput)`
  clean; `sanitizeLog(userInput)` still E0725.
- **Non-breaking:** zero prior `htmlResponse`/`htmlEscape` uses; 0× on
  corpus. 3 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `runtime.py`,
  `grammar/diagnostics.md` (D.2 catalog now 30 codes), `grammar/stdlib.md`,
  `tests/test_effect_scope.py`, taxonomy, this log.
- **Pattern proven:** `Untrusted<T>` + a new (sink, sanitizer) pair = a new
  injection-into-context class, cheaply. Remaining sinks in this vein:
  HTTP header (CWE-113 response splitting), XML/LDAP contexts.
- **Suite:** exit 0 (reach-scope tests E0710..E0725).

---

## Iteration 23 — HTTP response splitting, third Untrusted<T> sink (E0726, CWE-113)

- **Author:** main thread (Fable 5). Completed the Untrusted<T> HTTP-output
  trio: log (E0724) → HTML body (E0725) → header (E0726).
- **Class:** response splitting / header injection — untrusted CR/LF in a
  response header injects headers or a second response (cache poisoning,
  forged Set-Cookie).
- **New diagnostic: E0726.** `check_header_injection`, taint machinery;
  marker `Untrusted<T>`, sink `setHeader`, sanitizer `sanitizeHeader`. New
  pure stdlib `setHeader` + `sanitizeHeader`.
- **Before → after:** `setHeader("Content-Language", userLang)` with an
  Untrusted param exit 0 → **E0726 exit 2**; `sanitizeHeader(userLang)`
  clean.
- **Non-breaking:** zero prior uses; 2 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `runtime.py`,
  `grammar/diagnostics.md` (D.2 catalog now 31 codes), `grammar/stdlib.md`,
  `tests/test_effect_scope.py`, taxonomy, this log.
- **Vein status (honest):** the Untrusted-into-common-web-context vein is
  now well-covered (log/HTML/header). Further sinks (XML, LDAP, CSV
  formula) are real but lower-prevalence. Next iterations should pivot off
  this vein — either a different class entirely, a real-world validation
  batch of the new E0724/25/26, or consolidation — to avoid diminishing
  returns.
- **Suite:** exit 0 (reach-scope tests E0710..E0726).

---

## Iteration 24 — runtime-enforcement proof (pivot off the sink vein)

- **Author:** main thread (Fable 5). Pivoted off the Untrusted web-sink
  vein (as flagged in iter 23) to a genuinely different, high-credibility
  move.
- **What:** `tests/test_runtime_enforcement.py` — proves the static
  refusals are NOT theater. For 8 defenses it runs the FIXED Aether program
  end-to-end (parse → emit → exec) with a real attack payload and asserts
  the payload is DEFANGED in the actual output:
  - E0713 sqlBind → injection wrapped in quotes
  - E0714 shellArg → payload one quoted argument
  - E0725 htmlEscape → `<script>` becomes `&lt;script&gt;`
  - E0724 sanitizeLog → forged `\n[ADMIN]` line collapsed
  - E0726 sanitizeHeader → CR/LF stripped from header value
  - E0715 redact → PII masked to `j***@…`
  - E0720 schemaDecode → gadget payload inert under schema
  - E0711 safeJoin → `../../` stripped, path stays under base
- **Value:** closes the "is this just a static checker?" question — if any
  sanitizer regressed to a no-op, its assertion fails even though
  `aether check` still passes. Static refusal ⇔ real runtime defense, now
  a gated invariant.
- **Caught my own test bug honestly:** the safeJoin assertion was wrong
  (expected `etc/passwd` absent, but `uploads/etc/passwd` is correctly
  CONTAINED — the real property is "no `..` escapes"). Fixed the assertion
  to the actual security property, not a sloppy proxy.
- **Wired into `scripts/run_all.py`** as a gated line
  (`runtime_enforce: PASS`).
- **Files:** `tests/test_runtime_enforcement.py` (new), `scripts/run_all.py`,
  this log. No transpiler change.
- **Suite:** exit 0 (now includes the runtime-enforcement gate).

---

## Iteration 25 — false-positive gate (completes the credibility triangle)

- **Author:** main thread (Fable 5). Continued the credibility theme from
  iter 24 with its counterweight.
- **What:** `tests/test_false_positive_corpus.py` — runs all 17 reach-scope
  detectors over a corpus of LEGITIMATE programs (every `fixed.aeth` across
  bench/ + demos/, plus the clean playground examples: 01/06/07/08/09) and
  asserts ZERO diagnostics. 31 programs, 0 false positives.
- **Why it matters:** a security checker that over-flags gets turned off.
  This is the counterweight to the positive tests. The three suites now
  form the **credibility triangle**:
    - catches bad  (test_effect_scope, catch rate)
    - passes good  (this, false-positive rate 0)
    - not theater  (test_runtime_enforcement, fixes defang at runtime)
- **Wired into `scripts/run_all.py`** as a gated line
  (`false_positive: PASS (31 clean programs, 0 diagnostics)`). If any
  detector regresses to over-flagging a legitimate fixed form, this goes
  red.
- **SECURITY_POSTURE.md** updated with the credibility-triangle table.
- **Files:** `tests/test_false_positive_corpus.py` (new),
  `scripts/run_all.py`, `SECURITY_POSTURE.md`, this log. No transpiler
  change.
- **Note:** the corpus auto-grows — every future `fixed.aeth` a case study
  adds is automatically a false-positive assertion. The gate strengthens
  itself as the loop runs.
- **Suite:** exit 0 (now includes the false-positive gate).

---

## Iteration 26 — XML external entity / XXE (E0727, CWE-611)

- **Author:** main thread (Fable 5). A genuinely distinct class off the
  Untrusted web-sink vein — a parser-CONFIG issue like deserialization.
- **Class:** XXE — an entity-resolving XML parser on untrusted input reads
  local files (`file:///etc/passwd`), reaches internal URLs (SSRF), or
  billion-laughs DoS. OWASP-listed.
- **New diagnostic: E0727.** `check_xxe` mirrors E0720 (deserialization):
  `parseXml` on a non-literal argument is refused; `parseXmlSafe` (external
  entities disabled) is the sanctioned alternative. Reused
  `_deser_arg_is_safe` + `_safe_template_names` verbatim. New pure stdlib
  `parseXml` + `parseXmlSafe`.
- **Before → after:** `parseXml(raw)` exit 0 → **E0727 exit 2**;
  `parseXmlSafe(raw)` clean; the `<!ENTITY SYSTEM ...>` payload runs inert.
- **Non-breaking:** zero prior uses; 2 new tests. Auto-covered by the new
  false-positive gate (any parseXmlSafe fixed form stays clean).
- **Files:** `passes/effects.py`, `cli.py`, `runtime.py`,
  `grammar/diagnostics.md` (D.2 catalog now 32 codes), `grammar/stdlib.md`,
  `tests/test_effect_scope.py`, taxonomy, this log.
- **Family note:** the "dangerous sink + safe sibling function" shape
  (deserialize/schemaDecode, parseXml/parseXmlSafe) is distinct from both
  sink+sanitizer and Untrusted-marker — it's for parser/decoder CONFIG,
  where the safe form is a different constructor, not an escaped argument.
- **Suite:** exit 0 (reach-scope tests E0710..E0727).

---

## Iteration 27 — phase-2 validation of E0725/E0727 (Express XSS, lxml XXE)

- **Author:** main thread (Fable 5). Phase-2: validated the newest
  detectors against real high-user libraries.
- **Added two cases** to `bench/REALWORLD_VALIDATION.md`:
  - **Express** `res.send(reflected)` (~30M downloads/wk), reflected XSS
    (CWE-79, OWASP #2) → **E0725**. `bench/realworld_xss/` (+ `escapeHtml`
    fix; payload rendered `&lt;script&gt;` inert at runtime).
  - **lxml** `fromstring(resolve_entities=True)` (~50M/mo), XXE (CWE-611)
    → **E0727**. `bench/realworld_xxe/` (+ `parseXmlSafe` fix).
  - Each has `<lib>_repro.{js,py}` with the real call + 1:1 map,
    `vulnerable.aeth` refused, `fixed.aeth` passing.
- **Validation table now 7 projects / 7 detectors** (E0710, E0714, E0719,
  E0720, E0721/22, E0725, E0727).
- **Same honesty scope:** faithful models, not live-repo scans.
- **The new fixed.aeth files auto-join the false-positive gate** (iter 25):
  confirmed both stay clean there too.
- **No transpiler code changed** — validation artifacts only. Suite green.
- **Suite:** exit 0.

---

## Iteration 28 — CSV / formula injection (E0728, CWE-1236)

- **Author:** main thread (Fable 5). Extended `Untrusted<T>` to its first
  NON-HTTP context — proving the marker generalizes past web output.
- **Class:** spreadsheet formula injection — exported data whose cell
  begins with `= + - @` becomes a formula in Excel/Sheets (`=WEBSERVICE`
  exfil, DDE → RCE).
- **New diagnostic: E0728.** `check_csv_injection`, taint machinery; marker
  `Untrusted<T>`, sink `csvCell`, sanitizer `csvEscape` (prefixes a quote).
  New pure stdlib `csvCell` + `csvEscape`.
- **Before → after:** `csvCell(cell)` with an Untrusted param exit 0 →
  **E0728 exit 2**; `csvEscape(cell)` clean; runtime prefixes `'` so
  `=WEBSERVICE(...)` is inert text.
- **Also added to the runtime-enforcement gate** (now 9 defenses): proves
  csvEscape disarms a real `=WEBSERVICE` payload end-to-end.
- **Non-breaking:** zero prior uses; 2 detector tests + 1 runtime test.
- **Files:** `passes/effects.py`, `cli.py`, `runtime.py`,
  `grammar/diagnostics.md` (D.2 catalog now 33 codes), `grammar/stdlib.md`,
  `tests/test_effect_scope.py`, `tests/test_runtime_enforcement.py`,
  taxonomy, this log.
- **Marker generality proven:** `Untrusted<T>` now spans log, HTML, header,
  and CSV/spreadsheet contexts — 4 sinks, one trust-boundary primitive.
- **Suite:** exit 0 (reach-scope tests E0710..E0728).

---

## Iteration 29 — static match exhaustiveness (E0202) — a NON-security pivot

- **Author:** main thread (Fable 5). Deliberate pivot: 19 security detectors
  is thorough; more risks padding. Returned to Aether's ORIGINAL pitch —
  architectural integrity — with the first non-security detector.
- **Class:** non-exhaustive match (unhandled union variant). The classic
  Rust/Swift compile-time guarantee.
- **Gap confirmed first:** a match missing a case passed `check` at exit 0
  and only failed at RUNTIME (`RuntimeError: non-exhaustive match`). E0202
  lifts it to a STATIC refusal — the compiler-refuses-incomplete-
  composition promise applied to control flow.
- **New diagnostic: E0202** (type-check range, `check_exhaustiveness`).
  When the scrutinee's union type is resolvable (from a param or `let`
  annotation), every union case must be handled or a wildcard present.
  Default-on; opt out `--no-exhaustiveness-check`.
- **Conservative / non-breaking:** silent when the scrutinee type is
  unresolvable (no false positives). Scanned EVERY `.aeth` in the repo:
  **0 files flagged** — all existing matches are exhaustive, wildcarded, or
  unresolvable. Then adding a new variant to a union breaks stale matches
  at compile time — the whole point.
- **Value beyond security:** demonstrates Aether's core thesis isn't just a
  security-linter bolt-on — the same "refuse the unsound composition"
  machinery catches ordinary correctness bugs (a forgotten enum case is the
  most common real one). Broadens the story from "security tool" to
  "architectural-integrity compiler".
- **Files:** `passes/effects.py` (check + union/type/pattern helpers),
  `cli.py` (default-on step + flag), `grammar/diagnostics.md` (D.2 catalog
  now 34 codes), `tests/test_exhaustiveness.py` (new, 4 tests, gated),
  taxonomy (new non-security section), this log.
- **TYPE gap surfaced:** more non-security architectural classes now open —
  unhandled `Result`/`Option` (silent error swallowing), unreachable
  arms, dead code after a total match. The non-security vein is fresh.
- **Suite:** exit 0 (+ exhaustiveness gate).

---

## Iteration 30 — unreachable match arm (E0203), complement of E0202

- **Author:** main thread (Fable 5). Continued the non-security vein;
  paired with iter 29.
- **Class:** unreachable/dead match arm (CWE-561) — an arm after a wildcard
  catch-all, or a duplicate constructor case. E0202 = too few arms; E0203 =
  too many. Together match handling is total-and-minimal.
- **Gap confirmed first:** an arm after `case _` (and a duplicate case)
  passed `check` at exit 0.
- **New diagnostic: E0203** (`check_unreachable_arms`). Pure arm-ordering —
  no scrutinee type needed, so it applies to EVERY match. Folded into the
  same default-on step as E0202 (`--no-exhaustiveness-check`).
- **Non-breaking:** scanned every `.aeth` in the repo — 0 files flagged.
  3 new tests (after-wildcard, duplicate, trailing-wildcard-clean).
- **Files:** `passes/effects.py`, `cli.py`, `grammar/diagnostics.md`
  (D.2 catalog now 35 codes), `tests/test_exhaustiveness.py`, taxonomy,
  this log.
- **Milestone (30 iterations):** 19 security detectors (E0710–E0728) + 2
  architectural (E0202/E0203), across 4 detector families + a static
  type-completeness pair, all gated by the credibility triangle
  (catch/pass/defend) + composition + a 33-program false-positive corpus.
  D.2 catalog: 35 documented codes.
- **TYPE gap surfaced:** the non-security vein continues — dead code after
  `return`/`break` in a block (CWE-561 sibling), and `let`-bound values
  never used (dead binding). Both need block-flow walks, not the match
  helpers — slightly more machinery.
- **Suite:** exit 0.

---

## Iteration 31 — dead code after terminator (E0204, CWE-561)

- **Author:** main thread (Fable 5). Third architectural detector,
  generalizing reachability beyond match.
- **Class:** a statement after an unconditional `return`/`break`/`continue`
  in the same block — always a logic error.
- **Gap confirmed first:** `return x` followed by another statement passed
  `check` at exit 0.
- **New diagnostic: E0204** (`check_dead_code`). Purely structural — scans
  every statement list for a terminator that is not last (`_stmt_lists`
  identifies statement blocks by "every element is a kind-bearing dict").
  Folded into the same static-semantic step as E0202/E0203.
- **Non-breaking:** full-repo `.aeth` scan — 0 files flagged. 2 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `grammar/diagnostics.md`
  (D.2 catalog now 36 codes), `tests/test_exhaustiveness.py`, taxonomy,
  `scripts/run_all.py` (gate line renamed static_semantic), this log.
- **Architectural cluster now:** E0202 (exhaustive) + E0203 (no dead arm) +
  E0204 (no dead statement) = a small static reachability/completeness
  suite, the non-security half of the "refuse unsound compositions" thesis.
- **TYPE gap surfaced:** unused `let` binding (dead store), and a pure
  function whose result is ignored at the call site — both need a
  use/def walk (a bit more machinery than the structural scans).
- **Suite:** exit 0.

---

## Iteration 32 — unused let binding / dead store (E0205, CWE-563)

- **Author:** main thread (Fable 5). Fourth architectural detector,
  completing the static-semantic cluster with a use/def check.
- **Class:** a `let x = ...` whose `x` is never read — a dead store,
  usually a mistaken variable downstream.
- **New diagnostic: E0205** (`check_unused_binding`). Collects Ident reads
  across the function body; a bound name absent from that set is unused.
  The `_`-prefix (`let _r = writeFile(...)`) is the sanctioned
  intentional-discard convention and is exempt.
- **REAL FINDING on first run:** the corpus scan flagged exactly one file —
  `bench/aetherbench/results/cand/t4_02_shellarg__nl__a0.aeth`, an
  agent-GENERATED candidate that binds `let output = shellExec(...)` and
  never reads it. A genuine dead store the detector caught on code it had
  never seen. Not gated (untracked generated candidate), so suite stays
  green — but a concrete demonstration that E0205 finds real bugs, not just
  its own test fixtures.
- **Non-breaking:** the only corpus hit is that genuine finding; every
  hand-authored reference/demo/fixed form is clean (all reads or `_`).
  3 new tests.
- **Files:** `passes/effects.py`, `cli.py`, `grammar/diagnostics.md`
  (D.2 catalog now 37 codes), `tests/test_exhaustiveness.py`, taxonomy,
  `scripts/run_all.py`, this log.
- **Static-semantic cluster complete (E0202–E0205):** exhaustive match, no
  dead arm, no dead statement, no dead store — a coherent "no dead or
  incomplete code" suite, the non-security half of the thesis.
- **Suite:** exit 0.

---

## Iteration 33 — scan real AI-generated code (loop phase 2, authentic)

- **Author:** main thread (Fable 5). Phase-2 done on REAL code, not modeled
  CVEs: ran the full check pipeline over all 176 AI-generated `.aeth` files
  under `bench/aetherbench/`. Report: `bench/SCAN_FINDINGS.md`.
- **Three honest buckets:**
  1. **Independent security-fixture validation — 10/10 exact.** The
     aetherbench agent's own `tasks/t4_*/vulnerable.aeth` fixtures (NOT this
     project's case studies) each fire the exactly-correct expected code
     (sqlbind→E0713, shellarg→E0714, safejoin→E0711, ssrf→E0710,
     secret→E0712, pii→E0715, authz→E0716, idor→E0717, redirect→E0718,
     template→E0719). Task name ↔ code match 10/10 on an outside corpus.
  2. **A genuine finding — 1.** `cand/t4_02_shellarg__nl__a0.aeth` — a real
     E0205 dead store in a model candidate (confirmed iter 32).
  3. **Generation failures — E0201.** e.g. a candidate wrote `var result`,
     colliding with the reserved contract keyword; parser correctly refuses.
     Bucketed separately (generation-quality signal, not arch findings).
- **Honesty (in the report):** this is a spot-check on real generated code,
  NOT a controlled catch-rate study — the candidate set is small/skewed and
  the fixtures intentional. The statistical version is the RW_MINING /
  design-partner runbook's job.
- **Value:** first evidence of the detectors firing on an EXTERNALLY-
  authored corpus (stronger than self-authored tests) + a real find in
  unseen generated code. No transpiler change; evidence artifact only.
- **Suite:** exit 0 (unchanged).

---

## Iteration 34 — ignored Result / unchecked error (E0206, CWE-252)

- **Author:** main thread (Fable 5). Fifth architectural detector; the
  error-handling member of the static-semantic cluster.
- **Class:** a bare statement calling a `Result`-returning function drops
  the error case — the "forgot to check the write" bug.
- **New diagnostic: E0206** (`check_ignored_result`). Flags an `ExprStmt`
  whose call targets a Result-returning function (stdlib writeFile/readFile/
  readLine/parseInt/parseFloat, or any user `returns Result<...>`). Fix:
  bind+match, or `let _r = ...` explicit discard.
- **Non-breaking on the gate, 12 REAL FINDINGS off it:** the hand-authored
  corpus uses `let _r = writeFile(...)` (0 gated flags), but the scan of
  AI-generated aetherbench candidates found **12** bare `writeFile`
  statements silently dropping the Result — genuine CWE-252 bugs in unseen
  generated code. Updated `bench/SCAN_FINDINGS.md` (now 13 real findings:
  1 dead store + 12 unchecked errors).
- **Files:** `passes/effects.py`, `cli.py`, `grammar/diagnostics.md`
  (D.2 catalog now 38 codes), `tests/test_exhaustiveness.py`, taxonomy,
  `bench/SCAN_FINDINGS.md`, `scripts/run_all.py`, this log.
- **Pattern confirmed twice (E0205, E0206):** the architectural detectors
  are non-breaking on curated code yet find real bugs in AI-generated code
  — exactly the target-audience value proposition, demonstrated not
  claimed.
- **Static-semantic cluster now E0202–E0206** (6 checks): match
  completeness, reachability, dead store, unchecked error.
- **Suite:** exit 0.

---

## Iteration 35 — the corpus scanner (product shape of phase 2)

- **Author:** main thread (Fable 5). Turned iter-33's throwaway bash loop
  into `tools/scan.py` — the actual product: point Aether at a directory of
  AI-generated code, get a findings report.
- **What it is:** a standalone scanner running the full default-on suite
  (base effect/capability passes + 19 security detectors E0710-E0728 + 5
  static-semantic checks E0202-E0206) over every `.aeth` in a dir. Buckets
  parse errors (generation failures) separately from architectural/security
  findings. Text or `--json`. Exit 0 clean / 1 findings / 2 usage.
- **Verified behavior:** `python -m tools.scan reference` → exit 0, 0
  findings (clean curated corpus); `python -m tools.scan bench/aetherbench`
  → 23 files with findings + 6 parse errors (reproduces the iter-33/34
  results deterministically, structured).
- **Why it matters:** this is the phase-2 story made concrete and
  repeatable — Aether as a scanner for AI-generated code, not a set of
  hand-run checks. The 13 real findings (E0205×1, E0206×12) come out of one
  command now.
- **Gated:** `tests/test_scan.py` (clean→0, vulnerable→E0713, fixed→0)
  wired into `scripts/run_all.py` (`scan_tool: PASS`).
- **Files:** `tools/scan.py` (new), `tests/test_scan.py` (new),
  `scripts/run_all.py`, `bench/SCAN_FINDINGS.md`, this log. No transpiler
  change — a new consumer of the existing passes.
- **Suite:** exit 0.

---

## Iteration 36 — SARIF output (Aether as a CI gate)

- **Author:** main thread (Fable 5). Product-integration move: made the
  scanner's findings consumable by the ecosystem.
- **What:** `tools/scan.py --sarif` emits SARIF v2.1.0 — the standard
  static-analysis format GitHub Code Scanning, VS Code, and most CI
  security dashboards ingest. Each finding → a SARIF result with ruleId
  (Exxxx), file uri, and startLine; the detector set → the tool's rule
  list.
- **Why it matters:** this is the concrete path for "implement Aether into
  programs" — drop `python -m tools.scan <dir> --sarif` in CI, findings
  surface as code-scanning alerts, exit 1 fails the build. Aether stops
  being a local checker and becomes a pipeline gate on AI-generated code.
- **Verified:** SARIF for the SQLi demo is well-formed — tool.driver.name
  `aether-scan`, rule `E0713`, result with correct uri + line. Gated by a
  new `test_scan.py` case.
- **Files:** `tools/scan.py` (+`to_sarif`, `--sarif`), `tests/test_scan.py`
  (+1 test), `bench/SCAN_FINDINGS.md`, this log. No transpiler change.
- **Product arc (iters 33→36):** throwaway scan → reusable scanner →
  CI-ready SARIF. The phase-2 story is now a deployable tool, not a demo.
- **Suite:** exit 0.

---

## Iteration 37 — unsatisfiable refinement / impossible type (E0207)

- **Author:** main thread (Fable 5). A genuinely NOVEL architectural check
  (not a clone) — the compiler refusing an uninhabitable type.
- **Class:** a refinement `T where P` no value can satisfy (e.g.
  `Int where self >= 10 and self <= 5`) — always a bounds typo; every
  parameter of the type is impossible.
- **Gap confirmed first:** the contradictory type checked clean at exit 0.
- **New diagnostic: E0207** (`check_unsatisfiable_refinement`). Light,
  SOUND interval analysis: intersect the analyzable `self OP const` clauses
  of the predicate's conjunction; flag only a provably-empty interval
  (reversed bounds, contradictory `==`, exclusive-touch). Unanalyzable
  clauses (`self % 2 == 0`, `or`) widen to unbounded, so it NEVER
  false-positives — verified by a test.
- **Non-breaking:** full-repo scan — 0 files flagged (every real refinement
  is satisfiable). 4 new tests.
- **First refinement-level static check:** the base refinement guarantee is
  a RUNTIME boundary check (q2); E0207 adds a small STATIC layer catching
  the impossible-bounds subclass at compile time — a step toward the SMT
  story without the SMT dependency.
- **Files:** `passes/effects.py` (check + `_clause_bound`/`_refine_interval`/
  `_interval_empty`), `cli.py`, `grammar/diagnostics.md` (D.2 catalog now
  39 codes), `tests/test_exhaustiveness.py`, taxonomy, `scripts/run_all.py`,
  this log.
- **Static-semantic cluster now E0202–E0207** (7 checks): match, reach,
  dead store, error, and impossible type.
- **Suite:** exit 0.

---

## Iteration 38 — turnkey CI deployment (GitHub Action + SARIF upload)

- **Author:** main thread (Fable 5). Completed the deployment story — the
  literal "implement Aether into programs" directive, made drop-in.
- **What:** `.github/workflows/aether-scan.yml` — a ready-to-use GitHub
  Action that (1) checks out, (2) sets up Python (no installs — Aether is
  stdlib-only), (3) runs `python -m tools.scan <path> --sarif`, (4) uploads
  the SARIF to Code Scanning via `github/codeql-action/upload-sarif`, (5)
  fails the build if any finding. Plus `docs/SCANNING.md` — the local + CI
  quickstart.
- **Correctness care:** GitHub bash runs with `-e`, so the scanner's exit-1
  (findings present) would abort the step before the SARIF uploads. Guarded
  with `set +e`/capture/`set -e` so SARIF ALWAYS uploads and the failure is
  a separate, explicit step. Verified the exact CI command locally:
  `python -m tools.scan demos --sarif` → valid SARIF (16 rules, 70 results),
  exit 1.
- **Why it matters:** Aether is now genuinely deployable as a PR gate on
  AI-generated `.aeth` — findings surface inline on the diff like CodeQL.
  The product arc iters 33→38: throwaway scan → scanner → SARIF → CI action
  + docs. Nothing left between "AI writes Aether" and "CI blocks the unsafe
  composition".
- **Honest scope (in SCANNING.md):** Aether checks Aether source; scanning
  other-language code needs it ported first. The scanner's value today is
  on `.aeth` corpora.
- **Files:** `.github/workflows/aether-scan.yml` (new), `docs/SCANNING.md`
  (new), this log. No transpiler change.
- **Suite:** exit 0 (unchanged).

---

## Iteration 39 — marker flow across function boundaries (return-type seeding + E0729)

- **Author:** main thread (Fable 5). The q1 "highest-leverage soundness
  upgrade" (interprocedural flow), shipped the SIGNATURE-LEVEL way — no
  whole-program dataflow, declared types are the trust boundary.
- **Class:** marker laundering / taint erasure at internal boundaries.
  Two dual gaps: (A) a call returning a declared `Secret<...>`/`PII<...>`/
  `Untrusted<...>` seeded NO taint (`let t = getToken(); print(t)` — exit
  0); (B) a marked value passed to a helper's plain-typed param erased the
  marker (`logIt(password)` with `logIt(msg: String)` — exit 0). Both
  confirmed empirically before any code.
- **Gap A fix — return-type seeding:** `_marker_source_fns` (stdlib
  constructors `classify`/`classifyPII`/`classifyUntrusted` + user
  `returns <Marker><...>` decls) feeds the shared taint fixpoint of
  E0712/E0715/E0724/E0725/E0726/E0728. Inline source calls
  (`print(classify("pw"))`) flag too.
- **Gap B fix — new diagnostic E0729** (`check_marker_boundary`): a
  Secret/PII/Untrusted value into a user-declared callee param NOT typed
  with the marker is refused as laundering. Sanctioned exits: the
  marker's unwrappers (`reveal`/`redact`/per-sink sanitizers/`trusted`)
  or a marker-typed param. `Authorized<T>` deliberately excluded (proof
  marker — a widening rule there would RELAX acceptance).
- **Non-breaking, with one real interaction found and fixed properly:**
  `bench/realworld_xss/fixed.aeth` (`print(search(classifyUntrusted(x)))`)
  initially fired E0724 — the source call is CONSUMED by `search`'s
  `Untrusted`-typed param. Fixed by sanctioned-crossing pruning
  (`_marker_param_mask`): an arg feeding a marker-typed param of a
  user-declared callee is the callee's responsibility; what escapes is
  its return, covered by seeding. Corpus back to 0× (33 programs clean),
  never silenced.
- **Ratchet raised same commit:** 38→39 codes, 28→29 detectors (6aff558).
- **Files:** `passes/effects.py` (`_STDLIB_MARKER_CONSTRUCTORS`,
  `_marker_source_fns`, `_marker_param_mask`, widened `_expr_leaks_marked`/
  `_marked_tainted_names`, `check_marker_boundary`), `cli.py`,
  `grammar/diagnostics.md` (row + seeding prose), `tests/test_effect_scope.py`
  (13 tests), `tests/ratchet_baseline.json`, `playground/examples/24_*.aeth`,
  `demos/case_studies/marker_laundering/`, q1 + taxonomy updated.
- **TYPE gap surfaced for next iter:** body-level return laundering — a
  function whose body RETURNS a tainted local under a plain declared
  return type still washes the marker (declared signatures are the trust
  boundary; no body inference). Sibling residuals: stdlib transforms
  (`trim(secret)` → plain String) outside E0729 v1 scope; HOF /
  function-typed callees skipped. All three pushed to q1.
- **Suite:** exit 0 (ratchet green at floor = current 39/29).

---

## Iteration 40 — return laundering: the lying signature (E0730)

- **Author:** main thread (Fable 5). Iteration 39's surfaced residual,
  closed the same day — the q3 cheap-win profile: near-zero new
  machinery (one `_walk_returns` walker + the iter-39 helpers reused
  verbatim).
- **Class:** a function whose BODY returns a `Secret<...>`/`PII<...>`/
  `Untrusted<...>`-carrying value while its DECLARED return type is
  plain — the signature lies, the marker is washed off for every
  caller. Return-direction dual of E0729.
- **Gap confirmed first:** `function leak(pw: Secret<String>) returns
  String do return pw end` + `print(leak(password))` → exit 0 on the
  pre-iteration build (`gap_c_return_launder.aeth`).
- **New diagnostic: E0730** (`check_return_laundering`): per marker,
  skip functions with an honest marker-typed `return_type` (callers
  taint via seeding); otherwise flag any `Return` whose value leaks the
  marker. Sanctioned exits: declare the marker-typed return, or unwrap
  (`reveal`/`redact`/sanitizers/`trusted`) at the return site.
  `Authorized<T>` excluded (proof marker — plain-typed return only
  over-restricts).
- **The signature loop is now closed:** seeding (returns IN), E0729
  (params IN), E0730 (returns OUT) — declared signatures are ENFORCED
  in both directions, no longer merely trusted. "Signature-level
  interprocedural" is now a checked contract, not an assumption.
- **Non-breaking:** alsp corpus has zero marker files; false_positive
  gate (fixed.aeth + clean examples) green. One known TRUE positive on
  the ungated evidence corpus: `bench/realworld_xss/vulnerable.aeth`
  now fires E0730 alongside E0725 (header comment updated, nothing
  suppressed).
- **Ratchet raised same commit:** 39→40 codes, 29→30 detectors (8bb33db).
- **Files:** `passes/effects.py` (`_walk_returns`,
  `check_return_laundering`), `cli.py`, `grammar/diagnostics.md` (row +
  prose), `tests/test_effect_scope.py` (7 tests),
  `tests/ratchet_baseline.json`, `playground/examples/25_*.aeth`,
  `demos/case_studies/return_laundering/`, q1 + taxonomy updated.
- **TYPE gap surfaced for next iter:** stdlib transform propagation —
  `trim(secret)` / `padLeft(secret, …)` return plain values from stdlib
  signatures the marker model doesn't cover: the last laundering channel
  inside the modeled surface. Needs a stdlib marker-propagation table
  (input-marker → output-marker per stdlib fn). Sibling residual:
  boundary-sanitizer coarseness (any per-sink sanitizer clears the
  generic boundary — a `sanitizeLog`'d value returned as String could
  still XSS at an HTML sink). Both pushed to q1.
- **Suite:** exit 0 (ratchet green at floor = current 40/30).

---

## Infra — monotonic ratchet (Aether may only improve)

- **Author:** main thread (Fable 5), at the human's request: guarantee the
  self-teaching agent can only move Aether FORWARD.
- **Mechanism: `tests/test_ratchet.py`** (wired into the gate, `ratchet:
  PASS`), backed by `tests/ratchet_baseline.json`:
  1. **Detector floor.** Counts distinct emitted `Exxxx` codes (38) and
     gated `check_*(ast)` passes (28); asserts current ≥ the committed
     floor. Removing a detector — even deleting its code+doc+test together
     so the rest of the suite stays green — drops the count below the floor
     and turns the gate RED. Proven: floor 39 vs current 38 → exit 1.
  2. **Gain-lock reminder.** When current > floor, the test prints the
     exact numbers to raise the baseline to, so each addition is locked
     permanently. Proven: floor 37 → "raise to 38" note.
  3. **Fixed bugs stay fixed.** Every real `[FIXED <commit>]` entry in
     BUGS.md must name an existing `test:` regression file, so a repaired
     bug can't silently reappear.
- **Contract updated:** `tools/self_teaching_agent.md` §4 and `CLAUDE.md`
  step 6 now state the one-directional rule — never remove/weaken a
  detector, never lower the baseline, raise it when you add, add a `test:`
  line when you fix a BUGS.md entry.
- **Legitimacy guard (added same session).** A raised count must be a REAL
  detector, not a bumped number: every protected detector code (E07xx +
  E02xx≠E0201) must be actually emitted by a pass AND asserted by a test
  that proves it fires. Proven: a documented-but-dead `**E0799**` doc row
  with no pass → gate RED ("not emitted by any transpiler pass").
- **Git-monotonicity guard (added same session).** Closes the one edit the
  count-floor couldn't self-catch — lowering a baseline number. The
  working-tree baseline is compared against `git show HEAD:...`; any
  decrease is RED before it can be committed. Proven via a mocked
  higher committed floor → "baseline was LOWERED ... may only be raised".
- **Ratchet now has 4 layers:** count floor · legitimacy · git
  monotonicity · fixed-bugs-stay-fixed. Aether can only move forward, and
  every forward step is a verified, tested detector.
- **Suite:** exit 0 (with the ratchet gate green at floor = current).

---

## Next-iteration checklist (for the loop)

1. Read the previous report's "TYPE gap for next iter".
2. Find a real, citable OSS CVE of that class (prefer high-user-count
   projects). Confirm the gap empirically first (does current Aether
   accept the bad shape?).
3. Improve Aether to reject the whole TYPE; keep the change
   one-directional/conservative so legitimate code passes.
4. Survey the repo for existing usages the new rule would flag; update
   only tests that assert the *old* permissive behavior, never silence
   the rule.
5. Add: doc row, focused test, gate line, (optional) playground example.
6. Re-run the full suite to exit 0. Write the report + append here.
