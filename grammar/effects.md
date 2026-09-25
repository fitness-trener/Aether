# Aether Effect System (v0.1)

Every function declares its effects. Pure functions write `effects pure` (the explicit form is required — there is no implicit-pure).

An effect is a dotted path: `category.action` or `category.action(arg)`,
e.g. `fs.read`, `net.fetch("https://api.example.com/*")`.

## Effects the standard library performs

The static checker's registry (`_STDLIB_EFFECTS` in
`transpiler/aether/passes/effects.py`, from which `passes/capability.py`
derives its path table) is the complete list. Every other stdlib
function is `pure`. `tests/test_spec_docs.py` fails if this table and the
code disagree.

<!-- BEGIN stdlib-effects (checked by tests/test_spec_docs.py) -->
| Stdlib function | Effect | Capability required |
|---|---|---|
| `now` | `time.now` | `time` |
| `print` | `log` | `log` |
| `readFile` | `fs.read` | `fs` |
| `readLine` | `log` | `log` |
| `redirect` | `net.redirect` | `net` |
| `shellExec` | `exec.run` | `exec` |
| `sqlByOwner` | `db.exec` | `db` |
| `sqlExec` | `db.exec` | `db` |
| `sqlQuery` | `db.query` | `db` |
| `writeFile` | `fs.write` | `fs` |
<!-- END stdlib-effects -->

A function may also declare effects no stdlib function performs. The one
the checker reads is `net.fetch(url-glob)`: its URL glob is what the
`E0710` (unpinned host), `E0721` (cleartext `http://`) and `E0722`
(link-local / metadata address) rows inspect. Any other dotted path is
accepted as a declaration and takes part in composition (`E0801`) and
capability checking (`E0701`) like any other effect.

## Composition rule — checked statically (`E0801`)

Every call to a declared function or a stdlib function must have each of
the callee's effects covered by the caller's `effects` clause; a function
passed as a value counts as a callee of the call it is handed to.
`effects pure` declares the empty set, so a `pure` function may only call
`pure` functions. Coverage is decided on the parsed path, not on strings:

- the paths must be **equal** — a caller declaring `fs` does not cover
  `readFile`'s `fs.read` (measured: `E0801`);
- a caller effect **without** an argument covers the same path with any
  argument (`net.fetch` covers `net.fetch("https://api.x/*")`);
- a caller effect **with** a glob argument covers a callee argument the
  glob matches, where `*` matches any run of characters.

Not decided statically at this version: `pure` written alongside other
effects is not rejected, and effect names are not validated against a
list (`audits/audit_2026-09-24_plan.md`, A11).

## Capability gating — checked statically (`E0701`)

Each effect needs the capability named by its first path segment
(`fs.read` → `fs`, `net.fetch` → `net`), except `pure`, `panic` and
`mutate(...)`, which need none. A module declares the capabilities it
needs:

    module BillingService
      requires capability db
      requires capability net
      requires capability log
      exports processInvoice
    end

The capabilities a module may name (`_KNOWN_CAPABILITIES` in
`passes/modules.py`; any other name is `E0704`):

<!-- BEGIN known-capabilities (checked by tests/test_spec_docs.py) -->
`db`, `exec`, `fs`, `log`, `mutate`, `net`, `panic`, `random`, `time`
<!-- END known-capabilities -->

When the file declares at least one module, the checker computes each
function's transitive effect set through direct calls and refuses, with
`E0701`, any effect whose capability no module declares. When the file
declares **no** module, every capability is granted and `E0701` never
fires (measured: a module-less `print` program passes `check` and runs).

This is a static check. At this version there is no runtime capability
check: the runtime does not consult the module's capability list.

## Runtime effect tracking (`--effect-strict`, opt-in)

`aether run --effect-strict` records every effect a stdlib call performs
and raises `E0501` for an effect inside a function declared `pure`, or
`E0502` for an effect not in the running function's declared set. The
runtime match is by **prefix** (a declared `fs` admits an observed
`fs.read`), which is looser than the static rule above. These are runtime
guarantees, not static proof.

## Default effect annotations on standard library functions

See `stdlib.md` for the full list. A few high-frequency examples:

    function readFile(path: String) returns Result<String, String>
      effects fs.read

    function writeFile(path: String, contents: String) returns Result<Unit, String>
      effects fs.write

    function now() returns Instant
      effects time.now

    function print(s: String) returns Unit
      effects log

## Why effects are first-class for AI generation

A model proposing a function body must declare which effects it performs.
If the body calls a declared or stdlib function whose effects are not
declared, `check` refuses it with a structured `E0801` diagnostic pointing
at the call. This makes "I think this function is pure" a checkable claim
for every call the checker can see.
