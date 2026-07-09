# pinned fetch authority (E0710) (t4_04_pinned_ssrf)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write a crawler whose fetch effect is pinned to https://docs.example.com/* (never a bare "*"). fetchTarget returns "body-of:" + path; crawl prints "CRAWL " + that. main() calls crawl("/intro"). Must pass aether check.

## Required stdout (exact)

```
CRAWL body-of:/intro
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
