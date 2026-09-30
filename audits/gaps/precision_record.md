# Precision record — iteration 67 (2026-09-30)

Four E0713 false-positive shapes found by scanning the owner's projects on
2026-09-30, all at confidence 0.6 (by-method match). Fixed in `d18d2e2` on
the worktree branch forked from `release-0.5.0` @ `4435ee2`. Nothing here
has been copied into `BUGS.md`, `LOOP_LOG.md` or `vault/`; the blocks below
are ready to paste.

## BUGS.md entries

### BUG-098  `.text(x)` on any receiver was a raw-SQL entry, so document builders fired E0713  [OPEN]
test: tests/test_py_precision.py (`::test_bug098_text_needs_sql_evidence`)

The one-argument `.text(x)` row (iteration 59, BUG-065) matched by method
name on every receiver. `DocumentBuilder().text(text)` and
`builder.page(1).text(s)` fired (Halyk tests ×5), and so did streamlit
`st.text`, outlines `generate.text(client)` and LanceDB's hybrid FTS
builder `.vector(e).text(query)` on the framework corpus.

Fix (`d18d2e2`, `_text_is_sql`): a `.text(x)` call is a raw-SQL entry only
with SQL evidence. The evidence can be:
- the receiver resolves, through the imports or the constructor it is
  bound to, into `sqlalchemy` / `sqlmodel` / `flask_sqlalchemy`
  (`db = SQLAlchemy(app)`);
- the receiver is spelled `db` or `sa` in a file that imports one of those
  modules;
- the call's result reaches an argument of a SQL executor or clause in the
  same scope (`_sql_flow_ids`: the `sqlQuery`/`sqlExec` by-method rows plus
  `scalars`, `scalar`, `where`, `filter`, `order_by`, `from_statement`,
  `having`), through names bound to it (`cond = db.text(q)` then
  `.where(cond)`).

A receiver bound to any other constructor is not SQL by its name, but
flow still counts. Inside a recognised builder chain, `.text` with a
non-literal argument still sanctions nothing (`_is_sql_expression`,
unchanged).

Negative controls (all still E0713):
- `db.session.execute(select(User).where(db.text(f"name = '{n}'")))` with
  flask_sqlalchemy imported;
- `cond = db.text(q)` then `.where(cond)`;
- a bare `return db.text(q)` in a file importing flask_sqlalchemy;
- `from app.extensions import db` with `db.text(q)` flowing into
  `.filter(...)`;
- `session.execute(DocumentBuilder().text(q))`.

### BUG-099  a dict allowlist of literals was a dynamic expression  [OPEN]
test: tests/test_py_precision.py (`::test_bug099_dict_allowlist_is_literal`)

`order = {"a": "p.x ASC", "b": "p.x DESC"}.get(sort, "p.x ASC")`, then
`f"... ORDER BY {order}"` passed to `con.execute(sql, args)`, fired E0713:
the `.get` call was an opaque computed call. The value can only be one of
the literals written there.

Fix (`d18d2e2`, `_dict_choice`): the shape is a dict DISPLAY whose every
value is a str literal and which has no `**` splat, read with
`.get(key, "<str literal>")` or `[key]`. It is translated as a `+` of its
candidate literals, so it is accepted wherever a literal is. Any literal
bans are read over the candidates together, which errs toward over-flag.
The keys and the lookup key are still translated and carried, so a sink
inside the key is still found.

Negative controls (all still E0713):
- a dict with a non-literal value;
- `.get(key, key)`;
- `.get(key)` with no default;
- `f"... ORDER BY {sort}"` where `sort` is a parameter;
- a sink call used as the lookup key.

### BUG-100  a lambda parameter fed only literals was a parameter  [OPEN]
test: tests/test_py_precision.py (`::test_bug100_lambda_fed_only_literals`)

`g = lambda sql: con.execute(sql)`, called only as
`g("SELECT COUNT(*) FROM t")`, fired E0713 because the lambda body was
judged on its own and `sql` is a parameter (MedTech `db.py`).

