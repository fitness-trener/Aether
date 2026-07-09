# Case study — Server-Side Template Injection (SSTI, CWE-94)

**Iteration 10 of the self-teaching loop.** Class: server-side template
injection — the Jinja2/Flask/Handlebars/Twig incident shape, where
untrusted input is concatenated into the *template* string (not the data
model) and the engine evaluates it → remote code execution. Real-world
instances are legion (Flask/Jinja2 `{{7*7}}` → RCE, CVE-heavy across
Python, Node Handlebars, Java Velocity/Freemarker).

## The gap (confirmed empirically first)

Before this iteration, `renderTemplate("<h1>Hello " + userName + "</h1>", "")`
passed `aether check` with **exit 0** — the effect/capability passes see
a pure call; nothing flags that the *template* is attacker-steerable.

## The rule (E0719)

`renderTemplate`'s first argument (the template) must be a fixed string
literal, or a name bound only to literals. Untrusted input belongs in the
second (data) argument, which the engine escapes rather than evaluates. A
template built by concatenation or taken from a parameter is refused.

There is **no sanitizer** for this class — unlike E0713 (`sqlBind`) or
E0711 (`safeJoin`), the only correct form is a fixed template. The repair
is structural: move the untrusted value from the template slot to the
data slot.

## Before → after

| Form | `aether check` |
|---|---|
| `renderTemplate("Hi " + userName, "")` (vulnerable.aeth) | **E0719, exit 2** |
| `renderTemplate("<h1>Hello {}</h1>", userName)` (fixed.aeth) | OK, exit 0 |

`aether run fixed.aeth` prints `<h1>Hello {{7*7}}</h1>` — the `{{7*7}}`
payload is rendered as inert text, never evaluated to `49`.

## Design note — the sink+literal shape, minus the sanitizer

E0719 is the leanest member of the injection family: it reuses the exact
`_safe_*_names` straight-line fixpoint as E0713/E0714/E0718, but the
"safe" predicate admits only a literal (no sanctioned-call escape hatch).
This is the honest model of the class — SSTI has no safe way to build a
template from user input.

## Residual limit (stated honestly)

Template safety is checked at the `renderTemplate` call site by the
syntactic shape of the template argument. A template read from a file or
a database (`readFile(...)` → renderTemplate) is refused as non-literal —
correct for untrusted template stores, but it also refuses a trusted
on-disk template bundle. Distinguishing trusted template *sources* from
untrusted ones (a `TrustedTemplate<T>` provenance marker) is the surfaced
gap for a future iteration.
