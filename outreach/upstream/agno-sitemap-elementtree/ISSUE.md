# DRAFT — for github.com/agno-agi/agno — DO NOT AUTO-POST

**Title:** SitemapReader and PubmedTools parse remote XML with xml.etree; use defusedxml

## What happened

Three call sites parse XML fetched over the network with the standard
library's `xml.etree.ElementTree`:

```python
# agno/knowledge/reader/sitemap_reader.py, _parse_sitemap (~line 123)
root = ElementTree.fromstring(SitemapReader._decode_sitemap_bytes(raw))

# agno/tools/pubmed.py (~lines 43 and 51)
root = ElementTree.fromstring(response.content)
return ElementTree.fromstring(response.content)
```

The Python documentation's own note on `xml.etree.ElementTree` is that it
is not secure against maliciously constructed data — specifically the
entity-expansion attacks ("billion laughs", quadratic blowup) — and
recommends `defusedxml` for untrusted input.

`SitemapReader` is the stronger case: the sitemap URL is caller-supplied
in normal use, so the bytes being parsed are whatever that host returns.
`_decode_sitemap_bytes` already handles a gzipped body, which is also the
standard delivery for a compression-bomb sitemap. A hostile or compromised
host can make the reader consume memory and CPU without bound before any
`<loc>` is read.

PubMed's endpoint is a fixed, well-run service, so those two sites are
lower exposure; they are the same shape and the same one-line change.

## Suggested fix

```python
try:
    from defusedxml import ElementTree
except ImportError:
    from xml.etree import ElementTree  # or make defusedxml a hard dependency
```

`defusedxml.ElementTree.fromstring` is a drop-in replacement that refuses
entity expansion and DTDs.

## Environment

- agno 3.0.5 (wheel from PyPI), CPython 3.11
- Found by `aether check-py` (rule E0727, CWE-611) scanning the published
  wheel.

## Repro

```python
# no third-party packages needed
import time
from xml.etree import ElementTree

# a small "billion laughs" — 10 levels, 10x each, ~10 billion expansions
levels = 10
ents = ['<!ENTITY a0 "lol">'] + [
    f'<!ENTITY a{i} "' + "".join(f"&a{i-1};" for _ in range(10)) + '">'
    for i in range(1, levels)
]
payload = "<!DOCTYPE d [" + "".join(ents) + "]><d>&a" + str(levels - 1) + ";</d>"

t = time.time()
try:
    ElementTree.fromstring(payload)
except Exception as e:
    print("raised:", type(e).__name__)
print(f"stdlib ElementTree: {time.time() - t:.1f}s")

try:
    from defusedxml import ElementTree as DET
    try:
        DET.fromstring(payload)
    except Exception as e:
        print("defusedxml refused:", type(e).__name__)
except ImportError:
    print("pip install defusedxml to see the refusal")
```

Run with a memory limit; the stdlib call either exhausts memory or runs
for a long time, and `defusedxml` raises `EntitiesForbidden` immediately.
