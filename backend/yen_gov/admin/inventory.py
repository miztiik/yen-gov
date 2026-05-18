"""Inventory endpoint — family-agnostic walk of the canonical Parquet store.

The canonical pivot ([ADR-0030]) standardised every indicator family —
elections today, energy / demography / fiscal / health next — on the same
on-disk shape:

    datasets/<family>/observations.parquet     # long-format facts
    datasets/<family>/dim_<*>.parquet          # denormalised dim tables
    datasets/taxonomy/<*>.parquet              # cross-family taxonomy

Because the observations schema is family-invariant
(``observation_id, entity_id, year, period_label, period_seq,
indicator_id, value_numeric, value_text, source_id, derivation``), the
operator's "what's in my store?" question is one query against any
``observations.parquet`` regardless of family. This endpoint walks every
Parquet under ``datasets/`` and answers it in two passes:

* ``stores[]`` — one row per Parquet file. Family inferred from the
  top-level directory; kind inferred from filename. Stats are populated
  only for ``observations`` parquets; ``dim_*`` and taxonomy stores
  report row count + mtime only (their content is structure, not facts).

* ``indicators[]`` — one row per ``(family, indicator_id)`` across every
  ``observations.parquet``. This is the cross-family "is this indicator
  populated?" surface, complementary to the docs/completeness-driven
  Indicators panel.

Election-specific (event × state) coverage is deliberately NOT a
built-in here. That question is one drill among many a family-specific
panel could ask; the generic Inventory stays family-agnostic so the day
energy/demography land they appear automatically.

Path convention: every path emitted here is **POSIX-relative to the
repo root** (CLAUDE.md §2).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import duckdb
from fastapi import APIRouter, HTTPException

router = APIRouter()

log = logging.getLogger(__name__)


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


def _repo_root() -> Path:
    """Repo root used for filesystem walks.

    Honours ``YEN_GOV_REPO_ROOT`` so pytest can point the endpoint at a
    controlled fixture corpus (CLAUDE.md §10 / Holy Law #7 — no real-corpus
    walks from pytest). Same pattern as ``schemas.py``.
    """
    override = os.environ.get("YEN_GOV_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return _DEFAULT_REPO_ROOT


def _rel(p: Path, root: Path) -> str:
    return PurePosixPath(p.resolve().relative_to(root.resolve())).as_posix()


def _mtime_iso(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).isoformat()


# Directory prefixes under ``datasets/`` that the inventory ignores. These
# are sentinel / transitional spaces and the operator shouldn't see them
# alongside the real canonical stores.
_SKIP_DIR_PREFIXES: tuple[str, ...] = ("_test", "_old", "schemas", "patches")


def _classify(
    rel_path: PurePosixPath,
    manifest_index: dict[str, tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Return ``(family, kind)`` for a Parquet path under ``datasets/``.

    Family = top-level dir under ``datasets/`` (e.g. ``elections``,
    ``taxonomy``, ``energy`` once it lands). Kind is one of:

    * ``observations`` — the long-format facts table for a family.
    * ``dim``          — a denormalised dim_* lookup table.
    * ``taxonomy``     — anything under ``datasets/taxonomy/``.
    * ``other``        — Parquet we recognise but don't introspect.

    Resolution order: if ``manifest_index`` carries an entry for this file's
    POSIX-relative-under-datasets path, return its (family, kind) directly
    (the writer is the authority — see ``manifest.schema.json`` v1.1's
    ``kind`` field + canonical-store.md §2a). Otherwise fall back to the
    historical filename string-matching rules so orphan files and missing
    manifests do not crash the endpoint.
    """
    parts = rel_path.parts
    # parts[0] == 'datasets', parts[1] == family
    family = parts[1] if len(parts) >= 2 else "?"
    if manifest_index is not None:
        # Manifest paths are relative to datasets/, not to the repo root.
        datasets_rel = PurePosixPath(*parts[1:]).as_posix() if len(parts) >= 2 else ""
        hit = manifest_index.get(datasets_rel)
        if hit is not None:
            mf_family, mf_kind = hit
            if mf_kind:
                return mf_family or family, mf_kind
    fname = parts[-1]
    if family == "taxonomy":
        return family, "taxonomy"
    if fname == "observations.parquet":
        return family, "observations"
    if fname.startswith("dim_") and fname.endswith(".parquet"):
        return family, "dim"
    return family, "other"


def _load_manifest_index(
    datasets_dir: Path,
) -> dict[str, tuple[str, str]] | None:
    """Build ``{posix_path_under_datasets -> (family, kind)}`` from
    ``datasets/manifest.json``.

    Returns ``None`` if the manifest is missing or unreadable so the
    endpoint degrades gracefully to the filename-string-matching fallback
    (same precedent as the existing missing-``datasets/`` behaviour).
    Only reads ``tables[].family``, ``tables[].kind``, and
    ``tables[].files[].path`` — no pydantic, no full validation.
    """
    manifest_path = datasets_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("inventory: cannot read manifest.json (%s); using fallback classifier", exc)
        return None
    index: dict[str, tuple[str, str]] = {}
    for table in doc.get("tables", []) or []:
        family = table.get("family") or ""
        kind = table.get("kind") or ""
        for f in table.get("files", []) or []:
            path = f.get("path")
            if isinstance(path, str) and path:
                index[path] = (family, kind)
    return index


