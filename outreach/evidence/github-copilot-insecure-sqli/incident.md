# GitHub Copilot (GitHub / Microsoft) - real incident

- **Tier:** Tier 1 - AI coding tool
- **Aether detector:** `E0713 (SQL injection, CWE-89)`
- **CVSS:** n/a (research finding: ~40% of 1,689 Copilot completions in 89 CWE scenarios were vulnerable; SQL injection among leading classes)
- **CWE:** CWE-89 (and CWE Top-25 broadly)
- **Public sources (resolving URLs):**
  - https://arxiv.org/abs/2108.09293
  - https://dl.acm.org/doi/10.1145/3610721

## What happened

Peer-reviewed study - Pearce, Ahmad, Tan, Dolan-Gavitt, Karri, "Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions", IEEE S&P 2022.

## Why this company has this pain structurally

Copilot is trained on public code that contains these bugs, so it reproduces them at generation time. This is not a one-off - the study measured it as a base rate across scenarios. GitHub's own defense (CodeQL) runs AFTER the code exists; Aether is the target language where the bug can't be emitted in the first place.

## Would Semgrep / CodeQL also catch it?

Yes - the study itself used CodeQL to find these. That is the point: SAST is a post-hoc scanner GitHub already runs. Aether is complementary - it's the compile target that refuses the shape, so the agent's output is safe-by-construction, not safe-if-someone-scans.

## Aether refuses the ported boundary

`aether check aether/vulnerable.aeth` (exit 2):

```
[E0713] error (capability) at line 18, col 1: function 'findUser' builds a SQL query for 'sqlQuery' unsafely (query is built by string concatenation - use sqlBind(...)); untrusted input concatenated into a query is an injection
```

`aether check aether/fixed.aeth` -> `OK` (exit 0). The
vulnerable->fixed diff is only the real remediation.

**Honest scope:** retrospective port of a real, public incident
belonging to this named company - Aether refusing the ported
boundary at compile time. NOT a live scan of their systems.
