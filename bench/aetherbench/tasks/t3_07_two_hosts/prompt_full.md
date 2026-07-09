# two pinned fetch hosts (t3_07_two_hosts)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function syncA() returns String
  effects net.fetch("https://a.example.com/*")

function syncB() returns String
  effects net.fetch("https://b.example.com/*")

function syncBoth() returns Unit
  effects log, net.fetch("https://a.example.com/*"), net.fetch("https://b.example.com/*")
  // prints results of both

main() calls syncBoth() with the same effects.
```

## Required stdout (exact)

```
a-ok
b-ok
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
