"""State geocoder - assign a (lng, lat) point to an LGD state entity.

The coal-FGD feed carries each plant's coordinates but no state field, so the
share-by-state metric must GEOCODE every unit. This module loads the India
state-boundary polygons (``datasets/boundaries/in/states/all.geojson``), maps
each polygon to its canonical LGD entity_id via ``datasets/data/entities/
geo.csv`` (the polygon's ``State_LGD`` property -> the geo row whose
``aliases`` carries ``lgd:<code>``), and answers "which state contains this
point?".

shapely is NOT a project dependency, so containment is a hand-rolled
even-odd ray-casting test over the polygon rings (handles Polygon,
MultiPolygon, and interior holes). The boundary file is SIMPLIFIED, so a
handful of coastal plants sit a few hundred metres outside the drawn
coastline; for a point that misses every polygon we fall back to a BOUNDED
nearest-boundary snap (within :data:`SNAP_TOLERANCE_DEG`). The snap is
transparent - each match reports whether it was ``contained`` or ``snapped``
- and it cannot misattribute an interior point because states are contiguous
(an interior point is always strictly contained, so it never reaches the
snap). A point beyond the tolerance from every state is reported UNPLACED,
never guessed.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "StateGeocoder",
    "GeoMatch",
    "GeocoderError",
    "SNAP_TOLERANCE_DEG",
    "GEO_CSV_REL",
    "STATES_GEOJSON_REL",
]

GEO_CSV_REL = "datasets/data/entities/geo.csv"
STATES_GEOJSON_REL = "datasets/boundaries/in/states/all.geojson"

# Maximum distance (degrees of arc) a point may sit OUTSIDE every state polygon
# and still be snapped to the nearest state. ~0.1 deg ~= 11 km - comfortably
# above the observed coastline-simplification displacement (the real coal feed
# misses sit <= 0.4 km outside the drawn coast) yet far too tight to bridge to
# a non-adjacent state. A point further than this from every state is UNPLACED.
SNAP_TOLERANCE_DEG = 0.1


class GeocoderError(ValueError):
    """The boundary corpus could not be built into a usable geocoder.

    Raised when the states GeoJSON is missing/empty, a feature carries an
    unexpected geometry type, or a polygon's ``State_LGD`` does not map to any
    ``state`` row in geo.csv (a real integrity gap between the boundary corpus
    and the entity corpus that the operator must fix - never silently skipped).
    """


@dataclass(frozen=True)
class GeoMatch:
    """A located point: the state entity_id and how it was matched."""

    entity_id: str
    mode: str  # "contained" (strict point-in-polygon) | "snapped" (coastal)


@dataclass(frozen=True)
class _StatePolygons:
    """One state's entity_id and its list of polygons (each a list of rings)."""

    entity_id: str
    polygons: tuple[tuple[tuple[tuple[float, float], ...], ...], ...]


