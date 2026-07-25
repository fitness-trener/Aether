# Python sink detectors — measured results

**Date:** 2026-07-26
**Question:** with no rewrite, no `.aeth` port and no type annotations, how
many of Aether's security detectors fire correctly on ordinary Python — and
at what noise cost?

**Reproduce:** `python -B bench/py_frontend/run_bench.py`
(add `--json` for the machine-readable form). bandit is a bench-only
optional; without it, measurement 3 prints SKIP and the rest still runs.

This report leads with the weakest number, per the house rule
(`PYTHON_RESULTS.md`: "A bad result reported honestly is the goal").

---

## 0. What this measures, and what it does not

**In scope — the sink family**, which needs no annotations: E0711 path
traversal, E0713 SQL injection, E0714 command injection, E0718 open
redirect, E0719 SSTI, E0720 insecure deserialization, E0723 hardcoded
credential, E0727 XXE.

**Out of scope, by construction, not by omission:**

| Family | Why it cannot run on Python |
|---|---|
| E0801 effect composition | compares a call site against a **declared** `effects` clause; Python has none |
| E0712/E0715/E0724 taint markers | need `Secret<T>`/`PII<T>`/`Untrusted<T>` on a signature; Python has no annotation-free equivalent |
| E0716/E0717 authorization | need `Authorized<T>`, same reason |
| E0710/E0721/E0722 SSRF, cleartext | read the **declared** `net.fetch` annotation |
| E0202–E0207 semantic | check Aether language constructs; on translated Python they describe the translation, not the program (E0205 read `cur = conn.cursor()` as a dead store) |

The `requests_repro`, `capitalone_repro` and `pyjwt_repro` files therefore
produce nothing here. That is the correct result for this scope, not a miss.

**The starting point.** Before this work, `tools/py_frontend.py` emitted
`body=[]` — the function body was discarded, so all 21 security detectors
had no input. Measured on commit `f98fdce`, a file with five textbook
vulnerabilities produced **3 diagnostics, all E0701 capability facts, and
zero security findings.**

---

## 1. Detection vs ground truth

Ground truth: `bench/py_frontend/LABELS.json`, 19 labelled functions across
8 files, each label taken from the file's own header comment naming the CWE
and the documented fix. The `bench/realworld_*` repros were written earlier,
for the Aether ports, so their labels were not chosen to flatter this
frontend.

| | count |
|---|---|
| **false negatives** | **0** |
| **false positives** | **0** |
| true positives | 10 |
| labelled-clean functions correctly silent | 9 |

Every vulnerable function produced its expected code; every `*_safe`
function produced nothing. The safe half matters as much as the vulnerable
half: a checker that flags the fix trains people to ignore it.

**Independence caveat.** Author-established ground truth — the same repo
wrote the repros and the detectors. Same caveat as
`tools/py_corpus2/LABELS.json`. The differential in §3 is the partial
antidote: bandit was not written by this repo.

---

## 2. False positives on benign code — and the decision it forced

Corpus: all 76 parseable modules in `tools/py_corpus/` (26) and
`tools/py_corpus2/` (50). These were written for the **capability**
experiment — realistic FastAPI/Flask/SQLAlchemy/pandas code, not curated to
pass and not written as vulnerabilities.

| Code | Findings | Modules |
|---|---|---|
| E0711 | 11 | 10 |
| E0713 | 1 | 1 |
| E0720 | 1 | 1 |

Read individually rather than counted:

- **E0720 in `trap_05_pickle.py` is a TRUE positive.** `pickle.load(fh)` is
  CWE-502; the corpus author planted it as a soundness trap.
- **E0713 in `orm_03_migrations.py`** executes SQL read from a file. Intended
  in a migration runner, genuinely suspicious in general. Provenance-unknown.
- **E0711 in `fa_04_upload.py` is a TRUE positive**, and a good one:
  ```python
  dest = "/data/uploads/" + file.filename   # attacker-controlled
  with open(dest, "wb") as out:             # CWE-22 upload write-traversal
  ```
