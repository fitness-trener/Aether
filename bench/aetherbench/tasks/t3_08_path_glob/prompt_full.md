# host pinned, path wildcard (t3_08_path_glob)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function charge(amount: Int) returns String
  effects net.fetch("https://api.payments.example.com/charge/*")
  // returns "charged:" + amount

main() prints charge(100).
```

## Required stdout (exact)

```
charged:100
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
