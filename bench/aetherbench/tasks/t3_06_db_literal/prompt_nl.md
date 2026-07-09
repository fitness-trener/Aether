# db.query with a fixed literal (t3_06_db_literal)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write a Repo module (db + log capabilities) with `listUsers()` that runs the fixed query "SELECT id FROM users" via sqlQuery and prints "QUERIED". main() calls it.

## Required stdout (exact)

```
QUERIED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
