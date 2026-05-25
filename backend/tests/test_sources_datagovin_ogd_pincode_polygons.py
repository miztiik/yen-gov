"""Tests for the data.gov.in pincode-polygon KMZ pure parser (Phase A.2).

CLAUDE.md §10: no real-corpus walks. All KMZ fixtures are built
in-memory from inline KML byte literals.

Coverage:
  - happy path: 3-pincode fixture (simple polygon, polygon with hole,
    MultiGeometry) → 3 PincodePolygons with the expected shapes.
  - empty Region preserved as the empty string (upstream-correct;
    ~20% of the real 2025 corpus has empty Region).
  - whitespace stripping on string fields.
  - invalid pincode (5-digit, alpha-bearing, missing) → skipped + counted.
  - placemark with no parseable polygon → skipped + counted.
  - skipped_reasons capped at _MAX_SKIPPED_REASONS_RETAINED.
  - coordinate parsing: lon/lat order preserved (NOT lat/lon),
    altitude tokens discarded.
  - file-not-found raises FileNotFoundError.
  - zero-KML KMZ raises ValueError.
  - multi-KML KMZ raises ValueError.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from yen_gov.sources.datagovin_ogd.pincode_polygons import (
    _MAX_SKIPPED_REASONS_RETAINED,
    ParsedPincodePolygons,
    PincodePolygon,
    parse_pincode_polygons_from_kmz,
)


# ---------------------------------------------------------------------------
# KML fixture builder
# ---------------------------------------------------------------------------


_KML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
    "  <Document>\n"
    '    <Schema name="pincodes" id="pincodes">\n'
    '      <SimpleField name="Pincode" type="string"/>\n'
    '      <SimpleField name="Office_Name" type="string"/>\n'
    '      <SimpleField name="Division" type="string"/>\n'
    '      <SimpleField name="Region" type="string"/>\n'
    '      <SimpleField name="Circle" type="string"/>\n'
    "    </Schema>\n"
)
_KML_FOOTER = "  </Document>\n</kml>\n"


def _placemark(
    pincode: str,
    office: str,
    division: str,
    region: str,
    circle: str,
    geometry_xml: str,
) -> str:
    """Build one <Placemark> with ExtendedData + the given geometry XML."""
    return (
        "    <Placemark>\n"
        "      <ExtendedData>\n"
        '        <SchemaData schemaUrl="#pincodes">\n'
        f'          <SimpleData name="Pincode">{pincode}</SimpleData>\n'
        f'          <SimpleData name="Office_Name">{office}</SimpleData>\n'
        f'          <SimpleData name="Division">{division}</SimpleData>\n'
        f'          <SimpleData name="Region">{region}</SimpleData>\n'
        f'          <SimpleData name="Circle">{circle}</SimpleData>\n'
        "        </SchemaData>\n"
        "      </ExtendedData>\n"
        f"      {geometry_xml}\n"
        "    </Placemark>\n"
    )


def _simple_polygon(coords: str) -> str:
    return (
        "<Polygon>\n"
        "        <outerBoundaryIs>\n"
        f"          <LinearRing><coordinates>{coords}</coordinates></LinearRing>\n"
        "        </outerBoundaryIs>\n"
        "      </Polygon>"
    )


def _polygon_with_hole(outer: str, inner: str) -> str:
    return (
        "<Polygon>\n"
        "        <outerBoundaryIs>\n"
        f"          <LinearRing><coordinates>{outer}</coordinates></LinearRing>\n"
        "        </outerBoundaryIs>\n"
        "        <innerBoundaryIs>\n"
        f"          <LinearRing><coordinates>{inner}</coordinates></LinearRing>\n"
        "        </innerBoundaryIs>\n"
        "      </Polygon>"
    )


def _multi_polygon(coords_a: str, coords_b: str) -> str:
    return (
        "<MultiGeometry>\n"
        f"        {_simple_polygon(coords_a)}\n"
        f"        {_simple_polygon(coords_b)}\n"
        "      </MultiGeometry>"
    )


def _build_kml(*placemark_xml: str) -> bytes:
    return (_KML_HEADER + "".join(placemark_xml) + _KML_FOOTER).encode("utf-8")


def _wrap_kmz(tmp_path: Path, kml_bytes: bytes, *, kml_name: str = "pincodes.kml") -> Path:
    kmz = tmp_path / "fixture.kmz"
    with zipfile.ZipFile(kmz, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(kml_name, kml_bytes)
    return kmz


def _wrap_kmz_with(tmp_path: Path, entries: dict[str, bytes], *, name: str = "fixture.kmz") -> Path:
    kmz = tmp_path / name
    with zipfile.ZipFile(kmz, "w", zipfile.ZIP_DEFLATED) as z:
        for entry_name, entry_bytes in entries.items():
            z.writestr(entry_name, entry_bytes)
    return kmz


# A self-closing 4-vertex ring (last == first) — minimal valid GeoJSON-
# compatible polygon.
_RING_A = "77.0,12.0,0 77.1,12.0,0 77.1,12.1,0 77.0,12.1,0 77.0,12.0,0"
_RING_B = "78.0,13.0,0 78.1,13.0,0 78.1,13.1,0 78.0,13.1,0 78.0,13.0,0"
_OUTER_FOR_HOLE = "76.0,11.0,0 76.5,11.0,0 76.5,11.5,0 76.0,11.5,0 76.0,11.0,0"
_INNER_FOR_HOLE = "76.2,11.2,0 76.3,11.2,0 76.3,11.3,0 76.2,11.3,0 76.2,11.2,0"


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_happy_path_three_placemarks_yield_three_polygons(tmp_path: Path) -> None:
    kml = _build_kml(
        _placemark(
            "560038", "Indiranagar SO", "Bengaluru East", "Bengaluru",
            "Karnataka", _simple_polygon(_RING_A),
        ),
        _placemark(
            "600017", "T Nagar SO", "Chennai South", "Chennai",
            "Tamilnadu", _polygon_with_hole(_OUTER_FOR_HOLE, _INNER_FOR_HOLE),
        ),
        _placemark(
            "682001", "Fort Kochi SO", "Ernakulam", "Kochi",
            "Kerala", _multi_polygon(_RING_A, _RING_B),
        ),
    )
    kmz = _wrap_kmz(tmp_path, kml)
    parsed: ParsedPincodePolygons = parse_pincode_polygons_from_kmz(kmz)

    assert parsed.skipped_count == 0
    assert parsed.skipped_reasons == ()
    assert len(parsed.polygons) == 3
    # Input order is preserved.
    assert [p.pincode for p in parsed.polygons] == ["560038", "600017", "682001"]


def test_simple_polygon_has_one_geometry_pair_with_no_inner_rings(
    tmp_path: Path,
) -> None:
    kml = _build_kml(
        _placemark(
            "560038", "Indiranagar SO", "Bengaluru East", "Bengaluru",
            "Karnataka", _simple_polygon(_RING_A),
        )
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    poly = parsed.polygons[0]
    assert len(poly.geometries) == 1
    outer, inners = poly.geometries[0]
    assert inners == ()
    assert outer.coords[0] == (77.0, 12.0)
    assert outer.coords[-1] == (77.0, 12.0)  # closed ring


def test_polygon_with_hole_carries_one_inner_ring(tmp_path: Path) -> None:
    kml = _build_kml(
        _placemark(
            "600017", "T Nagar SO", "Chennai South", "Chennai",
            "Tamilnadu", _polygon_with_hole(_OUTER_FOR_HOLE, _INNER_FOR_HOLE),
        )
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    poly = parsed.polygons[0]
    assert len(poly.geometries) == 1
    outer, inners = poly.geometries[0]
    assert len(inners) == 1
    assert outer.coords[0] == (76.0, 11.0)
    assert inners[0].coords[0] == (76.2, 11.2)


def test_multigeometry_yields_multiple_geometry_pairs(tmp_path: Path) -> None:
    kml = _build_kml(
        _placemark(
            "682001", "Fort Kochi SO", "Ernakulam", "Kochi",
            "Kerala", _multi_polygon(_RING_A, _RING_B),
        )
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    poly = parsed.polygons[0]
    assert len(poly.geometries) == 2
    first_outer, _ = poly.geometries[0]
    second_outer, _ = poly.geometries[1]
    assert first_outer.coords[0] == (77.0, 12.0)
    assert second_outer.coords[0] == (78.0, 13.0)


# ---------------------------------------------------------------------------
# String-field invariants
# ---------------------------------------------------------------------------


def test_empty_region_preserved_as_empty_string(tmp_path: Path) -> None:
    # ~20% of the real 2025 corpus has empty <Region/>; preserve verbatim
    # rather than coercing to None.
    kml = _build_kml(
        _placemark(
            "110001", "Connaught Place HO", "New Delhi Central", "",
            "Delhi", _simple_polygon(_RING_A),
        )
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    assert parsed.polygons[0].region == ""


def test_string_fields_are_whitespace_stripped(tmp_path: Path) -> None:
    kml = _build_kml(
        _placemark(
            "560038", "  Indiranagar SO  ", "  Bengaluru East ",
            " Bengaluru ", "  Karnataka  ", _simple_polygon(_RING_A),
        )
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    poly = parsed.polygons[0]
    assert poly.office_name == "Indiranagar SO"
    assert poly.division == "Bengaluru East"
    assert poly.region == "Bengaluru"
    assert poly.circle == "Karnataka"


# ---------------------------------------------------------------------------
# Skipped-record paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_pincode", ["12345", "1234567", "60001A", ""])
def test_invalid_pincodes_are_skipped_and_counted(
    tmp_path: Path, bad_pincode: str
) -> None:
    kml = _build_kml(
        _placemark(
            "560038", "Indiranagar SO", "Bengaluru East", "Bengaluru",
            "Karnataka", _simple_polygon(_RING_A),
        ),
        _placemark(
            bad_pincode, "Bad SO", "Bad Div", "Bad Region",
            "Bad Circle", _simple_polygon(_RING_A),
        ),
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    assert len(parsed.polygons) == 1
    assert parsed.skipped_count == 1
    assert any(bad_pincode and bad_pincode in r for r in parsed.skipped_reasons) or (
        not bad_pincode and any("''" in r for r in parsed.skipped_reasons)
    )


def test_placemark_with_no_parseable_polygon_is_skipped(tmp_path: Path) -> None:
    kml = _build_kml(
        _placemark(
            "560038", "Indiranagar SO", "Bengaluru East", "Bengaluru",
            "Karnataka", "<Point><coordinates>77.0,12.0,0</coordinates></Point>",
        )
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    assert parsed.polygons == ()
    assert parsed.skipped_count == 1
    assert any("no parseable polygon" in r for r in parsed.skipped_reasons)


def test_skipped_reasons_are_capped(tmp_path: Path) -> None:
    # Generate _MAX_SKIPPED_REASONS_RETAINED + 5 bad placemarks; the
    # cap holds at the limit so log volume stays bounded.
    n = _MAX_SKIPPED_REASONS_RETAINED + 5
    parts = [
        _placemark(
            "00000A",  # invalid (alpha-bearing)
            f"BadSO_{i}", "Bad Div", "Bad Region", "Bad Circle",
            _simple_polygon(_RING_A),
        )
        for i in range(n)
    ]
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, _build_kml(*parts)))
    assert parsed.skipped_count == n
    assert len(parsed.skipped_reasons) == _MAX_SKIPPED_REASONS_RETAINED


# ---------------------------------------------------------------------------
# Coordinate-parsing invariants
# ---------------------------------------------------------------------------


def test_coords_preserve_lon_lat_order_and_discard_altitude(tmp_path: Path) -> None:
    # First token: lon=85.5 lat=20.5 alt=99 — confirm we keep (85.5, 20.5)
    # and NOT (20.5, 85.5).
    coords = "85.5,20.5,99 85.6,20.5,99 85.6,20.6,99 85.5,20.6,99 85.5,20.5,99"
    kml = _build_kml(
        _placemark(
            "751001", "Bhubaneswar GPO", "Bhubaneswar", "Bhubaneswar",
            "Odisha", _simple_polygon(coords),
        )
    )
    parsed = parse_pincode_polygons_from_kmz(_wrap_kmz(tmp_path, kml))
    outer, _ = parsed.polygons[0].geometries[0]
    assert outer.coords[0] == (85.5, 20.5)


# ---------------------------------------------------------------------------
# Archive-shape errors
# ---------------------------------------------------------------------------


def test_missing_kmz_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="KMZ not found"):
        parse_pincode_polygons_from_kmz(tmp_path / "absent.kmz")


def test_zero_kml_inside_kmz_raises(tmp_path: Path) -> None:
    kmz = _wrap_kmz_with(tmp_path, {"readme.txt": b"only a readme; no KML."})
    with pytest.raises(ValueError, match="No .kml entry"):
        parse_pincode_polygons_from_kmz(kmz)


def test_multi_kml_inside_kmz_raises(tmp_path: Path) -> None:
    kml_a = _build_kml(
        _placemark(
            "560038", "A SO", "A Div", "A Region", "A Circle",
            _simple_polygon(_RING_A),
        )
    )
    kml_b = _build_kml(
        _placemark(
            "600017", "B SO", "B Div", "B Region", "B Circle",
            _simple_polygon(_RING_B),
        )
    )
    kmz = _wrap_kmz_with(tmp_path, {"a.kml": kml_a, "b.kml": kml_b})
    with pytest.raises(ValueError, match="Multiple .kml entries"):
        parse_pincode_polygons_from_kmz(kmz)
