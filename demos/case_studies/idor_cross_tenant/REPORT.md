# Case Study + Aether Improvement: cross-tenant data access / IDOR

**Date:** 2026-07-04
**Loop iteration:** 8 (bigtech class from the self-teaching agent's §5:
cross-tenant / object-level authorization — taxonomy backlog **B9**)
**Target class:** an authenticated, action-authorized caller mutating a
resource that belongs to ANOTHER tenant — **broken object-level
authorization / IDOR, CWE-639** (OWASP API1, the #1 API risk). The shape
behind Facebook's "delete any photo" bug and the Peloton account-data
disclosure: the request passes authentication and even a coarse
permission check, but the id it *authorizes* is not the id it *touches*.

## 1. The failure class (TYPE, not instance)

Every function is locally fine: input validated, query parameterized (no
injection), effects declared, AND an authorization call is present on the
path (so E0716 is satisfied). The lie is one level deeper — the
authorization named resource `A`, the mutation touches resource `B`. Two
correct-looking ids that happen to differ. Local review cannot see it;
only relating the guard's id to the sink's id shows the gap, which is why
IDOR dominates bug-bounty reports at scale.

## 2. The gap this exposed in Aether

E0716 proves *an* authorization is on the dataflow of a mutation — but
not that it named the SAME resource being mutated. Confirmed
empirically: a handler that calls `authorizeResource(user, "docs:edit",
requestedId)` and then mutates a DIFFERENT `victimId` checked **clean,
exit 0** before this iteration (the auth proof existed, so nothing
flagged it).

## 3. The improvement — E0717, the resource-binding extension of E0716

- **`sqlByOwner(stmt, resourceId, proof)`** — a new stdlib
  resource-scoped mutation sink (effect `db.exec`, existing `db`
  capability). Its `stmt` argument is additionally covered by the E0713
  injection rule (one-line sink-list extension).
- **`authorizeResource(principal, action, resourceId)`** — the
  object-level guard; returns an `Authorized<String>` proof token bound
  to that resource id.
- **E0717** (`check_resource_authorization`) — every `sqlByOwner` call's
  `proof` must be an `authorizeResource(...)` (direct, or a name bound
  exactly once to one) whose id **resolves to the same identity** as the
  sink's `resourceId`. Identity is an identical literal, or the same
  *stable* name — a parameter or name bound exactly once, so it denotes
  one value for the whole body. Anything the checker cannot relate is
  refused.

| Mutation dataflow | Verdict |
|---|---|
| `sqlByOwner(stmt, id)` — no proof | REJECT |
| proof is `authorize(user, action)` (no resource) | REJECT |
| `authorizeResource(u, a, reqId)` ... `sqlByOwner(stmt, victimId, proof)` | REJECT (id mismatch) |
| id reassigned between guard and sink | REJECT (identity unprovable) |
| computed id (not literal/stable name) | REJECT (identity unprovable) |
| `authorizeResource(u, a, docId)` ... `sqlByOwner(stmt, docId, proof)` | ALLOW |
| same literal id in guard and sink | ALLOW |

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0717] function 'updateDoc' mutates a resource via 'sqlByOwner' whose
  authorization is not bound to the same resource id (the proof
  authorizes resource name 'requestedId' but the sink mutates resource
  name 'victimId'); an authorized caller reaching ANOTHER tenant's row is
  the IDOR / cross-tenant class (CWE-639)
exit 2

$ aether check aether/fixed.aeth      # exit 0
$ aether run   aether/fixed.aeth      # exit 0
```

## 5. Regression posture

- Non-breaking: surveyed first — nothing in the repo used `sqlByOwner`,
  `authorizeResource`, or names colliding with them; E0717 fires zero
  times on the corpus (it only fires on the new sink). The E0713 sink
  extension adds a sink no prior code called.
- `sqlByOwner`/`authorizeResource` in `runtime.py` (auto-exported via the
  `_ae_` prefix) + effect registries (`passes/effects.py`
  `_STDLIB_EFFECTS`, `passes/capability.py` `_STDLIB_EFFECT_PATHS`);
  E0717 folded into the `effect_scope` gate in `cli.py`; docs in
  `grammar/diagnostics.md` + `grammar/stdlib.md`; 8 tests in
  `tests/test_effect_scope.py` + `stdlib_d1` runtime assertions; case
  study here; playground example 18. No new capability (`db` already
  known). Full suite green, exit 0.

## 6. Honesty / residual limits

- Aether checks Aether source; `authorizeResource` *models* the
  ownership decision (returns a token) — a real backend would consult
  the row's owner. The guarantee is structural: no `sqlByOwner` path can
  authorize one id and mutate another, not that the ownership policy
  itself is correct.
- Identity matching is **syntactic**, deliberately narrow: identical
  literal or same never-rebound name. It does NOT track that two
  differently-named parameters hold the same value, nor an id threaded
  through arithmetic/string ops — those are refused as unprovable
  (over-flag, never miss). Widening to alias/value equality is a future
  refinement.
- The proof must be resolved **within the function**: a bare
  `Authorized<String>` parameter (E0716's cross-boundary proof) carries
  no resource id, so it is refused by E0717 — a resource-scoped sink
  wants the binding visible where it mutates. A helper that mutates on
  behalf of a caller should authorize the id it receives, not trust an
  opaque token.
- v1 resource sink is `sqlByOwner` only; extending to more scoped sinks
  (a scoped `deleteFile`, a per-tenant net sink) is cheap once they
  exist.

## 7. Files

```
aether/vulnerable.aeth   authorized for requestedId, mutates victimId -> E0717
aether/fixed.aeth        one docId authorized AND mutated             -> OK + runs
```
Playground: `playground/examples/18_idor_cross_tenant.aeth`.
