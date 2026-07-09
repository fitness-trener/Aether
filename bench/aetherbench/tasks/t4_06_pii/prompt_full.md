# PII redacted before logging (E0715) (t4_06_pii)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Analytics
  requires capability log
  exports track
end

function track(userEmail: PII<String>, action: String) returns Unit
  effects log
  // print "EVENT action=" + action, then
  // print "EVENT user=" + redact(userEmail)

main() calls track(classifyPII("jane.doe@corp.example"), "checkout").
```

## Required stdout (exact)

```
EVENT action=checkout
EVENT user=j***@corp.example
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
