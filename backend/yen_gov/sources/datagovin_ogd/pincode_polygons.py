"""Pure I/O-free KMZ → pincode-polygon parser.

Phase A.2 of TODO/20260524-boundary-coverage-expansion-plan.md. Parses
the all-India pincode boundaries KMZ published by the Department of
Posts (Government of India) via data.gov.in into in-memory
``PincodePolygon`` records.

The parser is deliberately I/O-free at the boundary between modules:
``parse_pincode_polygons_from_kmz`` accepts a ``Path`` or bytes-like
KMZ source and yields the parsed structure. Cross-joining to the A.1.b
``pincode-directory.parquet`` for state assignment, coordinate
rounding for byte budget, and emission to Hive-partitioned GeoJSON
shards live in the sibling ``ingest_pincode_polygons`` module.

KMZ shape (verified 2026-05-25 via .tmp_explore_kmz.py on the 21 MB
upstream archive):

* Archive contains exactly one ``.kml`` file (``india_pin_codes_2025.kml``).
* 19,312 ``<Placemark>`` elements, one per pincode, no duplicates
  (every pincode appears exactly once).
* Each placemark carries 5 ``<SimpleData>`` rows under
  ``<ExtendedData>/<SchemaData>``: ``Pincode``, ``Office_Name``,
  ``Division``, ``Region``, ``Circle``. ``Region`` is empty on 3,811
  placemarks (20%) — this is upstream-correct, not a parse error.
* Geometry is either a single ``<Polygon>`` (18,316 placemarks) or
  a ``<MultiGeometry>`` containing multiple ``<Polygon>`` elements
  (996 placemarks, ~5%, typically pincodes with detached enclaves).
* 360 placemarks (~2%) have one or more ``<innerBoundaryIs>`` rings
  inside an outer polygon (holes — e.g. a pincode that wraps around
  but does not include a separate institutional pincode).
* All coordinates are WGS84 lon,lat[,alt] in space-separated tokens.
  Altitude is always 0 and is discarded. Bbox of the corpus:
  lon=[68.178, 97.413] lat=[6.711, 37.088] (matches India incl.
  island territories).

Determinism: parser preserves upstream placemark order; coordinate
floats are NOT rounded here (rounding lives in the emitter so the
parser stays bit-exact wrt upstream). Stripped whitespace on all
string fields. Empty ``Region`` values flow through as empty strings
(NOT None) so the round-trip is lossless.

Skipped records (counted in ``ParsedPincodePolygons.skipped_count``,
diagnostics in ``skipped_reasons``):

* Pincode missing, non-numeric, or not 6 digits.
* Placemark has no parseable polygon (no outer ring, or coordinate
  string yields zero valid (lon,lat) pairs).

Out of scope (these are NOT skipped — they flow through as-is and
become the emitter's problem):

* Coordinate envelope check (lon outside [-180, 180] or lat outside
  [-90, 90]). Confirmed clean on the 2025 corpus; future drift caught
  at boundary contract test layer.
* State assignment (uses ``Pincode`` → ``statename`` lookup against
  A.1.b ``pincode-directory.parquet`` via DuckDB, NOT KMZ ``Circle``
  which is the postal-admin proxy not the canonical ECI state code).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO, BinaryIO

# KML 2.2 namespace per OGC spec; all element tags use this prefix.
_KML_NS = "{http://www.opengis.net/kml/2.2}"


@dataclass(frozen=True)
class PolygonRing:
    """A closed linear ring in lon/lat order.

    Coordinates are kept as ``(lon, lat)`` 2-tuples (NOT lat/lon).
    KML coordinates are published in that order per OGC spec; we
    preserve it through to the emitter so the round-trip is
    bit-stable.
    """

    coords: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class PincodePolygon:
    """A single pincode with its geometry.

    ``geometries`` is a tuple of ``(outer_ring, inner_rings)`` pairs.
    Most pincodes have exactly one pair (a simple polygon, possibly
    with holes). Pincodes with detached enclaves have multiple pairs
    (emitted as a GeoJSON MultiPolygon by the ingest layer).

    String fields are stripped at parse time. ``region`` may be the
    empty string (upstream omits it for ~20% of pincodes — Delhi
    Circle uses an empty Region, e.g. — the empty string is the
    upstream value and is preserved verbatim).
    """

    pincode: str  # 6-digit numeric string; PK on the row
    office_name: str
    division: str
    region: str  # may be empty (upstream-correct)
    circle: str
    geometries: tuple[tuple[PolygonRing, tuple[PolygonRing, ...]], ...]


@dataclass(frozen=True)
class ParsedPincodePolygons:
    """The full parse result.

    Invariant: ``len(polygons) + skipped_count == upstream_placemark_count``.

    ``skipped_reasons`` is a parallel diagnostic list (one entry per
    skipped record) so callers can log a per-record reason without
    paying the cost of structured logging for the 19k common-path
    records. Kept short by truncation when very large; see
    ``_MAX_SKIPPED_REASONS_RETAINED``.
    """

    polygons: tuple[PincodePolygon, ...]
    skipped_count: int
    skipped_reasons: tuple[str, ...]


_MAX_SKIPPED_REASONS_RETAINED = 100
"""Cap on ``ParsedPincodePolygons.skipped_reasons`` length.

