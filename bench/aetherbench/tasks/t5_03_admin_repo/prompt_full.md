# sqlBind + authorize combined (t5_03_admin_repo)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module AdminRepo
  requires capability db
  requires capability log
  exports deleteUser
end

function deleteUser(userId: String, admin: String) returns Unit
  effects db.exec, log
  // bound DELETE with authorize(admin, "users:delete") proof;
  // print "DELETED " + userId

main() calls deleteUser("7", "root").
```

## Required stdout (exact)

```
DELETED 7
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
