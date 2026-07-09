"""GitHub /pulls/{n}/files enrichment -> population FILE-shape prior (Mining §A.1).

GH Archive gives counts, not paths. This step fetches the per-file `status`
(added/modified/removed/renamed) for a sample of candidate agent PRs and produces
the FILE-shape mix M0 — the directional prior. It runs NO engine and needs NO
labels.

IMPORTANT (honesty): this is a FILE-level shape prior (added file vs modified
file), NOT the region-level, capability-relevant mix that the gate metric uses
(that needs the engine on real code -> SWE-bench step). M0 brackets where to look.

Live mode needs GITHUB_TOKEN. Offline mode accepts a pre-fetched list of files
responses (list of {"pr": id, "files": [{path, status, additions, deletions}]}).
"""
from __future__ import annotations
import json
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from tools.diff_shape import path_bucket           # noqa: E402


def fetch_pr_files(repo: str, number: int, token: str) -> List[Dict[str, Any]]:
    """Live fetch (paginated). Only used when a token is present and network is
    available; the offline path below is what we test here."""
    import urllib.request
    out, page = [], 1
    while True:
        url = f"https://api.github.com/repos/{repo}/pulls/{number}/files?per_page=100&page={page}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req) as r:        # noqa: S310
            batch = json.loads(r.read())
        if not batch:
            break
        out.extend(batch); page += 1
        if len(batch) < 100:
            break
    return out


def shape_mix_from_files(pr_file_responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Classify each file by status+path into the FILE-shape prior + buckets."""
    counts = {"ADD_NEW_FILE": 0, "MODIFY_EXISTING": 0}
    buckets: Dict[str, int] = {}
    excluded_lines = 0
    analyzed_files = 0
    for resp in pr_file_responses:
        for f in resp.get("files", []):
            bucket = path_bucket(f["path"])
            buckets[bucket] = buckets.get(bucket, 0) + 1
            if bucket != "analyze":
                excluded_lines += f.get("additions", 0) + f.get("deletions", 0)
                continue
            analyzed_files += 1
            status = f.get("status", "modified")
            if status == "added":
                counts["ADD_NEW_FILE"] += 1
            elif status in ("removed",):
                pass                                  # deletions never introduce
            else:
                counts["MODIFY_EXISTING"] += 1
    total = counts["ADD_NEW_FILE"] + counts["MODIFY_EXISTING"]
    mix = {k: (round(v / total, 4) if total else None) for k, v in counts.items()}
    return {
        "file_shape_prior_M0": mix,
        "modify_share_M0": mix["MODIFY_EXISTING"],
        "file_buckets": buckets,
        "n_analyzed_files": analyzed_files,
        "excluded_dependency_and_vendored_lines": excluded_lines,
        "caveat": "FILE-level prior on PUBLIC MERGED agent PRs: biased optimistic for "
                  "modify; NOT region-level, NOT capability-relevant, NOT enterprise.",
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        data = json.load(open(sys.argv[1]))
        print(json.dumps(shape_mix_from_files(data), indent=2))
    else:
        print("usage: gh_enrich_files.py <prefetched_files.json>", file=sys.stderr)
        raise SystemExit(2)