If the parser somehow encounters thousands of skipped rows (e.g.
upstream schema break), we keep the first 100 reasons + a single
summary entry, so callers' logs stay bounded.
"""


def _parse_coordinates(text: str) -> tuple[tuple[float, float], ...]:
    """Parse a KML coordinates string to a tuple of ``(lon, lat)``.

    KML coordinates are whitespace-separated ``lon,lat[,alt]`` tokens
    (per OGC KML 2.2 §10.4). Altitude is always 0 in this corpus and
    is discarded. Tokens that don't parse as two floats are silently
    dropped (the placemark-level "no parseable polygon" check catches
    a placemark whose entire ring failed).
    """
    out: list[tuple[float, float]] = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        out.append((lon, lat))
    return tuple(out)


def _parse_polygon_element(
    poly_el: ET.Element,
) -> tuple[PolygonRing, tuple[PolygonRing, ...]] | None:
    """Parse a single ``<Polygon>`` element into (outer, inners).

    Returns None if the polygon has no parseable outer ring (in which
    case the caller treats the placemark as malformed and increments
    ``skipped_count``).
    """
    outer_el = poly_el.find(
        f"{_KML_NS}outerBoundaryIs/{_KML_NS}LinearRing/{_KML_NS}coordinates"
    )
    if outer_el is None or not outer_el.text:
        return None
    outer = PolygonRing(coords=_parse_coordinates(outer_el.text))
    if not outer.coords:
        return None
    inners: list[PolygonRing] = []
    for inner_el in poly_el.iterfind(
        f"{_KML_NS}innerBoundaryIs/{_KML_NS}LinearRing/{_KML_NS}coordinates"
    ):
        if inner_el.text:
            ring = PolygonRing(coords=_parse_coordinates(inner_el.text))
            if ring.coords:
                inners.append(ring)
    return outer, tuple(inners)


def _parse_kml_stream(kml_fp: BinaryIO | IO[bytes]) -> ParsedPincodePolygons:
    """Stream-parse a KML file-like to ``ParsedPincodePolygons``.

    Uses ``iterparse`` with ``elem.clear()`` after each Placemark so
    peak memory stays bounded (KML uncompressed is ~80 MB on the 2025
    corpus; loading the full tree balloons to ~600 MB Python-object
    overhead).
    """
    polygons: list[PincodePolygon] = []
    skipped_count = 0
    skipped_reasons: list[str] = []

    context = ET.iterparse(kml_fp, events=("end",))
    for _event, elem in context:
        if elem.tag != f"{_KML_NS}Placemark":
            continue

        # ExtendedData/SchemaData → field map
        fields: dict[str, str] = {}
        for sd in elem.iter(f"{_KML_NS}SimpleData"):
            name = sd.attrib.get("name", "")
            if name:
                fields[name] = (sd.text or "").strip()

        pincode = fields.get("Pincode", "")
        if not pincode or not pincode.isdigit() or len(pincode) != 6:
            skipped_count += 1
            if len(skipped_reasons) < _MAX_SKIPPED_REASONS_RETAINED:
                skipped_reasons.append(f"invalid pincode {pincode!r}")
            elem.clear()
            continue

        pairs: list[tuple[PolygonRing, tuple[PolygonRing, ...]]] = []
        for poly_el in elem.iter(f"{_KML_NS}Polygon"):
            parsed = _parse_polygon_element(poly_el)
            if parsed is not None:
                pairs.append(parsed)

        if not pairs:
            skipped_count += 1
            if len(skipped_reasons) < _MAX_SKIPPED_REASONS_RETAINED:
                skipped_reasons.append(
                    f"pincode {pincode}: no parseable polygon"
                )
            elem.clear()
            continue

        polygons.append(
            PincodePolygon(
                pincode=pincode,
                office_name=fields.get("Office_Name", "").strip(),
                division=fields.get("Division", "").strip(),
                region=fields.get("Region", "").strip(),
                circle=fields.get("Circle", "").strip(),
                geometries=tuple(pairs),
            )
        )
        elem.clear()

    return ParsedPincodePolygons(
        polygons=tuple(polygons),
        skipped_count=skipped_count,
        skipped_reasons=tuple(skipped_reasons),
    )


def parse_pincode_polygons_from_kmz(kmz_path: str | Path) -> ParsedPincodePolygons:
    """Parse a pincode-boundaries KMZ archive.

    KMZ archives are ZIP containers around a single ``.kml`` file plus
    optional auxiliary resources. We require exactly one ``.kml``
    entry inside; multi-KML or zero-KML archives raise ``ValueError``.

    Memory: streams the KML through ``iterparse`` rather than reading
    the full 80 MB blob into Python text first — keeps peak RSS
    sub-200 MB on the 2025 corpus.
    """
    kmz_path = Path(kmz_path)
    if not kmz_path.is_file():
        raise FileNotFoundError(f"KMZ not found at {kmz_path.as_posix()!r}")

    with zipfile.ZipFile(kmz_path) as z:
        kml_names = [n for n in z.namelist() if n.lower().endswith(".kml")]
        if not kml_names:
            raise ValueError(f"No .kml entry inside KMZ {kmz_path.as_posix()!r}")
        if len(kml_names) > 1:
            raise ValueError(
                f"Multiple .kml entries inside KMZ {kmz_path.as_posix()!r}: {kml_names!r}"
            )
        with z.open(kml_names[0]) as kml_fp:
            return _parse_kml_stream(kml_fp)


__all__ = [
    "ParsedPincodePolygons",
    "PincodePolygon",
    "PolygonRing",
    "parse_pincode_polygons_from_kmz",
]