class StateGeocoder:
    """Point -> LGD state entity_id, by ray-cast containment + bounded snap."""

    def __init__(self, states: list[_StatePolygons]) -> None:
        if not states:
            raise GeocoderError("no state polygons were loaded.")
        self._states = states

    # --- construction ----------------------------------------------------- #
    @classmethod
    def from_repo(cls, repo_root: Path) -> "StateGeocoder":
        """Build from the standard in-repo boundary + entity files."""
        return cls.from_files(
            repo_root / GEO_CSV_REL, repo_root / STATES_GEOJSON_REL
        )

    @classmethod
    def from_files(cls, geo_csv: Path, states_geojson: Path) -> "StateGeocoder":
        """Build from explicit geo.csv + states-GeoJSON paths.

        Raises:
            FileNotFoundError: either input file is absent.
            GeocoderError: the GeoJSON is malformed, or a polygon's State_LGD
                has no matching ``state`` row in geo.csv.
        """
        if not geo_csv.exists():
            raise FileNotFoundError(f"geocoder: geo.csv not found at {geo_csv}")
        if not states_geojson.exists():
            raise FileNotFoundError(
                f"geocoder: states GeoJSON not found at {states_geojson}"
            )

        lgd_to_slug = _load_lgd_to_slug(geo_csv)
        gj = json.loads(states_geojson.read_text(encoding="utf-8"))
        features = gj.get("features") if isinstance(gj, dict) else None
        if not isinstance(features, list) or not features:
            raise GeocoderError(
                f"geocoder: {states_geojson} has no 'features' array."
            )

        states: list[_StatePolygons] = []
        for feature in features:
            props = feature.get("properties") or {}
            raw_lgd = props.get("State_LGD")
            if raw_lgd is None:
                raise GeocoderError(
                    f"geocoder: a state feature has no 'State_LGD' property "
                    f"(STNAME={props.get('STNAME')!r})."
                )
            lgd = int(raw_lgd)
            slug = lgd_to_slug.get(lgd)
            if slug is None:
                raise GeocoderError(
                    f"geocoder: state polygon State_LGD={lgd} "
                    f"(STNAME={props.get('STNAME')!r}) maps to no 'state' row "
                    f"in geo.csv. Boundary corpus and entity corpus disagree."
                )
            states.append(
                _StatePolygons(entity_id=slug, polygons=_geometry_polygons(feature))
            )
        return cls(states)

    # --- query ------------------------------------------------------------ #
    def locate(self, lng: float, lat: float) -> GeoMatch | None:
        """Return the containing state (or nearest within tolerance), else None.

        Strict ray-cast containment first; on a miss, the nearest state within
        :data:`SNAP_TOLERANCE_DEG` of any state boundary (a coastal-simplification
        snap). ``None`` when the point is beyond the tolerance from every state.
        """
        for state in self._states:
            for rings in state.polygons:
                if _point_in_polygon(lng, lat, rings):
                    return GeoMatch(entity_id=state.entity_id, mode="contained")

        best_slug: str | None = None
        best_dist = math.inf
        for state in self._states:
            for rings in state.polygons:
                d = _point_to_ring_distance(lng, lat, rings[0])
                if d < best_dist:
                    best_dist = d
                    best_slug = state.entity_id
        if best_slug is not None and best_dist <= SNAP_TOLERANCE_DEG:
            return GeoMatch(entity_id=best_slug, mode="snapped")
        return None


# --------------------------------------------------------------------------- #
# geo.csv LGD -> slug
# --------------------------------------------------------------------------- #
def _load_lgd_to_slug(geo_csv: Path) -> dict[int, str]:
    """Map each state's LGD code to its entity_id slug, from geo.csv aliases."""
    mapping: dict[int, str] = {}
    with geo_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("entity_kind") != "state":
                continue
            aliases = row.get("aliases") or ""
            for alias in aliases.split("|"):
                if alias.startswith("lgd:"):
                    try:
                        mapping[int(alias[4:])] = row["entity_id"]
                    except ValueError:
                        continue
    if not mapping:
        raise GeocoderError(
            f"geocoder: no 'state' rows with an 'lgd:<code>' alias found in "
            f"{geo_csv}; cannot map boundary polygons to entities."
        )
    return mapping


# --------------------------------------------------------------------------- #
# geometry helpers (pure - no shapely)
# --------------------------------------------------------------------------- #
def _geometry_polygons(
    feature: dict[str, Any],
) -> tuple[tuple[tuple[tuple[float, float], ...], ...], ...]:
    """Normalise a feature's geometry to a tuple of polygons (each: rings)."""
    geom = feature.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        raw_polys = [coords]
    elif gtype == "MultiPolygon":
        raw_polys = coords
    else:
        raise GeocoderError(
            f"geocoder: unsupported geometry type {gtype!r} "
            f"(STNAME={(feature.get('properties') or {}).get('STNAME')!r})."
        )
    return tuple(
        tuple(tuple((float(pt[0]), float(pt[1])) for pt in ring) for ring in poly)
        for poly in raw_polys
    )


def _point_in_ring(x: float, y: float, ring: tuple[tuple[float, float], ...]) -> bool:
    """Even-odd ray-cast: is point (x, y) inside the closed ring?"""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _point_in_polygon(
    x: float, y: float, rings: tuple[tuple[tuple[float, float], ...], ...]
) -> bool:
    """Inside the exterior ring (rings[0]) and outside every hole (rings[1:])."""
    if not rings or not _point_in_ring(x, y, rings[0]):
        return False
    return not any(_point_in_ring(x, y, hole) for hole in rings[1:])


def _point_to_ring_distance(
    x: float, y: float, ring: tuple[tuple[float, float], ...]
) -> float:
    """Minimum planar distance (degrees) from point (x, y) to a ring's edges.

    Planar (equirectangular) distance is adequate for ranking the nearest
    state at India's latitudes and for the small (<= ~11 km) snap tolerance;
    no geodesic precision is needed to decide a coastal point's state.
    """
    best = math.inf
    n = len(ring)
    for i in range(n - 1):
        d = _point_to_segment_distance(x, y, ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
        if d < best:
            best = d
    return best


def _point_to_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Planar distance from point P to segment AB."""
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)
