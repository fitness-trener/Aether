# resource-bound authorization (E0717) (t4_08_idor)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Docs
  requires capability db
  requires capability log
  exports updateDoc
end

function updateDoc(docId: String, user: String) returns Unit
  effects db.exec, log
  // authorizeResource(user, "docs:edit", docId), then
  // sqlByOwner(boundStmt, docId, proof) — SAME docId;
  // print "UPDATED " + docId

main() calls updateDoc("doc-1", "alice").
```

## Required stdout (exact)

```
UPDATED doc-1
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
