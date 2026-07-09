# host-pinned redirect (E0718) (t4_09_redirect)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Auth
  requires capability net
  requires capability log
  exports login
end

function login(returnTo: String) returns Unit
  effects net.redirect, log
  // redirect(safeRedirect("app.example.com", returnTo));
  // then print "REDIRECTED"

main() calls login("/dashboard").
```

## Required stdout (exact)

```
REDIRECTED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
