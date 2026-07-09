# Port number refinement (t2_02_port)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Port = Int where self >= 1 and self <= 65535

function describePort(p: Port) returns String
  effects pure
  // returns "port:" + the number

main() prints describePort(80) and describePort(65535).
```

## Required stdout (exact)

```
port:80
port:65535
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
