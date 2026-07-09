# module with log capability (t3_01_logger)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Logger
  requires capability log
  exports emit
end

function emit(line: String) returns Unit
  effects log
  // prints "LOG " + line

main() emits "startup" and "ready".
```

## Required stdout (exact)

```
LOG startup
LOG ready
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
