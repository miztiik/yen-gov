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
    * "$schema_version" is accepted by the json-corpus compatibility contract.
        Accepted same-major additive minors validate against the current schema
        unless a release entry chooses retained-schema validation; retained
        schema resolution is defined by datasets/schema-evolution.json.
  * The file validates against that schema.
  * Legacy folded-indicator shards under datasets/indicators/in/ are
    pinned to the allowlist datasets/_ops/meadow-shard-contract.txt
    (CLAUDE.md §10 anti-pattern computationally enforced). New shards are
    rejected; allowlist entries with no on-disk file are reported as orphans.
  * Energy installed-capacity shards under datasets/indicators/in/energy/
    matching `<state_>?installed_capacity_<X>_mw.json` are pinned to a
    closed enum of fuel + attribution-axis suffixes (the 5-bucket fuel
    axis per ADR-0030 D33.8 plus the on-disk aggregate / attribution
    variants). New sub-fuel breakouts (e.g. `installed_capacity_rooftop_solar_mw.json`,
    `installed_capacity_small_hydro_mw.json`) are rejected -- sub-fuel
    detail collapses at lift time per `backend/yen_gov/canonical/adapters/energy/_shared.py:SUB_FUEL_TO_CANONICAL`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from yen_gov.preflight import predicates as _P

SCHEMAS_SUBDIR = Path("datasets/schemas")
DATA_ROOTS = (Path("datasets"), Path("config"))
SCHEMA_COMPATIBILITY_PATH = Path("datasets/schema-compatibility.json")
JSON_CORPUS_SURFACE = "json-corpus"
CURRENT_SCHEMA_VALIDATION = "current_schema"

# Legacy per-indicator JSON shard tree (CLAUDE.md §10 anti-pattern).
# The 110 shards under `datasets/indicators/in/<topic>/<id>.json` pre-date
# the canonical-long-format pivot (TODO/20260517 §0e.7 P.*). New shards
# are forbidden; existing shards retire family-by-family. The allowlist
# enumerates the legacy set; the Tier-B check
# `tier_b_meadow_shard_contract` enforces the doctrine. See
# docs/architecture/backend/validator.md and
# docs/architecture/canonical-pivot-deletion-manifest.md §6a.
LEGACY_INDICATOR_SHARDS_DIR = Path("datasets/indicators/in")
LEGACY_INDICATOR_SHARDS_ALLOWLIST = Path("datasets/_ops/meadow-shard-contract.txt")

# Legacy boundary sidecar tree (CLAUDE.md §10 anti-pattern, ADR-0031
# Amendment 2026-05-22 -- T.0d boundaries consolidation). Pre-T.0d every
# `*.geojson` carried sibling `*.sources.json` / `*.metadata.json` /
# `*.unkeyed.json` and per-state `*-index.json` manifests. Provenance,
# simplification metadata, and shard inventory now live in
# `datasets/data/entities/boundary_layer.csv` (FK to
# `datasets/data/entities/source.csv`). New sidecars are forbidden; the
# allowlist exists only to permit short-lived temporary overrides during
# a follow-up PR (none today — file ships empty). The Tier-B check
# `tier_b_legacy_boundary_sidecars` enforces the doctrine.
LEGACY_BOUNDARY_SIDECARS_DIR = Path("datasets/boundaries")
LEGACY_BOUNDARY_SIDECARS_ALLOWLIST = Path("datasets/_ops/legacy-boundary-sidecars.txt")

# Indicator catalogue grain-prefix fence (PR-B1 2026-05-26 grain-over-entity
# rip per ADR-0044). The catalogue at `datasets/taxonomy/indicators.json`
# v2.0 carries entity_kinds + default_entity_kind on each row; the grain
# axis lives on the row, never in the indicator_id. `tier_b_indicator_id_no_grain_prefix`
# rejects any indicator_id matching `^(state|district|national)-` so future
# agents cannot re-encode grain on the id. SHIPS DARK in PR-B1 (function
# present but NOT chained into `run()`); ENFORCED post-PR-B9 once the existing
# 132 grain-prefixed rows have migrated under the per-PR `tools/migrate/path_b_*`
# scripts (now retired in the G6 tools/ prune 2026-06-08 after the
# per-family migrations landed). The 60-day Tier-B alias-window check
# (T.3 2026-05-22) was deleted in PR-B1 -- back-compat surface migrates
# to per-PR rename scripts.
INDICATOR_CATALOGUE_JSON = Path("datasets/taxonomy/indicators.json")
# Predicate body lives in yen_gov.preflight.predicates.grain_prefix_violation
# (ADR-0046 DRY extraction). Re-exported here for back-compat with callers
# that import the constant.
_INDICATOR_ID_GRAIN_PREFIX_RE = _P.GRAIN_PREFIX_RE

# Concept registry FK fence (PR-Z3b-tail3 2026-05-26 dark). Per guardrail #13
# every indicator MUST FK to a row in `datasets/taxonomy/concepts.json` declaring
# (noun, unit_canonical, normalisation, entity_kinds). Two indicators sharing the
# same `(concept_id, entity_kinds)` tuple is a proliferation bug -- UPSERT into the
# existing indicator or add a facet, never mint a new id. `tier_b_one_indicator_per_concept`
# enforces this. SHIPS DARK in PR-Z3b-tail3 (function present but NOT chained into
# `run()`); will enforce post-PR-Z3b-tail-actionC once the 183 existing indicators.json
# rows have been backfilled with `concept_id`.
CONCEPT_REGISTRY_JSON = Path("datasets/taxonomy/concepts.json")

