# T06 — `AuditLogger` module declared `log` only, persists to disk

## Architectural promise
Module `AuditLogger` declares `requires capability log` — meaning it
is safe to deploy in a sandbox without filesystem access. The
deployment manifest, threat model, and on-call playbook all assume
this.

## Naive-agent failure
A "let's also persist the audit line to disk" refactor adds
`writeFile` to a helper. The module declaration still says
`requires capability log`. Deployment manifest is now a lie.

## Aether outcome
[E0701] capability leak — the module's transitive effect closure
contains `fs.write`, which requires capability `fs`, which the module
hasn't declared.

## Python outcome
Silently writes the file.