Fix (`d18d2e2`, `_refine_bindings`): the lambda is refined when all of
these hold:
- it is bound once to a local name in a FUNCTION scope;
- it has plain positional parameters only (no defaults, `*args`,
  `**kwargs` or keyword-only parameters);
- every load of the name in the scope, nested defs included, is the callee
  of a positional call with matching arity (no escape).

Each parameter whose every call-site argument is a str literal then takes
those literals: one binding row per call site, and one synthetic Let per
call site that E0723 skips. Module and class scopes are excluded, because
a function the scope walk never sees may call the name.

Negative controls (all still E0713):
- `g(user_sql)` at any call site;
- `other(g)`;
- `return g`;
- `g = other`;
- `g(sql=q)`;
- the parameter name also bound to a function parameter;
- a module-level `g` called as `g(x)` from a function.

### BUG-101  a SQLAlchemy statement unpacked in a `for` loop was a for-target  [OPEN]
test: tests/test_py_precision.py (`::test_bug101_for_over_sqlalchemy_specs`)

`delete_specs = (("a", delete(A).where(...)), ...)` followed by
`for label, statement in delete_specs: session.execute(statement)` fired
E0713: a for-target has no value, so it was never a safe name (Growly).

Fix (`d18d2e2`, `_refine_bindings`): the iterable must be a tuple/list
display. It can be written inline, bound once to a tuple, or bound once to
a list whose only loads are `for` iterables (so the list is never
mutated). Every element is unpacked to the target's arity with no starred
elements. A target position whose every element is a SQLAlchemy
expression (`_is_sql_expression`) or a str literal is bound to those
elements. The binding is an argument-free `sqlBind` or a synthetic literal
Let. This applies to function scopes only.

Negative controls (all still E0713):
- `text(user)` among the elements;
- an f-string SQL element;
- a list `.append`ed before the loop;
- the target rebound to input after the loop.

## LOOP_LOG block

## Iteration 67 — precision: four E0713 false-positive shapes from the owner's projects (no new detector)

- **Target:** the owner's projects produced 16 default findings, and 8 of
  them were four false-positive shapes, all E0713 at 0.6. This is a
  precision iteration. No detector was added or removed, and
  `tests/ratchet_baseline.json` is unchanged.
- **Gap confirmed first:** a minimal snippet per shape went red under
  `--json check-py` at `4435ee2`. The four new tests fail on `4435ee2` only
  on their clean shapes; every negative control already fired there.
- **Fixes (`d18d2e2`, `transpiler/aether/py_frontend.py`):**
  - BUG-098: `.text` needs SQL evidence (receiver or same-scope flow).
  - BUG-099: a dict allowlist of literals is those literals.
  - BUG-100: a non-escaping lambda fed only literals has literal
    parameters.
  - BUG-101: a `for` over a literal display of SQLAlchemy expressions or
    literals binds sanctioned names.
- **Measured** (`--json check-py`, `4435ee2` → `d18d2e2`, same inputs):

| corpus | before | after | removed | added |
|---|---|---|---|---|
| framework corpus (`bench/framework_scan/_work/src`) | 684 | 679 | 5 | 0 |
| in-repo `bench tests tools playground demos` | 113 | 113 | 0 | 0 |
| owner projects (Growly, Halyk, Law_Consultant, MedTech, Sulu-Read, TrumpaBot) | 16 | 8 | 8 | 0 |

- **Gate:** `python -B scripts/run_all.py` exit 0.
- **TYPE gap surfaced:** receiver evidence for `.text` stops at the
  function boundary. `from app.extensions import db` followed by
  `return db.text(q)`, in a file importing neither sqlalchemy nor
  flask_sqlalchemy, is now silent: the one miss-direction trade in this
  iteration, and the owner's call (see q1 row 1).

## q1 residual rows

