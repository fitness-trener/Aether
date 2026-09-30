---
type: question_page
question_id: q9
status: answered
confidence: medium
last_updated: 2026-09-30
tags: [design-rationale, evidence, positioning]
---

# Why do Aether ports find bugs in real libraries, and what is specific to Aether in that?

## Short Answer

**Nearly all of the bug-finding power comes from the method, not the
language.** The method has three parts:

- an independent re-implementation, written from the spec or the stated
  convention rather than from the library's code;
- a differential run over hundreds of thousands of generated inputs,
  with a fixed seed and every divergence machine-attributed;
- boundary-heavy input generation.

Differential testing is an established technique, and a disciplined
second Python implementation would find the same defects.

**Aether contributes four things, only two of which are enforced:**

1. **Enforced: runtime contracts.** `requires`/`ensures` turn spec
   invariants into checks on every call: antisymmetry, build metadata
   ignored, sign preservation. They caught humanize's historical issues
   #86, #57 and #171, and they rejected semver mutants.
2. **Enforced: arbitrary-precision `Int` at run time.** BUG-102 closed the
   4300-digit leak.
3. **Not enforced: exactness.** The humanize regression is a float compared
   against an exact int above 2**53. It surfaced because the port was
   written in exact integers. Aether does **not** refuse implicit Int/Float
   mixing: `1 + 2.5` passes `check`, because there is no type checker.
   `[source: types, section: What is checked, key: coercion]`
   **Partly enforced since iter-75:** E0209 refuses an Int/Float mix
   where both types are statically known. A mix through an unknown-typed
   value is still not refused, and floats are not opt-in. Int `/` and `%`
   are now specified as floor operations (BUG-103), so a port no longer
   inherits the rounding by accident `[source: types, section: What is
   checked, key: E0209]`.
4. **A small, regular language** that an agent can write a faithful port
   in, with structured diagnostics it can act on.

**What would make the language itself the reason:** refuse implicit
numeric coercion statically (the q8 slice), and make floats opt-in. Then
the port's exactness would be a guarantee, not the porter's discipline.

## Evidence

| Finding | Evidence | Confidence |
|---|---|---|
| The only third-party-confirmed defect came from a port plus a differential run | humanize `intword` carry, found 2026-07-05 (`docs/history/REALWORLD_HUMANIZE.md` §0, §4); independently fixed by humanize PR #346 (merged 2026-09-16) | high |
| The defect class is float vs exact int, and the port avoided it by construction, not by any language rule | `grammar/types.md` "Excluded by design but not refused": `let a = 1 + 2.5` passes `check` `[source: types, section: What is checked, key: coercion]` | high |
| Contracts add detection beyond the differential | humanize §5: issues #86, #57, #171 become E0304/E0301. semver: the §10 mutant was stopped by the port's own `ensures` (`bench/realworld_semver/REPORT.md` §3) | high |
| Hit rate across 8 library runs is low and uneven | 1 confirmed significant (humanize); minor and new: semver #487, isodate #114, croniter over-fires; known upstream: num2words #402, #603; zero defects: packaging, bech32, numpy-financial (`docs/history/REALWORLD_*.md`, `bench/realworld_*/REPORT.md`) | high |
| Sprint of 2026-09-30, four spec-first targets: two clean, two with new candidates | tomllib (TOML 1.0): 0 spec departures, one low candidate (`ValueError` instead of `TOMLDecodeError`). packaging specifiers (PEP 440): 0 divergences in matching; the only defect reached was already fixed on main. CPython `datetime` (ISO 8601): two defects still on `main`, no prior report found. dateutil `rrule` (RFC 5545): one defect that looks new (mixed plain/ordinal BYDAY intersected), one known (#1398). Filed 2026-09-30 with the owner's approval: dateutil#1588 + fix PR #1589, cpython#158500, cpython#158501, tomli#309, and a supporting comment on dateutil PR #1575; none confirmed by a maintainer yet (`bench/realworld_{tomllib,packaging_specifiers,datetime_iso,dateutil}/REPORT.md`) | high |
| The sprint also found three Aether-side bugs | BUG-103 (Int division rounding unspecified), BUG-104 and BUG-105 (`fmt` escapes and comment anchoring), all fixed (`BUGS.md`). Writing ports is also a test of the toolchain | high |
| Filing a report is not the same as getting a fix | the humanize fix came from someone else's PR, and the Appendix A draft was never filed | high |

## Recommended Actions

- **Test the repositioning before committing to it.** Run a short sprint on
  targets where a correctness divergence has consequences: parsers of
  untrusted input, version resolution, money and decimals, dates and
  times, encodings. Measure confirmed defects and merged fixes per target,
  not findings.
- **Submit fixes, not only issues**, with the owner's approval each time. A
  merged fix in a critical project is stronger third-party evidence than
  an open issue.
- **If Aether is meant to be the reason, build the exactness guarantee.**
  Statically refuse implicit Int/Float mixing (q8's first slice). Without
  it, "Aether finds bugs" should be worded as "the method, with Aether as
  the spec language, finds bugs".
- **Parser differentials between libraries are also a known security bug
  class** (URL and host parsing confusion). Work there only with
  coordinated disclosure.

## Related
- [[q8-static-type-checking-after-name-resolution]]
- [[q3-what-makes-a-good-backlog-target]]
- [[q2-runtime-refinement-vs-smt]]
