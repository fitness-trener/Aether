"""The published GitHub Action stays wired to the CLI it drives.

`action.yml` is the Marketplace entry point: consumers pin it with `uses:`
and never read it. Every failure mode it has is silent —

  * a flag the CLI renamed becomes an "unrecognized arguments" exit that
    reads like a scan failure in someone else's repo;
  * a mistyped `${{ inputs.foo }}` is substituted with the EMPTY STRING by
    GitHub, so a scan quietly runs against the wrong path or with a gate
    turned off;
  * a caller-controlled input spliced into a `run:` block is a script
    injection — in a security scanner, which would be its own headline.

None of those is visible from the repo's own CI, because the action only
executes in a consumer's workflow. So they are asserted here instead.

Run: python -B tests/test_action.py   (exit 0 = pass)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTION = os.path.join(ROOT, "action.yml")


def _text() -> str:
    with open(ACTION, encoding="utf-8") as f:
        return f.read()


def _run_blocks(text: str) -> list:
    """Every `run: |` block body, by indentation. Enough of a YAML reader
    for this one question, and it keeps the repo stdlib-only."""
    blocks, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)run:\s*\|", line)
        if not m:
            continue
        indent = len(m.group(1))
        body = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent:
                break
            body.append(nxt)
        blocks.append("\n".join(body))
    return blocks


def test_action_file_exists_and_is_marketplace_shaped():
    text = _text()
    for key in ("name:", "description:", "branding:", "runs:", "inputs:"):
        assert key in text, f"action.yml is missing {key!r}"
    assert "using: 'composite'" in text or "using: composite" in text
    # Marketplace refuses a listing without both branding fields.
    assert re.search(r"branding:\s*\n\s*icon:", text), "branding.icon required"
    assert re.search(r"icon:.*\n\s*color:", text), "branding.color required"
    print("action: present and Marketplace-shaped")


def test_no_caller_input_is_spliced_into_a_shell_script():
    """`${{ inputs.X }}` inside a `run:` block is a script-injection sink:
    the value is pasted into the script before bash sees it, so a crafted
    input executes. Inputs must reach the shell through `env:` instead."""
    for block in _run_blocks(_text()):
        hits = re.findall(r"\$\{\{\s*inputs\.[\w-]+", block)
        assert not hits, (
            f"caller input spliced into a run: block — pass it via env: "
            f"instead: {hits}")
    print("action: no caller input is spliced into a shell script")


def test_every_input_is_declared_and_used():
    text = _text()
    # The `inputs:` block only, bounded by the next top-level key —
    # `outputs:` declares names the same way and must not be counted.
    body = re.split(r"^\w", text.split("inputs:", 1)[1], maxsplit=1,
                    flags=re.M)[0]
    declared = set(re.findall(r"^  ([a-z][\w-]*):$", body, re.M))
    assert declared, "no inputs parsed — the reader drifted from the file"
    # `if:` conditions reference an input WITHOUT the `${{ }}` wrapper, so
    # match the bare form too or a used input reads as dead.
    referenced = set(re.findall(r"\binputs\.([\w-]+)", text))
    undeclared = referenced - declared
    assert not undeclared, (
        f"referenced but not declared (GitHub substitutes the EMPTY STRING "
        f"for these, silently): {sorted(undeclared)}")
    unused = declared - referenced
    assert not unused, f"declared but never used: {sorted(unused)}"
    print(f"action: {len(declared)} inputs, all declared and all used")


def test_outputs_point_at_a_real_step():
    text = _text()
    step_ids = set(re.findall(r"^\s*id:\s*([\w-]+)\s*$", text, re.M))
    for ref in set(re.findall(r"\$\{\{\s*steps\.([\w-]+)\.", text)):
        assert ref in step_ids, \
            f"output/condition references step id {ref!r}, which does not exist"
    print("action: every steps.<id> reference names a real step")


def test_every_cli_flag_the_action_passes_still_exists():
    """The drift that matters. If `check-py` renames a flag, the action
    keeps passing the old one and every consumer's scan fails with an
    argparse error that looks like their problem."""
    help_text = subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", "check-py",
         "--help"], cwd=ROOT, capture_output=True, text=True).stdout
    known = set(re.findall(r"(--[\w-]+)", help_text))
    assert "--sarif" in known and "--strict" in known, \
        f"the CLI's own --help did not parse: {help_text!r}"
    used = set()
    for block in _run_blocks(_text()):
        for line in block.splitlines():
            if "check-py" not in line:
                continue
            used.update(re.findall(r"(--[\w-]+)", line))
    # `--strict` is appended into an array on its own line, so pick it up
    # wherever the script builds check-py flags.
    used.update(re.findall(r"flags\+=\((--[\w-]+)\)", _text()))
    assert used, "no check-py flags found in action.yml — the reader drifted"
    unknown = used - known
    assert not unknown, f"action.yml passes flags check-py does not accept: {sorted(unknown)}"
    print(f"action: all {len(used)} check-py flags it passes exist in the CLI")


def test_sarif_upload_permission_is_documented():
    """A composite action cannot grant itself `security-events: write`, so
    the caller must. Undocumented, this is a 403 on the upload step."""
    text = _text()
    assert "security-events: write" in text, \
        "the permission the caller must grant is not documented in action.yml"
    print("action: the required caller permission is documented")


if __name__ == "__main__":
    test_action_file_exists_and_is_marketplace_shaped()
    test_no_caller_input_is_spliced_into_a_shell_script()
    test_every_input_is_declared_and_used()
    test_outputs_point_at_a_real_step()
    test_every_cli_flag_the_action_passes_still_exists()
    test_sarif_upload_permission_is_documented()
    print("ACTION: all tests pass")
