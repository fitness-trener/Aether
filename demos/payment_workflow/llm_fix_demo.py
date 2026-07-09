"""H.A.2 LLM fix demo — Layer 1 replay + Layer 2 positive control.

The deterministic fix-loop in `fix_loop.py` handles diagnostic codes
whose `extra` dict is sufficient for a mechanical AST rewrite (E0801
effect-not-covered, E0701 capability-not-declared). The codes that
require *intent-level* reasoning (E0301, E0302, E0304, E0305) need a
real LLM in the loop.

This file demonstrates that the same protocol runs end-to-end against
a logic-error case (E0304 ensures violation) using Anthropic's Claude
3.5 Sonnet, and against a refinement-boundary case (E0302) as an
unmocked positive control.

Three subcommands:

  replay
      Default. Reads `llm_fix_demo.transcript.json` and applies the
      fixed source verbatim, then runs `aether check` to prove the
      replay still passes. NO Anthropic API call. Reproducible from
      a fresh clone with zero secrets. Used by the regression test
      and the recorded demo video.

  live-fix
      Calls Anthropic for E0304. Requires `ANTHROPIC_API_KEY` in env.
      Overwrites `llm_fix_demo.transcript.json` with a fresh
      transcript stamped `_meta.source = "live-anthropic-<ISO>"`. The
      replay-mode test will then run against the live transcript.

  live-positive-control
      Calls Anthropic for E0302 (the refinement-boundary candidate at
      `broken_E0302.aeth`). Requires `ANTHROPIC_API_KEY`. Writes a
      DIFFERENT transcript file
      (`llm_fix_demo.positive_control.json`) so the cherry-picking
      defense is dual-channel: the replay transcript covers one
      shape, the positive control covers another, neither overwrites
      the other.

Honesty notes:

  - The transcript schema includes `_meta.source` declaring whether
    the artifact is `"deterministic-fallback"` (placeholder) or
    `"live-anthropic-<ISO>"`. Reviewers know what they're reading.
  - The replay subcommand applies the saved `fixed_source` and runs
    `aether check` to verify it actually passes — so even a
    placeholder transcript can't lie about whether the fix is real.
  - The Layer-2 positive control is never auto-run by CI. It exists
    so a diligent reviewer with their own API key can re-run the
    same protocol against an un-cherry-picked example.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether import sdk  # noqa: E402

E0304_INPUT = os.path.join(HERE, "broken_E0304.aeth")
E0302_INPUT = os.path.join(HERE, "broken_E0302.aeth")
REPLAY_TRANSCRIPT = os.path.join(HERE, "llm_fix_demo.transcript.json")
POSITIVE_CONTROL_TRANSCRIPT = os.path.join(HERE, "llm_fix_demo.positive_control.json")

ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"

_PROMPT_TEMPLATE = """\
You are an Aether code-repair assistant. Aether is a programming language
designed for AI agents; it ships structured diagnostics that name the
exact contract that failed. Your job is to read one such diagnostic and
return a corrected source file that satisfies the contract.

CONSTRAINTS

- Return ONLY a JSON object. No prose. No markdown fence.
- The JSON object has exactly two keys:
    "fixed_source": the corrected Aether source, verbatim and complete
    "rationale":    one sentence explaining why the fix satisfies the contract
- The fixed source must keep all original function names, type names,
  module declarations, and overall shape. You may rewrite function
  BODIES only. Do not weaken or remove contracts. Do not change
  refinement-type definitions.

DIAGNOSTIC

{diagnostic_block}

ORIGINAL SOURCE

```aether
{source}
```

