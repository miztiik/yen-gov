"""Geometric AC->PC parent backfill crosswalk (Row P0a).

Resolves the ``parent`` (Parliament constituency, PC) link for the
2008-delimitation Assembly constituencies (AC) that are still NULL-parent in
``datasets/data/entities/electoral.csv`` (the LGD snapshot lacks
``parent_pc_lgd_code`` for them - confirmed at
``electoral_csv_from_snapshot.py``). The link is derived by an in-repo
GEOMETRIC spatial join, not by scraping ECI PDFs:

    A Parliament constituency is, by the 2008 Delimitation Order, the union of
    WHOLE Assembly constituencies. So each AC's parent PC is the PC polygon that
    contains it - i.e. the PC with the largest area-overlap with the AC.

Both boundary layers already ship in-repo (the consolidated 2008-delim AC
TopoJSON + the PC GeoJSON), so the derivation is verifiable, reproducible, and
network-free (Hans + Max ruling, 2026-06-25; CLAUDE.md section 0a authority).

Inputs (read relative to ``repo_root``):

- ``datasets/boundaries/electoral/delim=2024/ac/all.topojson`` (object ``ac``;
  2008-delim AC geometry relabelled; each feature carries ``state_ut_code`` +
  ``ac_no`` (the ECI ballot serial) + ``ac_name``).
- ``datasets/boundaries/electoral/delim=2024/pc/all.geojson`` (each feature
  carries ``unique_id`` = ``<state_ut_code>_<eci_no>``).
- ``datasets/data/entities/electoral.csv`` (the target AC + PC entity rows).
- ``datasets/data/entities/geo.csv`` (state/UT slug <-> ECI code).

Output (only when the validation gate passes):

- ``datasets/data/entities/ac_pc_geometric_backfill.csv`` - one row per resolved
  gap AC: ``ac_entity_id, parent_pc_entity_id, parent_pc_eci_no, match_method,
  overlap_frac, source_id``.
- one provenance row appended to ``datasets/data/entities/source.csv`` (Holy
  Law #9; ``source_id`` built via :func:`derive_source_id`).

Safety (HARD validation gate + per-row double-lock):

1. GATE - before writing anything, the geometric parent of every ALREADY-linked
   AC (the ~3865 LGD-resolved seats) is compared to its existing LGD parent. If
   the overall agreement is below ``min_agreement`` (95% by default) the run
   STOPS and writes nothing - this catches a broken decode / bridge before it
   can fabricate links.
2. PER-ROW double-lock - a gap AC is emitted only when its dominant PC overlap
   is unambiguous (``overlap_frac >= min_overlap`` AND it clearly beats the
   runner-up) AND its PC bridge resolves AND one of: (Tier A) the geometry's own
   seat name matches the electoral seat name (per-row identity proof, robust
   even in states whose delimitation was renumbered after 2008), or (Tier B) the
   AC's state passed the per-state LGD-agreement bar (the pipeline is proven for
   the whole state). Seats that satisfy neither lock are LEFT OUT (stay NULL ->
   "data pending"), never guessed.

This module needs ``shapely>=2.0`` (declared as the ``geo`` optional extra in
``backend/pyproject.toml``). It is a BUILD-time generator only; the committed
pipeline that READS the crosswalk CSV does not import shapely.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.strtree import STRtree

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

# ---------------------------------------------------------------------------
# Repo-relative inputs / outputs (POSIX; resolved against repo_root at call).
# ---------------------------------------------------------------------------
AC_TOPOJSON_REL = "datasets/boundaries/electoral/delim=2024/ac/all.topojson"
PC_GEOJSON_REL = "datasets/boundaries/electoral/delim=2024/pc/all.geojson"
ELECTORAL_REL = "datasets/data/entities/electoral.csv"
GEO_REL = "datasets/data/entities/geo.csv"
SOURCE_REL = "datasets/data/entities/source.csv"
OUT_REL = "datasets/data/entities/ac_pc_geometric_backfill.csv"

FILE_CLASS = "datasets/data/entities/ac_pc_geometric_backfill.csv"
SOURCE_FILE_CLASS = "datasets/data/entities/source.csv"
TOPOJSON_OBJECT = "ac"
DELIM_YEAR = 2008
MATCH_METHOD = "geometric_overlap"

# Defaults for the two safety knobs (overridable from the CLI for diagnosis).
DEFAULT_MIN_AGREEMENT = 0.95  # GATE: geometric-vs-LGD agreement on filled ACs
DEFAULT_MIN_OVERLAP = 0.80  # per-row: winning PC must cover >= 80% of the AC
DEFAULT_MIN_STATE_FILLED = 20  # Tier-B state-trust needs this many filled ACs

# Provenance triple for the derived crosswalk (Holy Law #9 / section 12). The
# crosswalk is a yen-gov geometric INFERENCE from the two in-repo boundary
# layers - neither boundary publisher (ramSeraph AC src-a1dd899f902d, shijithpk
# PC src-2af556fe59e0) published the AC->PC linkage, so attributing it to them
# would be dishonest; producer is yen-gov, the title discloses both inputs +
# the method, vintage is the delimitation the linkage encodes.
SOURCE_PRODUCER = "yen-gov"
SOURCE_TITLE = (
    "Geometric AC-to-PC parent overlay (in-repo spatial join of ramSeraph "
    "LGD-keyed Assembly boundaries + shijithpk Lok Sabha PC boundaries)"
)
SOURCE_VINTAGE = "2008-delimitation"
SOURCE_URL = ""

_ECI_CODE_RE = re.compile(r"^[SU]\d{2}$")
_PC_UID_RE = re.compile(r"^([SU]\d{2})_(\d+)$")
_PAREN_RE = re.compile(r"\([^)]*\)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
@dataclass
class BackfillResult:
    """Outcome of a backfill run (returned to the CLI for reporting)."""

    status: str  # "ok" | "stopped-low-agreement"
    agreement_rate: float
    agreement_matched: int
    agreement_total: int
    per_state_agreement: dict[str, tuple[int, int]] = field(default_factory=dict)
    name_confirmed_rate: float = 0.0
    emitted: int = 0
    residual: int = 0
    gap_total: int = 0
    emitted_per_state: dict[str, int] = field(default_factory=dict)
    residual_per_state: dict[str, int] = field(default_factory=dict)
    source_id: str = ""
    out_path: Path | None = None
    source_path: Path | None = None
    samples: list[tuple[str, str, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------
def _norm_name(value: str | None) -> str:
    """Lowercase alphanumeric key with parentheticals (e.g. ``(SC)``) dropped.

    The geometry labels often append a reservation tag (``Malavalli (SC)``) and
    use abbreviations the electoral register spells out, so the comparison drops
    ``(...)`` groups then strips every non-alphanumeric. It is deliberately
    lossy: a match is strong evidence of the SAME physical seat; a mismatch only
    means "fall back to the per-state trust lock", never a wrong assignment.
    """
    stripped = _PAREN_RE.sub("", value or "")
    return _NON_ALNUM_RE.sub("", stripped.lower())


# ---------------------------------------------------------------------------
# TopoJSON decode (pure-Python; no node/mapshaper dependency at build time)
# ---------------------------------------------------------------------------
def _decode_arcs(topo: dict[str, Any]) -> list[list[tuple[float, float]]]:
    """Dequantise + delta-decode every arc to absolute lon/lat coordinates."""
    transform = topo.get("transform")
    raw_arcs = topo["arcs"]
    decoded: list[list[tuple[float, float]]] = []
    if transform:
        (scale_x, scale_y) = transform["scale"]
        (translate_x, translate_y) = transform["translate"]
        for arc in raw_arcs:
            x = y = 0
            points: list[tuple[float, float]] = []
            for dx, dy in arc:
                x += dx
                y += dy
                points.append((x * scale_x + translate_x, y * scale_y + translate_y))
            decoded.append(points)
    else:
        for arc in raw_arcs:
            decoded.append([(px, py) for px, py in arc])
    return decoded


def _stitch_ring(
    arc_indices: list[int], arcs: list[list[tuple[float, float]]]
) -> list[tuple[float, float]]:
    """Concatenate the referenced arcs into one ring (negatives are reversed)."""
    coords: list[tuple[float, float]] = []
    for idx in arc_indices:
        segment = arcs[idx] if idx >= 0 else arcs[~idx][::-1]
        coords.extend(segment[1:] if coords else segment)
    return coords


def _geometry_from_topo(
    geom_obj: dict[str, Any], arcs: list[list[tuple[float, float]]]
) -> Polygon | MultiPolygon | None:
    """Build a shapely Polygon/MultiPolygon from a TopoJSON geometry object."""
    kind = geom_obj.get("type")
    if kind == "Polygon":
        rings = [_stitch_ring(r, arcs) for r in geom_obj["arcs"]]
        rings = [r for r in rings if len(r) >= 4]
        return Polygon(rings[0], rings[1:]) if rings else None
    if kind == "MultiPolygon":
        polygons: list[Polygon] = []
        for poly in geom_obj["arcs"]:
            rings = [_stitch_ring(r, arcs) for r in poly]
            rings = [r for r in rings if len(r) >= 4]
            if rings:
                polygons.append(Polygon(rings[0], rings[1:]))
        return MultiPolygon(polygons) if polygons else None
    return None


def _safe(geom: Any) -> Any:
    """Return a non-empty valid geometry (``buffer(0)`` repair) or ``None``."""
    if geom is None:
        return None
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom is None or geom.is_empty:
        return None
    return geom


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _load_eci_to_slug(geo_csv: Path) -> dict[str, str]:
    """Map ECI state/UT code (``S01`` / ``U05``) -> geo.csv state slug."""
    out: dict[str, str] = {}
    for row in _read_csv_rows(geo_csv):
        if row.get("parent") != "IN" or row.get("entity_kind") not in {"state", "ut"}:
            continue
        eci = next(
            (a.strip() for a in (row.get("aliases") or "").split("|") if _ECI_CODE_RE.match(a.strip())),
            "",
        )
        if eci:
            out[eci] = row["entity_id"]
    return out


@dataclass
class _ElectoralIndex:
    ac_by_key: dict[tuple[str, str], str]  # (slug, eci_no) -> ac entity_id
    ac_key_dups: set[tuple[str, str]]
    pc_by_key: dict[tuple[str, str], str]  # (slug, eci_no) -> pc entity_id
    pc_eci_of: dict[str, str]  # pc entity_id -> eci_no
    ac_null: set[str]  # NULL-parent gap AC entity_ids
    ac_parent: dict[str, str]  # filled AC entity_id -> LGD parent pc entity_id
    name_norm: dict[str, str]  # AC entity_id -> normalised name
    state_of: dict[str, str]  # AC entity_id -> state slug


def _load_electoral(electoral_csv: Path) -> _ElectoralIndex:
    rows = _read_csv_rows(electoral_csv)
    ac_rows = [r for r in rows if r["entity_kind"] == "ac" and r.get("delim_year") == str(DELIM_YEAR)]
    pc_rows = [r for r in rows if r["entity_kind"] == "pc" and r.get("delim_year") == str(DELIM_YEAR)]

    ac_by_key: dict[tuple[str, str], str] = {}
    ac_key_dups: set[tuple[str, str]] = set()
    ac_null: set[str] = set()
    ac_parent: dict[str, str] = {}
    name_norm: dict[str, str] = {}
    state_of: dict[str, str] = {}
    for r in ac_rows:
        eid = r["entity_id"]
        name_norm[eid] = _norm_name(r["name"])
        state_of[eid] = r["state"]
        eci = (r.get("eci_no") or "").strip()
        if eci:
            key = (r["state"], eci)
            if key in ac_by_key:
                ac_key_dups.add(key)
            ac_by_key[key] = eid
        if (r.get("parent") or "").strip():
            ac_parent[eid] = r["parent"]
        else:
            ac_null.add(eid)

    pc_by_key: dict[tuple[str, str], str] = {}
    pc_eci_of: dict[str, str] = {}
    for r in pc_rows:
        eci = (r.get("eci_no") or "").strip()
        pc_eci_of[r["entity_id"]] = eci
        if eci:
            pc_by_key[(r["state"], eci)] = r["entity_id"]

    return _ElectoralIndex(
        ac_by_key=ac_by_key,
        ac_key_dups=ac_key_dups,
        pc_by_key=pc_by_key,
        pc_eci_of=pc_eci_of,
        ac_null=ac_null,
        ac_parent=ac_parent,
        name_norm=name_norm,
        state_of=state_of,
    )


@dataclass
class _AcFeature:
    entity_id: str
    slug: str
    geom: Any
    name_norm: str


def _load_ac_geometries(
    ac_topojson: Path, eci_to_slug: dict[str, str], idx: _ElectoralIndex
) -> dict[str, list[_AcFeature]]:
    """Decode the AC TopoJSON and bridge each polygon to its electoral AC id.

    Bridge key = (state slug from ``state_ut_code``, ``ac_no`` == electoral
    ``eci_no``). Colliding (state, eci_no) keys are excluded (ambiguous).
    """
    topo = json.loads(ac_topojson.read_text(encoding="utf-8"))
    arcs = _decode_arcs(topo)
    geometries = topo["objects"][TOPOJSON_OBJECT]["geometries"]
    by_state: dict[str, list[_AcFeature]] = defaultdict(list)
    for g in geometries:
        props = g.get("properties") or {}
        slug = eci_to_slug.get(props.get("state_ut_code"))
        if slug is None:
            continue
        geom = _safe(_geometry_from_topo(g, arcs))
        if geom is None:
            continue
        ac_no = props.get("ac_no")
        key = (slug, str(ac_no)) if ac_no is not None else None
        if key is None or key in idx.ac_key_dups:
            continue
        entity_id = idx.ac_by_key.get(key)
        if entity_id is None:
            continue
        by_state[slug].append(
            _AcFeature(
                entity_id=entity_id,
                slug=slug,
                geom=geom,
                name_norm=_norm_name(props.get("ac_name")),
            )
        )
    return by_state


def _load_pc_geometries(
    pc_geojson: Path, eci_to_slug: dict[str, str], idx: _ElectoralIndex
) -> dict[str, list[tuple[str, Any]]]:
    """Load the PC GeoJSON and bridge each polygon to its electoral PC id."""
    fc = json.loads(pc_geojson.read_text(encoding="utf-8"))
    by_state: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    for feature in fc["features"]:
        props = feature.get("properties") or {}
        match = _PC_UID_RE.match(props.get("unique_id") or "")
        geometry = feature.get("geometry")
        geom = _safe(shape(geometry)) if geometry else None
        if geom is None or match is None:
            continue
        slug = eci_to_slug.get(match.group(1))
        if slug is None:
            continue
        entity_id = idx.pc_by_key.get((slug, match.group(2)))
        if entity_id is None:
            continue
        by_state[slug].append((entity_id, geom))
    return by_state


# ---------------------------------------------------------------------------
# Spatial join
# ---------------------------------------------------------------------------
@dataclass
class _Join:
    pc_entity_id: str
    overlap_frac: float
    runner_frac: float


def _join_state(
    ac_features: list[_AcFeature], pc_list: list[tuple[str, Any]]
) -> dict[str, _Join]:
    """Largest-area-overlap PC per AC, within one state (STRtree)."""
    out: dict[str, _Join] = {}
    if not pc_list:
        return out
    pc_geoms = [g for _, g in pc_list]
    tree = STRtree(pc_geoms)
    for feature in ac_features:
        ac_area = feature.geom.area
        if ac_area <= 0:
            continue
        overlaps: list[tuple[float, str]] = []
        for cand in tree.query(feature.geom):
            pc_entity_id, pc_geom = pc_list[int(cand)]
            if not feature.geom.intersects(pc_geom):
                continue
            inter = feature.geom.intersection(pc_geom).area
            if inter > 0:
                overlaps.append((inter / ac_area, pc_entity_id))
        if not overlaps:
            continue
        overlaps.sort(key=lambda t: -t[0])
        top_frac, top_pc = overlaps[0]
        runner = overlaps[1][0] if len(overlaps) > 1 else 0.0
        out[feature.entity_id] = _Join(top_pc, top_frac, runner)
    return out


# ---------------------------------------------------------------------------
# source.csv upsert
# ---------------------------------------------------------------------------
def _upsert_source_row(source_csv: Path, source_id: str) -> Path:
    """Append the derived-crosswalk citation row to source.csv (idempotent)."""
    existing = _read_csv_rows(source_csv) if source_csv.exists() else []
    nullable = ("producer", "title", "vintage", "url")
    rows: list[dict[str, Any]] = []
    present = False
    for r in existing:
        if r.get("source_id") == source_id:
            present = True
        rows.append(
            {
                "source_id": r["source_id"],
                **{c: ((r.get(c) or "").strip() or None) for c in nullable},
            }
        )
    if not present:
        rows.append(
            {
                "source_id": source_id,
                "producer": SOURCE_PRODUCER,
                "title": SOURCE_TITLE,
                "vintage": SOURCE_VINTAGE,
                "url": SOURCE_URL or None,
            }
        )
    return write_csv(path=source_csv, file_class=SOURCE_FILE_CLASS, rows=rows)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def generate(
    *,
    repo_root: Path,
    min_agreement: float = DEFAULT_MIN_AGREEMENT,
    min_overlap: float = DEFAULT_MIN_OVERLAP,
    min_state_filled: int = DEFAULT_MIN_STATE_FILLED,
    write: bool = True,
) -> BackfillResult:
    """Run the geometric backfill; write the crosswalk iff the gate passes.

    Args:
        repo_root: repository root (inputs + outputs resolved against it).
        min_agreement: GATE threshold - geometric-vs-LGD agreement on the
            already-linked ACs must reach this or the run STOPS (writes nothing).
        min_overlap: per-row minimum winning-PC overlap fraction.
        min_state_filled: Tier-B state-trust needs at least this many filled ACs.
        write: when ``False`` compute + gate only (no file I/O) - used by
            diagnosis runs.

    Returns:
        A :class:`BackfillResult`. ``status == "stopped-low-agreement"`` means
        the gate failed and nothing was written.
    """
    ac_topojson = repo_root / AC_TOPOJSON_REL
    pc_geojson = repo_root / PC_GEOJSON_REL
    electoral_csv = repo_root / ELECTORAL_REL
    geo_csv = repo_root / GEO_REL
    for required in (ac_topojson, pc_geojson, electoral_csv, geo_csv):
        if not required.exists():
            raise FileNotFoundError(required)

    eci_to_slug = _load_eci_to_slug(geo_csv)
    idx = _load_electoral(electoral_csv)
    ac_by_state = _load_ac_geometries(ac_topojson, eci_to_slug, idx)
    pc_by_state = _load_pc_geometries(pc_geojson, eci_to_slug, idx)

    joins: dict[str, _Join] = {}
    for slug, ac_features in ac_by_state.items():
        joins.update(_join_state(ac_features, pc_by_state.get(slug, [])))

    # --- GATE + per-state trust: geometric parent vs LGD parent on filled ACs.
    per_state_agreement: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    matched = total = 0
    for ac_id, lgd_parent in idx.ac_parent.items():
        join = joins.get(ac_id)
        if join is None:
            continue
        total += 1
        slug = idx.state_of[ac_id]
        per_state_agreement[slug][1] += 1
        if join.pc_entity_id == lgd_parent:
            matched += 1
            per_state_agreement[slug][0] += 1
    rate = matched / total if total else 0.0
    per_state = {s: (ok, tot) for s, (ok, tot) in per_state_agreement.items()}

    if rate < min_agreement:
        return BackfillResult(
            status="stopped-low-agreement",
            agreement_rate=rate,
            agreement_matched=matched,
            agreement_total=total,
            per_state_agreement=per_state,
            gap_total=len(idx.ac_null),
        )

    trusted_states = {
        s
        for s, (ok, tot) in per_state.items()
        if tot >= min_state_filled and ok / tot >= min_agreement
    }

    # --- name-confirmed pipeline rate (diagnosis only; bridge correctness).
    nc_matched = nc_total = 0
    name_norm_geo: dict[str, str] = {
        f.entity_id: f.name_norm for fs in ac_by_state.values() for f in fs
    }
    for ac_id, lgd_parent in idx.ac_parent.items():
        join = joins.get(ac_id)
        if join is None or name_norm_geo.get(ac_id) != idx.name_norm.get(ac_id):
            continue
        nc_total += 1
        if join.pc_entity_id == lgd_parent:
            nc_matched += 1
    name_confirmed_rate = nc_matched / nc_total if nc_total else 0.0

    # --- emit (per-row double-lock).
    rows: list[dict[str, Any]] = []
    name_by_ac = {f.entity_id: f for fs in ac_by_state.values() for f in fs}
    source_id = derive_source_id(SOURCE_PRODUCER, SOURCE_TITLE, SOURCE_VINTAGE)
    for feature in name_by_ac.values():
        ac_id = feature.entity_id
        if ac_id not in idx.ac_null:
            continue
        join = joins.get(ac_id)
        if join is None:
            continue
        if join.overlap_frac < min_overlap or join.overlap_frac <= join.runner_frac + 1e-9:
            continue
        name_ok = bool(feature.name_norm) and feature.name_norm == idx.name_norm.get(ac_id)
        state_ok = feature.slug in trusted_states
        if not (name_ok or state_ok):
            continue
        eci = idx.pc_eci_of.get(join.pc_entity_id)
        if not eci:
            continue
        rows.append(
            {
                "ac_entity_id": ac_id,
                "parent_pc_entity_id": join.pc_entity_id,
                "parent_pc_eci_no": int(eci),
                "match_method": MATCH_METHOD,
                "overlap_frac": round(join.overlap_frac, 4),
                "source_id": source_id,
            }
        )

    emitted_ids = {r["ac_entity_id"] for r in rows}
    residual = idx.ac_null - emitted_ids
    emitted_per_state: dict[str, int] = defaultdict(int)
    for r in rows:
        emitted_per_state[idx.state_of[r["ac_entity_id"]]] += 1
    residual_per_state: dict[str, int] = defaultdict(int)
    for ac_id in residual:
        residual_per_state[idx.state_of[ac_id]] += 1

    display_name = _entity_name_lookup(electoral_csv)  # entity_id -> name (AC + PC)
    samples: list[tuple[str, str, float]] = []
    for r in sorted(rows, key=lambda x: x["ac_entity_id"])[:12]:
        samples.append(
            (
                display_name.get(r["ac_entity_id"], r["ac_entity_id"]),
                display_name.get(r["parent_pc_entity_id"], r["parent_pc_entity_id"]),
                float(r["overlap_frac"]),
            )
        )

    out_path: Path | None = None
    source_path: Path | None = None
    if write:
        out_path = write_csv(path=repo_root / OUT_REL, file_class=FILE_CLASS, rows=rows)
        source_path = _upsert_source_row(repo_root / SOURCE_REL, source_id)

    return BackfillResult(
        status="ok",
        agreement_rate=rate,
        agreement_matched=matched,
        agreement_total=total,
        per_state_agreement=per_state,
        name_confirmed_rate=name_confirmed_rate,
        emitted=len(rows),
        residual=len(residual),
        gap_total=len(idx.ac_null),
        emitted_per_state=dict(emitted_per_state),
        residual_per_state=dict(residual_per_state),
        source_id=source_id,
        out_path=out_path,
        source_path=source_path,
        samples=samples,
    )


def _entity_name_lookup(electoral_csv: Path) -> dict[str, str]:
    return {r["entity_id"]: r["name"] for r in _read_csv_rows(electoral_csv)}