def _observations_stats(con: duckdb.DuckDBPyConnection, abs_path: Path) -> dict[str, Any]:
    """One-shot summary of an ``observations.parquet``.

    Single SQL round-trip over the file; DuckDB reads only the column
    statistics + sampled metadata it needs, so this is cheap even at
    hundreds-of-MB Parquet sizes.
    """
    row = con.execute(
        """
        SELECT
            count(*)                       AS row_count,
            count(DISTINCT indicator_id)   AS indicators,
            count(DISTINCT entity_id)      AS entities,
            count(DISTINCT period_label)   AS periods,
            min(year)                      AS min_year,
            max(year)                      AS max_year,
            count(DISTINCT source_id)      AS sources
        FROM read_parquet(?)
        """,
        [str(abs_path)],
    ).fetchone()
    assert row is not None
    return {
        "row_count": int(row[0]),
        "indicators": int(row[1]),
        "entities": int(row[2]),
        "periods": int(row[3]),
        "min_year": None if row[4] is None else int(row[4]),
        "max_year": None if row[5] is None else int(row[5]),
        "sources": int(row[6]),
    }


def _plain_row_count(con: duckdb.DuckDBPyConnection, abs_path: Path) -> int:
    row = con.execute("SELECT count(*) FROM read_parquet(?)", [str(abs_path)]).fetchone()
    assert row is not None
    return int(row[0])


def _indicator_breakdown(
    con: duckdb.DuckDBPyConnection, family: str, abs_path: Path
) -> list[dict[str, Any]]:
    """Per-indicator stats for one observations.parquet."""
    rows = con.execute(
        """
        SELECT
            indicator_id,
            count(*)                       AS obs_count,
            count(DISTINCT entity_id)      AS entity_count,
            count(DISTINCT period_label)   AS period_count,
            min(year)                      AS min_year,
            max(year)                      AS max_year
        FROM read_parquet(?)
        GROUP BY indicator_id
        ORDER BY indicator_id
        """,
        [str(abs_path)],
    ).fetchall()
    return [
        {
            "family": family,
            "indicator_id": r[0],
            "obs_count": int(r[1]),
            "entity_count": int(r[2]),
            "period_count": int(r[3]),
            "min_year": None if r[4] is None else int(r[4]),
            "max_year": None if r[5] is None else int(r[5]),
        }
        for r in rows
    ]


def _discover_parquets(datasets_dir: Path) -> list[Path]:
    """Every Parquet under ``datasets/`` worth surfacing, sorted.

    Filtering rules sit here, not in the route handler, so the test can
    seed a fixture corpus and trust the same discovery logic the live
    endpoint uses.
    """
    if not datasets_dir.exists():
        return []
    out: list[Path] = []
    for p in datasets_dir.rglob("*.parquet"):
        # Skip files inside any sentinel top-level directory.
        try:
            rel = p.resolve().relative_to(datasets_dir.resolve())
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in _SKIP_DIR_PREFIXES:
            continue
        out.append(p)
    return sorted(out)


@router.get("/inventory")
def inventory() -> dict[str, Any]:
    """Family-agnostic inventory of the canonical Parquet store.

    Returns
    -------
    dict
        ``generated_at`` : RFC 3339 UTC, when this response was built.
        ``stores``       : one entry per Parquet under ``datasets/``
                           (excluding sentinel dirs). Observations parquets
                           carry a ``stats`` block; dim / taxonomy carry
                           ``row_count`` + ``size_bytes`` only.
        ``indicators``   : per-indicator stats rolled up across every
                           ``observations.parquet`` in the store. Family
                           is preserved so a future multi-family operator
                           can group by it.
    """
    root = _repo_root()
    datasets_dir = root / "datasets"
    parquets = _discover_parquets(datasets_dir)

    if not datasets_dir.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"datasets/ does not exist at {datasets_dir!s}; "
                "run from the repo root."
            ),
        )

    manifest_index = _load_manifest_index(datasets_dir)

    con = duckdb.connect()
    try:
        stores: list[dict[str, Any]] = []
        indicators: list[dict[str, Any]] = []

        for p in parquets:
            rel = PurePosixPath(_rel(p, root))
            family, kind = _classify(rel, manifest_index)
            entry: dict[str, Any] = {
                "family": family,
                "kind": kind,
                "path": str(rel),
                "size_bytes": p.stat().st_size,
                "mtime": _mtime_iso(p),
                "row_count": None,
                "stats": None,
            }
            try:
                if kind == "observations":
                    stats = _observations_stats(con, p)
                    entry["row_count"] = stats.pop("row_count")
                    entry["stats"] = stats
                    indicators.extend(_indicator_breakdown(con, family, p))
                else:
                    entry["row_count"] = _plain_row_count(con, p)
            except duckdb.Error as e:  # pragma: no cover — surfaces corrupt files
                entry["error"] = f"{type(e).__name__}: {e}"
            stores.append(entry)
    finally:
        con.close()

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "stores": stores,
        "indicators": indicators,
    }