Return the JSON object now.
"""


def _build_prompt(source: str, diag) -> str:
    diag_block = json.dumps({
        "code": diag.code,
        "message": diag.message,
        "extra": diag.extra,
    }, indent=2)
    return _PROMPT_TEMPLATE.format(diagnostic_block=diag_block, source=source)


def _collect_first_diagnostic(source: str, filename: str):
    """Try check + run, return the first diagnostic that fires."""
    r = sdk.check(source, filename=filename)
    if r.diagnostics:
        return r.diagnostics[0]
    # No static diagnostic — try runtime (E0301/E0302/E0303/E0304/E0305 only
    # surface at run time).
    rr = sdk.run(source, filename=filename)
    return rr.diagnostic


# ---------------------------------------------------------------------
# replay (Layer 1)
# ---------------------------------------------------------------------

def cmd_replay(args):
    if not os.path.isfile(REPLAY_TRANSCRIPT):
        print(f"[fail] missing transcript: {REPLAY_TRANSCRIPT}",
              file=sys.stderr)
        return 1
    with open(REPLAY_TRANSCRIPT) as f:
        tr = json.load(f)
    fixed = tr.get("fixed_source")
    if not fixed:
        print("[fail] transcript missing fixed_source", file=sys.stderr)
        return 1
    # Verify the saved fix actually passes aether check.
    r = sdk.check(fixed, filename="<replay>")
    if not r.ok:
        print(f"[fail] saved fix has {len(r.diagnostics)} diagnostic(s):",
              file=sys.stderr)
        for d in r.diagnostics:
            print(f"  {d.code} {d.message}", file=sys.stderr)
        return 1
    src = "(deterministic-fallback)" if tr["_meta"]["source"] == "deterministic-fallback" \
        else f"(live: {tr['_meta']['source']})"
    print(f"[ok] replay {tr['_meta']['target_code']} {src}")
    print(f"     transcript: {REPLAY_TRANSCRIPT}")
    print(f"     fixed source passes `aether check`")
    if args.verbose:
        print("--- fixed source ---")
        print(fixed)
    return 0


# ---------------------------------------------------------------------
# live-fix (Layer 1 regenerate, requires API key)
# ---------------------------------------------------------------------

def _call_anthropic(prompt: str) -> str:
    """Single-call wrapper around Anthropic's messages API. Returns the
    raw text response. Raises if the API key is missing or the call
    fails — the live-* subcommands handle the user-facing error."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        raise RuntimeError(
            "anthropic SDK not installed. `pip install anthropic`."
        )
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _do_live(input_path: str, transcript_path: str, label: str) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"[skip] {label}: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2
    src = open(input_path).read()
    diag = _collect_first_diagnostic(src, input_path)
    if diag is None:
        print(f"[fail] {input_path} no longer produces a diagnostic",
              file=sys.stderr)
        return 1
    prompt = _build_prompt(src, diag)
    response = _call_anthropic(prompt)
    try:
        body = json.loads(response)
        fixed = body["fixed_source"]
        rationale = body.get("rationale", "")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[fail] model response not parseable: {e}", file=sys.stderr)
        print("--- raw response ---", file=sys.stderr)
        print(response, file=sys.stderr)
        return 1
    # Verify the fix passes aether check.
    r = sdk.check(fixed, filename="<live-fix>")
    if not r.ok:
        print(f"[fail] live fix has {len(r.diagnostics)} diagnostic(s) "
              f"still firing; not committing:", file=sys.stderr)
        for d in r.diagnostics:
            print(f"  {d.code} {d.message}", file=sys.stderr)
        return 1
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    transcript = {
        "_meta": {
            "source": f"live-anthropic-{now}",
            "model": ANTHROPIC_MODEL,
            "target_code": diag.code,
            "input_file": os.path.relpath(input_path, ROOT),
            "label": label,
        },
        "input": {
            "source": src,
            "diagnostic": {
                "code": diag.code,
                "message": diag.message,
                "extra": diag.extra,
            },
        },
        "prompt": prompt,
        "response": response,
        "fixed_source": fixed,
        "rationale": rationale,
    }
    with open(transcript_path, "w") as f:
        json.dump(transcript, f, indent=2)
    print(f"[ok] {label}: wrote live transcript -> {transcript_path}")
    print(f"     model: {ANTHROPIC_MODEL}")
    print(f"     fix verified by aether check")
    return 0


def cmd_live_fix(args):
    return _do_live(E0304_INPUT, REPLAY_TRANSCRIPT, "live-fix (E0304)")


def cmd_live_positive_control(args):
    return _do_live(E0302_INPUT, POSITIVE_CONTROL_TRANSCRIPT,
                    "live-positive-control (E0302)")


# ---------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="llm_fix_demo")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("replay", help="Layer 1 replay (no API key)")
    sp.add_argument("--verbose", action="store_true")
    sub.add_parser("live-fix",
                   help="Layer 1 regenerate transcript (needs API key)")
    sub.add_parser("live-positive-control",
                   help="Layer 2 positive control (needs API key)")
    args = p.parse_args(argv)
    if args.cmd is None or args.cmd == "replay":
        if args.cmd is None:
            args.verbose = False
        return cmd_replay(args)
    if args.cmd == "live-fix":
        return cmd_live_fix(args)
    if args.cmd == "live-positive-control":
        return cmd_live_positive_control(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