- **The other 8 E0711** are all `open(path_param)`, where the path is the
  function's own parameter and nothing in the module constrains it. Not
  proven safe, not proven unsafe. Aether's rule — a path must be a literal
  or `safeJoin`ed — flags them because Python has no `safeJoin` convention.

**Decision, driven by that ratio.** `aether check-py` holds **E0711** out of
its default output; `--strict` turns it on. It is not deleted and not
silently downgraded: the rule is correct, its precision on Python is not yet
good enough to lead with. The capability stage (E0701) is opt-in for a
different reason — on Python the module policy is empty by construction, so
every I/O call yields one. That is an inventory, and `tools/py_surface.py`
already reports it properly.

Everything else ships default-on: **9 of 76 benign modules produce a
default-set finding, and 2 of those are real bugs.**

---

## 3. Differential vs bandit

Same 8 labelled files. `python -m bandit -f json -q <file>`, bandit 1.9.4
on CPython 3.11.15.

| File | Aether | bandit |
|---|---|---|
| `sqli_repro.py` | E0713 | B608 |
| `pyyaml_repro.py` | E0720 | B506 |
| `subprocess_repro.py` | E0714 | B602, B603, B607, B404 |
| `hardcoded_secret_repro.py` | E0723 | — |
| `open_redirect_repro.py` | E0718 | — |
| `path_traversal_repro.py` | E0711 | — |
| `flask_repro.py` (SSTI) | E0719 | — |
| `lxml_repro.py` (XXE) | E0727 | — |

**Where the two agree:** SQL injection, unsafe YAML load, `shell=True`
command injection. On its core overlap bandit is a perfectly good tool and
finds the same bugs.

**Aether-only here:** the hardcoded AWS key, open redirect, SSTI, XXE, and
path traversal. bandit's default plugin set does not cover lxml XXE or
Flask SSTI, and its hardcoded-secret checks (B105/B106) match password-ish
variable names rather than provider key shapes.

**bandit-only here — stated, not omitted:** B404 on `import subprocess`
(line 13), an advisory that fires on the import itself; and B603/B607 on
**line 24**. Line 24 is `make_thumbnail_safe` — the documented fix, the
argv-list form with no shell. Aether reports nothing there.

That difference is the whole argument, and it is checkable:
`python -m bandit -f json -q bench/realworld_subprocess_cmdi/subprocess_repro.py`.
A pattern matcher sees `subprocess.call(...)` and warns; the sink mapping
gates on `shell=True`, which is what actually decides whether a shell is
involved.

**What this comparison does NOT show.** bandit ships ~70 plugins across
crypto, Django, Flask config, SSL/TLS, tempfile, assert-in-production and
more; Aether models 8 rows on Python. On breadth bandit wins outright, and
this corpus was built from Aether's rows, so it is scoped to where Aether
has something to say. The honest claim is narrow: **on the eight classes
Aether models, its dataflow-and-argument-shape reading distinguished the
bug from the documented fix on every pair, and a pattern matcher did not.**
Nothing here supports a general "better than bandit".

---

## 4. Limits

- **Intraprocedural and syntactic.** Over-flag, never miss *within the
  modeled surface*. Not a soundness proof.
- **Sinks are matched by method name** on receivers of unresolved type —
  `cursor.execute(...)` is a SQL sink whatever `cursor` is. Over-flag, not
  inference. Why that is legitimate here when it was unsound for purity:
  `vault/wiki/questions/q5-sink-matching-vs-purity-matching.md`.
- **Guard-bound-elsewhere is mostly unhandled.** When a call's safety lives
  in a *different statement* rather than in its argument shape, no
  argument-shape rule can see it. XXE is handled specially
  (`resolve_entities=False` disarms the sink, because the vulnerable and
  safe `etree.fromstring(raw, parser)` call sites are byte-identical).
  Every other member of that class — a session configured elsewhere, a
  flag set at import time — is **not** handled. This is a residual, not a
  solved problem.
- **Single file.** No cross-module resolution, matching `py_frontend` today.
- **No control flow.** Neither these passes nor the frontend model branches
  or loops.
- **A finding is a sound positive, not a complete inventory** — the same
  caveat `PYTHON_VIABILITY.md` states for capabilities. Unresolved regions
  remain UNPROVABLE and are reported as such.
