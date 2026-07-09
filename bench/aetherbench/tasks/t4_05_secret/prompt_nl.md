# secret never logged raw (E0712) (t4_05_secret)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `authenticate(user, password)` where password is a Secret<String>. Print "AUTH user=" + user only. The secret must not reach print (aether check rejects that); do not use reveal. main() calls authenticate("alice", classify("hunter2")).

## Required stdout (exact)

```
AUTH user=alice
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
