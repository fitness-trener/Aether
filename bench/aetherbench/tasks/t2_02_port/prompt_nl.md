# Port number refinement (t2_02_port)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Define a Port refinement (1..65535) and `describePort(p)` returning "port:" followed by the number. Print for 80 and 65535.

## Required stdout (exact)

```
port:80
port:65535
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
