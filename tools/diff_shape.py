"""Sound diff-shape classification (Real-World Mining, §C).

SOUNDNESS RULE (§C): do NOT invent a parallel classifier. Shape is derived from
the SAME ingestion that produces the verdict — we call `cap_delta.capability_delta`
once and read both the changed-region set and each region's verdict from its
output. A region's shape and its UNPROVABLE/INTRODUCES verdict are therefore always
consistent.

Per changed region we assign exactly one shape:
  ADD_NEW_FILE     — region lives in a newly-created file (delta = whole module).
  ADD_IN_EXISTING  — new function/region inserted into a pre-existing file.
  MODIFY_EXISTING  — edits inside a pre-existing function/region (or import-time
                     edits to a pre-existing module's top level).

And a capability-relevance flag: the region touches or might touch a capability
(it introduces a cap, or it is UNPROVABLE so a cap could be hiding). Pure,
fully-resolved regions are capability-IRRELEVANT and excluded from the rate
denominators — they are not where UNPROVABLE risk lives.

§C filtering (applied before counting):
  * Exclude vendored / generated / lockfile / binary / migration paths.
  * Bucket pure dependency-manifest changes separately (report, don't fold in).
  * Deletions never count as "introducing"; renames/moves are not adds.
  * The excluded fraction is reported explicitly.
"""
from __future__ import annotations
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from tools.cap_delta import capability_delta          # noqa: E402

ADD_NEW_FILE = "ADD_NEW_FILE"
ADD_IN_EXISTING = "ADD_IN_EXISTING"
MODIFY_EXISTING = "MODIFY_EXISTING"
MODULE_REGION = "<module-scope>"

# --- §C path filtering ------------------------------------------------------
_EXCLUDE_PATTERNS = [
    (re.compile(r"(^|/)(vendor|third_party|node_modules|\.venv|venv|dist|build)/"), "vendored"),
    (re.compile(r"(^|/)(migrations|alembic)/"), "migration"),
    (re.compile(r"\.(min\.js|map)$"), "generated_or_lock"),
    (re.compile(r"(^|/)(package-lock\.json|yarn\.lock|poetry\.lock|Pipfile\.lock|"
                r"go\.sum|Cargo\.lock|composer\.lock)$"), "lockfile"),
    (re.compile(r"(_pb2\.py|\.pb\.go|\.generated\.|\.g\.dart)$"), "generated"),
    (re.compile(r"\.(png|jpg|jpeg|gif|ico|pdf|zip|gz|tar|whl|so|dylib|dll|bin|woff2?)$"), "binary"),
]
_DEP_MANIFEST = re.compile(
    r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|setup\.py|setup\.cfg|"
    r"package\.json|go\.mod|Cargo\.toml|Gemfile|composer\.json)$")


def path_bucket(path: str) -> str:
    """Return 'analyze' | 'dependency_manifest' | <exclude_reason>."""
    for rx, reason in _EXCLUDE_PATTERNS:
        if rx.search(path):
            return reason
    if _DEP_MANIFEST.search(path):
        return "dependency_manifest"
    if not path.endswith(".py"):
        return "non_python"          # this engine is Python-only in Phase 0/1
    return "analyze"


@dataclass
class RegionRecord:
    path: str
    region: str
    shape: str
    capability_relevant: bool
    unprovable: bool                 # pure-residual (no caps) — reporting only
    has_residual: bool = False       # PER_PR_RESIDUAL primitive (presence-based)
    introduced_caps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class FileResult:
    path: str
    bucket: str                       # analyze | dependency_manifest | excluded reason
    regions: List[RegionRecord] = field(default_factory=list)
    note: str = ""


def classify_file_change(path: str, base_src: str, head_src: str,
                         file_status: str) -> FileResult:
    """file_status ∈ {added, modified, deleted, renamed}.
    base_src / head_src are the file contents at base/head ('' if absent)."""
    bucket = path_bucket(path)
    if file_status == "deleted":
        return FileResult(path, "deleted", note="deletion never introduces a capability")
    if file_status == "renamed" and base_src.strip() == head_src.strip():
        return FileResult(path, "rename_no_change", note="pure rename/move; not an add")
    if bucket != "analyze":
        return FileResult(path, bucket, note="excluded from rate counting per §C")

    file_is_new = (file_status == "added") or (not base_src.strip())
    delta = capability_delta(base_src, head_src)
    cs = delta.get("changeset", {})
    kind_by_name = {c["name"]: c["kind"] for c in cs.get("changed_functions", [])}

    regions: List[RegionRecord] = []
    for r in delta.get("regions", []):
        name = r["region"]
        unprov = bool(r.get("unprovable"))
        has_resid = bool(r.get("has_residual", unprov))   # presence of any residual
        head_caps = r.get("head_capabilities", [])
        introduced = r.get("newly_introduced", [])
        cap_relevant = has_resid or bool(head_caps)
        if name == MODULE_REGION:
            shape = ADD_NEW_FILE if file_is_new else MODIFY_EXISTING
        else:
            kind = kind_by_name.get(name, "modified")
            if file_is_new:
                shape = ADD_NEW_FILE
            elif kind == "added":
                shape = ADD_IN_EXISTING
            else:
                shape = MODIFY_EXISTING
        regions.append(RegionRecord(path, name, shape, cap_relevant, unprov,
                                    has_residual=has_resid, introduced_caps=introduced))
    return FileResult(path, "analyze", regions=regions)


def classify_changeset(files: List[Dict[str, str]]) -> Dict[str, Any]:
    """files: list of {path, base_src, head_src, status}. Returns the per-region
    records plus the §C bucket accounting (excluded fraction is reported)."""
    results = [classify_file_change(f["path"], f.get("base_src", ""),
                                    f.get("head_src", ""), f.get("status", "modified"))
               for f in files]
    all_regions: List[RegionRecord] = []
    buckets: Dict[str, int] = {}
    for fr in results:
        buckets[fr.bucket] = buckets.get(fr.bucket, 0) + 1
        all_regions.extend(fr.regions)
    cap_relevant = [r for r in all_regions if r.capability_relevant]
    return {
        "regions": [r.to_dict() for r in all_regions],
        "capability_relevant_regions": [r.to_dict() for r in cap_relevant],
        "file_buckets": buckets,
        "n_files": len(files),
        "n_files_analyzed": buckets.get("analyze", 0),
        "n_files_excluded": len(files) - buckets.get("analyze", 0),
    }
