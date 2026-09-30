# Robustness on 209 small AI-agent and MCP-server repositories (2026-09-29)

This is a robustness measurement: does `check-py` run to completion on
code nobody wrote for it, and what does it report? It is **not** a
precision or vulnerability study. No finding here was triaged for
exploitability, and none is claimed to be a vulnerability. The
high-confidence findings of the 15-framework corpus were triaged by hand
(`bench/framework_scan/REPORT.md` §12): none was exploitable.

## Corpus

- **Selection:** a GitHub repository search on 2026-09-29 for the topics
  `mcp-server`, `mcp`, `ai-agent` and `llm-agent`. Filters: language
  Python, 15–800 stars, updated after 2026-06-01, not a fork, not
  archived, at most 20 MB. That gave 210 repositories.
- **Clone:** `git clone --depth 1` of each default branch, with a sparse
  checkout of `*.py` only. 209 cloned; one did not check out on Windows.
- **Pinning:** the repository names and commit SHAs are kept outside the
  public tree. The scan is about the tool, not about any one project.

## Results

`python -B -m transpiler.aether.cli --json check-py <the 209 checkouts>`,
Python 3.11.15, Windows, 8 logical cores, default `--jobs`, run
2026-09-29 at 0.5.0:

| | |
|---|---|
| files analysed | **41,499** |
| analyzer errors (crashes) | **0** |
| files not parsed | 209, every one a `SyntaxError`; 194 of them carry the "valid on a newer Python? scan with 3.12+" note |
| wall time | 277 s |
| findings | 6,862 |
| of which in test paths (`test`/`tests/` in the path) | 3,648 (53%) |
| findings at `--min-confidence 0.9` | 1,361 |

Findings by code: E0713 4,438 · E0714 1,061 · E0727 614 · E0723 212 ·
E0731 210 · E0716 164 · E0720 75 · E0718 58 · E0719 30.

Findings by confidence: 0.6 → 5,501 · 0.9 → 151 · 0.95 → 834 · 1.0 → 376.

## What the run changed in Aether

The first scan, before this recalibration, reported 2,079 findings at
`--min-confidence 0.9`. 765 of them were E0714 argv findings. Nearly all
of those were a positional path handed to `git` in test code
(`["git", "init", str(tmp_path)]`), rated 0.9 by the argument-injection
rule of iteration 65.

Such a word runs a command only if it lands as an option, and the word
itself decides that at run time. So that match now has its own kind,
`argv_option`, rated at the 0.6 floor:
- the findings stay, and `--min-confidence 0.9` now hides them;
- `["bash", "-c", cmd]` keeps its 0.9 `argv` rating (47 findings here).

On the 15-framework corpus the change moves one finding from 0.9 to 0.6,
and the set of 684 findings is identical.

## What this does not show

- **Precision.** No finding here was read to decide whether the rule was
  right or the flagged value is attacker-controlled.
- **Recall.** There is no ground truth for this corpus.
