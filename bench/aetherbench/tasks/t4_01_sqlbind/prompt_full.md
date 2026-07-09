# parameterized query (E0713) (t4_01_sqlbind)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module UserRepo
  requires capability db
  requires capability log
  exports findUser
end

function findUser(userId: String) returns Unit
  effects db.query, log
  // query users by id with sqlBind; then print "LOOKED-UP " + userId

main() calls findUser("42").
```

## Required stdout (exact)

```
LOOKED-UP 42
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
