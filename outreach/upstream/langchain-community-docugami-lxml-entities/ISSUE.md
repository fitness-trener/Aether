# DRAFT — for the langchain_community repository — DO NOT AUTO-POST

Verify the current home of `langchain_community` before posting
(`langchain-ai/langchain` under `libs/community`, or its successor repo);
the file path below is from the `langchain_community-0.4.2` wheel.

**Priority: low.** Read the scope paragraph before deciding to post.

**Title:** DocugamiLoader: pass an explicit XMLParser(resolve_entities=False) for users on lxml < 5

## What happened

`langchain_community/document_loaders/docugami.py` parses DGML with lxml's
default parser in two places:

```python
# _parse_dgml, ~line 153
tree = etree.parse(io.BytesIO(content))

# artifact handling, ~line 277
artifact_tree = etree.parse(io.BytesIO(response.content))
```

The second site parses bytes from an HTTP response; the first parses
whatever the caller hands in.

## Scope — this is narrower than a typical XXE report

- **lxml ≥ 5.0 (December 2023) is safe by default.** The default
  `resolve_entities` became `'internal'`, so a `SYSTEM` entity is not
  fetched — verified on lxml 6.1.1 / libxml2 2.11.9, where such a document
  fails to parse with `Entity 'x' not defined`. libxml2 also caps
  internal-entity amplification (`Maximum entity amplification factor
  exceeded`), so the billion-laughs shape is refused too.
- **lxml < 5 resolved external entities by default**, and
  `langchain_community` does not declare an lxml version — it is an
  optional import — so a user with an older environment gets the old
  behaviour. That is the population this note is for.

For a maintainer this is a one-line hardening that removes a
version-dependent difference, not a vulnerability in the package.

## Suggested fix

Construct the parser once and pass it at both sites:

```python
_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)

tree = etree.parse(io.BytesIO(content), parser=_XML_PARSER)
...
artifact_tree = etree.parse(io.BytesIO(response.content), parser=_XML_PARSER)
```

Behaviour on lxml ≥ 5 is unchanged; on lxml < 5 it matches.

## Environment

- `langchain_community` 0.4.2 (wheel from PyPI); lxml not pinned
- Found by `aether check-py` (rule E0727, CWE-611) scanning the published
  wheel. The rule flags `lxml.etree.parse` on an unconfigured parser
  because it cannot know which lxml is installed; this note is the
  version-dependent case it cannot resolve statically.

## Repro (only meaningful on lxml < 5)

```python
# pip install "lxml<5"   -- on lxml >= 5 this raises XMLSyntaxError instead
import io
from lxml import etree

payload = b'<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/hostname">]><d>&x;</d>'
print("default parser:", repr(etree.parse(io.BytesIO(payload)).getroot().text))
safe = etree.XMLParser(resolve_entities=False, no_network=True)
print("explicit parser:", repr(etree.parse(io.BytesIO(payload), parser=safe).getroot().text))
```
