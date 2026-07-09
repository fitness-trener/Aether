# two capabilities declared and used (t3_03_audit)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Audit
  requires capability log
  requires capability fs
  exports emit
end

function persist(line: String) returns Unit
  effects fs.write

function emit(line: String) returns Unit
  effects log, fs.write
  // prints "AUDIT " + line, then persists it

main() emits "login".
```

## Required stdout (exact)

```
AUDIT login
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
