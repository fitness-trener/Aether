"""Aether differential capability PR check (Phase 0, P0.5).

OFFLINE, READ-ONLY, ADDITIVE. In Phase 0 this check NEVER blocks a PR — it only
computes the capability delta of a change-set and emits a comment + a JSON
artifact. Enforcement (allow/block) is Phase 1+; here we are building trust and
measuring, exactly as the gate discipline requires.

Inputs (pick one):
  --files BASE HEAD          two source files
  --git REPO BASE HEAD PATH  diff one file across two refs (read-only `git show`)
  --diff DIFF BASE HEAD      explicit unified diff + both sources

Outputs:
  - the human comment to stdout
  - --out FILE.json          write the machine-readable artifact (provenance)
  - --post {github,gitlab}   OPT-IN: post the comment as a PR/MR note. Requires
                             the platform env vars below. Without --post nothing
                             leaves the machine. Posting a comment never blocks.

Exit code is ALWAYS 0 in Phase 0 (additive). The verdict lives in the artifact
and comment, not the exit status, so CI cannot be configured to block on it yet.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from tools.cap_delta import capability_delta, render_comment        # noqa: E402
from tools.diff_ingest import changed_regions_from_git              # noqa: E402


def _post_github(comment: str) -> str:
    """Post a comment to a GitHub PR. Opt-in; needs GITHUB_TOKEN, GITHUB_REPO
    (owner/name), GITHUB_PR (number). Uses only the stdlib; never blocks."""
    import urllib.request
    tok = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    pr = os.environ.get("GITHUB_PR")
    if not (tok and repo and pr):
        return "skipped: set GITHUB_TOKEN, GITHUB_REPO, GITHUB_PR to enable posting"
    url = f"https://api.github.com/repos/{repo}/issues/{pr}/comments"
    data = json.dumps({"body": comment}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:        # noqa: S310 (https only)
        return f"posted: HTTP {r.status}"


def _post_gitlab(comment: str) -> str:
    """Post a note to a GitLab MR. Needs GITLAB_TOKEN, GITLAB_PROJECT (url-encoded
    id), GITLAB_MR (iid), optional GITLAB_HOST (default gitlab.com)."""
    import urllib.request, urllib.parse
    tok = os.environ.get("GITLAB_TOKEN")
    proj = os.environ.get("GITLAB_PROJECT")
    mr = os.environ.get("GITLAB_MR")
    host = os.environ.get("GITLAB_HOST", "gitlab.com")
    if not (tok and proj and mr):
        return "skipped: set GITLAB_TOKEN, GITLAB_PROJECT, GITLAB_MR to enable posting"
    url = f"https://{host}/api/v4/projects/{proj}/merge_requests/{mr}/notes"
    data = urllib.parse.urlencode({"body": comment}).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"PRIVATE-TOKEN": tok})
    with urllib.request.urlopen(req) as r:        # noqa: S310
        return f"posted: HTTP {r.status}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--files", nargs=2, metavar=("BASE", "HEAD"))
    g.add_argument("--git", nargs=4, metavar=("REPO", "BASE", "HEAD", "PATH"))
    g.add_argument("--diff", nargs=3, metavar=("DIFF", "BASE", "HEAD"))
    ap.add_argument("--out", help="write JSON artifact here")
    ap.add_argument("--post", choices=("github", "gitlab"))
    ap.add_argument("--json", action="store_true", help="print JSON instead of comment")
    a = ap.parse_args(argv)

    if a.files:
        base_src = open(a.files[0]).read(); head_src = open(a.files[1]).read()
        delta = capability_delta(base_src, head_src)
    elif a.git:
        repo, base, head, path = a.git
        cs = changed_regions_from_git(repo, base, head, path)
        import subprocess
        def show(ref):
            try:
                return subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"],
                                      capture_output=True, text=True, check=True).stdout
            except subprocess.CalledProcessError:
                return ""
        delta = capability_delta(show(base), show(head))
    else:
        diff_src = open(a.diff[0]).read()
        base_src = open(a.diff[1]).read(); head_src = open(a.diff[2]).read()
        delta = capability_delta(base_src, head_src, unified_diff=diff_src)

    comment = render_comment(delta)
    print(json.dumps(delta, indent=2) if a.json else comment)

    if a.out:
        with open(a.out, "w") as fh:
            json.dump(delta, fh, indent=2)

    if a.post:
        result = _post_github(comment) if a.post == "github" else _post_gitlab(comment)
        print(f"\n[post:{a.post}] {result}", file=sys.stderr)

    # Phase 0 is additive: ALWAYS exit 0. The verdict is informational only.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
