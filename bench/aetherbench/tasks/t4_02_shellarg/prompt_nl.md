# quoted shell argument (E0714) (t4_02_shellarg)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `convert(filename)` that runs the shell command "convert ? out.png" with the filename quoted via shellArg (never concatenated), then prints "CONVERTED " + filename. main() calls convert("photo.jpg"). Must pass aether check.

## Required stdout (exact)

```
CONVERTED photo.jpg
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
