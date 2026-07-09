# effect propagation three deep (t3_10_chain)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function inner(msg: String) returns Unit
  effects log

function middle(msg: String) returns Unit
  effects log

function outer(msg: String) returns Unit
  effects log

main() calls outer("deep"); every level declares log.
```

## Required stdout (exact)

```
GOT deep
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
