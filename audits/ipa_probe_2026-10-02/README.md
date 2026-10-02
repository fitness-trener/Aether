# Probe: does interprocedural taint flow pay off? (2026-10-02)

The owner asked for interprocedural dataflow for taint. Step 2 of the loop
method is to confirm the gap empirically before building. The probe
measures two things: misses across functions, and false positives that an
interprocedural pass would clear.

## Misses (check-py, modelled sinks)

| Probe | Shape | Result |
|---|---|---|
| `p1_sql.py` | SQL built in a helper and executed by the caller; a parameter executed in a helper | Both flagged, E0713 |
| `p2_cmd.py` | Command returned from a helper, and an identity wrapper | Both flagged, E0714 |
| `p4_path.py`, `b4_path.py` | `open`/`send_file` of a request-derived path | `open` paths are flagged as E0711 under `--strict` only, cross-function shapes included (`user_path()`, helper parameter). `send_file` has no rule even within one function. Off by default and unmodelled sinks are not cross-function gaps |

For a sink check-py models, a non-literal argument is flagged wherever its
value comes from, so a flow across functions cannot be missed. It is
over-flagged instead. For `.aeth`, a marker crossing a function boundary
is refused at the signature (E0729/E0730, vault q1).

## False positives an interprocedural pass would clear

`python -B bench/framework_scan/run_scan.py --json` gave 679 findings over
15 agent frameworks (6,946 files). Then
`python -B classify.py <dir with fw.json> bench/framework_scan/_work/src`
classifies each finding by its sink argument:

| Shape | Findings | Share |
|---|---:|---:|
| other (no parameter or local call at the sink) | 592 | 87.2% |
| a parameter, and some in-module caller passes a non-literal | 55 | 8.1% |
| a parameter, with no in-module caller | 19 | 2.8% |
| a call to a local function that computes its result | 13 | 1.9% |
| **a parameter, and every in-module caller passes a literal** | **0** | 0% |
| **a call to a local function that returns only literals** | **0** | 0% |

A same-module interprocedural pass would clear **0 of 679**.

`other.py` breaks down the 603 E0713 findings:
- 235 have an f-string at the sink. The interpolated values are a local
  name (175), a call (52), `self.attr` (31) and another attribute (10).
- 368 have no f-string at the sink.

The volume sits in E0713's own precision: dynamic identifiers such as
table names, and the method-name rule from q5. It is not in flows across
functions.

## Conclusion

Not built. On real code, interprocedural flow would neither close a miss
nor clear a false positive. See vault q1 (Evidence) and q10, corrected
today. (The package-wide follow-up below refines "0": a same-module
helper summary clears 4 findings soundly and 9 under the `_private`
convention. The decision stands.)

## Package-wide follow-up (track D, same day)

The measurement above was same-module and read only the call on the
sink's line. `pkg_ipa.py` widens it to the whole distribution and to every
value the judged argument is built from, through the sink function's local
bindings ("leaves"). A finding is cleared only when an interprocedural
fact is needed and every leaf is literal-shaped:

- a parameter, when every call site in the distribution passes a
  clearable value (recursively, across modules: imports, `from x import f`,
  module aliases, `self.`/`cls.`/`super()` methods, nested functions);
- a call to a package function, when every `return` is clearable with the
  callee's parameters bound to this call's arguments (a summary);
- `self.x` (a separate row), when every store to `.x` in the distribution
  is clearable.

Call sites are over-approximated (`obj.m(...)` with any receiver may call
method `m`). A function read as a value, decorated, a dunder, or with no
caller in the distribution is not cleared. Each clearing records the
weakest assumption it needed:

| Tier | Assumption |
|---|---|
| sound | parameters of nested functions; summaries of module-level and nested functions (monkeypatching aside) |
| convention | `_private` functions/methods (no base class outside the distribution, which could call them); summaries of `_private` methods reached through `self.`. Holds only if nothing outside calls or overrides a `_name`, which Python does not enforce |
| unsound | public functions/methods: "assume no external callers or overrides" |
| loose upper bound | unsound, plus no escape check and only call sites whose receiver resolves. Not a design: a bound on what a better call graph could add |

Every clearing was then checked by a counterfactual: the leaves it relies
on are replaced by a string literal, the module is unparsed, and check-py
must drop the finding.

Run (repo root; `_work/` comes from `run_scan.py`):

    python -B audits/ipa_probe_2026-10-02/scan_full.py bench/framework_scan/_work/src fw_full.json
    python -B audits/ipa_probe_2026-10-02/pkg_ipa.py fw_full.json bench/framework_scan/_work/src --verify
    python -B audits/ipa_probe_2026-10-02/quoter.py fw_full.json bench/framework_scan/_work/src

