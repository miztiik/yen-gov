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
from datetime import date, datetime
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

# Legacy boundary sidecar tree (CLAUDE.md §10 anti-pattern, ADR-0031
# Amendment 2026-05-22 -- T.0d boundaries consolidation). Pre-T.0d every
# `*.geojson` carried sibling `*.sources.json` / `*.metadata.json` /
# `*.unkeyed.json` and per-state `*-index.json` manifests. Provenance,
# simplification metadata, and shard inventory now live in
# `datasets/boundaries/boundary_layers.parquet` (FK to
# `datasets/taxonomy/sources.parquet`). New sidecars are forbidden; the
# allowlist exists only to permit short-lived temporary overrides during
# a follow-up PR (none today — file ships empty). The Tier-B check
# `tier_b_legacy_boundary_sidecars` enforces the doctrine.
LEGACY_BOUNDARY_SIDECARS_DIR = Path("datasets/boundaries")
LEGACY_BOUNDARY_SIDECARS_ALLOWLIST = Path("datasets/_ops/legacy-boundary-sidecars.txt")

# Indicator catalogue alias-window enforcement (T.3 2026-05-22, locked
# by user direction Q3). The catalogue at `datasets/taxonomy/indicators.json`
# v1.1+ supports `id_aliases[]` + `deprecated_in` (ISO date) for one-release
# back-compat dereferencing of legacy `<topic>/<id>` slugs. `tier_b_indicator_alias_window`
# enforces a 60-day expiry: rows whose `deprecated_in` is older than 60 days
# at validator runtime are rejected (operator must delete the alias entries).
# Also catches the paired-semantic violation: `id_aliases` non-empty with
# `deprecated_in` null (mirrors the compile-time check in indicators_seed.py).
INDICATOR_CATALOGUE_JSON = Path("datasets/taxonomy/indicators.json")
INDICATOR_ALIAS_WINDOW_DAYS = 60

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
    # the `boundary_layers.parquet` ledger or future contract surfaces.
    if name.endswith("-index.json"):
        return True
    return False


def tier_b_legacy_boundary_sidecars(root: Path) -> list[Failure]:
    """Forbid pre-T.0d boundary sidecars and index manifests.

    Per ADR-0031 Amendment 2026-05-22 (T.0d boundaries consolidation) the
    per-shard sidecar files (`*.sources.json`, `*.metadata.json`,
    `*.unkeyed.json`) and the per-state villages-index manifests
    (`<eci>-villages-index.json`) were retired in favour of a single
    parquet ledger at `datasets/boundaries/boundary_layers.parquet` (with
    `source_id` FK to `datasets/taxonomy/sources.parquet`).

    Two symmetric failure modes (mirroring
    `tier_b_legacy_folded_indicator_shards`):
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
                "shard inventory live in datasets/boundaries/boundary_layers.parquet. "
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


def tier_b_indicator_alias_window(
    root: Path, today: date | None = None
) -> list[Failure]:
    """Enforce the 60-day expiry window on indicator catalogue id_aliases.

    Per indicator-catalogue.schema.json v1.1 (T.3 2026-05-22) each row in
    ``datasets/taxonomy/indicators.json`` may carry:
      * ``id_aliases``: list of legacy indicator_id slugs (D30 kebab OR
        legacy ``<topic>/<snake_case_id>``) that resolve to this row for
        one-release back-compat URL / query dereferencing.
      * ``deprecated_in``: ISO ``YYYY-MM-DD`` date the alias chain was
        introduced.

    The two fields are paired:
      1. ``id_aliases`` non-empty with ``deprecated_in`` null is a
         paired-semantic violation (the validator cannot apply the expiry
         window without an anchor date). Same check exists at compile time
         in ``indicators_seed.py``; replicated here so operators see the
         failure BEFORE running ``emit-taxonomy`` (i.e. at the same
         validator gate they run before staging).
      2. ``(today - deprecated_in).days > INDICATOR_ALIAS_WINDOW_DAYS``
         (60 days, locked 2026-05-22 user direction Q3) is the expiry
         signal -- the alias entries MUST be deleted in the next operator
         cycle. Lexicographic ISO ``YYYY-MM-DD`` parsing; no semver math.

    The ``today`` injection point lets tests pin time-of-day without
    monkeypatching ``datetime``. Production callers pass ``None`` and get
    ``date.today()``.

    No-ops when ``datasets/taxonomy/indicators.json`` is absent or fails
    to parse / lacks an ``indicators`` array -- those failures surface
    via the schema-driven Tier-B check, not this one.
    """
    failures: list[Failure] = []
    catalogue_path = root / INDICATOR_CATALOGUE_JSON
    catalogue_rel = INDICATOR_CATALOGUE_JSON.as_posix()
    cutoff_day = today if today is not None else date.today()

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
        aliases = row.get("id_aliases")
        if not isinstance(aliases, list) or not aliases:
            continue
        indicator_id = row.get("indicator_id", "<unknown>")
        deprecated_in = row.get("deprecated_in")

        if not isinstance(deprecated_in, str) or not deprecated_in:
            failures.append(
                Failure(
                    catalogue_rel,
                    "B",
                    f"indicators[indicator_id={indicator_id!r}]: id_aliases set but "
                    f"deprecated_in is null. Per indicator-catalogue.schema.json v1.1 "
                    f"the two fields are paired; set deprecated_in to the ISO "
                    f"'YYYY-MM-DD' date the alias chain was introduced so Tier-B can "
                    f"apply the {INDICATOR_ALIAS_WINDOW_DAYS}-day expiry window.",
                )
            )
            continue

        try:
            anchor = datetime.strptime(deprecated_in, "%Y-%m-%d").date()
        except ValueError:
            failures.append(
                Failure(
                    catalogue_rel,
                    "B",
                    f"indicators[indicator_id={indicator_id!r}]: deprecated_in "
                    f"{deprecated_in!r} is not a valid ISO 'YYYY-MM-DD' date.",
                )
            )
            continue

        age_days = (cutoff_day - anchor).days
        if age_days > INDICATOR_ALIAS_WINDOW_DAYS:
            failures.append(
                Failure(
                    catalogue_rel,
                    "B",
                    f"indicators[indicator_id={indicator_id!r}]: id_aliases expired -- "
                    f"deprecated_in={deprecated_in} is {age_days} days old "
                    f"(window={INDICATOR_ALIAS_WINDOW_DAYS} days, locked 2026-05-22 "
                    f"user direction Q3). Delete the id_aliases entries (and the "
                    f"deprecated_in field) in the next operator cycle; downstream "
                    f"consumers have had at least one release to migrate to the "
                    f"canonical indicator_id.",
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
    fall under `tier_b_legacy_folded_indicator_shards` (any new file
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


def run(root: Path) -> list[Failure]:
    """Run Tier A then Tier B against a repo root."""
    schemas, parse_failures = load_schemas(root / SCHEMAS_SUBDIR)
    return (
        parse_failures
        + tier_a(schemas)
        + tier_b(schemas, root)
        + tier_b_legacy_folded_indicator_shards(root)
        + tier_b_legacy_boundary_sidecars(root)
        + tier_b_indicator_alias_window(root)
        + tier_b_no_new_sub_fuel_shards(root)
    )
