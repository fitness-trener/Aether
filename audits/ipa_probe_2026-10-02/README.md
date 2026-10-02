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
today.
