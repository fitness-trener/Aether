# Aether Wiki — Schema & Maintenance Manifest

## Purpose
This vault is the long-term analysis memory for **Aether**, a programming language whose
compiler refuses to compose components that violate declared architectural constraints
(effect locality, capability scope, refinement-typed boundaries) and emits structured,
machine-readable diagnostics an agent fix-loop can act on. The vault analyzes the v0.1
language specification and the v0.3 toolchain behavior. Consumers: the maintainer
(fitness-trener) and any LLM reasoning about Aether's design, invariants, and the
deterministic-vs-live fix-loop split. Single level (no MVP/Vision tiers).

Vault is meant to be opened in Obsidian: the LLM writes and maintains `wiki/` pages;
the human curates `raw/` sources and asks questions.

## Folder Rules
- `raw/sources/` — immutable first sources. **Read-only.** The canonical copies live in the
  Aether repo (`grammar/`, `README.md`); files here are read-only pointer stubs naming the
  in-repo path of record. Never edit them; add NEW source stubs only.
- `raw/assets/` — local images/attachments for sources.
- `wiki/` — analysis pages. The LLM owns this layer entirely.
- `templates/` — page contracts for ingesting new sources and questions.
- Every architectural claim must cite a specific source section.

## Data Model
Requirement capture format:
- `source_name`: one of README | keywords | effects | types | diagnostics (matches `wiki/sources/`)
- `section`: the section/heading in the source
- `key`: key quote/keyword
- `context_level`: version the claim is true for — `v0.1` (spec), `v0.3` (toolchain), or `parked` (v0.2+)

## Page Types
- `source_note` → `wiki/sources/`
- `cluster_page` → `wiki/clusters/`
- `question_page` → `wiki/questions/`
- `concept_page` → `wiki/concepts/` — differentiator decisions; claims beyond sources marked "Strategic addition".
- `content_idea` → `wiki/content-ideas/`

YAML frontmatter (`type`, `status`, `confidence`, `last_updated`, `tags`) lets Obsidian Dataview build live tables.

## Citation Rules
Every claim, requirement, or constraint carries a source marker:
`[source: <source_name>, section: <name>, key: <keyword>]`

## Ingest Workflow
1. Profile the incoming doc (`wiki/sources/<name>.md`).
2. Split content by Data Model levels/categories.
3. Update taxonomy if needed (by editing this file).
4. Distribute items into clusters and question answers.
5. Update `wiki/index.md`, prepend an entry to `wiki/log.md`.
6. Run the lint check.

## Query Workflow
1. Read `wiki/index.md` → find relevant pages.
2. Read them, synthesize an answer with citations.
3. Good answer → save as `question_page` (answers compound as sources).

## Lint Workflow
- Find orphan pages, broken links, unsourced numbers.
- Every claim has a source marker; assumptions flagged.
- Taxonomy has no labels outside the list.
- Check "Never Do".

## Taxonomy
effect-system · capability-model · type-system · refinement-contracts · diagnostics · fix-loop · toolchain · design-rationale

## Never Do
- Never edit `raw/` (except adding NEW source files).
- Never present a runtime-checked guarantee as static: v0.1 checks refinements/contracts/capabilities at runtime; do not overstate soundness. `[source: types, section: Refinement types]`
- Never invent diagnostic codes, effect names, keywords, or capabilities absent from the spec.
- Never present v0.2+ parked features (`async`, SMT pass, brace-init, value-level `as`, static subset checks) as available in v0.1/v0.3.
- Never create page types outside this list without first adding them to Page Types here.
