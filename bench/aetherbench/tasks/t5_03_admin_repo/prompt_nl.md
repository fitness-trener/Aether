# sqlBind + authorize combined (t5_03_admin_repo)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `deleteUser(userId, admin)` executing a bound DELETE (sqlBind) via sqlExec with an authorize(admin, "users:delete") proof, printing "DELETED " + userId. main() calls deleteUser("7", "root"). Must pass aether check.

## Required stdout (exact)

```
DELETED 7
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
