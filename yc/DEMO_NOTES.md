# Demo Recording Handoff — Aether YC video, take 2 (90 seconds)

This is a press-record-and-go script. Six clips, ~15 seconds each,
front-loaded so a partner who only watches the first 20 seconds
still sees the architectural-integrity claim. Voiceover is timed to
the on-screen action; every command shown produces stdout that's
already in this repo and is reproducible from a fresh clone with
zero secrets.

The video is **the second take** — it replaces the F-phase video
which made the fix-loop look more "AI-driven" than it is. The new
framing is *"protocol + deterministic reference + one-shot LLM
proof on the codes that need intent."*

---

## Before you press record

1. **Regenerate the LLM transcript with a real API key.** From the
   founder's laptop:

   ```sh
   export ANTHROPIC_API_KEY=...
   python3 -B demos/payment_workflow/llm_fix_demo.py live-fix
   ```

   This overwrites `demos/payment_workflow/llm_fix_demo.transcript.json`
   with a transcript stamped `"_meta.source": "live-anthropic-<ISO>"`.
   Commit it. The committed transcript is now the *real* artifact a
   partner will inspect — not the placeholder ship.

   If `live-fix` fails (model returns malformed JSON, network drops),
   re-run until it succeeds. The committed transcript must show
   `live-anthropic-<ISO>` before recording.

2. **Run the live positive control once** (you don't need to
   commit the output — just verify the protocol works on E0302
   too):

   ```sh
   python3 -B demos/payment_workflow/llm_fix_demo.py live-positive-control
   ```

   This writes `demos/payment_workflow/llm_fix_demo.positive_control.json`
   (gitignored). If it succeeds, you're confident the protocol
   extends to a second un-cherry-picked code; if a partner asks
   "did you only test one shape?" you can run this on screen.

3. **Run the full gate once.** Both fixes verified by `aether check`,
   no regression elsewhere:

   ```sh
   python3 -B scripts/run_all.py
   ```

   Must exit 0 with all 21 PASS lines. If any line is FAIL, fix it
   before recording. (Was 18 in the take-1 script; Phase E added
   `lsp`, `multi_file`, plus the packaging / playground / llm_fix
   gates folded into the same run_all aggregate.)

4. **Stage the terminal.** White background, monospace font 18pt+
   so a YC partner watching on a phone can read it. Two windows
   side-by-side: terminal on the left, an editor on the right
   showing `demos/payment_workflow/aether/main.aeth`.

5. **Practice the voiceover once cold.** It's tight. If you stumble
   on the run-through, slow the second take by ~10%.

---

## The six clips (90 seconds total)

### Clip 1 — Open (0:00 – 0:12)

**On screen:** terminal at the repo root; `ls demos/payment_workflow/`
shows the two `main.*`, the `broken*.aeth`, the `*.py`, and the
`*.transcript.json`.

**Voiceover (founder speaks):**

> "Aether is a programming language designed for AI agents to write
> production code. The compiler refuses to compose components that
> violate the architectural promises declared in the source — and it
> emits diagnostics that an agent can act on without reading English.
> Here's the same payment workflow, two languages, byte-identical
> output."

### Clip 2 — Aether passes every promise (0:12 – 0:27)

**On screen:** two commands run back-to-back:

```sh
python3 -B -m transpiler.aether.cli check demos/payment_workflow/aether/main.aeth
python3 -B -m transpiler.aether.cli run   demos/payment_workflow/aether/main.aeth
```

Output:

```
OK: demos/payment_workflow/aether/main.aeth (11 decls)
PERSIST rcpt-8500-USD
EVENT payment.success rcpt-8500-USD
DONE rcpt-8500-USD
```

**Voiceover:**

> "104 lines of Aether. Effects are statically checked. URL
> discipline is enforced — this gateway can only reach
> `/charge/*`, the admin URL is unreachable by construction.
> Module capability is `log, net, time` — the compiler refuses
> any composition that needs more. Refinement-typed parameters
> are rejected at the boundary. `aether check` confirms every
> promise; `aether run` prints the receipt."

### Clip 3 — Python runs identically; nothing enforced (0:27 – 0:37)

**On screen:**

```sh
python3 -B demos/payment_workflow/python/main.py
```

Output:

```
PERSIST rcpt-8500-USD
EVENT payment.success rcpt-8500-USD
DONE rcpt-8500-USD
```

**Voiceover:**

> "Same workflow in Python. Identical output. Every architectural
> promise lives only in reviewer discipline; the language enforces
> none of them. Watch what happens when an agent edits this."

### Clip 4 — Aether catches the broken candidate (0:37 – 0:55)

**On screen:** two commands:

```sh
python3 -B -m transpiler.aether.cli check demos/payment_workflow/broken.aeth
```

Output highlights:

```
[E0801] error (effect) at line 20, col 1: function 'validateOrder' (effects 'pure')
        calls 'print' which has effect 'log' not covered by the caller
```

then:

```sh
python3 -B demos/payment_workflow/fix_loop.py demos/payment_workflow/broken.aeth
cat demos/payment_workflow/broken.transcript.json | python3 -m json.tool | head -n 30
```

**Voiceover:**

> "Broken candidate. Pure function logs; module performs `fs.write`
> outside its declared capability. The compiler refuses both. The
> SDK-driven fix-loop reads the diagnostic's `extra` dict and
> applies a deterministic AST repair — two mechanical fixes, one
> per axis. No model in the loop. Reproducible on every run."

### Clip 5 — LLM demo on the codes that need intent (0:55 – 1:18)

**On screen:**

```sh
python3 -B demos/payment_workflow/llm_fix_demo.py replay --verbose
```

Output highlights:

