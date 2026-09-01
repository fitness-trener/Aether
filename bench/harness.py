"""Benchmark harness for Aether.

Each task lives in `bench/tasks/<task_id>/` with these files:

    prompt.md         The user-facing instruction the model receives.
    grader.json       JSON object with grading config — see TASK_SCHEMA.
    reference.aeth    A reference solution, used to verify the grader works.

A run is invoked as:

    python -m bench.harness run-task <task_id> --candidate <path-to-.aeth>

It compiles the candidate, executes with stdin from `grader.json.stdin`,
captures stdout/stderr/exit_code, and compares against the grader.

Output is structured JSON the agent can consume:

    {
      "task_id": "...",
      "candidate": "...",
      "stage": "parse|emit|exec|grade",
      "ok": true|false,
      "diagnostic": null | {...},
      "expected": "...",
      "actual": "...",
      "stderr": "...",
      "exit_code": int,
      "elapsed_ms": ...
    }

Wedge-grading mode:
  When `expected_exit_code` or `expected_stderr_pattern` is present in
  grader.json, the harness checks those in addition to expected_stdout.
  This is for "contract-wedge" tasks where the desired outcome is a
  structured failure (Aether catches with E0301/E0302/...) rather than
  a successful stdout output.
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

# transpiler must be importable
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))



TASK_SCHEMA = {
    "expected_stdout": "str — exact stdout the candidate must produce",
    "stdin": "str | None — optional stdin input fed to the program",
    "timeout_ms": "int — wall-clock timeout (default 5000)",
    "expected_exit_code": "int | None — wedge-grading: required exit code",
    "expected_stderr_pattern": "str | None — wedge-grading: regex match on stderr",
    "tags": "list[str] — categorisation",
    "difficulty": "easy|medium|hard",
}


# ----------------------------------------------------------------------
# Compile + run a candidate program
# ----------------------------------------------------------------------

# The implementation lives in the package (`aether/runner.py`), not here.
# `aether.sdk.run`/`grade` need it too, and `bench/` is excluded from the
# wheel by `[tool.setuptools.packages.find]` — so while it lived only here,
# the SDK raised ModuleNotFoundError in every installed copy and reported it
# as the candidate failing (BUGS.md BUG-008). Re-exported under the original
# names so every `from bench.harness import compile_and_run` still works.
from aether.runner import (compile_and_run,                   # noqa: E402,F401
                           format_diag_as_stderr as _format_diag_as_stderr,
                           TIMEOUT_ENFORCED)


# ----------------------------------------------------------------------
# Task loading + grading
# ----------------------------------------------------------------------

def load_task(task_id: str) -> Dict[str, Any]:
    base = os.path.join(HERE, "tasks", task_id)
    if not os.path.isdir(base):
        raise FileNotFoundError(f"task not found: {task_id}")
    with open(os.path.join(base, "grader.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(os.path.join(base, "prompt.md"), "r", encoding="utf-8") as f:
        prompt = f.read()
    return {"id": task_id, "config": cfg, "prompt": prompt, "dir": base}


def grade_task(task: Dict[str, Any], candidate_path: str) -> Dict[str, Any]:
    if not os.path.isfile(candidate_path):
        return {"task_id": task["id"], "candidate": candidate_path,
                "ok": False, "stage": "missing",
                "diagnostic": {"message": "candidate file not found"}}
    with open(candidate_path, "r", encoding="utf-8") as f:
        src = f.read()
    cfg = task["config"]
    result = compile_and_run(
        src,
        candidate_path,
        stdin_text=cfg.get("stdin", "") or "",
        timeout_ms=int(cfg.get("timeout_ms", 5000)),
    )
    out = {"task_id": task["id"], "candidate": candidate_path}
    out.update(result)

    expected_stdout = cfg.get("expected_stdout", "")
    expected_exit_code = cfg.get("expected_exit_code")
    expected_stderr_pattern = cfg.get("expected_stderr_pattern")

    actual_stdout = result.get("actual", "")
    actual_stderr = result.get("stderr", "")
    actual_exit_code = result.get("exit_code", 0 if result.get("ok") else 1)

    stdout_ok = (actual_stdout == expected_stdout)
    exit_ok = (expected_exit_code is None) or (actual_exit_code == expected_exit_code)
    stderr_ok = True
    if expected_stderr_pattern:
        stderr_ok = bool(re.search(expected_stderr_pattern, actual_stderr))

    wedge_mode = (expected_exit_code is not None) or (expected_stderr_pattern is not None)
    if wedge_mode:
        match = stdout_ok and exit_ok and stderr_ok
    else:
        match = stdout_ok

    out["expected"] = expected_stdout
    out["match"] = match
    out["ok"] = match
    out["wedge_mode"] = wedge_mode
    out["checks"] = {
        "stdout_ok": stdout_ok,
        "exit_code_ok": exit_ok,
        "stderr_pattern_ok": stderr_ok,
        "expected_exit_code": expected_exit_code,
        "expected_stderr_pattern": expected_stderr_pattern,
        "actual_exit_code": actual_exit_code,
    }
    return out


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def cmd_list_tasks(args) -> int:
    base = os.path.join(HERE, "tasks")
    if not os.path.isdir(base):
        print("[]")
        return 0
    out = []
    for tid in sorted(os.listdir(base)):
        td = os.path.join(base, tid)
        if not os.path.isdir(td):
            continue
        try:
            with open(os.path.join(td, "grader.json")) as f:
                cfg = json.load(f)
            out.append({"id": tid,
                        "tags": cfg.get("tags", []),
                        "difficulty": cfg.get("difficulty", ""),
                        "wedge": (cfg.get("expected_exit_code") is not None)
                                 or (cfg.get("expected_stderr_pattern") is not None)})
        except Exception:
            continue
    print(json.dumps(out, indent=2))
    return 0


def cmd_show_prompt(args) -> int:
    task = load_task(args.task_id)
    print(task["prompt"])
    return 0


def cmd_run_task(args) -> int:
    task = load_task(args.task_id)
    out = grade_task(task, args.candidate)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def cmd_run_reference(args) -> int:
    base = os.path.join(HERE, "tasks")
    summary = []
    for tid in sorted(os.listdir(base)):
        td = os.path.join(base, tid)
        if not os.path.isdir(td):
            continue
        ref = os.path.join(td, "reference.aeth")
        if not os.path.isfile(ref):
            summary.append({"id": tid, "ok": False, "note": "no reference.aeth"})
            continue
        try:
            task = load_task(tid)
        except Exception as e:
            summary.append({"id": tid, "ok": False, "note": f"load: {e}"})
            continue
        out = grade_task(task, ref)
        summary.append({"id": tid, "ok": out.get("ok", False),
                        "stage": out.get("stage"),
                        "wedge_mode": out.get("wedge_mode", False),
                        "elapsed_ms": out.get("elapsed_ms")})
    print(json.dumps(summary, indent=2))
    n_ok = sum(1 for s in summary if s.get("ok"))
    print(f"# {n_ok}/{len(summary)} reference solutions pass", file=sys.stderr)
    return 0 if n_ok == len(summary) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="aether-bench")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("list-tasks", help="list available tasks")
    sp = sub.add_parser("show-prompt", help="print a task's prompt")
    sp.add_argument("task_id")
    sp = sub.add_parser("run-task", help="grade a candidate solution")
    sp.add_argument("task_id")
    sp.add_argument("--candidate", required=True)
    sp = sub.add_parser("run-reference",
                        help="run reference.aeth for every task; sanity check")
    args = p.parse_args(argv)
    if args.cmd == "list-tasks":      return cmd_list_tasks(args)
    if args.cmd == "show-prompt":     return cmd_show_prompt(args)
    if args.cmd == "run-task":        return cmd_run_task(args)
    if args.cmd == "run-reference":   return cmd_run_reference(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
