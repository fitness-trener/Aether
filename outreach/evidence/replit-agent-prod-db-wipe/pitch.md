# Outreach - Replit

**Buyer persona:** Replit Head of Security / agent-platform eng (post-incident, actively hardening).

**2-sentence opener (grounded in their real incident):**

> After the July 2025 agent wiped a production database during a freeze, Replit shipped dev/prod separation and a planning-only mode. Aether encodes that guarantee in the type system: a production mutation without an authorization proof is a compile error, so the agent can't emit the path that caused the incident.

**90-second live demo:**

Run replit-agent-prod-db-wipe: `vulnerable.aeth` is an agent-issued DROP with no authorization -> E0716, exit 2. `fixed.aeth` threads authorize(operator, 'prod:migrate') into the sink -> exit 0.

**Honesty rail:** lead with "Aether would have *refused* this at
compile time (retrospective port of your public incident)" - never
imply a live scan or breach of their systems.
