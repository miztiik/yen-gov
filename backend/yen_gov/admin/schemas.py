"""Schemas endpoint — Tier-A schema health + Tier-B data conformance.

Reuses :mod:`yen_gov.validate` so the admin panel never disagrees with
CI: the validator that gates `main` is the same code surfaced here.

Shape (per schema):

* ``id`` — schema basename (``result.summary.schema.json``).
* ``title``, ``x_version``, ``last_changelog_entry``.
* ``meta_ok`` — passed Tier A (meta-schema + version invariants).
* ``data_files`` — count of `*.json` files declaring this schema.
* ``data_failures`` — Tier B failures whose file targets this schema.

Plus a top-level ``orphan_failures`` list for Tier-B failures that
couldn't be attributed to a schema (missing ``$schema``, unknown URL,
wrong ``$schema_version``).

Path convention: POSIX-relative to repo root, per CLAUDE.md §2.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ..validate import (
    SCHEMAS_SUBDIR,
    Failure,
    load_schemas,
    tier_a,
    tier_b,
)

router = APIRouter()

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


def _repo_root() -> Path:
    """Repo root for validation walks.

    Honours the ``YEN_GOV_REPO_ROOT`` env var so tests can point the
    endpoint at a controlled fixture corpus instead of walking the real
    ``datasets/**`` tree (which is the slow path we descoped from
    pytest; see docs/architecture/backend/validator.md).
    """
    override = os.environ.get("YEN_GOV_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return _DEFAULT_REPO_ROOT


def _classify_b_failure(msg: str, file_path: str, schema_files: list[str], repo_root: Path) -> str | None:
    """Best-effort attribution of a Tier-B failure to a schema basename.

    The validator records the failure against a *file*, not a schema. We
    re-derive the schema by reading the file's ``$schema`` field (cheap;
    ~hundreds of files at worst). Failures with no resolvable schema
    (missing field, unknown URL, version mismatch) return None and end
    up in the orphan bucket.
    """
    try:
        with (repo_root / file_path).open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    url = data.get("$schema")
    if not isinstance(url, str):
        return None
    tail = url.rsplit("/", 1)[-1]
    return tail if tail in schema_files else None


@router.get("/schemas")
def schemas() -> dict[str, Any]:
    repo_root = _repo_root()
    schemas_dict, parse_failures = load_schemas(repo_root / SCHEMAS_SUBDIR)
    a_failures = tier_a(schemas_dict)
    b_failures = tier_b(schemas_dict, repo_root)

    # Index Tier-A failures by schema basename so a per-schema panel can
    # surface them without grepping the global list.
    a_by_schema: dict[str, list[dict[str, str]]] = defaultdict(list)
    for f in parse_failures + a_failures:
        # f.file is e.g. "datasets/schemas/result.summary.schema.json"
        basename = f.file.rsplit("/", 1)[-1]
        a_by_schema[basename].append({"file": f.file, "message": f.message})

    # Index Tier-B failures by file (one file = many failures), then group
    # by attributed schema.
    b_by_file: dict[str, list[Failure]] = defaultdict(list)
    for f in b_failures:
        b_by_file[f.file].append(f)

    schema_files = list(schemas_dict.keys())
    b_by_schema: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"failing_files": 0, "examples": []}
    )
    orphans: list[dict[str, str]] = []
    for file_path, errs in b_by_file.items():
        schema_id = _classify_b_failure(errs[0].message, file_path, schema_files, repo_root)
        if schema_id is None:
            for e in errs[:3]:
                orphans.append({"file": file_path, "message": e.message})
            continue
        bucket = b_by_schema[schema_id]
        bucket["failing_files"] += 1
        if len(bucket["examples"]) < 5:
            bucket["examples"].append(
                {"file": file_path, "message": errs[0].message}
            )

    # Count data files claiming each schema (denominator for "% passing").
    data_counts: dict[str, int] = defaultdict(int)
    for p in (repo_root / "datasets").rglob("*.json"):
        if p.name.endswith(".schema.json"):
            continue
        try:
            with p.open(encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        url = doc.get("$schema")
        if not isinstance(url, str):
            continue
        tail = url.rsplit("/", 1)[-1]
        if tail in schemas_dict:
            data_counts[tail] += 1

    out: list[dict[str, Any]] = []
    for name, schema in sorted(schemas_dict.items()):
        a_errs = a_by_schema.get(name, [])
        b_bucket = b_by_schema.get(name, {"failing_files": 0, "examples": []})
        changelog = schema.get("x-changelog") or []
        last_entry = changelog[-1] if changelog else None
        out.append(
            {
                "id": name,
                "title": schema.get("title"),
                "x_version": schema.get("x-version"),
                "last_changelog": last_entry,
                "meta_ok": not a_errs,
                "meta_errors": a_errs,
                "data_files": data_counts.get(name, 0),
                "data_failing_files": b_bucket["failing_files"],
                "data_failures": b_bucket["examples"],
            }
        )

    return {
        "schemas": out,
        "orphan_failures": orphans[:50],  # cap so the response stays small
        "summary": {
            "total_schemas": len(out),
            "meta_failing": sum(1 for s in out if not s["meta_ok"]),
            "data_failing_files": sum(s["data_failing_files"] for s in out),
            "orphan_files": len({o["file"] for o in orphans}),
        },
    }