1. **`.text` evidence is per-scope (BUG-098).** A `db.text(q)` whose
   receiver is imported from a project module (`from app.extensions import
   db`), in a file that imports neither `sqlalchemy` nor `flask_sqlalchemy`,
   and whose result is only returned or stored is not a finding. The result
   reaching an executor or clause in the SAME scope still is. The same
   applies to an attribute receiver (`self.db.text(q)`). Widening it would
   mean counting any imported `db`/`sa` receiver as evidence. That is
   over-flag direction and does not touch the four reported shapes; it
   needs the owner's decision because the brief scoped the convention to
   files that import SQLAlchemy.
2. **Dict allowlist, inline display only (BUG-099).** A name bound to a
   dict (`ORDER = {...}; ORDER.get(k, "x")`) is still a computed call. It
   over-flags because a dict is mutable elsewhere. When the candidates are
   joined to read the literal bans, a ban can match across two candidates
   (`".."` spanning `"a."` and `".b"`), which is also over-flag.
3. **Lambda escape through reflection (BUG-100).** `locals()` / `vars()`
   can reach the lambda without loading its name. The frontend already
   reports those builtins as UNPROVABLE, but the refinement does not look
   for them. Lambdas with defaults, keyword calls or `*args` are not
   refined (over-flag).
4. **Loop refinement: `for` statements only (BUG-101).** Comprehension
   targets and nested unpack targets are not refined (over-flag). A list
   counts as unmutated only when every load of it is a `for` iterable.

## Measurements: every removed finding, justified

### Framework corpus (684 → 679)

All paths are under `bench/framework_scan/_work/src/`. Every removed finding
is E0713 at 0.6.

| file:line | justification |
|---|---|
| `agno/agno/vectordb/lancedb/lance_db.py:758` | LanceDB hybrid query `.vector(e).text(query)`: a full-text-search query string, not SQL. The later `.where(where_clause)` is still judged by the str-shape rule. (BUG-098) |
| `aider_chat/aider/gui.py:320` | streamlit `st.text(text)`, a UI widget. (BUG-098) |
| `aider_chat/aider/gui.py:400` | streamlit `st.text(self.prompt)`, a UI widget. (BUG-098) |
| `langchain_community/langchain_community/chat_models/outlines.py:329` | outlines `generate.text(self.client)`, a text generator factory; its argument is a model client. (BUG-098) |
| `langchain_community/langchain_community/llms/outlines.py:269` | Same as the previous row. (BUG-098) |

### In-repo trees (113 → 113)

No change.

### Owner projects (16 → 8)

Every removed finding is E0713 at 0.6.

| file:line | justification |
|---|---|
| `Growly/growly-tz3/code/app/services/business_context_service.py:124` | `for label, statement in delete_specs: session.execute(statement)` over a local tuple of `delete(...)[.where(...)]`. (BUG-101) |
| `Halyk/tests/test_covenants.py:77` | `builder = DocumentBuilder()` then `builder.text(text)`. (BUG-098) |
| `Halyk/tests/test_features.py:86` | `builder.page(page).text("...")` / `builder.text(f"...")` on a DocumentBuilder. (BUG-098) |
| `Halyk/tests/test_metadata.py:224` | `DocumentBuilder().text(text)`. (BUG-098) |
| `Halyk/tests/test_metadata.py:234` | `DocumentBuilder().text(text)`. (BUG-098) |
| `Halyk/tests/test_metrics.py:444` | `DocumentBuilder().text(...)`, chained. (BUG-098) |
| `MedTech/nomad-price-normalizer/db.py:355` | `g = lambda sql: con.execute(sql).fetchone()[0]`; all 5 calls pass literals, and `g` never escapes. (BUG-100) |
| `TrumpaBot/trumpbot/state.py:83` | `adds = [("entry_price", "TEXT DEFAULT '0'"), ...]`, a list of str-literal pairs bound once and loaded only as a `for` iterable. `f"ALTER TABLE positions ADD COLUMN {name} {decl}"` is built only from literals the developer wrote. This is the literal column of BUG-101's rule, true by rule. |

The MedTech call `con.execute(f"... WHERE {fresh}", (cutoff,))` in the same
function is not through `g` and is unchanged.

Added: 0 on every corpus.
