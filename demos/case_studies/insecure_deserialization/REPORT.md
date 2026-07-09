# Case study — Insecure Deserialization (CWE-502)

**Iteration 12 of the self-teaching loop.** Class: insecure
deserialization — the pickle / Java `readObject` / unsafe-YAML gadget
class, where untrusted bytes reach an unrestricted decoder that can
instantiate arbitrary types and execute code during construction. One of
the most damaging RCE classes in the wild (Python pickle, `ObjectInputStream`,
Ruby Marshal, PHP `unserialize`).

## The gap (confirmed empirically first)

Before this iteration, `deserialize(raw)` on a `String` parameter passed
`aether check` at **exit 0** — the effect passes see a pure call; nothing
flags that `raw` is untrusted and the decoder is unrestricted.

## The rule (E0720)

`deserialize` on any non-literal (untrusted) argument is refused. Like
SSTI (E0719) there is **no sanitizer** — an unrestricted decoder on
attacker bytes has no safe form. The sanctioned alternative is a
different function, `schemaDecode(schema, data)`, a decoder pinned to a
fixed schema that can only ever produce the declared shape.

## Before → after

| Form | `aether check` |
|---|---|
| `deserialize(raw)` (vulnerable.aeth) | **E0720, exit 2** |
| `schemaDecode("SessionV1", raw)` (fixed.aeth) | OK, exit 0 |

`aether run fixed.aeth` prints `SessionV1:cookie=abc;__reduce__=os.system(...)`
— the gadget payload is inert data under the schema, never executed.

## Design note

E0720 is a near-clone of E0719: same literal-only "safe" predicate
(reusing `_safe_template_names` for the trusted-constant case), but the
repair is a *sibling function* (`schemaDecode`) rather than a wrapper.
This is the honest model — you don't sanitize your way into a safe
`deserialize`, you switch to a schema-bound decoder.

## Residual limit (stated honestly)

E0720 keys on the `deserialize` callee name and its argument shape. It
does not track whether a value bound through several hops or read from a
trusted-but-dynamic source is genuinely untrusted — a `deserialize` on
any non-literal is refused (over-flag). Distinguishing trusted dynamic
sources would need the same provenance/taint-origin machinery flagged as
the next structural investment in q1/q3.
