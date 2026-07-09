# resource-bound authorization (E0717) (t4_08_idor)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `updateDoc(docId, user)` that gets a proof from authorizeResource(user, "docs:edit", docId) and mutates via sqlByOwner(stmt, docId, proof) with the SAME docId — a mismatched id is rejected as IDOR. Print "UPDATED " + docId. main() calls updateDoc("doc-1", "alice").

## Required stdout (exact)

```
UPDATED doc-1
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
