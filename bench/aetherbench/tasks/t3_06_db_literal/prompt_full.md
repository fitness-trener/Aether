# db.query with a fixed literal (t3_06_db_literal)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Repo
  requires capability db
  requires capability log
  exports listUsers
end

function listUsers() returns Unit
  effects db.query, log
  // runs sqlQuery("SELECT id FROM users") and prints "QUERIED"

main() calls listUsers().
```

## Required stdout (exact)

```
QUERIED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
