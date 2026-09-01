# `aether check-py` on 15 AI-agent frameworks

**Date:** 2026-09-01, re-measured 2026-09-02 after BUG-010 and BUG-011.
**Question:** `bench/pypi_scan/` scanned whatever happened to be in
site-packages. What does the tool do on the population it actually claims
to be for — the frameworks that generate and execute AI-written Python?

**Reproduce:** `python -B bench/framework_scan/run_scan.py`
(`--json` for every finding). Wheels only, via
`pip download --only-binary`, so no sdist build step runs; nothing is
imported or executed.

**Headline, stated first and unflatteringly.** The first run found no
vulnerability worth reporting to anyone, and found that 97% of its own
output was one false-positive class. Fixing that class exposed a
**false-negative class underneath it** — imports under `try:` had never
been registered, so a guarded `yaml.load(x)` was silent — and repairing
both moved the count from **1,055 findings to 411**, four of which are
sinks that were invisible before. The useful output of this run is two
bugs in Aether, not a bug in LangChain.

---

## 1. Corpus and robustness

| | |
|---|---|
| distributions | 15 |
| `.py` files | **4,946** |
| files that failed to parse | **0** |
| analyzer crashes | **0** (in all three passes over the corpus) |

Zero crashes and zero parse failures on a corpus with a very different
shape from `site-packages` — heavy `async`, pydantic models, decorators,
generated protocol code. Combined with the 1.19M-line PyPI run, the
frontend has now read ~1.2M lines of third-party Python without an
unguarded exception.

| distribution | files | before | **after** |
|---|---:|---:|---:|
| agno | 1,024 | 868 | **245** |
| langchain-community | 1,204 | 139 | **118** |
| semantic-kernel | 555 | 17 | 17 |
| openhands-ai | 165 | 8 | 8 |
| crewai | 512 | 7 | 7 |
| aider-chat | 81 | 4 | 4 |
| smolagents | 20 | 4 | **5** |
| langchain | 36 | 3 | 3 |
| llama-index-core | 480 | 2 | 1 |
| mcp | 123 | 2 | 2 |
| haystack-ai | 283 | 1 | 1 |
| langchain-core, langgraph, autogen-agentchat, browser-use | 463 | 0 | 0 |
| **total** | **4,946** | **1,055** | **411** |

## 2. BUG-010 — the E0713 flood was Aether's

1,029 of the original 1,055 findings were `E0713`, and read at the source
line they were overwhelmingly **SQLAlchemy Core expression objects**:

```python
conn.execute(select(table.c.client_metadata).where(table.c.client_id == client_id))
conn.execute(delete(table).where(table.c.expires_at < now))
```

That is the *safest* form of SQL in Python: the expression is compiled
with bound parameters, and no string is assembled anywhere. Two correct
rules composed into refusing it — `execute` is a sink by method name (the
over-flag q5 sanctions) and any non-literal argument read as dynamic — so
**every ORM call site in the corpus was a finding.**

Neither rule changed. The frontend now names a call rooted at a
`sqlalchemy`/`sqlmodel` builder as E0713's wrapper, `sqlBind`, the way
`shlex.quote` is already named `shellArg`. Three shapes, each with its
own soundness argument (`bench/py_frontend/REPORT.md` §3c):

- a builder call at the sink, resolved **through the file's imports** —
  a bare name spelled `select` from anywhere else clears nothing;
- a statement **built incrementally** (`stmt = select(t)`, then
  `stmt = stmt.where(...)`), resolved by a least fixpoint that allows
  self-reference but requires an anchor;
- the **Table-method form** (`table.delete().where(...)`), accepted only
  when the root call takes no positional argument.

The line that does not move: `text(...)` or `literal_column(...)` handed
a non-literal, **anywhere inside the expression**, sanctions nothing.

It took three rounds to get from 1,029 to 381, and the second round is
the interesting one.

## 3. BUG-011 — the second round cleared almost nothing, because of a false negative

The first cut cleared 43 of 1,029. Reading the survivors showed that
bindings like `stmt = select(t)` — the anchor case — were still firing,
which meant `select` was not resolving to `sqlalchemy.select` at all.
agno imports it the way every framework does:

```python
try:
    from sqlalchemy.sql.expression import select, text
except ImportError:
    raise ImportError("`sqlalchemy` not installed. ...")
```

`py_to_ir` registered imports only as direct children of the module
body. Anything under `try:`, under `if`, or inside a function was never
seen. For a builder that is a precision problem. For a sink it is a
**false accept**: confirmed by execution before the fix, this produced no
finding at all —

```python
try:
    import yaml, pickle
except ImportError:
    raise
def load(raw):    return yaml.load(raw)      # silent
def unpickle(b):  return pickle.loads(b)     # silent
```