For site-packages, pass the purelib directory and add `--site`.

### Results

| Corpus | Findings | Sound | + convention | + unsound | Loose bound | Counterfactual |
|---|---:|---:|---:|---:|---:|---|
| framework (15 dists, 6,946 files) | 679 | **4 (0.6%)** | 9 (1.3%) | 9 | 11 (1.6%) | 9 of 9 confirmed |
| site-packages (11,259 files) | 687 | 12 (1.7%) | 13 | 48 (7.0%) | 66 (9.6%) | 47 of 48 confirmed |

- **Framework, the 4 sound:** one module's helper (`_index_columns_query`)
  returns `text("<fixed SQL>")`. The 5 convention-tier findings are
  `self._helper()` staticmethods returning a fixed table name or query
  (4 agno `_cascade_tool_results`, 1 langchain-community iMessage loader).
  **All 9 are same-module helper summaries.** No parameter is cleared at
  any tier, and the cross-module call graph adds nothing.
- **Site-packages:** all 12 sound clearings are in one test file
  (`tornado/test/template_test.py`, a `utf8("<literal>")` wrapper). The
  unsound tier is mostly one test base class (`adodbapi/test/dbapi20.py`,
  32 findings via a public field a driver's subclass is meant to override).
  **Outside test code: 0 sound, 0 convention.**
- The earlier probe's "0 helpers return only literals" missed the 9 because
  its literal test did not unwrap `text(...)` and it saw only calls passed
  directly at the sink, not inside an f-string or through a local name.

Item 1, parameters. 143 framework findings have a parameter among their
leaves; 0 are cleared at any tier. The reasons, counted per finding:

| Visibility | Reason | Findings |
|---|---|---:|
| private | a caller passes a non-literal | 69 |
| public | read as a value (callback, registry) | 25 |
| public | a caller passes a non-literal | 19 |
| private, framework base | a caller passes a non-literal | 7 |
| any | a caller passes `*args`/`**kw` or omits it | 11 |
| public/dunder/decorated | no caller in the distribution, implicit call or framework call | 11 |
| private | read as a value | 1 |

What blocks the callers' arguments, per call site: another package call
whose result is computed (131), the caller's own parameter (88), `self.attr`
(34), a module-level name bound to a computed value (30). Of the 75
"parameter at the sink" findings (this replication of `classify.py` puts
591/75/13 where its run gave 592/74/13), 27 have no parameter in the
argument check-py judges: `classify.py` read every argument of every call
on the line, including the bound-values tuple of `execute(q, params)`.

Item 2, helper summaries. 214 framework findings have a package-function
call in the judged argument, 173 of them to a function in another module.
9 clear (above). In the rest the helper's result depends on an argument
that is itself dynamic (177 findings) or on an external call (42).

Item 3, return flow into the "other" bucket. 188 of the 591 "other"
findings take a value from a package-function call; 5 clear (convention
tier), the rest as above.

Side finding, not interprocedural (`quoter.py`). 156 framework findings
(23%) pass through one hand-written identifier quoter,
`agno.db.migrations.utils.quote_db_identifier`. It returns the identifier
in backticks or double quotes, with that quote character doubled inside.
If such a helper were recognised as a sanitizer, **120** of those findings
would have no other dynamic leaf. This is not provable by shape: a
`db_type` string picks the quote character at run time. A double-quoted
"identifier" sent to MySQL is a string literal with backslash escapes,
and a backtick-quoted one sent to Postgres is not a quoted identifier.
The shape occurs in no other distribution of either corpus.

### Decision

Threshold for building package-wide IPA: **at least 2% of a corpus's
findings soundly clearable (counterfactual-confirmed, outside test code)
on both corpora.** The threshold comes from q3 (reuse × prevalence ÷ new
machinery). check-py analyses one file at a time in a worker pool, so a
distribution pre-pass, a call graph and summaries passed into the frontend
are large new machinery (this measurement alone is about 1,000 lines). For
scale, a recent precision slice in `demos/case_studies/LOOP_LOG.md` moved
the framework corpus by 3.5% (707 → 683). The threshold was written after the first numbers
were seen. The result is below any plausible threshold: 0.6% framework,
0 outside tests in site-packages.

**Not built.** A package-wide pass would clear 4 framework findings
soundly, 9 under the `_private` convention, and at most 11 with a loose
call graph. Where clearing happens, it is a same-module helper summary,
never a parameter. The lever with volume is sanitizer recognition for
hand-written identifier quoters, and it needs a dialect argument that
shape cannot give.
