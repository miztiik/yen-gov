"""Two-tier validator for yen-gov schemas and data files (CLAUDE.md §11).

Tier A — schema sanity:
  * Each *.schema.json under datasets/schemas/ validates against the
    JSON Schema 2020-12 meta-schema.
  * x-version is "<major>.<minor>".
  * x-changelog is non-empty; every entry has version/date/description;
    the tail entry's version equals x-version.

Tier B — data conformance:
  * Every *.json file under datasets/ (excluding schemas/) and config/
    declares "$schema" and "$schema_version".
  * "$schema" resolves to a known schema by basename or by $id.
  * "$schema_version" equals the schema's current x-version.
  * The file validates against that schema.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

SCHEMAS_SUBDIR = Path("datasets/schemas")
DATA_ROOTS = (Path("datasets"), Path("config"))

# Path segments under DATA_ROOTS whose entire subtree is exempt from
# Tier-B conformance. Today only `_test/` (shared cross-language test
# fixtures). Adding to this set is a doctrine decision -- see
# `_iter_data_files` and docs/architecture/backend/validator.md.
_EXCLUDED_PATH_SEGMENTS: frozenset[str] = frozenset({"_test"})
VERSION_RE = re.compile(r"\d+\.\d+")


@dataclass(frozen=True)
class Failure:
    file: str   # POSIX-relative to repo root
    tier: str   # "A" or "B"
    message: str


def _posix(p: Path, root: Path) -> str:
    return PurePosixPath(p.resolve().relative_to(root.resolve())).as_posix()


def _load_json(p: Path) -> object:
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_schemas(schemas_dir: Path) -> tuple[dict[str, dict], list[Failure]]:
    """Map basename -> parsed schema; collect any JSON parse failures as Tier A issues."""
    schemas: dict[str, dict] = {}
    failures: list[Failure] = []
    for p in sorted(schemas_dir.glob("*.schema.json")):
        try:
            schemas[p.name] = _load_json(p)
        except json.JSONDecodeError as e:
            failures.append(
                Failure(f"datasets/schemas/{p.name}", "A", f"invalid JSON: {e.msg} (line {e.lineno})")
            )
    return schemas, failures


def tier_a(schemas: dict[str, dict]) -> list[Failure]:
    """Validate every schema against the meta-schema and yen-gov invariants."""
    failures: list[Failure] = []
    for name, s in schemas.items():
        rel = f"datasets/schemas/{name}"

        try:
            Draft202012Validator.check_schema(s)
        except SchemaError as e:
            failures.append(Failure(rel, "A", f"meta-schema: {e.message}"))
            continue

        v = s.get("x-version")
        if not isinstance(v, str) or not VERSION_RE.fullmatch(v):
            failures.append(Failure(rel, "A", f"x-version must match major.minor, got {v!r}"))
            v = None

        cl = s.get("x-changelog")
        if not isinstance(cl, list) or not cl:
            failures.append(Failure(rel, "A", "x-changelog missing or empty"))
            continue

        for i, entry in enumerate(cl):
            if not isinstance(entry, dict):
                failures.append(Failure(rel, "A", f"x-changelog[{i}] must be an object"))
                continue
            for key in ("version", "date", "description"):
                if key not in entry:
                    failures.append(Failure(rel, "A", f"x-changelog[{i}] missing '{key}'"))

        if v is not None and isinstance(cl[-1], dict) and cl[-1].get("version") != v:
            failures.append(
                Failure(rel, "A", f"x-changelog tail version {cl[-1].get('version')!r} != x-version {v!r}")
            )

    return failures


def _resolve_schema(schema_url: str, schemas: dict[str, dict]) -> tuple[str, dict] | None:
    """Find the local schema referenced by a data file's '$schema' URL.

    Match priority: exact `$id` first, then exact basename match. We deliberately
    do NOT use `endswith` — it falsely matches `constituency.schema.json` against
    `.../result.constituency.schema.json`, picking the wrong schema.
    """
    for name, s in schemas.items():
        if s.get("$id") == schema_url:
            return name, s
    tail = schema_url.rsplit("/", 1)[-1]
    if tail in schemas:
        return tail, schemas[tail]
    return None


def _iter_data_files(root: Path) -> Iterable[Path]:
    for base in DATA_ROOTS:
        d = root / base
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.json")):
            if p.name.endswith(".schema.json"):
                continue
            # Skip the shared cross-language test-fixture subtree
            # (datasets/_test/...). These files back unit tests that
            # consume them via plain JSON loads (e.g. the
            # `derive_temporal_range` parity fixtures consumed by both
            # pytest and vitest); they are NOT citizen-facing artifacts
            # and intentionally carry no `$schema`. Match the literal
            # `_test` segment -- not any leading-underscore segment --
            # so future stray underscore-prefixed dirs (e.g. accidental
            # `_scratch/`) keep failing Tier B loudly. Per Fowler
            # review 2026-05-17.
            if any(part in _EXCLUDED_PATH_SEGMENTS for part in p.relative_to(d).parts[:-1]):
                continue
            yield p


def tier_b(schemas: dict[str, dict], root: Path) -> list[Failure]:
    """Validate every data file against its declared schema."""
    failures: list[Failure] = []
    for p in _iter_data_files(root):
        rel = _posix(p, root)
        try:
            data = _load_json(p)
        except json.JSONDecodeError as e:
            failures.append(Failure(rel, "B", f"invalid JSON: {e.msg} (line {e.lineno})"))
            continue

        if not isinstance(data, dict):
            failures.append(Failure(rel, "B", "top-level must be a JSON object"))
            continue

        schema_url = data.get("$schema")
        if not isinstance(schema_url, str) or not schema_url:
            failures.append(Failure(rel, "B", "missing or empty '$schema' field"))
            continue

        resolved = _resolve_schema(schema_url, schemas)
        if resolved is None:
            failures.append(Failure(rel, "B", f"unknown schema {schema_url!r}"))
            continue
        _, schema = resolved

        declared = data.get("$schema_version")
        current = schema.get("x-version")
        if declared != current:
            failures.append(
                Failure(rel, "B", f"$schema_version {declared!r} != schema x-version {current!r}")
            )
            continue

        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        for err in errors:
            path = "/".join(str(x) for x in err.absolute_path) or "(root)"
            failures.append(Failure(rel, "B", f"{path}: {err.message}"))

    return failures


def run(root: Path) -> list[Failure]:
    """Run Tier A then Tier B against a repo root."""
    schemas, parse_failures = load_schemas(root / SCHEMAS_SUBDIR)
    return parse_failures + tier_a(schemas) + tier_b(schemas, root)
