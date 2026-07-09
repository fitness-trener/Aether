# B4 — Anyscale (Ray)

**To:** `[FILL — head of platform / DevRel; identify via KubeCon talks]`
**Subject:** Architectural-correctness for Ray actors

---

Hi `[FIRST_NAME]`,

I'm `[FOUNDER]`, building Aether — a language for AI agents to write
production code with statically-enforced architectural constraints
(effect scope, capability scope, refinement types).

Ray-specific failure mode: an actor declared "compute-only" silently
performs `fs.write` on a worker node; the cluster's deploy manifest
is now a lie. Capability composition is exactly the wedge — Aether
catches the lie at compile time, before the actor is shipped.

If "Aether is the language Ray actors should be written in" is
directionally interesting, 20 minutes? The wedge demos + the SDK +
a possible Ray-actor binding.

`[CALENDAR LINK]` · `[REPO]` · `[VIDEO]`

`[FOUNDER]`
