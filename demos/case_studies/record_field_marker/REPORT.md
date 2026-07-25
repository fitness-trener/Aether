# Case study — taint markers carried in a record field

**Class:** PII egress (CWE-359), reached through a container.
**Codes:** E0715 (×2) on `aether/vulnerable.aeth`; `aether/fixed.aeth` clean.

## The shape

Real services do not pass personal data as bare parameters; they pass a
struct. `record User do email: PII<String> ... end` is the declaration
that says *this container carries personal data in this field*.

## The gap (probe-confirmed, before the fix)

`transpiler/aether/passes/detector_specs.py`'s `_is_marker_type` matched a
marker only at the top of a type node. Four consequences, all measured on
the build at commit `f98fdce`:

| Shape | Result before |
|-------|---------------|
| `record User do email: PII<String> end` + `print("user=" + u.email)` + `writeFile(p, "user=" + u.email)` | exit 0 — no diagnostic |
| `function leak(xs: List<PII<String>>) ... print(toString(xs))` | exit 0 — no diagnostic |
| `leak(User(classifyPII(e), "jane"))` where `leak(u: User)` | E0729 **false positive** |
| `function build(e: PII<String>) returns User do return User(e, "jane") end` | E0730 **false positive** |

The false positives are the other half of the same bug: with no way to
express "this record carries the marker", the safe shape was unwritable,
which is why the unsafe shape went unnoticed.

## The fix

Two changes in the shared marker machinery, so all six marker-flow rows
(E0712/E0715/E0724/E0725/E0726/E0728) and both boundary detectors
(E0729/E0730) inherit them:

1. `_type_carries_marker` searches the whole type tree, so a marker nested
   in a generic argument (`List<PII<String>>`) counts. `_is_marker_type`
   keeps its top-level-only rule for `Authorized<T>` — widening a PROOF
   marker would relax acceptance, the wrong direction.
2. `_marker_param_mask` emits a mask for every `RecordDecl` too, keyed by
   the record name and indexed by declared field order (v0.1 records are
   constructed positionally). A marker-typed field is a sanctioned
   crossing exactly like a marker-typed parameter. `_marker_field_names`
   makes a read of such a field a taint source.

## Limits (honest)

- Field matching is **by name**, not by resolved record type. A plain
  `email` field on an unrelated record is flagged too. Over-flag, never
  miss within the modeled surface — not a soundness proof.
- The record-typed name itself is never tainted; only the field read is.
  Passing the record on is a clean crossing by design.
- Putting a marked value into a **plain** field still launders the marker
  and is still refused, by E0729 (record-typed argument) or E0730
  (record-typed return) at the crossing.
- Still syntactic and intraprocedural. Residuals:
  `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`.
