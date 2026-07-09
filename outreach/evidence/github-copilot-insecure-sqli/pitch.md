# Outreach - GitHub Copilot (GitHub / Microsoft)

**Buyer persona:** Copilot platform security / trust & safety; secure-codegen research leads.

**2-sentence opener (grounded in their real incident):**

> Your own S&P 2022 study found ~40% of Copilot completions in security-relevant scenarios were vulnerable - SQL injection among them. Aether is a target language where that exact completion is a compile error, so the agent physically can't emit it.

**90-second live demo:**

Run github-copilot-insecure-sqli: `vulnerable.aeth` is the classic concatenated-query completion -> E0713, exit 2. `fixed.aeth` parameterizes with sqlBind -> exit 0. 90s: the diff is the one line the study recommends, and the compiler enforces it.

**Honesty rail:** lead with "Aether would have *refused* this at
compile time (retrospective port of your public incident)" - never
imply a live scan or breach of their systems.
