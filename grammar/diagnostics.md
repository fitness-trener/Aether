# Aether Diagnostic Catalog

Every diagnostic the toolchain can emit has a stable code, a category,
a severity, and a machine-readable `extra` dict. This catalog is the
contract; the regression test `tests/test_diagnostic_catalog.py`
enforces that every code grep'd from the source tree is documented
here.

The code-number ranges are stable:

| Range       | Category               | Where emitted |
|-------------|------------------------|---------------|
| E01xx       | lex                    | `transpiler/aether/lexer.py` |
| E02xx       | parse                  | `transpiler/aether/parser.py` |
| E03xx       | contract / refinement  | `transpiler/aether/runtime.py` |
| E05xx       | effect (runtime)       | `transpiler/aether/runtime.py` (opt-in `--effect-strict`) |
| E06xx       | timeout                | `bench/harness.py` |
| E07xx       | capability             | `transpiler/aether/passes/capability.py` |
| E08xx       | effect (static)        | `transpiler/aether/passes/effects.py` |
| E09xx       | (reserved for SMT)     | unused at v0.3; reserved by `AUDIT_B.md` |
| E9xxx       | internal / harness     | `bench/harness.py` |

All codes below are listed with: short description, where they fire,
what's in `extra`, and what an agent fix-loop is supposed to do.

---

## Lex (E01xx)

| Code | Description | Fires when |
|------|-------------|------------|
| **E0101** | unexpected character | the lexer sees a character that isn't part of any token |
| **E0102** | unterminated `/* */` comment | EOF inside a block comment |
| **E0103** | unterminated string literal | EOF before closing `"` |
| **E0104** | unknown string escape | e.g. `"\q"` |
| **E0105** | expected digits after exponent | e.g. `1e` with no digits |
| **E0106** | keyword has trailing `?` / `!` | e.g. `if?` |

## Parse (E02xx)

| Code | Description |
|------|-------------|
| **E0201** | parse error (unified code for every "expected X, got Y") |

Emitted by `Parser.err`. The lenient `parse_collect` (C.6) accumulates
all E0201 diagnostics it can recover past; strict `parse` raises on
the first.

## Contract / refinement (E03xx)

| Code | Description | `extra` keys |
|------|-------------|--------------|
| **E0301** | `requires` (precondition) violation | `function`, `clause_kind="requires"`, `clause_text`, `args` |
| **E0302** | refinement-type boundary violation (B.4) | `type`, `binding`, `predicate`, `value_repr` |
| **E0303** | refinement predicate raised exception (B.4) | `type`, `binding`, `predicate`, `value_repr` |
| **E0304** | `ensures` (postcondition) violation (D.2 split from E0301) | `function`, `clause_kind="ensures"`, `clause_text`, `args` |
| **E0305** | stdlib precondition violation (D.2 split from E0301) | `stdlib_function`, optionally `value` |

**Caller-vs-implementer split (D.2):** `E0301` always means "the caller
gave bad input"; `E0304` always means "the implementation lied about
what it returns". An agent fix-loop can read the code alone and decide
where to apply the fix.

## Effect — runtime (E05xx)

These fire at runtime when `--effect-strict` is enabled or
`set_effect_strict(True)` is called. The static checks (E0801) are
default-on and catch most cases before runtime.

| Code | Description |
|------|-------------|
| **E0501** | effect performed inside a function declared `pure` |
| **E0502** | effect not in the function's declared effect set |

## Timeout (E06xx)

| Code | Description | `extra` |
|------|-------------|---------|
| **E0601** | program execution exceeded `timeout_ms` | `timeout_ms` |

Bench-harness only. The CLI does not currently enforce timeouts;
`bench/harness.py:compile_and_run` does, via POSIX `SIGALRM`.

## Capability (E07xx)

