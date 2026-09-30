# Changelog

## 0.5.0 (unreleased)

0.5.0 is the first release since 0.4.0 (0.4.1 was prepared and never
published; its changes are here). Most of it comes from a whole-repo audit
on 2026-09-24 (`audits/audit_2026-09-24_plan.md`) that reproduced about
60 flaws a green gate did not catch, and from the known-gaps round that
followed. Each item below has a `BUGS.md` entry with its repro and a
regression test; `demos/case_studies/LOOP_LOG.md` iterations 53-65 are
the record.

On the 15-framework corpus (4,946 files, versions pinned in
`bench/framework_scan/frameworks.lock.txt`) 0.4.0 reports 676 findings
and 0.5.0 reports 679 (`bench/framework_scan/REPORT.md` sections 9-11,
13): 31 added by closed misses, 1 added by argument injection, and 29
removed as documented safe idioms or non-SQL calls (24 in iteration 60,
5 in iteration 67). None of the four misses closed for Python in
"Silent misses" below occurs in that corpus.

### Breaking: one exit-code table, one JSON contract

`aether check`, `aether check-py`, `aether fix-loop` and `tools/scan.py`
now share one exit-code table, in text, `--json` and `--sarif` mode
(audit 2026-09-24 D5/D6/B6; full contract in `docs/SCANNING.md`,
"Exit codes and the JSON contract"):

| exit | meaning |
|---|---|
| `0` | clean |
| `1` | findings (`fix-loop`: not repaired) |
| `2` | usage error (bad flag or value, missing path) |
| `3` | analyzer crash — a bug in Aether |
| `4` | incomplete — some input could not be read or parsed, and nothing was found |

What changes for a caller:

- **Findings exit `1`, not `2`** (`check`, `check-py`, `run`'s static
  stages and runtime violations). A script testing `rc == 2` for
  "found something" must test `rc == 1`.
- **A file that does not parse is exit `4`, not `2` (`check`) or `0`
  (`check-py`) or `1` (`tools/scan.py`).** `check-py` over a tree it could
  not parse used to exit `0` with `"ok": true` — including valid 3.12+
  source scanned on Python 3.10/3.11, which now also says "valid on a
  newer Python? scan with 3.12+". An unresolved `import` (E0705/E0706) is
  `4` too. With findings as well, the exit is `1` and the JSON says
  `"complete": false`.
- **An analyzer crash is exit `3`** everywhere, whatever else was found;
  under `--json` it still prints a JSON document (`error.kind: "crash"`)
  instead of a raw traceback (`--debug` adds the traceback).
- **`--json` prints exactly one JSON document on stdout.** `aether --json
  check` used to print one `{"ok": false, "diagnostic": {...}}` line per
  diagnostic on **stderr**; it now prints `{"ok", "complete",
  "diagnostics": [...], "decls"?, "prove"?}` on stdout. `--collect-errors`
  no longer duplicates its diagnostics on stderr. Usage errors print
  `{"ok": false, "complete": false, "diagnostics": [], "error": {...}}`.
- **Every diagnostic is `Diagnostic.to_dict()`** with every key present:
  `stage` and `patch_target` are new, on every surface (`check`,
  `check-py`, `tools/scan.py`, `sdk.CheckResult.to_dict()` (new), LSP).
  `tools/scan.py` findings are that dict plus `risk` — the top-level
  `line`/`column` keys are gone (read `position.line`/`position.column`),
  and `parse_error` is the parse diagnostic's `to_dict()`.
- **`check-py --json`**: `ok` is false when a file could not be parsed;
  new `complete` key; new `--no-unprovable` flag drops the `unprovable`
  rows.
- **LSP**: `aether/check` returns the `to_dict()` rows; the old
  `position.col` and `data` keys stay as aliases through 0.5.x and go in
  0.6. `publishDiagnostics` maps warnings to LSP severity 2 (was always
  1) and its `data` is the full `to_dict()`.
- **SARIF**: rules gain `fullDescription`, `help` and `helpUri`; results
  gain `properties.stage`; a crash sets `executionSuccessful: false`.
