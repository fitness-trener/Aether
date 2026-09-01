# `aether check-py` on 15 AI-agent frameworks

**Date:** 2026-09-01
**Question:** `bench/pypi_scan/` scanned whatever happened to be in
site-packages. What does the tool do on the population it actually claims
to be for — the frameworks that generate and execute AI-written Python?

**Reproduce:** `python -B bench/framework_scan/run_scan.py`
(`--json` for every finding). Wheels only, via
`pip download --only-binary`, so no sdist build step runs; nothing is
imported or executed.

**Headline, stated first and unflatteringly: the scan found no
vulnerability worth reporting to anyone, and it found a false-positive
class in Aether large enough that `E0713` is currently unusable on any
codebase that uses SQLAlchemy.** 1,029 of 1,055 findings are that one
class. The useful output of this run is a bug in Aether, not a bug in
LangChain.

---

## 1. Corpus and robustness

| | |
|---|---|
| distributions | 15 |
| `.py` files | **4,946** |
| files that failed to parse | **0** |
| analyzer crashes | **0** |

Zero crashes and zero parse failures again, on a corpus with a very
different shape from `site-packages` — heavy `async`, pydantic models,
decorators, and generated protocol code. Combined with the 1.19M-line
PyPI run, the frontend has now read ~1.2M lines of third-party Python
without an unguarded exception.

| distribution | files | findings |
|---|---:|---:|
| agno | 1,024 | 868 |
| langchain-community | 1,204 | 139 |
| semantic-kernel | 555 | 17 |
| openhands-ai | 165 | 8 |
| crewai | 512 | 7 |
| aider-chat | 81 | 4 |
| smolagents | 20 | 4 |
| langchain | 36 | 3 |
| llama-index-core | 480 | 2 |
| mcp | 123 | 2 |
| haystack-ai | 283 | 1 |
| langchain-core, langgraph, autogen-agentchat, browser-use | 463 | 0 |

## 2. The E0713 flood is Aether's bug — BUG-010

1,029 of 1,055 findings are `E0713`, and read at the source line they are
overwhelmingly **SQLAlchemy Core expression objects**:

```python
conn.execute(select(table.c.client_metadata).where(table.c.client_id == client_id))
conn.execute(delete(table).where(table.c.expires_at < now))
conn.execute(text("SELECT 1"))
```

That is the *safest* form of SQL in Python. The expression is compiled by
SQLAlchemy with bound parameters; no string is concatenated anywhere.

Two correct rules combine into a wrong answer. `execute` is a SQL sink
matched by method name — the documented over-flag q5 sanctions, because
the error direction is safe. Then `_SQL_RULE` reads a non-literal argument
as dynamic, and a `select(...)` call is a non-literal. The result is that
**every ORM call site in the corpus is a finding**, at a rate that buries
everything else: `agno` alone produced 868, from 31 files.

This is precision, not soundness — Aether over-flags, it does not miss —
but at this ratio the distinction does not help a user. It is the same
shape of decision `E0711` already got in `bench/py_frontend/REPORT.md`
§2, and it should get the same treatment or a recogniser. Filed as
**BUGS.md BUG-010**.

A second, much smaller precision residual appeared in the same family:
`haystack_ai/haystack/marshal/yaml.py:40` calls
`yaml.load(data_, Loader=YamlLoader)` where `YamlLoader` is a
`yaml.SafeLoader` **subclass**. Aether refuses it because the guard value
is not positively identified as sanctioned — BUG-004's deliberate
"unrecognized means SINK" contract, and the already-documented
subclass/from-import limit in `bench/py_frontend/REPORT.md` §4. Correct by
policy, wrong in fact.

## 3. The 26 findings that are not E0713

Read at the source line, none is a reportable vulnerability.

| Class | n | Verdict |
|---|---:|---|
| `E0714` shell in agent runtimes / coding tools | 13 | **True by shape, by-design context** |
| `E0720` pickle behind an explicit opt-in | 8 | True by shape, gated by the callers |
| `E0727` stdlib XML parser on remote content | 3 | **Worth an upstream note** |
| `E0719` framework's own Jinja templates | 2 | By-design |

**`E0714` — the agent frameworks run shells on purpose.** `openhands-ai`
builds five `subprocess.run(f'chown -R {username}:root {pwd}', shell=True)`
calls in its sandbox bootstrap; `aider` shells out to the user's editor
and notification command; `agno`'s coding tool takes a command and runs
it. Each is textbook CWE-78 *shape* and each is the product's stated
purpose. This is the same verdict the PyPI scan reached for `pip` and
`fire`: true by shape, local-trust context.

Two of them are worth a maintainer's attention as **correctness** rather
than security: `mcp/cli/cli.py:48` and `aider/commands.py:964` both pass
an **argv list together with `shell=True`**, which on POSIX runs only the
first element and on Windows is undefined. That is a latent bug in both,
and it is the kind of thing a scanner is genuinely useful for.

**`E0720` — every pickle site is already gated.** `crewai` carries
`# noqa: S301`; both `langchain-community` sites carry
`# ignore[pickle]: explicit-opt-in` and sit behind
`allow_dangerous_deserialization`; `smolagents` checks an `allow_pickle`
flag and warns. The maintainers know. Aether's rows agree with tools they
already run, which is a mild positive result for precision on this family
and nothing more.

**`E0727` — the one thing worth sending upstream.**
`agno/knowledge/reader/sitemap_reader.py:123` parses a **remote, caller-supplied
sitemap** with `xml.etree.ElementTree.fromstring`, and
`agno/tools/pubmed.py:43,51` parse remote HTTP responses the same way.
Modern CPython's ElementTree does not resolve external entities, so this
is not file-read or SSRF — but it remains exposed to entity-expansion and
quadratic-blowup DoS, and `defusedxml` is the standard remedy. The sitemap
reader is the strongest of the three because the URL is attacker-choosable
in normal use.

## 4. What this run did and did not establish

- **Did:** 4,946 more files parsed with zero crashes; a real, measured
  precision ceiling (BUG-010) that would have made the tool unusable for
  the first backend user who tried it; two genuine upstream correctness
  bugs (`shell=True` with a list).
- **Did not:** find a security vulnerability in any of the 15 frameworks.
  It is worth saying plainly that this is the expected outcome for
  widely-reviewed code, and that a scanner's value on such a corpus is
  measured by its false-positive rate, which here was poor.

The honest one-line summary: **on the corpus Aether is aimed at, its
best-covered detector currently produces 97% noise, and finding that out
is what this scan was for.**
