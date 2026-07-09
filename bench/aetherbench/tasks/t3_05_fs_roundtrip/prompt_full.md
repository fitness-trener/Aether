# file write/read roundtrip (t3_05_fs_roundtrip)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function save(path: String, body: String) returns Unit
  effects fs.write
  // writeFile(safeJoin(".", path), body) — dynamic paths must go
  // through safeJoin

function load(path: String) returns String
  effects fs.read
  // unwrapOr(readFile(safeJoin(".", path)), "ERR")

main() saves "hello-fs" to "aetherbench_scratch.tmp", loads it back,
prints it.
```

## Required stdout (exact)

```
hello-fs
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