| Code | Description | `extra` keys |
|------|-------------|--------------|
| **E0701** | function's transitive effect closure requires a capability not declared by any module | `function`, `effect`, `required_capability`, `declared_capabilities`, `via_transitive` |
| **E0702** | module exports a name that isn't declared in this file (D.3) | `module`, `exported`, `declared_names` |
| **E0703** | more than one `module ... end` in a single file (v0.3 is single-file; D.3) | `first_module`, `duplicate_module` |
| **E0704** | module requires a capability outside the known vocabulary (D.3) | `module`, `capability`, `known` |
| **E0710** | a `net.fetch` effect leaves the host/authority unpinned (bare `*`, `scheme://*`, wildcard scheme, or leading `*` that is not a `*.subdomain` pin), admitting SSRF to internal hosts like `169.254.169.254` | `function`, `effect_arg`, `reason` |
| **E0711** | `readFile`/`writeFile` is called with a path that is neither a fixed string literal nor routed through `safeJoin(...)`, i.e. a path steerable by untrusted input (path-traversal / Zip-Slip precondition) | `function`, `sink`, `reason` |
| **E0712** | a `Secret<...>`-marked value reaches a log sink (`print`) without an explicit `reveal(...)` — the "secret/PII accidentally logged" class (CWE-532) | `function`, `sink` |
| **E0713** | a `sqlQuery`/`sqlExec` query argument is built by raw string concatenation (or another dynamic expression) instead of a fixed literal or `sqlBind(...)` parameterized query — SQL injection (CWE-89) | `function`, `sink`, `reason` |
| **E0714** | a `shellExec` argument is built by raw string concatenation (or another dynamic expression) instead of a fixed literal or `shellArg(...)`-quoted command — command injection (CWE-78) | `function`, `sink`, `reason` |
| **E0715** | a `PII<...>`-marked value reaches a log sink (`print`) or the contents of `writeFile` without `redact(...)` — personal data persisted/logged in the clear (data-residency / GDPR leak) | `function`, `sink` |
| **E0716** | a data-mutating sink (`sqlExec`) is called without an authorization proof in its dataflow — the auth argument is absent or not a proven `Authorized<...>` value (an `authorize(...)` call, an `Authorized<T>` parameter, or a binding of one) — missing authorization (CWE-862/863) | `function`, `sink`, `reason` |
| **E0717** | a resource-scoped mutation (`sqlByOwner(stmt, resourceId, proof)`) whose `proof` is not an `authorizeResource(principal, action, resourceId)` result bound to the SAME `resourceId` the sink mutates — missing, unbound, or wrong-resource authorization — IDOR / cross-tenant data access (CWE-639) | `function`, `sink`, `reason` |
| **E0718** | a `redirect` target is neither a fixed literal nor a `safeRedirect(host, path)` result — an untrusted/dynamic redirect target (open redirect, CWE-601) | `function`, `sink`, `reason` |

E0701 comes from the B.3 default-on capability pass. E0702/E0703/E0704
come from the D.3 module-validation pass — also default-on, opt out
with `--no-module-check`. Programs without any module declaration
retain an implicit all-grant; the module pass is a no-op for them.

E0710 comes from the broad-scope pass — default-on, opt out with
`--no-scope-check`. It refuses the *promise* itself when a fetch scope
is broad enough to be steered inward, closing the SSRF precondition
that E0801/E0701 (which a wildcard scope satisfies) cannot see.
Path/query wildcards (`https://api.x/charge/*`) and subdomain pins
(`https://*.corp.example/*`) keep the host bounded and pass untouched.

E0711 is the filesystem sibling from the same reach-scope pass (also
default-on, same `--no-scope-check` opt-out). A `readFile`/`writeFile`
path that is a fixed literal, or is built with the `safeJoin` stdlib
sanitizer (which strips `..` and absolute roots), is safe; any other
path expression is steerable by untrusted input and is refused —
closing the path-traversal / Zip-Slip precondition.

E0712 is the taint sibling in the same reach-scope pass. `Secret<T>` is
a compile-time-only marker type (erased at runtime); taint originates at
`Secret`-typed parameters and propagates through straight-line bindings.
A value still carrying the marker cannot reach `print`; `reveal(...)` is
the sanctioned, auditable disclosure that clears it. `classify(x)` wraps
a value as `Secret<T>`. Same `--no-scope-check` opt-out.

E0713 is the injection sibling in the same reach-scope pass. The
`sqlQuery` sink (effect `db.query`) must receive a fixed string literal
or a `sqlBind(template, value)` parameterized query (which escapes the
value so it cannot break out of the string). A raw `+` concatenation or
any other dynamic query expression is refused. Same `--no-scope-check`
opt-out; same sink+sanitizer+literal shape as E0711/`safeJoin`.

E0714 is the command sibling of E0713 (the OpenSSL `c_rehash`
CVE-2022-1292 shape: a filename concatenated into a shell command line).
The `shellExec` sink (effect `exec.run`, capability `exec`) must receive
a fixed string literal or a `shellArg(template, value)` result (which
quotes the value as a single argument so it cannot inject `;`/`|`/`$( )`
shell syntax). A raw `+` concatenation or any other dynamic command
expression is refused. Same `--no-scope-check` opt-out.

E0715 is the PII-egress sibling of E0712 in the same reach-scope pass:
same taint machinery, distinct marker `PII<T>` and distinct sanctioned
exit `redact(...)` (which masks the value — emails keep first char +
domain). A PII value must not reach `print` (logs) or the contents
argument of `writeFile` (disk) in the clear. `classifyPII(x)` wraps a
value as `PII<T>`. This is the data-residency / GDPR-leak class. Same
`--no-scope-check` opt-out. (Network-body egress is deferred until a
body-carrying stdlib net sink exists.)

