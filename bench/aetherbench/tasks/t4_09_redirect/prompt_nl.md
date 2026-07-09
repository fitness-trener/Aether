# host-pinned redirect (E0718) (t4_09_redirect)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `login(returnTo)` that redirects to the user-supplied path via redirect(safeRedirect("app.example.com", returnTo)) — a raw dynamic target is rejected as an open redirect. Print "REDIRECTED". main() calls login("/dashboard").

## Required stdout (exact)

```
REDIRECTED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
