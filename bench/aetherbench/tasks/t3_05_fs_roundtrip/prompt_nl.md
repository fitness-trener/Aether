# file write/read roundtrip (t3_05_fs_roundtrip)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `save(path, body)` (fs.write) and `load(path)` (fs.read, returning the file text or "ERR"). Dynamic paths must be routed through safeJoin(".", path). main() writes "hello-fs" to "aetherbench_scratch.tmp", reads it back and prints it.

## Required stdout (exact)

```
hello-fs
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
