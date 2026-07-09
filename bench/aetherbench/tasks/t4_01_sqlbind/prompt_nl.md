# parameterized query (E0713) (t4_01_sqlbind)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `findUser(userId)` that queries "SELECT * FROM users WHERE id = ?" with the id bound via sqlBind (never concatenated), then prints "LOOKED-UP " + userId. main() calls findUser("42"). Must pass aether check.

## Required stdout (exact)

```
LOOKED-UP 42
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