E0716 inverts the taint polarity of E0712/E0715 in the same reach-scope
pass: instead of "a marked value must not reach a sink", a mutating
sink REQUIRES a marked value in its dataflow. `sqlExec(stmt, auth)` —
a data-mutating statement (effect `db.exec`, capability `db`) — must
receive as `auth` a proof of authorization: a direct
`authorize(principal, action)` guard call, an `Authorized<T>`-typed
parameter (the caller authorized; the proof crosses the call boundary),
or a name bound only to those. Omitting the argument or passing
anything unproven is refused — the missing-authorization class
(CWE-862/863; the Ivanti EPMM CVE-2023-35078 shape: a mutating API
path reachable with no auth check on it). Conservative direction: a
proof the checker cannot see is refused (over-flag, never miss).
`sqlExec`'s query argument is additionally covered by E0713. Same
`--no-scope-check` opt-out.

E0717 is the resource-binding extension of E0716 in the same reach-scope
pass. E0716 proves *an* authorization happened on the dataflow — but not
that it named the SAME resource being mutated, so an authorized caller
can still reach ANOTHER tenant's row (broken object-level authorization
/ IDOR, CWE-639, OWASP API1). The resource-scoped sink
`sqlByOwner(stmt, resourceId, proof)` (effect `db.exec`, capability
`db`) requires its `proof` to be an `authorizeResource(principal,
action, resourceId)` result — a direct call or a name bound exactly once
to one — whose id expression resolves to the same identity as the sink's
`resourceId`: an identical literal, or the same *stable* name (a
parameter or a name bound exactly once, so it denotes one value for the
whole body). Anything the checker cannot relate — a computed id, a
rebound name, a proof carried across a call boundary as a plain
`Authorized<T>` parameter — is refused (over-flag, never miss).
`sqlByOwner`'s statement argument is additionally covered by E0713.
Same `--no-scope-check` opt-out.

E0718 is the open-redirect sibling of E0711 in the same reach-scope pass
(CWE-601). The `redirect` sink (effect `net.redirect`, capability `net`)
must receive a fixed literal target or a `safeRedirect(host, path)`
result, which strips any scheme/authority and leading slashes from
`path` so the target can only ever stay on `host` (defeating both
absolute-url and protocol-relative `//evil.com` redirects). A bare
parameter, a concatenation, or any other dynamic target is refused.
Same `--no-scope-check` opt-out.

## Effect — static (E08xx)

| Code | Description | `extra` keys |
|------|-------------|--------------|
| **E0801** | callee's effects not covered by caller's declared set (B.1 + B.2) | `caller`, `callee`, `caller_effects`, `missing_effect` |

Default-on. Opt out per-file with `aether check --no-static-effects`.
Glob-matching on effect args (B.2) is part of this code.

## Internal / harness (E9xxx)

These are emitted by `bench/harness.py` only, when something below the
Aether layer fails. They don't indicate user-code bugs; they indicate
toolchain/sandbox/etc. issues.

| Code | Description |
|------|-------------|
| **E9001** | emit error (Python `compile()` rejected the emitted source) |
| **E9002** | internal error (parser/emitter raised something other than `AetherError`) |
| **E9003** | Python runtime error inside the candidate (e.g. divide-by-zero with no precondition) |

## SMT contract proving — E09xx (opt-in, `aether check --prove`)

Emitted by `transpiler/aether/passes/smt.py`. The pass is opt-in
(`--prove`) and requires the optional `z3-solver` dependency
(`pip install 'aether-lang[smt]'`).

| Code | Description | `extra` fields |
|------|-------------|----------------|
| **E0901** | SMT-refuted `ensures` clause: the solver found concrete inputs that satisfy every `requires` clause and every param refinement predicate but violate the postcondition | `function`, `clause_kind="ensures"`, `clause_index` (0-based), `counterexample` |
| **E0902** | SMT solver returned `unknown` (usually the per-obligation timeout, default 5000 ms, `--prove-timeout-ms`); warning — the clause keeps its runtime check | `function`, `clause_kind`, `clause_index`, `timeout_ms` |

E0901's `counterexample` maps param names (plus `result`) to the
violating values, so a fix-loop can re-prompt with them.

The pass only analyzes a restricted fragment (Int/Bool params,
single-`return` bodies, linear arithmetic without `/` and `%`);
everything else is counted `skipped` in the `prove:` summary and keeps
runtime checks. A function whose `requires` clauses or param
refinements do not translate is skipped entirely — dropping an
assumption would fabricate spurious counterexamples.