# Energy installed-capacity sub-fuel fence (P.1.A C4.8 2026-05-24, Hans+Max
# Q3 verdict Option B per TODO/20260524-p1a-data-reacquisition-plan.md §5).
# Hans's D33.8 ruling locks the canonical fuel axis to five buckets:
# {coal, gas, hydro, nuclear, renewable}. Upstream publishers (ICED Capacity
# Metatable, MNRE Physical Progress) carry finer sub-fuel detail (small-hydro,
# bio-power, wind, utility-solar, rooftop-solar, waste-to-energy) which the
# C4 lift adapter collapses to the 5-bucket axis at emit time per
# `backend/yen_gov/canonical/adapters/energy/_shared.py:SUB_FUEL_TO_CANONICAL`
# (derivation=sum so the precision loss is auditable). The methodology break
# `energy-installed-capacity-5-bucket-fuel-axis-collapse` in
# `datasets/taxonomy/methodology_breaks.json` documents the rationale for
# the citizen.
#
# This Tier-B check makes the doctrine computationally enforced: any NEW
# JSON shard under `datasets/indicators/in/energy/` matching the
# `<state_>?installed_capacity_<X>_mw.json` shape with `<X>` outside the
# closed allowed-suffix set is rejected. Future sub-fuel shards
# (`installed_capacity_rooftop_solar_mw.json`,
# `installed_capacity_small_hydro_mw.json`,
# `installed_capacity_bio_power_mw.json` etc.) cannot regress the
# 5-bucket axis without an explicit doctrine amendment.
#
# The allowed suffix set covers the 5 fuels (Hans D33.8) plus the on-disk
# aggregate / attribution-axis variants currently in the corpus:
#   * Fuels: coal, gas, hydro, nuclear, renewable (also `thermal` -- the
#     pre-D33.8 coal+gas+oil composite, still on disk as a legacy total)
#   * Aggregate markers: total (publisher total, no fuel split),
#     by_source (rolled-up multi-fuel artifact)
#   * Attribution-axis variants: geographical (where the plant sits),
#     with_alloc (state's allocated share of central / joint-sector plants)
ENERGY_INDICATOR_DIR = Path("datasets/indicators/in/energy")
_INSTALLED_CAPACITY_FILE_RE = re.compile(
    r"^(?P<prefix>state_)?installed_capacity_(?P<suffix>[a-z][a-z0-9_]*)_mw\.json$"
)
_INSTALLED_CAPACITY_ALLOWED_SUFFIXES: frozenset[str] = frozenset(
    {
        # 5-bucket canonical fuels (Hans D33.8)
        "coal",
        "gas",
        "hydro",
        "nuclear",
        "renewable",
        # Pre-D33.8 composite fuel (legacy; still on disk as total composite)
        "thermal",
        # Aggregate markers
        "total",
        "by_source",
        # Attribution-axis variants (not fuels)
        "geographical",
        "with_alloc",
    }
)


# Meadow producer-shortname registry (ADR-0041 §nn4 + ADR-0042).
# Maps the `<source>` path segment used in `datasets/<family>/_meadow/
# <source>/<vintage>/*.json` to the full producer string carried on
# `datasets/taxonomy/sources.parquet`. The Tier-B rule
# `tier_b_meadow_vintage_matches_source_id` walks every meadow file and
# verifies that the (path-resolved producer, path vintage) pair exists
# as at least one row on the sources parquet -- i.e. that the meadow
# path tells the truth about the citation provenance.
#
# This rule was structurally unenforceable before ADR-0042 bumped the
# source schema to v3.0 (`vintage: minLength: 1`); multiple meadow
# files could legitimately share a `vintage=""` source row, defeating
# the path-vs-citation consistency check.
#
# Add a new producer here only when a new family lands a `_meadow/`
# subdirectory under a new publisher. Producer strings MUST match the
# `derive_source_id()` 3-arg hash input exactly (case-sensitive).
MEADOW_PRODUCER_REGISTRY: dict[str, str] = {
    "cea": "Central Electricity Authority",
    "iced": "NITI Aayog India Climate & Energy Dashboard",
    "rbi": "Reserve Bank of India",
    "ndlm": (
        "Department of Animal Husbandry & Dairying, "
        "Ministry of Fisheries, Animal Husbandry & Dairying, "
        "Government of India"
    ),
}


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