An unresolved qualified sink matches no table and is translated as
`py:load`, which every detector looks past. Same family as BUG-004: the
unknown case defaulted to "not a sink".

Imports are now collected from the whole module. A local name bound by
two imports to *different* targets is ambiguous and resolves to nothing:
it clears no query and sanctions no builder. Never pick a winner.

**What surfaced on this corpus once imports resolved — four sinks that
were silent on 2026-09-01:**

| | site | what it is |
|---|---|---|
| `E0727` | `langchain_community/document_loaders/docugami.py:153` | `etree.parse(io.BytesIO(content))` — **lxml, whose default parser resolves external entities**, on content fetched from a remote API. `from lxml import etree` under `try:`. |
| `E0727` | `langchain_community/document_loaders/docugami.py:277` | same, on `response.content` |
| `E0727` | `smolagents/default_tools.py:443` | `ET.fromstring(response.text)` on a Bing RSS response — stdlib, so DoS-class rather than XXE |
| `E0720` | `agno/utils/pickle.py:26` | `pickle.load(...)` with a function-local `import pickle`; a persistence helper, true by shape |

The two docugami sites are the strongest finding of the whole exercise:
lxml with entity resolution on, over bytes that arrived from the network.
`etree.XMLParser(resolve_entities=False)` is the one-line remedy, and it is
the E0727 hint.

The same fix, measured on the PyPI corpus the same day (before → after,
same interpreter): E0720 **109 → 124**, and against the bandit oracle
B301→E0720 hits **102 → 118**, misses **26 → 10**. Independent
confirmation on a second corpus.

## 4. The 381 E0713 that remain, read at source

| n | shape | verdict |
|---:|---|---|
| 158 | `text(<non-literal>)` — a parameter, or an f-string of table/schema names in migrations | true by shape; DDL assembled from names is the classic "safe-looking" injection and stays flagged |
| 64 | name-bound, other | almost all disqualified by one binding that is a helper call (`stmt = apply_sorting(stmt, ...)`) — cross-function, the recorded residual |
| 31 + 23 + 22 + 28 + 4 | `str.format(...)`, f-string, or concatenation, directly or through a name | **true by shape** — 108 real dynamic queries, mostly in `agno/tools/*` (a SQL toolkit that takes queries from the agent, by design) and migrations |
| 20 | `stmt = self._helper(...)` | cross-function residual |
| 12 | the name is a parameter | unresolvable, correctly |
| 8 | psycopg `sql.SQL(...).format(sql.Identifier(...))` | a second safe-composition grammar; not modelled, residual |
| 11 | `Starred`, `Attribute`, `IfExp`, one-off helpers | unmodelled shapes, over-flag |

So of 381, roughly **108 are genuinely dynamic queries** (the toolkits
that run agent-supplied SQL on purpose), **~100 are cross-function or
parameter cases** no intraprocedural rule can resolve, and the rest are
unmodelled shapes. None is a reportable vulnerability; the toolkits are
the product.

## 5. The 30 findings that are not E0713

| Class | n | Verdict |
|---|---:|---|
| `E0714` shell in agent runtimes / coding tools | 13 | true by shape, by-design context |
| `E0720` pickle | 9 | 8 behind an explicit opt-in the maintainers wrote; 1 newly visible (agno, above) |
| `E0727` XML on remote content | 6 | **3 worth an upstream note** — the two docugami lxml sites above, and `agno/knowledge/reader/sitemap_reader.py:123` (attacker-choosable sitemap URL, stdlib parser, DoS-class) |
| `E0719` the framework's own Jinja templates | 2 | by design |

Two correctness bugs, not security, remain worth filing:
`mcp/cli/cli.py:48` and `aider/commands.py:964` both pass an argv list
together with `shell=True`, which on POSIX runs only the first element.

## 6. What this run established

- The frontend parses 4,946 more files of a different shape with zero
  crashes.
- **Two Aether bugs, one of each kind:** a precision ceiling (BUG-010,
  97% of output) that would have made `check-py` unusable for the first
  backend user, and a false-accept class (BUG-011) underneath it that no
  amount of reading the over-flags would have found — it took clearing
  them to see what was missing.
- **No security vulnerability in any of the 15 frameworks.** The expected
  outcome for widely-reviewed code; the docugami lxml sites are the
  nearest thing, and they are a hardening note, not a CVE.

The honest one-line summary: **on the corpus Aether is aimed at, its
best-covered detector produced 97% noise, fixing the noise exposed a
class of silence, and the tool is now both quieter and less blind than
it was two days ago — measured, on the same 4,946 files.**
