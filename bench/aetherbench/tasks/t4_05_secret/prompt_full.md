# secret never logged raw (E0712) (t4_05_secret)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Auth
  requires capability log
  exports authenticate
end

function authenticate(user: String, password: Secret<String>) returns Unit
  effects log
  // print "AUTH user=" + user; the secret itself must never reach
  // the log unless explicitly disclosed with reveal(...)

main() calls authenticate("alice", classify("hunter2")).
```

## Required stdout (exact)

```
AUTH user=alice
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