def _version_pair(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        return None
    major, minor = value.split(".", 1)
    return int(major), int(minor)


def _changelog_versions(schema: dict) -> set[str]:
    changelog = schema.get("x-changelog")
    if not isinstance(changelog, list):
        return set()
    versions: set[str] = set()
    for entry in changelog:
        if isinstance(entry, dict) and isinstance(entry.get("version"), str):
            versions.add(entry["version"])
    return versions


def _current_schema_can_validate_declared_version(schema: dict, version: str) -> bool:
    current = schema.get("x-version")
    current_pair = _version_pair(current)
    version_pair = _version_pair(version)
    if current_pair is None or version_pair is None:
        return False
    if version_pair[0] != current_pair[0] or version_pair[1] > current_pair[1]:
        return False
    return version in _changelog_versions(schema)


def _json_corpus_accepted_versions(root: Path, schemas: dict[str, dict]) -> dict[str, frozenset[str]]:
    accepted: dict[str, set[str]] = {}
    for name, schema in schemas.items():
        current = schema.get("x-version")
        accepted[name] = {current} if isinstance(current, str) and VERSION_RE.fullmatch(current) else set()

    registry_path = root / SCHEMA_COMPATIBILITY_PATH
    try:
        registry = _load_json(registry_path)
    except (OSError, json.JSONDecodeError):
        return {name: frozenset(versions) for name, versions in accepted.items()}
    if not isinstance(registry, dict):
        return {name: frozenset(versions) for name, versions in accepted.items()}

    overrides = registry.get("overrides")
    if not isinstance(overrides, list):
        return {name: frozenset(versions) for name, versions in accepted.items()}

    for override in overrides:
        if not isinstance(override, dict):
            continue
        if override.get("surface") != JSON_CORPUS_SURFACE:
            continue
        if override.get("validation") != CURRENT_SCHEMA_VALIDATION:
            continue
        schema_name = override.get("schema")
        if not isinstance(schema_name, str) or schema_name not in schemas:
            continue
        versions = override.get("accepted_versions")
        if not isinstance(versions, list):
            continue
        for version in versions:
            if isinstance(version, str) and _current_schema_can_validate_declared_version(
                schemas[schema_name], version
            ):
                accepted[schema_name].add(version)

    return {name: frozenset(versions) for name, versions in accepted.items()}


def _format_versions(versions: Iterable[str]) -> str:
    ordered = sorted(versions, key=lambda version: _version_pair(version) or (999999, 999999))
    return ", ".join(ordered) if ordered else "<none>"


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
    accepted_versions_by_schema = _json_corpus_accepted_versions(root, schemas)
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
        schema_name, schema = resolved

        declared = data.get("$schema_version")
        accepted_versions = accepted_versions_by_schema.get(schema_name, frozenset())
        if not isinstance(declared, str) or declared not in accepted_versions:
            failures.append(
                Failure(
                    rel,
                    "B",
                    f"$schema_version {declared!r} is not accepted for {schema_name}; "
                    f"accepted versions: {_format_versions(accepted_versions)}",
                )
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


def tier_b_meadow_shard_contract(root: Path) -> list[Failure]:
    """Forbid new per-indicator JSON shards under datasets/indicators/in/.

    Per CLAUDE.md §10 anti-pattern and Gregor's Phase-2 pre-flight audit
    (TODO/20260521-phase-2-preflight-audit-gregor.md finding #1), the 110
    legacy folded-indicator shards retire family-by-family per
    TODO/20260517 §0e.7 P.*. New content must land directly on the
    canonical Parquet store -- `datasets/<family>/<family>_<role>.parquet`
    + ``datasets/data/variables.csv``. This Tier-B check makes the
    doctrine computationally enforced rather than purely textual.

    The allowlist `datasets/_ops/meadow-shard-contract.txt`
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
                "(required by tier_b_meadow_shard_contract; see "
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
                "+ datasets/data/variables.csv). To retire an existing family, "
                "remove its lines from datasets/_ops/meadow-shard-contract.txt "
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


# Glob patterns that match the pre-T.0d boundary sidecar / index shapes.
# Any file under `datasets/boundaries/` matching one of these names is a
# legacy artifact and must be either deleted (the T.0d normal case) or
# allowlisted (only for short-lived overrides during a follow-up PR).
_LEGACY_BOUNDARY_SIDECAR_SUFFIXES: tuple[str, ...] = (
    ".sources.json",
    ".unkeyed.json",
    ".metadata.json",
)


def _is_legacy_boundary_sidecar(p: Path) -> bool:
    name = p.name
    if any(name.endswith(s) for s in _LEGACY_BOUNDARY_SIDECAR_SUFFIXES):
        return True
    # Per-state villages-index manifests: e.g. `S22-villages-index.json`.
    # Match the `<eci>-villages-index.json` family without false-positiving
    # the `boundary_layer.csv` ledger or future contract surfaces.
    if name.endswith("-index.json"):
        return True
    return False


def tier_b_legacy_boundary_sidecars(root: Path) -> list[Failure]:
    """Forbid pre-T.0d boundary sidecars and index manifests.

    Per ADR-0031 Amendment 2026-05-22 (T.0d boundaries consolidation) the
    per-shard sidecar files (`*.sources.json`, `*.metadata.json`,
    `*.unkeyed.json`) and the per-state villages-index manifests
    (`<eci>-villages-index.json`) were retired in favour of a single
    canonical ledger at `datasets/data/entities/boundary_layer.csv` (with
    `source_id` FK to `datasets/data/entities/source.csv`). The X1a-fu2-E
    rip (2026-06-07) replaced the prior parquet form of the ledger
    (`datasets/boundaries/boundary_layers.parquet`) with the long-format
    CSV per the platform-reset plan.

    Two symmetric failure modes (mirroring
    `tier_b_meadow_shard_contract`):
      1. Forbidden sidecar: file on disk under `datasets/boundaries/`
         matching a legacy pattern, not listed in the allowlist.
      2. Orphan allowlist entry: path listed in the allowlist but not
         present on disk.

    The allowlist file ships empty under normal operation. Re-introducing
    a sidecar requires either a doctrine amendment (delete this check) or
    an explicit short-lived allowlist entry called out in the PR body.

    If `datasets/boundaries/` does not exist, the check is a no-op.
    """
    failures: list[Failure] = []
    boundaries_dir = root / LEGACY_BOUNDARY_SIDECARS_DIR
    allowlist_path = root / LEGACY_BOUNDARY_SIDECARS_ALLOWLIST
    allowlist_rel = LEGACY_BOUNDARY_SIDECARS_ALLOWLIST.as_posix()

    if not boundaries_dir.exists():
        return failures

    if not allowlist_path.exists():
        failures.append(
            Failure(
                allowlist_rel,
                "B",
                "missing allowlist file while datasets/boundaries/ still exists "
                "(required by tier_b_legacy_boundary_sidecars; see "
                "docs/architecture/decisions/0031-boundary-geometry-strategy.md "
                "Amendment 2026-05-22).",
            )
        )
        return failures

    allowed = _load_allowlist(allowlist_path)
    on_disk: set[str] = {
        _posix(p, root)
        for p in boundaries_dir.rglob("*.json")
        if _is_legacy_boundary_sidecar(p)
    }

    for sidecar in sorted(on_disk - allowed):
        failures.append(
            Failure(
                sidecar,
                "B",
                "forbidden legacy boundary sidecar: per ADR-0031 Amendment "
                "2026-05-22 (T.0d), provenance + simplification metadata + "
                "shard inventory live in datasets/data/entities/boundary_layer.csv. "
                "Delete the sidecar (the normal case), or add the path to "
                "datasets/_ops/legacy-boundary-sidecars.txt for a short-lived "
                "override and explain in the PR body.",
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


def tier_b_indicator_id_no_grain_prefix(root: Path) -> list[Failure]:
    """Reject indicator_id values that encode the grain in the id prefix.

    Per ADR-0044 (PR-B1 grain-over-entity rip 2026-05-26) the canonical
    catalogue carries ``entity_kinds`` + ``default_entity_kind`` on each
    row. Grain dispatches at READ time from each observation row's
    ``entity_kind`` column; the indicator_id is ``<measure>-<unit>-<facet>``
    kebab-case only. Future agents must NOT re-encode grain on the id
    (e.g. ``state-installed-capacity-mw`` or ``district-pashu-aadhaar-count``).

    SHIPS DARK in PR-B1 (function present but NOT chained into ``run()``).
    Will be wired into ``run()`` in PR-B9 once the existing 132 grain-prefixed
    catalogue rows have migrated via the per-PR ``tools/migrate/path_b_*``
    scripts (PR-B2..B8; those scripts were retired in the G6 tools/ prune
    2026-06-08 after the per-family migrations landed). Until then,
    calling this function returns the backlog of grain-prefix violations
    for visibility -- useful in migration-PR acceptance gates.

    No-ops when ``datasets/taxonomy/indicators.json`` is absent or fails
    to parse.
    """
    failures: list[Failure] = []
    catalogue_path = root / INDICATOR_CATALOGUE_JSON
    catalogue_rel = INDICATOR_CATALOGUE_JSON.as_posix()

    if not catalogue_path.exists():
        return failures

    try:
        payload = _load_json(catalogue_path)
    except json.JSONDecodeError:
        return failures
    if not isinstance(payload, dict):
        return failures
    rows = payload.get("indicators")
    if not isinstance(rows, list):
        return failures

    for row in rows:
        if not isinstance(row, dict):
            continue
        indicator_id = row.get("indicator_id")
        if not isinstance(indicator_id, str):
            continue
        if _P.grain_prefix_violation(indicator_id) is not None:
            failures.append(
                Failure(
                    catalogue_rel,
                    "B",
                    f"indicators[indicator_id={indicator_id!r}]: indicator_id "
                    f"encodes a grain prefix (state-/district-/national-). "
                    f"Per ADR-0044 grain lives on the observation row's "
                    f"entity_kind column, not in the indicator_id. Drop the "
                    f"prefix; populate entity_kinds + default_entity_kind on "
                    f"the catalogue row instead. See docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md "
                    f"Phase B for the per-family migration scripts.",
                )
            )

    return failures


def tier_b_no_new_sub_fuel_shards(root: Path) -> list[Failure]:
    """Forbid new sub-fuel installed-capacity shards under datasets/indicators/in/energy/.

    Per ADR-0030 D33.8 (Hans's ruling) the canonical energy fuel axis is
    a closed 5-bucket enum {coal, gas, hydro, nuclear, renewable}. The
    C4 lift adapter collapses upstream sub-fuels (small-hydro, bio-power,
    wind, utility-solar, rooftop-solar, waste-to-energy) at emit time per
    `backend/yen_gov/canonical/adapters/energy/_shared.py:SUB_FUEL_TO_CANONICAL`
    with derivation=sum on the per-fuel observation rows so the precision
    loss is auditable. The companion methodology break
    `energy-installed-capacity-5-bucket-fuel-axis-collapse` in
    `datasets/taxonomy/methodology_breaks.json` documents the rationale
    for the citizen.

    This fence makes the doctrine computationally enforced: ANY new JSON
    shard under `datasets/indicators/in/energy/` matching the
    `<state_>?installed_capacity_<X>_mw.json` shape with `<X>` outside
    the closed allowed-suffix set (5 fuels + `thermal` legacy composite +
    `total`/`by_source` aggregate markers + `geographical`/`with_alloc`
    attribution-axis variants) is rejected. Future sub-fuel breakouts
    (`installed_capacity_rooftop_solar_mw.json`,
    `installed_capacity_small_hydro_mw.json`,
    `installed_capacity_bio_power_mw.json` etc.) cannot regress the
    5-bucket axis without an explicit doctrine amendment that updates
    this allowlist and rewrites the lift adapter.

    Scope-boxing: this check ONLY fences the
    `<state_>?installed_capacity_<X>_mw.json` filename family. Other
    energy-shard shapes (e.g. `state_rooftop_solar_capacity_mw.json`)
    fall under `tier_b_meadow_shard_contract` (any new file
    under `datasets/indicators/in/` must be in the legacy allowlist).
    Sub-fuel preservation as canonical citizen-surface indicators
    requires a Hans+Max doctrine amendment routed via CLAUDE.md §0a;
    see TODO/20260524-p1a-data-reacquisition-plan.md §5 Q3 for the
    rejected Option A.

    If `datasets/indicators/in/energy/` does not exist (the family has
    fully retired to canonical), the check is a no-op.
    """
    failures: list[Failure] = []
    energy_dir = root / ENERGY_INDICATOR_DIR

    if not energy_dir.exists():
        return failures

    for p in sorted(energy_dir.glob("*.json")):
        if p.name.endswith(".schema.json"):
            continue
        m = _INSTALLED_CAPACITY_FILE_RE.match(p.name)
        if m is None:
            continue
        suffix = m.group("suffix")
        if suffix in _INSTALLED_CAPACITY_ALLOWED_SUFFIXES:
            continue
        rel = _posix(p, root)
        allowed = ", ".join(sorted(_INSTALLED_CAPACITY_ALLOWED_SUFFIXES))
        failures.append(
            Failure(
                rel,
                "B",
                f"forbidden new sub-fuel installed-capacity shard: suffix "
                f"{suffix!r} is not in the closed allowed-suffix set "
                f"({allowed}). Per ADR-0030 D33.8 the canonical energy "
                f"fuel axis is the 5-bucket enum {{coal, gas, hydro, nuclear, "
                f"renewable}} and the C4 lift adapter collapses sub-fuels at "
                f"emit time (see backend/yen_gov/canonical/adapters/energy/"
                f"_shared.py:SUB_FUEL_TO_CANONICAL and the methodology break "
                f"'energy-installed-capacity-5-bucket-fuel-axis-collapse' in "
                f"datasets/taxonomy/methodology_breaks.json). Sub-fuel "
                f"preservation as a citizen-surface indicator requires a "
                f"Hans+Max doctrine amendment routed via CLAUDE.md §0a; see "
                f"TODO/20260524-p1a-data-reacquisition-plan.md §5 Q3 for the "
                f"rejected Option A and the Tier-B fence design decision.",
            )
        )

    return failures


def tier_b_meadow_vintage_matches_source_id(root: Path) -> list[Failure]:
    """ADR-0041 §nn4 + ADR-0042: meadow path vintage MUST match a source row.

    For every file under ``datasets/<family>/_meadow/<source>/<vintage>/*.json``:

    1. The path segment ``<source>`` MUST be a key in
       ``MEADOW_PRODUCER_REGISTRY`` (a known producer-shortname).
    2. There MUST exist at least one row in
       ``datasets/taxonomy/sources.parquet`` whose ``producer`` equals
       ``MEADOW_PRODUCER_REGISTRY[<source>]`` AND whose ``vintage`` equals
       the path's ``<vintage>`` segment (strict equality, no wildcards).

    Otherwise the meadow path lies about the source provenance. This
    check was structurally unenforceable before ADR-0042 bumped the
    source schema to v3.0 (``vintage: minLength: 1``); under v2.0
    multiple meadow files could legitimately share a ``vintage=""``
    source row, defeating the path-vs-citation consistency contract.

    Three symmetric failure modes:

    * Unknown source segment: the path uses a ``<source>`` shortname not
      registered in ``MEADOW_PRODUCER_REGISTRY``. Either add the mapping
      (when a new family lands a ``_meadow/`` subdirectory under a new
      publisher) or rename the directory to a registered shortname.
    * No matching citation row: the (registry-resolved producer, path
      vintage) pair has no corresponding row in
      ``datasets/taxonomy/sources.parquet``. Either rotate the meadow
      file to a vintage segment that matches an existing citation row,
      or add the citation row to the appropriate seed (e.g.
      ``backend/yen_gov/canonical/energy_sources_seed.py``) and re-run
      ``python -m yen_gov emit-taxonomy --root .``.
    * Missing sources catalogue: if any meadow file exists but
      ``datasets/taxonomy/sources.parquet`` is absent, every meadow file
      is reported (the operator must run ``emit-taxonomy`` first).

    If no ``_meadow/`` subdirectories exist anywhere under ``datasets/``,
    the check is a no-op.
    """
    failures: list[Failure] = []
    datasets_dir = root / "datasets"
    if not datasets_dir.exists():
        return failures

    # Walk every datasets/<family>/_meadow/<source>/<vintage>/*.json.
    meadow_files: list[tuple[Path, str, str]] = []  # (file, source_seg, vintage_seg)
    for family_dir in sorted(datasets_dir.iterdir()):
        if not family_dir.is_dir():
            continue
        meadow_dir = family_dir / "_meadow"
        if not meadow_dir.exists() or not meadow_dir.is_dir():
            continue
        for source_dir in sorted(meadow_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            for vintage_dir in sorted(source_dir.iterdir()):
                if not vintage_dir.is_dir():
                    continue
                for json_file in sorted(vintage_dir.glob("*.json")):
                    if json_file.name.endswith(".schema.json"):
                        continue
                    meadow_files.append(
                        (json_file, source_dir.name, vintage_dir.name)
                    )

    if not meadow_files:
        return failures

    sources_csv = root / "datasets" / "data" / "entities" / "source.csv"
    if not sources_csv.exists():
        for meadow_file, _, _ in meadow_files:
            failures.append(
                Failure(
                    _posix(meadow_file, root),
                    "B",
                    "meadow file present but datasets/data/entities/source.csv "
                    "is missing; run `python -m yen_gov emit-taxonomy --root .` "
                    "to regenerate the citation ledger so meadow paths can be "
                    "validated against it (ADR-0041 §nn4, ADR-0042). "
                    "Post-B3 (2026-06-06): the legacy sources.parquet was "
                    "retired in X1b (#814); the new SoT is source.csv.",
                )
            )
        return failures

    import duckdb

    con = duckdb.connect(":memory:")
    try:
        present_pairs: set[tuple[str, str]] = {
            (row[0], row[1])
            for row in con.execute(
                f"SELECT DISTINCT producer, vintage "
                f"FROM read_csv('{sources_csv.as_posix()}', "
                f"columns={{'source_id':'VARCHAR','producer':'VARCHAR','title':'VARCHAR',"
                f"'vintage':'VARCHAR','license':'VARCHAR','url_main':'VARCHAR'}}, "
                f"header=true, delim=',')"
            ).fetchall()
        }
    finally:
        con.close()

    registry_keys = ", ".join(sorted(MEADOW_PRODUCER_REGISTRY))
    for meadow_file, src_seg, vintage_seg in meadow_files:
        rel = _posix(meadow_file, root)
        producer = MEADOW_PRODUCER_REGISTRY.get(src_seg)
        if producer is None:
            failures.append(
                Failure(
                    rel,
                    "B",
                    f"unknown meadow source segment {src_seg!r}: expected one "
                    f"of {{{registry_keys}}}. Either rename the meadow "
                    f"directory to a registered shortname, or (when a new "
                    f"family lands a `_meadow/` subdirectory under a new "
                    f"publisher) add the producer-shortname mapping to "
                    f"MEADOW_PRODUCER_REGISTRY in backend/yen_gov/validate.py.",
                )
            )
            continue
        if (producer, vintage_seg) not in present_pairs:
            failures.append(
                Failure(
                    rel,
                    "B",
                    f"meadow path declares producer={producer!r} "
                    f"vintage={vintage_seg!r} but no row in "
                    f"datasets/data/entities/source.csv matches that "
                    f"(producer, vintage) pair. Per ADR-0041 §nn4 the meadow "
                    f"path vintage MUST equal a source vintage (ADR-0042 "
                    f"source schema v3.0 enforces vintage:minLength:1). "
                    f"Either (a) rotate the meadow file to a vintage segment "
                    f"that matches an existing citation row, or (b) add the "
                    f"citation row to the appropriate seed (e.g. "
                    f"backend/yen_gov/canonical/livestock_sources_seed.py) "
                    f"and re-emit source.csv via B2a's seed/source_csv "
                    f"pipeline.",
                )
            )

    return failures


def tier_b_indicator_freshness_declared(root: Path) -> list[Failure]:
    """Reject indicator catalogue rows missing a positive ``update_period_days``.

    Per ADR-0044 + docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md
    §0quat guardrail #18, every indicator MUST declare its publisher refresh
    cadence in days (NDLM monthly = 30, RBI Handbook annual = 365, Census
    decennial = 3650). Staleness can only be surfaced when cadence is named.
    OWID precedent: every Grapher variable carries this.

    SHIPS DARK in PR-Z3b-cli (function present but NOT chained into ``run()``).
    Will be wired into ``run()`` post-PR-Z3b-tail once the existing 183 catalogue
    rows have been backfilled with ``update_period_days``. Until then, calling
    this function returns the backlog of freshness-undeclared violations for
    visibility -- useful in handover-doc acceptance gates.

    No-ops when ``datasets/taxonomy/indicators.json`` is absent or fails to
    parse.
    """
    failures: list[Failure] = []
    catalogue_path = root / INDICATOR_CATALOGUE_JSON
    catalogue_rel = INDICATOR_CATALOGUE_JSON.as_posix()

    if not catalogue_path.exists():
        return failures

    try:
        payload = _load_json(catalogue_path)
    except json.JSONDecodeError:
        return failures
    if not isinstance(payload, dict):
        return failures
    rows = payload.get("indicators")
    if not isinstance(rows, list):
        return failures

    for row in rows:
        if not isinstance(row, dict):
            continue
        indicator_id = row.get("indicator_id")
        if not isinstance(indicator_id, str):
            continue
        cadence = row.get("update_period_days")
        if _P.update_period_days_violation(cadence) is not None:
            failures.append(
                Failure(
                    catalogue_rel,
                    "B",
                    f"indicators[indicator_id={indicator_id!r}]: "
                    f"missing or non-positive update_period_days "
                    f"(got {cadence!r}). Per guardrail #18 every "
                    f"indicator MUST declare the publisher refresh "
                    f"cadence in days as a positive integer (NDLM "
                    f"monthly = 30, RBI Handbook annual = 365, Census "
                    f"decennial = 3650). Staleness can only be surfaced "
                    f"when cadence is named. See ADR-0044 + "
                    f"docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md "
                    f"§0quat guardrail #18.",
                )
            )

    return failures


def tier_b_one_indicator_per_concept(root: Path) -> list[Failure]:
    """Reject indicator catalogue rows that proliferate within one concept.

    Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md
    §0quat guardrail #13, identity is what is MEASURED, not who published
    it. Each indicator FKs to a row in ``datasets/taxonomy/concepts.json``
    declaring ``(noun, unit_canonical, normalisation, entity_kinds)``. Two
    indicators sharing the same ``(concept_id, entity_kinds)`` tuple is a
    proliferation bug -- the right action is UPSERT into the existing
    indicator (new vintage / new publisher) or add a facet, never mint a
    new id. The 7 duplicate clusters surfaced by Z3a clustering (5×coal-MW,
    5×gas-MW, 4×hydro/nuclear/renewable-MW, 2×vote-share, 2×winning-party-id)
    are the oracle for this check.

    SHIPS DARK in PR-Z3b-tail3 (function present but NOT chained into ``run()``).
    Will be wired into ``run()`` post-PR-Z3b-tail-actionC once the existing
    183 catalogue rows have been backfilled with ``concept_id`` (schema v2.1).
    Until then the check no-ops cleanly on today's catalogue (no row carries
    ``concept_id`` yet).

    No-ops when ``datasets/taxonomy/indicators.json`` is absent or fails to
    parse.
    """
    failures: list[Failure] = []
    catalogue_path = root / INDICATOR_CATALOGUE_JSON
    catalogue_rel = INDICATOR_CATALOGUE_JSON.as_posix()

    if not catalogue_path.exists():
        return failures

    try:
        payload = _load_json(catalogue_path)
    except json.JSONDecodeError:
        return failures
    if not isinstance(payload, dict):
        return failures
    rows = payload.get("indicators")
    if not isinstance(rows, list):
        return failures

    # Group indicator_ids by (concept_id, sorted-entity_kinds tuple).
    # Rows without concept_id are skipped (backfill still pending).
    groups: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        indicator_id = row.get("indicator_id")
        concept_id = row.get("concept_id")
        entity_kinds = row.get("entity_kinds")
        if not isinstance(indicator_id, str):
            continue
        if not isinstance(concept_id, str) or not concept_id:
            continue
        if not isinstance(entity_kinds, list):
            continue
        key = (concept_id, tuple(sorted(str(k) for k in entity_kinds)))
        groups.setdefault(key, []).append(indicator_id)

    for (concept_id, ekinds), ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        failures.append(
            Failure(
                catalogue_rel,
                "B",
                f"indicators: {len(ids)} rows share "
                f"(concept_id={concept_id!r}, entity_kinds={list(ekinds)!r}): "
                f"{sorted(ids)!r}. Per guardrail #13 identity is what is "
                f"MEASURED, not who published it; UPSERT into the existing "
                f"indicator or add a facet, never mint a new id. Run "
                f"`python -m yen_gov check-overlap` before authoring any new "
                f"catalogue row. See "
                f"docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md "
                f"§0quat guardrail #13.",
            )
        )

    return failures


# Predicate bodies live in yen_gov.preflight.predicates (ADR-0046 DRY
# extraction). Re-exported here for back-compat with callers that import
# the constants.
_SOURCE_ID_HEX_RE = _P.SOURCE_ID_HEX_RE
_SOURCE_IDS_ASSIGN_RE = _P.SOURCE_IDS_ASSIGN_RE
BACKEND_SOURCES_DIR = Path("backend/yen_gov/sources")


def tier_b_no_hand_typed_source_id(root: Path) -> list[Failure]:
    """Reject hand-typed ``source_id`` hashes in adapter source files.

    Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md
    §0quat guardrail #6, ``source_id`` MUST be looked up via the
    forthcoming ``source_registry.resolve(nickname)`` seam (PR-A6); raw
    ``src-<hex>`` literals or ``SOURCE_IDS = {...}`` hash-tables inside
    ``backend/yen_gov/sources/**/*.py`` are forbidden. The only legit
    homes for the hex literals are ``datasets/data/entities/source.csv``
    (the citation ledger itself post-X1b #814; previously
    ``datasets/taxonomy/sources.parquet``) and
    ``datasets/taxonomy/source_nicknames.json``
    (the nickname -> source_id resolver table). Copy-pasting a hash into
    an adapter silently couples the adapter to a snapshot of the ledger
    and bypasses the resolver.

    SHIPS DARK in PR-Z3b-tail-actionB (function present but NOT chained
    into ``run()``). Will be wired into ``run()`` post-PR-A6 once the
    ``source_registry`` seam exists and all adapters route through it.
    Until then the check no-ops on today's adapters (verified clean
    at PR ship time).

    No-ops when ``backend/yen_gov/sources/`` is absent (e.g. running
    against a docs-only sub-tree).
    """
    failures: list[Failure] = []
    sources_dir = root / BACKEND_SOURCES_DIR
    if not sources_dir.is_dir():
        return failures

    for path in sorted(sources_dir.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = _posix(path, root)
        for snippet, line_no in _P.hand_typed_source_id_hits(text):
            if snippet == "SOURCE_IDS=":
                failures.append(
                    Failure(
                        rel,
                        "B",
                        f"{rel}: forbidden top-level ``SOURCE_IDS = ...`` "
                        f"hash-table assignment. Per guardrail #6 source_id "
                        f"MUST be looked up via source_registry.resolve("
                        f"nickname); raw hash tables inside adapter modules "
                        f"silently snapshot the citation ledger. See "
                        f"docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md "
                        f"§0quat guardrail #6.",
                    )
                )
            else:
                failures.append(
                    Failure(
                        rel,
                        "B",
                        f"{rel}:{line_no}: forbidden hand-typed source_id "
                        f"literal {snippet}. Per guardrail #6 the only "
                        f"legit homes are datasets/data/entities/source.csv "
                        f"and datasets/taxonomy/source_nicknames.json; "
                        f"adapters MUST resolve via source_registry.resolve("
                        f"nickname). See "
                        f"docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md "
                        f"§0quat guardrail #6.",
                    )
                )

    return failures


def tier_b_indicator_has_justification(root: Path) -> list[Failure]:
    """Reject cross-grain concept twins missing ``meta.justification``.

    Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md
    §0quat guardrail #15, default action for new data is UPSERT into the
    existing indicator. Minting a SECOND indicator that shares a
    ``concept_id`` with an existing one (only entity_kinds differing) is
    permitted only when the catalogue row carries a non-empty
    ``meta.justification`` naming the difference (different concept /
    unit / normalisation / sampling frame). Without justification the
    twin is a proliferation bug — the right action is to merge via
    cross-grain ``entity_kinds[]`` on the original row.

    SHIPS DARK in PR-Z3b-tail-actionD (function present but NOT chained
    into ``run()``). Will be wired into ``run()`` post-PR-Z3b-tail-actionC
    once the 183 existing rows have been backfilled with ``concept_id``
    and ``meta.justification``. Until then the check no-ops cleanly on
    today's catalogue (no row carries ``concept_id`` yet).

    No-ops when ``datasets/taxonomy/indicators.json`` is absent or fails
    to parse.
    """
    failures: list[Failure] = []
    catalogue_path = root / INDICATOR_CATALOGUE_JSON
    catalogue_rel = INDICATOR_CATALOGUE_JSON.as_posix()

    if not catalogue_path.exists():
        return failures

    try:
        payload = _load_json(catalogue_path)
    except json.JSONDecodeError:
        return failures
    if not isinstance(payload, dict):
        return failures
    rows = payload.get("indicators")
    if not isinstance(rows, list):
        return failures

    # Group rows by concept_id; clusters with 2+ distinct entity_kinds
    # tuples are cross-grain twins and trigger the justification check.
    by_concept: dict[str, list[tuple[str, tuple[str, ...], str]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        indicator_id = row.get("indicator_id")
        concept_id = row.get("concept_id")
        entity_kinds = row.get("entity_kinds")
        if not isinstance(indicator_id, str):
            continue
        if not isinstance(concept_id, str) or not concept_id:
            continue
        if not isinstance(entity_kinds, list):
            continue
        meta = row.get("meta")
        justification = ""
        if isinstance(meta, dict):
            j = meta.get("justification")
            if isinstance(j, str):
                justification = j.strip()
        by_concept.setdefault(concept_id, []).append(
            (indicator_id, tuple(sorted(str(k) for k in entity_kinds)),
             justification)
        )

    # Cross-grain twin set computed via predicate (ADR-0046 DRY extraction).
    twin_concepts = _P.cross_grain_twin_concepts(rows)
    for concept_id, entries in sorted(by_concept.items()):
        if concept_id not in twin_concepts:
            continue  # single-grain cluster -- not a cross-grain twin
        for indicator_id, _ek, justification in entries:
            # Tier-B preserves the original "non-empty after strip" semantics
            # (min_len=1) so the existing #d63709eb backfill stays valid.
            # The pre-flight gate uses the stricter min_len=20 default to
            # enforce a real distinguishing-dimension rationale on net-new
            # ingests.
            if _P.justification_violation(justification, min_len=1) is None:
                continue
            failures.append(
                Failure(
                    catalogue_rel,
                    "B",
                    f"indicators[indicator_id={indicator_id!r}]: "
                    f"cross-grain twin under concept_id={concept_id!r} "
                    f"is missing non-empty meta.justification. Per "
                    f"guardrail #15 default action for new data is "
                    f"UPSERT into the existing indicator; minting a "
                    f"second id that shares a concept_id requires "
                    f"meta.justification naming the difference "
                    f"(different concept / unit / normalisation / "
                    f"sampling frame) or the twin must be merged via "
                    f"cross-grain entity_kinds[]. See "
                    f"docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md "
                    f"§0quat guardrail #15.",
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
        + tier_b_meadow_shard_contract(root)
        + tier_b_legacy_boundary_sidecars(root)
        + tier_b_no_new_sub_fuel_shards(root)
        + tier_b_meadow_vintage_matches_source_id(root)
        + tier_b_indicator_freshness_declared(root)
        + tier_b_indicator_has_justification(root)
        + tier_b_one_indicator_per_concept(root)
        + tier_b_no_hand_typed_source_id(root)
        + tier_b_indicator_id_no_grain_prefix(root)
    )
