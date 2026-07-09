# Case Study + Aether Improvement: command injection

**Date:** 2026-07-04
**Loop iteration:** 5 (backlog row B2 remainder; first run of the
self-teaching agent per `tools/self_teaching_agent.md`)
**Target class:** CWE-78 OS command injection — untrusted input
concatenated into a shell command line. Modeled on OpenSSL `c_rehash`
(CVE-2022-1292, CVSS 9.8), where certificate file names were
concatenated into shell commands; a crafted filename executed arbitrary
commands. Siblings across every "build the command string by hand"
exec path.

## 1. The failure class (TYPE, not instance)

Command injection = untrusted input assembled into a command line by
concatenation instead of a quoted-argument form. Locally each line is
"run a tool on a file"; the lie is that the interpolated value can carry
shell syntax (`;`, `|`, `$( )`) and change what runs.

## 2. The gap this exposed in Aether

Aether had no exec sink; a command built by concatenation was just a
`String` — invisible to every pass. Confirmed empirically before
building: the concatenated `shellExec("convert " + filename + " out.png")`
shape checked clean (exit 0) on the pre-iteration toolchain.

## 3. The improvement — E0714 (clones the E0713 slice)

- **`exec`** — new capability in the E0704 vocabulary
  (`passes/modules.py`); `exec.run` maps to it via the first-segment
  rule in `passes/capability.py`.
- **`shellExec(cmd)`** — a new stdlib sink carrying effect `exec.run`.
- **`shellArg(template, value)`** — pure quoting sanitizer: binds
  `value` into the first `?` quoted as a single shell argument
  (POSIX `'` -> `'\''` escaping), so it cannot inject shell syntax.
- **E0714** (`check_command_injection` in `passes/effects.py`) — a
  `shellExec` argument that is a raw `+` concatenation (or any dynamic
  expression) rather than a literal or `shellArg(...)` result is a
  compile error. Reuses the straight-line dataflow (a variable bound to
  a `shellArg` result is safe). Folded into the default-on
  `effect_scope` gate (shared `--no-scope-check` opt-out).

| `shellExec` argument | Verdict |
|---|---|
| `"ls -la /var/log"` | ALLOW (literal) |
| `"convert " + filename + " out.png"` | REJECT (concatenation) |
| `shellArg("convert ? out.png", filename)` | ALLOW (quoted) |
| `let cmd = shellArg(...); shellExec(cmd)` | ALLOW (dataflow) |

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0714] function 'convert' builds a shell command for 'shellExec'
  unsafely (command is built by string concatenation - use
  shellArg(...)); untrusted input concatenated into a command line is a
  command injection
exit 2

$ aether run aether/fixed.aeth
EXEC(convert 'x.jpg; rm -rf /' out.png)
```

The identical attack payload, under the fix, is one inert quoted
argument — the `; rm -rf /` stays data, not a second command.

## 5. Regression posture

- Non-breaking, verified by survey before wiring: no `.aeth` or `.py`
  in the repo calls `shellExec`/`shellArg` or declares capability
  `exec`, so E0714 fires zero times on the existing corpus. Adding
  `exec` to the E0704 vocabulary only *widens* what modules may
  declare (and the E0704 test's unknown capability is `quantum`).
- `shellExec`/`shellArg` added to the stdlib runtime + both
  capability/effect registries; documented in
  `grammar/{diagnostics,stdlib}.md`; `shellArg` quoting covered by
  `stdlib_d1` unit assertions. Tests in `tests/test_effect_scope.py`;
  playground example 15. Full suite green, exit 0.

## 6. Honesty

- The direction of error is sound (over-flag): ANY dynamic command
  expression that is not a `shellArg(...)` result is refused, even one
  a human might prove safe. The repair is always available.
- `shellExec` models execution (returns an `EXEC(...)` marker; no real
  process is spawned). `shellArg` models the argv discipline with POSIX
  single-quoting; a real runner would pass an argv array without a
  shell at all. The model is faithful to what the class turns on:
  untrusted input must not alter command structure.
- Detection is on the sink argument's shape; a command smuggled through
  an opaque helper returning a pre-concatenated string needs the taint
  dataflow extended to helper returns — same known limit as E0713.
- B2's last remainder is template injection / SSTI; the bigger prize is
  the bigtech §5 classes (cross-tenant, auth-before-mutation, PII
  egress), which need marker-type machinery like `Secret<T>`'s.

## 7. Files

```
aether/vulnerable.aeth   concatenated command  -> E0714
aether/fixed.aeth        shellArg-quoted       -> OK + runs (payload inert)
```
Playground: `playground/examples/15_command_injection.aeth`.