```
[ok] replay E0304 (live: live-anthropic-2026-05-17T18:23:04Z)
     transcript: demos/payment_workflow/llm_fix_demo.transcript.json
     fixed source passes `aether check`
```

then scroll through the transcript file showing the prompt + the
real Claude 3.5 Sonnet response with the corrected `return x + x`.

**Voiceover:**

> "Some diagnostics need intent-level reasoning to repair. An
> `ensures` clause violation — the function lied about its
> postcondition — can't be auto-fixed from a structured `extra`
> dict alone. The same protocol runs end-to-end, but a single
> Claude 3.5 Sonnet call sits in the loop instead of a
> deterministic transformer. Here's the live transcript from
> recording day: the diagnostic, the prompt, the model's
> response, the fix verified by `aether check`."

### Clip 6 — Close (1:18 – 1:30)

**On screen:**

```sh
python3 -B scripts/run_all.py | tail -n 22
```

(21 PASS lines.) Then jump to the application's submission link or
to the public landing page.

**Voiceover:**

> "Twenty-one end-to-end gate suites green from a fresh clone. The
> agent SDK, the LSP — diagnostics, hover, completion, go-to-
> definition — the architectural-integrity benchmark, the multi-
> file resolver, the fix-loop protocol — all reproducible by anyone.
> We're building the substrate AI-generated production code is going
> to need. I'm `[FOUNDER NAME]`. Aether."

---

## Recording checklist (final)

- [ ] `ANTHROPIC_API_KEY` set in shell; `live-fix` regenerated the
      committed transcript; commit shows `"live-anthropic-<ISO>"`.
- [ ] `live-positive-control` succeeded once today (output not
      committed; just confirms the protocol extends).
- [ ] `python3 -B scripts/run_all.py` → exit 0, all 21 PASS lines.
- [ ] Terminal staged: clean prompt, no scrollback, 18pt+ monospace,
      white background.
- [ ] Editor pane staged: `demos/payment_workflow/aether/main.aeth`
      open, syntax highlighting on.
- [ ] Six clips recorded back-to-back; review each before moving on.
- [ ] Total length 85–95 seconds. If over 95, cut clip 5's transcript
      scroll first; the verbal frame is what does the work.
- [ ] Watch the full take once at 1.0× and once at 1.5×. The 1.5×
      pass simulates a tired YC partner skimming.
- [ ] Re-record clips 4 and 5 if either reads as overclaim. The
      framing must say "deterministic protocol + LLM-driven on intent
      codes," not "an AI agent fixes the code."

---

## Voiceover read-through reference (paste-into-a-prompter)

> Aether is a programming language designed for AI agents to write
> production code. The compiler refuses to compose components that
> violate the architectural promises declared in the source — and it
> emits diagnostics that an agent can act on without reading English.
> Here's the same payment workflow, two languages, byte-identical
> output.
>
> 104 lines of Aether. Effects are statically checked. URL
> discipline is enforced — this gateway can only reach charge slash
> star, the admin URL is unreachable by construction. Module
> capability is log, net, time — the compiler refuses any
> composition that needs more. Refinement-typed parameters are
> rejected at the boundary. `aether check` confirms every promise;
> `aether run` prints the receipt.
>
> Same workflow in Python. Identical output. Every architectural
> promise lives only in reviewer discipline; the language enforces
> none of them. Watch what happens when an agent edits this.
>
> Broken candidate. Pure function logs; module performs fs.write
> outside its declared capability. The compiler refuses both. The
> SDK-driven fix-loop reads the diagnostic's `extra` dict and
> applies a deterministic AST repair — two mechanical fixes, one
> per axis. No model in the loop. Reproducible on every run.
>
> Some diagnostics need intent-level reasoning to repair. An
> `ensures` clause violation — the function lied about its
> postcondition — can't be auto-fixed from a structured `extra`
> dict alone. The same protocol runs end-to-end, but a single
> Claude 3.5 Sonnet call sits in the loop instead of a
> deterministic transformer. Here's the live transcript from
> recording day: the diagnostic, the prompt, the model's
> response, the fix verified by `aether check`.
>
> Twenty-one end-to-end gate suites green from a fresh clone. The
> agent SDK, the LSP — diagnostics, hover, completion, go-to-
> definition — the architectural-integrity benchmark, the multi-
> file resolver, the fix-loop protocol — all reproducible by anyone.
> We're building the substrate AI-generated production code is going
> to need. I'm `[FOUNDER NAME]`. Aether.

(Word count: ~350. At normal cadence that's 90–94 seconds.)

---

## What happens if recording fails on the day

Three contingencies, in increasing severity:

1. **A command produces unexpected output.** Stop the take. Re-run
   the same command from a fresh terminal. If the unexpected output
   is real (something regressed since the last `scripts/run_all.py`),
   abort the recording, fix the regression, run the gate again, then
   restart from clip 1.
2. **`live-fix` produces a fix that doesn't pass `aether check`.**
   This means Claude 3.5 Sonnet's response failed the auto-verify
   step in `llm_fix_demo.py`. Re-run `live-fix` 2–3 times; non-
   determinism normally resolves in two tries. If it doesn't,
   record the demo using the placeholder transcript (still flagged
   `"_meta.source": "deterministic-fallback"`); ship the video with
   a brief on-screen acknowledgment that the live transcript is
   regenerable. Less impressive but honest.
3. **You stumble on the voiceover.** Re-record. The audio is the
   load-bearing element of every clip; a clean voiceover over a
   slightly imperfect terminal scroll is fine, the reverse isn't.

The 90-second video is the highest-leverage artifact in the whole
application. Do not ship a sloppy take. A weak video is worse than
a delayed video.
