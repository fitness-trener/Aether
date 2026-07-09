# Result-handling config loader (t5_06_config)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Config
  requires capability fs
  requires capability log
  exports loadConfig
end

function loadConfig(path: String) returns String
  effects fs.read
  // unwrapOr(readFile(safeJoin(".", path)), "default-config") —
  // dynamic paths must go through safeJoin

main() prints loadConfig("aetherbench_no_such_file.cfg").
```

## Required stdout (exact)

```
default-config
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