- **GitHub Action**: runs `check-py` once (was twice); an analyzer crash
  always fails the job (it was detected only as "exit 2 with no
  findings"); an incomplete scan fails the job unless the new
  `allow-incomplete: true` input is set; new `unparsed` output.
- `tools/scan.py` given a path that does not exist is a usage error (2);
  it used to scan nothing and exit 0.
- **`aether --json run`** prints one document, `{"ok", "complete",
  "diagnostics", "stdout", "stderr"}`, with the program's own output
  captured into `stdout`/`stderr` (the keys `sdk.RunResult.to_dict()`,
  new, also returns). It used to print the program's output on stdout
  ahead of the document, and a clean run printed no document at all.
  Exit codes unchanged: `0` ran clean; `1` a static finding, a runtime
  contract/refinement violation (E03xx) or an exception the program
  raised (now reported as `E9003` in `diagnostics`, traceback in
  `stderr`). Text mode is unchanged.

### Python scanner: silent misses closed

- `html.escape`, `markupsafe.escape`, `urllib.parse.quote(_plus)` and
  `flask.render_template` no longer count as `trusted`: `eval(html.escape(x))`
  and `render_template_string(html.escape(x))` are reported (BUG-032).
- A name imported two ways (`try: import cPickle as pickle / except
  ImportError: import pickle`, the lxml/ElementTree fallback) is a sink if
  any candidate is one (BUG-033).
- `subprocess.run(shlex.quote(cmd), shell=True)` is E0714: the input still
  chooses the program (BUG-034).
- A `ValueError` inside a detector is an analyzer error, not "could not
  parse" with the findings dropped (BUG-035).
- A non-literal raw SQL string is E0713 wherever it appears: `text()`,
  `literal_column()`, `.text(x)`, a runtime string into
  `.where/.filter/.having`, not only inside an `execute` call (BUG-065).
- `importlib.import_module("os")`, `__import__`, module-level aliases,
  `functools.partial` and dispatch tables reach the sink; `builtins.eval`
  forms are E0731 (BUG-066, BUG-067).
- 28 more sink spellings (werkzeug/quart/django/aiohttp redirects, peewee,
  duckdb, `runpy`, `code.InteractiveInterpreter`, LangChain jinja2
  templates, tornado, ruamel `typ="unsafe"`, `_pickle`, ...) and the Stripe
  `rk_live_` credential shape (BUG-068).
- E0723 inside an f-string reports its real line and column; bytes
  literals are scanned (BUG-069).
- Argument injection: `git`, `ssh`, `tar`, `find`, `rsync` and `zip` with a
  non-literal word before a literal `--` in an argv list, or a
  `shlex.quote`d word in a shell string (a quoted word that starts with
  `-` is still an option), are E0714 (BUG-096). The argv form is rated
  0.6 (match kind `argv_option`): on 209 agent/MCP repositories nearly
  every such word was a positional path in test code, so
  `--min-confidence 0.9` hides it; `["bash", "-c", cmd]` keeps 0.9.

### Python scanner: fewer false positives, findings in Python terms

- The documented fixes are no longer flagged: a literal program with
  `shlex.quote`d arguments (`"ls -l " + shlex.quote(p)`, `shlex.join`),
  `redirect(url_for(...))` / `reverse(...)` and a dominating
  `url_has_allowed_host_and_scheme` check, psycopg `sql.SQL(...).format(
  sql.Identifier(...))`, module- and class-level SQL constants, the
  SQLAlchemy Table form on `self.table`, IN-list placeholders, Jinja's
  `SandboxedEnvironment`, `compile(..., ast.PyCF_ONLY_AST)`,
  `os.path.join(base, secure_filename(x))` (BUG-073..076, BUG-039).
- A finding whose argument already contains a sanitizer or an own-origin
  URL builder rates 0.6 (output only; the finding set does not change).
- Python findings name your call (`execute`, `subprocess.call`) and a
  Python fix, and carry `category: "security"`. Three rows still use
  Aether names; the README lists them.
- E0727 text is written per callee: what each standard-library and lxml
  parser actually does with external entities, measured (0.4.1 work,
  BUG-031).

### Python scanner: four more false positives removed

Found by scanning the maintainer's own projects on 2026-09-30:

- `.text(x)` counts as raw SQL only with SQL evidence: a SQLAlchemy
  receiver, an imported `db`/`sa`, or the result reaching an executor or
  clause. Document builders are not SQL (BUG-098).
- An inline dict of string literals read with `.get(key, literal)` is
  literal (BUG-099).
- A local lambda that never escapes and is called only with literals has
  literal parameters (BUG-100).
- A loop over a local tuple of SQLAlchemy expressions gives a sanctioned
  loop variable (BUG-101).

Each has a negative control that stays a finding. On the framework corpus
the findings go from 684 to 679 (five non-SQL `.text` calls), and nothing
is added.

### Language (`.aeth`)

- The checker refuses what it promised to refuse: effects inside
  `requires`/`ensures`, refinement predicates and `const` initializers are
  checked; a call through a function value the checker cannot name is
  charged every function-value effect in the program; a `for`/`match`
  rebinding no longer launders a name proven safe, stable or authorized
  (BUG-055..057).
- Name mangling is injective and runtime helpers live in a namespace no
  user name reaches: a user function named `assert_contract` no longer
  disables contracts (BUG-058).
- A module's capability grant is enforced at run time for programs that
  declare a module (a runtime guarantee) (BUG-059).
- `net.fetch` glob cover is decided on the parsed URL (BUG-060);
  refinements are checked at returns, typed lets, consts, record fields
  and list elements (BUG-061); deep nesting is a structured diagnostic
  (BUG-062).
- New code **E0208**, reference to an undeclared name: a misspelt sink
  such as `sqlQeury(...)` is refused instead of passing `check` and failing
  at `run` (BUG-086). This is name resolution, not type checking.
- An `effects` clause is validated: `pure` beside another effect is E0201,
  an unknown capability segment is E0704, a second `effects` clause is
  E0201 (BUG-083..085).
- E0801 is reported at the offending call, not the function (BUG-082).
- `remove` on a `Set` works (BUG-050).
- **Behaviour change:** `parseInt` accepts exactly the ASCII grammar
  `-?[0-9]+`. Surrounding whitespace, `+`, `_` and non-ASCII digits used
  to parse, because `int()` accepts them; they are now `Err`. `parseInt`
  and `intToString` also round-trip an `Int` of any length, past CPython's
  4300-digit guard, as the arbitrary-precision `Int` of `grammar/types.md`
  requires (BUG-102).

### Fix-loop and tool surfaces

- The deterministic fix-loop never widens a declared effect or capability
  to make a diagnostic go away: it ends `not_repaired` (exit 1) and names
  the call to remove or replace. `--allow-widen` applies widening repairs,
  tags each `weakens_constraint`, and still exits 1 (BUG-040).
- One loader (parse and resolve imports) for the CLI, SDK, LSP, fix-loop
  and `tools/scan.py`: a cross-file violation is reported on every surface
  (BUG-041). `tools/scan.py` reads UTF-8 BOMs and fails on parse errors
  (BUG-042). `fmt` and the fix-loop keep full-line comments and print
  function types (BUG-044, BUG-047).

### Performance

- One per-function index shared by every detector, an early return for
  marker rows on programs with no marker type, and one frontend walk per
  scope. `check-py` output is byte-identical to the previous release.
  Measured 2026-09-25 on the framework corpus (8 logical cores): 85 s
  serially, 26 s on 8 workers (was 365.9 s / 111.3 s) (BUG-080, BUG-081,
  BUG-095).

### Gate

- The monotonic ratchet compares against the merge-base with
  `origin/main`, counts recall (claimed corpus findings and Python table
  rows) and only accepts a code proven by a positive `assert`; every
  Python sink, guard and sanitizer row has its own test; the gate
  discovers every `tests/test_*.py` (BUG-036..038).

### Fixed

- `grammar/stdlib.md` is now checked against the runtime's signatures
  (`tests/test_spec_docs.py`): arity for every documented function,
  parameter order for every function documented once, and a run of every
  overload documented for several types (`length`, `get`, `size`,
  `remove`, `contains?`). Six runtime helpers named their parameters
  differently from the spec (`startsWith?`, `endsWith?`, `reveal`,
  `csvEscape`, `redirect`, `pow`); renamed to the spec's names. Aether
  has no named arguments, so no program's behaviour changes.
