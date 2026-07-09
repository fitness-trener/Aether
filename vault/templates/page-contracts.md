# Page contracts (frontmatter + required sections)

Language of a page = language of its sources (English). Every page reachable from
`wiki/index.md`. A `Related` section (min 2 wikilinks) ends every page or it becomes an orphan.

## source_note → `wiki/sources/<name>.md`
frontmatter: `type: source_note`, `source_name`, `status: ingested`, `confidence`, `last_updated`.
Sections: **Profile** · **Core Concepts** (table: concept → gist → where embedded) · **Accepted / Rejected** · **Fact-check** (if external claims verified) · **Related**.

## cluster_page → `wiki/clusters/<slug>.md`
frontmatter: `type: cluster_page`, `cluster_id`, `status: active`, `confidence`, `last_updated`, `tags`.
Sections: **Summary** · **Evidence** (table: Source | Section | Quote/Rule | Signal) · **Implications** (assumptions flagged) · **Related**.

## question_page → `wiki/questions/q<N>-<slug>.md`
frontmatter: `type: question_page`, `question_id`, `status: answered`, `confidence`, `last_updated`.
Sections: **question heading** · **Short Answer** (3–6 sentences, with markers) · **Evidence** (table: Finding | Evidence | Confidence) · **Recommended Actions** (if apt) · **Related**. Errata on top if it corrects a prior version.

## concept_page → `wiki/concepts/<slug>.md`
frontmatter: `type: concept_page`, `concept_id`, `status: active`, `confidence`, `last_updated`, `tags`.
For decisions beyond sources. Sections: **Summary** · decision sections · **Related**. Anything beyond sources marked "Strategic addition".

## content_idea → `wiki/content-ideas/<slug>.md`
frontmatter: `type: content_idea`, `idea_id`, `status: draft`, `confidence`, `last_updated`.
Sections: **Audience/Pain** · per-element artifact structure with markers · **Risks / What Not To Promise** · **Related**.

## index.md / log.md / lint-report.md
See the manifest. index links every page; log is append-only (newest on top); lint newest run on top.
