# pinned fetch authority (E0710) (t4_04_pinned_ssrf)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Crawler
  requires capability net
  requires capability log
  exports crawl
end

function fetchTarget(path: String) returns String
  effects net.fetch("https://docs.example.com/*")
  // returns "body-of:" + path

function crawl(path: String) returns Unit
  effects log, net.fetch("https://docs.example.com/*")
  // prints "CRAWL " + fetchTarget(path)

main() calls crawl("/intro").
```

## Required stdout (exact)

```
CRAWL body-of:/intro
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
