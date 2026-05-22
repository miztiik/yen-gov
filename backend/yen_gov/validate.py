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
  * Legacy folded-indicator shards under datasets/indicators/in/ are
    pinned to the allowlist datasets/_ops/legacy-folded-indicator-shards.txt
    (CLAUDE.md §10 anti-pattern computationally enforced). New shards are
    rejected; allowlist entries with no on-disk file are reported as orphans.
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

# Legacy per-indicator JSON shard tree (CLAUDE.md §10 anti-pattern).
# The 110 shards under `datasets/indicators/in/<topic>/<id>.json` pre-date
# the canonical-long-format pivot (TODO/20260517 §0e.7 P.*). New shards
# are forbidden; existing shards retire family-by-family. The allowlist
# enumerates the legacy set; the Tier-B check
# `tier_b_legacy_folded_indicator_shards` enforces the doctrine. See
# docs/architecture/backend/validator.md and
# docs/architecture/canonical-pivot-deletion-manifest.md §6a.
LEGACY_INDICATOR_SHARDS_DIR = Path("datasets/indicators/in")
LEGACY_INDICATOR_SHARDS_ALLOWLIST = Path("datasets/_ops/legacy-folded-indicator-shards.txt")

# Path segments under DATA_ROOTS whose entire subtree is exempt from
# Tier-B conformance. Adding to this set is a doctrine decision -- see
# `_iter_data_files` and docs/architecture/backend/validator.md.
#
# Exemptions:
#   * `ephemeral` -- operator scratch directory (datasets/ephemeral/...).
#                    Whole subtree is gitignored (.gitignore = `*`); same
#                    rationale as `.runtime/` under CLAUDE.md §2. Holds
#                    raw XLSX/PDF dumps, restored legacy-corpus snapshots,
#                    and operator inventory sidecars (e.g. `_ingest_inventory.json`)
#                    that are NOT contract surfaces.
#
# Historical note: `_test` was previously exempt as a cross-language
# test-fixture subtree. T.1 (TODO/20260517 §0e.7) deleted that subtree;
# shared cross-language fixtures now live under `backend/tests/fixtures/`
# (Python-owned, single source of truth) and are pointed at by both
# pytest and vitest. Any future underscore-prefixed subtree under
# `datasets/` is NOT auto-exempt and MUST raise Tier-B loudly. The
# regression guard is `test_tier_b_does_not_silently_skip_unknown_underscore_dirs`.
_EXCLUDED_PATH_SEGMENTS: frozenset[str] = frozenset({"ephemeral"})
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
            # Skip exempt subtrees (see `_EXCLUDED_PATH_SEGMENTS`
            # docstring for rationale per entry). Match by literal segment --
            # not by underscore-prefix -- so any future stray dirs
            # (e.g. accidental `_scratch/`) keep failing Tier B loudly.
            # Per Fowler review 2026-05-17.
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


def _load_allowlist(path: Path) -> set[str]:
    """Parse a one-path-per-line allowlist text file. Ignores blank lines and `#` comments."""
    allowed: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        allowed.add(line)
    return allowed


def tier_b_legacy_folded_indicator_shards(root: Path) -> list[Failure]:
    """Forbid new per-indicator JSON shards under datasets/indicators/in/.

    Per CLAUDE.md §10 anti-pattern and Gregor's Phase-2 pre-flight audit
    (TODO/20260521-phase-2-preflight-audit-gregor.md finding #1), the 110
    legacy folded-indicator shards retire family-by-family per
    TODO/20260517 §0e.7 P.*. New content must land directly on the
    canonical Parquet store -- `datasets/<family>/<family>_<role>.parquet`
    + `datasets/taxonomy/indicators.parquet`. This Tier-B check makes the
    doctrine computationally enforced rather than purely textual.

    The allowlist `datasets/_ops/legacy-folded-indicator-shards.txt`
    enumerates the legacy set. When a P.* PR retires a family, that PR
    `git rm`s the family's shards AND removes the matching lines from the
    allowlist in the same Tier-A commit. When the final P.* family ships,
    the directory disappears, the allowlist file disappears, and this
    check disappears alongside `backend/yen_gov/legacy/folded_indicator_writer.py`.

    Two symmetric failure modes:
      1. Forbidden new shard: file on disk under `datasets/indicators/in/`
         but not listed in the allowlist.
      2. Orphan allowlist entry: path listed in the allowlist but not
         present on disk (allowlist out-of-sync with the legacy set).

    If `datasets/indicators/in/` does not exist (final P.* PR has shipped),
    the check is a no-op and the allowlist may be deleted.
    """
    failures: list[Failure] = []
    indicators_dir = root / LEGACY_INDICATOR_SHARDS_DIR
    allowlist_path = root / LEGACY_INDICATOR_SHARDS_ALLOWLIST
    allowlist_rel = LEGACY_INDICATOR_SHARDS_ALLOWLIST.as_posix()

    if not indicators_dir.exists():
        # Final P.* family has shipped; the legacy tree is gone. No-op.
        return failures

    if not allowlist_path.exists():
        failures.append(
            Failure(
                allowlist_rel,
                "B",
                "missing allowlist file while datasets/indicators/in/ still exists "
                "(required by tier_b_legacy_folded_indicator_shards; see "
                "docs/architecture/backend/validator.md)",
            )
        )
        return failures

    allowed = _load_allowlist(allowlist_path)
    on_disk: set[str] = {
        _posix(p, root)
        for p in indicators_dir.rglob("*.json")
        if not p.name.endswith(".schema.json")
    }

    for new_shard in sorted(on_disk - allowed):
        failures.append(
            Failure(
                new_shard,
                "B",
                "forbidden new indicator shard: per CLAUDE.md §10, new content must land "
                "on the canonical Parquet store (datasets/<family>/<family>_<role>.parquet "
                "+ datasets/taxonomy/indicators.parquet). To retire an existing family, "
                "remove its lines from datasets/_ops/legacy-folded-indicator-shards.txt "
                "in the same PR as the per-family P.* pivot.",
            )
        )

    for orphan in sorted(allowed - on_disk):
        failures.append(
            Failure(
                allowlist_rel,
                "B",
                f"orphan allowlist entry {orphan!r}: file no longer exists on disk. "
                f"Remove the line from {allowlist_rel}.",
            )
        )

    return failures


def run(root: Path) -> list[Failure]:
    """Run Tier A then Tier B against a repo root."""
    schemas, parse_failures = load_schemas(root / SCHEMAS_SUBDIR)
    return (
        parse_failures
        + tier_a(schemas)
        + tier_b(schemas, root)
        + tier_b_legacy_folded_indicator_shards(root)
    )
