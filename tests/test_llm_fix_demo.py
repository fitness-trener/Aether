"""H.A.2 regression tests for the LLM fix demo.

Three contracts:
  1. The replay subcommand exits 0 (transcript present + fix passes).
  2. The committed transcript's `_meta.source` is one of the documented
     values, and its `fixed_source` is structurally a valid Aether
     program that passes every default-on pass.
  3. The Layer-2 positive control gracefully skips with exit 2 when
     no ANTHROPIC_API_KEY is set in the environment.

These tests deliberately do NOT call the Anthropic API. The live-fix
and live-positive-control subcommands are exercised by a developer
with a real API key — never by CI.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether import sdk  # noqa: E402

DEMO = os.path.join(ROOT, "demos", "payment_workflow", "llm_fix_demo.py")
TRANSCRIPT = os.path.join(ROOT, "demos", "payment_workflow",
                          "llm_fix_demo.transcript.json")


def _run(*args, env=None):
    base_env = {k: v for k, v in os.environ.items()
                if k != "ANTHROPIC_API_KEY"}
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, "-B", DEMO, *args],
        cwd=ROOT, capture_output=True, text=True, env=base_env,
    )


def test_replay_exits_0():
    r = _run("replay")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "replay E0304" in r.stdout, r.stdout
    print("H.A.2 replay: exit 0 with E0304 replay confirmation")


def test_transcript_schema_and_fix_validity():
    assert os.path.isfile(TRANSCRIPT), TRANSCRIPT
    with open(TRANSCRIPT) as f:
        tr = json.load(f)
    meta = tr["_meta"]
    # Source must be either the placeholder marker or a live timestamp.
    src = meta["source"]
    assert src == "deterministic-fallback" or src.startswith("live-anthropic-"), \
        f"unexpected _meta.source: {src!r}"
    assert meta["target_code"] == "E0304", meta
    assert meta["model"] == "claude-3-5-sonnet-latest", meta
    # The saved fix must pass aether check.
    r = sdk.check(tr["fixed_source"], filename="<transcript-test>")
    assert r.ok, [d.code for d in r.diagnostics]
    # And it must actually run + produce something sensible.
    rr = sdk.run(tr["fixed_source"], filename="<transcript-test>")
    assert rr.ok, (rr.stdout, rr.stderr)
    print(f"H.A.2 transcript: schema valid, _meta.source={src!r}, "
          f"fixed source passes check + run")


def test_layer2_positive_control_skips_without_key():
    """Without ANTHROPIC_API_KEY the positive control must NOT crash and
    must NOT silently pass. It exits 2 with a `[skip]` message — the
    test runner reads exit 2 as "intentionally not exercised."""
    r = _run("live-positive-control")
    # Exit 2 means "skipped because no API key" — that's the contract.
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "skip" in (r.stdout + r.stderr).lower(), (r.stdout, r.stderr)
    assert "ANTHROPIC_API_KEY" in (r.stdout + r.stderr), (r.stdout, r.stderr)
    print("H.A.2 live-positive-control: cleanly skips with exit 2 + reason")


if __name__ == "__main__":
    test_replay_exits_0()
    test_transcript_schema_and_fix_validity()
    test_layer2_positive_control_skips_without_key()
    print("H.A.2 ALL LLM FIX DEMO TESTS PASS")
