"""Tier-A tests for the pincode-polygon ingest (Phase A.2).

CLAUDE.md §10: NO real-corpus walks. Every test builds a mini KMZ +
mini directory.parquet + mini entities.parquet under ``tmp_path`` and
runs the full ingest end-to-end against those.

Coverage:
  - end-to-end ingest writes one shard per assigned state + ledger rows.
  - per-state pincode counts match input.
  - alias resolution: DELHI -> delhi; JAMMU AND KASHMIR -> jammu-and-kashmir;
    THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU -> dadra-and-nagar-haveli-and-daman-and-diu.
  - unkeyed pincodes (no directory row OR NULL statename) routed to
    the synthetic ``scope=unkeyed`` ledger row + empty shard, with
    the pincode list in ``unkeyed_keys_json``.
  - zero unkeyed → no synthetic row written.
  - GeoJSON shard shape: FeatureCollection sorted by pincode, each
    feature carries the 6 fixed property keys + Polygon/MultiPolygon
    geometry with coordinates rounded to COORD_PRECISION_DIGITS.
  - boundary_layer.csv rows pass the schema invariant
    (original = retained + unkeyed) and carry the right source_id FK.
  - byte-determinism: re-running against byte-identical input yields
    byte-identical shards + ledger.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
import csv as _csv
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.boundary_layers_seed import (
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BOUNDARY_SOURCES,
)
from yen_gov.canonical.adapters.datagovin_ogd.ingest_pincode_polygons import (
    COORD_PRECISION_DIGITS,
    PINCODE_POLYGONS_SOURCE_ID,
    IngestResult,
    ingest_pincode_polygons,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


_KML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
)
_KML_FOOTER = "</Document></kml>\n"


def _placemark(pincode: str, office: str, division: str, region: str,
               circle: str, coords: str) -> str:
    return (
        "<Placemark>"
        "<ExtendedData>"
        f'<SchemaData schemaUrl="#x">'
        f'<SimpleData name="Pincode">{pincode}</SimpleData>'
        f'<SimpleData name="Office_Name">{office}</SimpleData>'
        f'<SimpleData name="Division">{division}</SimpleData>'
        f'<SimpleData name="Region">{region}</SimpleData>'
        f'<SimpleData name="Circle">{circle}</SimpleData>'
        "</SchemaData>"
        "</ExtendedData>"
        "<Polygon><outerBoundaryIs><LinearRing>"
        f"<coordinates>{coords}</coordinates>"
        "</LinearRing></outerBoundaryIs></Polygon>"
        "</Placemark>"
    )


def _build_kmz(tmp_path: Path, placemarks: list[str]) -> Path:
    kml = (_KML_HEADER + "".join(placemarks) + _KML_FOOTER).encode("utf-8")
    kmz = tmp_path / "fixture.kmz"
    with zipfile.ZipFile(kmz, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("fixture.kml", kml)
    return kmz


def _build_directory_parquet(
    tmp_path: Path, rows: list[tuple[str, str | None]]
) -> Path:
    """Build a minimal pincode directory CSV with (pincode, statename) rows.

    Only the two columns the ingest reads are populated; the rest of
    the A.1.b schema is irrelevant here because the ingest's
    ``_build_pincode_to_state_lookup`` only ``SELECT pincode,
    MIN(statename) FROM ... GROUP BY pincode``.

    G8 (2026-06-08): the on-disk pincode directory moved from
    ``reference/in/pincodes/pincode-directory.parquet`` to
    ``data/entities/pincode.csv`` and the reader switched to typed
    ``read_csv(columns=...)`` per plan-doc section 21.2. The fixture
    function name is preserved for back-compat with the rest of this
    test module; it now writes a CSV under tmp_path.
    """
    out = tmp_path / "pincode.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh, lineterminator="\n")
        w.writerow(["pincode", "statename"])
        for pincode, statename in rows:
            w.writerow([pincode, "" if statename is None else statename])
    return out


def _build_entities_parquet(
    tmp_path: Path, rows: list[tuple[str, str, str]]
) -> Path:
    """Build a minimal entities.parquet with (entity_id, entity_type, display_name)."""
    out = tmp_path / "entities.parquet"
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE e (entity_id VARCHAR, entity_type VARCHAR, display_name VARCHAR)"
        )
        con.executemany("INSERT INTO e VALUES (?, ?, ?)", rows)
        con.execute(f"COPY e TO '{out.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()
    return out


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# Four self-closing 4-vertex rings, one per fixture pincode.
_RING_TN = "80.24,13.04,0 80.25,13.04,0 80.25,13.05,0 80.24,13.05,0 80.24,13.04,0"
_RING_DEL = "77.21,28.61,0 77.22,28.61,0 77.22,28.62,0 77.21,28.62,0 77.21,28.61,0"
_RING_JK = "74.78,34.08,0 74.79,34.08,0 74.79,34.09,0 74.78,34.09,0 74.78,34.08,0"
_RING_DH = "72.84,20.27,0 72.85,20.27,0 72.85,20.28,0 72.84,20.28,0 72.84,20.27,0"
_RING_ORPHAN = "85.50,20.50,0 85.51,20.50,0 85.51,20.51,0 85.50,20.51,0 85.50,20.50,0"


_ENTITIES_FIXTURE = [
    ("IN-S22", "state", "Tamil Nadu"),
    ("IN-U05", "ut", "NCT of Delhi"),
    ("IN-U08", "ut", "Jammu and Kashmir (UT)"),
    ("IN-U03", "ut", "Dadra and Nagar Haveli and Daman and Diu"),
    # Decoy: a non-state entity that MUST be ignored by the lookup
    # (entity_type filter on state+ut).
    ("IN", "country", "India"),
]


def _build_standard_fixtures(
    tmp_path: Path,
    *,
    include_orphan: bool = True,
) -> tuple[Path, Path, Path, Path]:
    """Build the 4-or-5-pincode standard fixture set.

    Returns ``(kmz, directory_parquet, entities_parquet, datasets_root)``.
    """
    placemarks = [
        _placemark("600017", "T Nagar SO", "Chennai South", "Chennai",
                   "Tamilnadu", _RING_TN),
        _placemark("110001", "Connaught Place HO", "New Delhi Central",
                   "", "Delhi", _RING_DEL),  # empty Region (real-data shape)
        _placemark("190001", "Srinagar GPO", "Srinagar", "Kashmir",
                   "Jammukashmir", _RING_JK),
        _placemark("396210", "Silvassa SO", "Silvassa", "Silvassa",
                   "Maharashtra", _RING_DH),
    ]
    directory_rows: list[tuple[str, str | None]] = [
        ("600017", "TAMIL NADU"),
        ("110001", "DELHI"),
        ("190001", "JAMMU AND KASHMIR"),
        ("396210", "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU"),
    ]
    if include_orphan:
        placemarks.append(
            _placemark("999999", "Ghost SO", "Ghost", "Ghost", "Ghost",
                       _RING_ORPHAN)
        )
        # NB: NO directory row for 999999 — it lands in unkeyed.

    kmz = _build_kmz(tmp_path, placemarks)
    directory_parquet = _build_directory_parquet(tmp_path, directory_rows)
    entities_parquet = _build_entities_parquet(tmp_path, _ENTITIES_FIXTURE)
    datasets_root = tmp_path / "datasets"
    datasets_root.mkdir(parents=True, exist_ok=True)
    return kmz, directory_parquet, entities_parquet, datasets_root


def _run_ingest(
    kmz: Path, directory: Path, entities: Path, datasets_root: Path
) -> IngestResult:
    return ingest_pincode_polygons(
        input_kmz=kmz,
        output_dir=datasets_root / "boundaries" / "in" / "postal",
        directory_parquet=directory,
        entities_parquet=entities,
        datasets_root=datasets_root,
    )


# ---------------------------------------------------------------------------
# Smoke + structural assertions
# ---------------------------------------------------------------------------


def test_ingest_writes_per_state_shards_and_ledger(tmp_path: Path) -> None:
    kmz, directory, entities, root = _build_standard_fixtures(tmp_path)
    result = _run_ingest(kmz, directory, entities, root)

    # 4 keyable pincodes → 4 per-state shards + 1 unkeyed shard.
    assert result.layer_count == 5
    assert result.unkeyed_count == 1
    assert sorted(result.per_state_counts.keys()) == [
        "dadra-and-nagar-haveli-and-daman-and-diu", "delhi", "jammu-and-kashmir", "tamil-nadu",
    ]
    for slug in ["tamil-nadu", "dadra-and-nagar-haveli-and-daman-and-diu", "delhi", "jammu-and-kashmir"]:
        assert result.per_state_counts[slug] == 1

    # On-disk shard tree.
    postal_root = root / "boundaries" / "in" / "postal"
    for slug in ["tamil-nadu", "dadra-and-nagar-haveli-and-daman-and-diu", "delhi", "jammu-and-kashmir"]:
        assert (postal_root / f"state={slug}" / "all.geojson").is_file()
    assert (postal_root / "scope=unkeyed" / "all.geojson").is_file()


def test_per_state_shard_geojson_shape_is_valid_featurecollection(
    tmp_path: Path,
) -> None:
    kmz, directory, entities, root = _build_standard_fixtures(
        tmp_path, include_orphan=False
    )
    _run_ingest(kmz, directory, entities, root)

    tn_shard = root / "boundaries" / "in" / "postal" / "state=tamil-nadu" / "all.geojson"
    fc = json.loads(tn_shard.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    feat = fc["features"][0]
    assert feat["type"] == "Feature"
    # Property keys in the fixed canonical order.
    assert list(feat["properties"].keys()) == [
        "pincode", "office_name", "division", "region", "circle", "source_id",
    ]
    assert feat["properties"]["pincode"] == "600017"
    assert feat["properties"]["source_id"] == PINCODE_POLYGONS_SOURCE_ID
    assert feat["geometry"]["type"] == "Polygon"
    # Coordinates rounded to COORD_PRECISION_DIGITS — verify the first
    # vertex matches the rounded-input.
    assert feat["geometry"]["coordinates"][0][0] == [
        round(80.24, COORD_PRECISION_DIGITS),
        round(13.04, COORD_PRECISION_DIGITS),
    ]


def test_empty_region_round_trips_as_empty_string(tmp_path: Path) -> None:
    kmz, directory, entities, root = _build_standard_fixtures(
        tmp_path, include_orphan=False
    )
    _run_ingest(kmz, directory, entities, root)
    del_shard = root / "boundaries" / "in" / "postal" / "state=delhi" / "all.geojson"
    fc = json.loads(del_shard.read_text(encoding="utf-8"))
    assert fc["features"][0]["properties"]["region"] == ""


# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "directory_statename,expected_slug",
    [
        ("DELHI", "delhi"),
        ("JAMMU AND KASHMIR", "jammu-and-kashmir"),
        ("THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU", "dadra-and-nagar-haveli-and-daman-and-diu"),
        # Canonical match path (no alias needed) — proves the alias map
        # composes with the entity-display-name lookup.
        ("TAMIL NADU", "tamil-nadu"),
    ],
)
def test_state_assignment_handles_aliases_and_canonical_names(
    tmp_path: Path, directory_statename: str, expected_slug: str
) -> None:
    kmz = _build_kmz(tmp_path, [
        _placemark("123456", "Office", "Div", "Region", "Circle", _RING_TN),
    ])
    directory = _build_directory_parquet(tmp_path, [("123456", directory_statename)])
    entities = _build_entities_parquet(tmp_path, _ENTITIES_FIXTURE)
    root = tmp_path / "datasets"
    root.mkdir(parents=True, exist_ok=True)

    result = _run_ingest(kmz, directory, entities, root)
    assert result.unkeyed_count == 0
    assert list(result.per_state_counts.keys()) == [expected_slug]


# ---------------------------------------------------------------------------
# Unkeyed handling
# ---------------------------------------------------------------------------


def test_unkeyed_shard_is_empty_featurecollection_with_pincode_list_in_ledger(
    tmp_path: Path,
) -> None:
    kmz, directory, entities, root = _build_standard_fixtures(tmp_path)
    _run_ingest(kmz, directory, entities, root)

    # On-disk empty FeatureCollection.
    unkeyed_shard = root / "boundaries" / "in" / "postal" / "scope=unkeyed" / "all.geojson"
    fc = json.loads(unkeyed_shard.read_text(encoding="utf-8"))
    assert fc == {"type": "FeatureCollection", "features": []}

    # Ledger row carries the pincode list in unkeyed_keys_json.
    ledger = root / "data" / "entities" / "boundary_layer.csv"
    with ledger.open(encoding="utf-8", newline="") as fh:
        rows = list(_csv.DictReader(fh))
    matches = [
        r
        for r in rows
        if r["layer_id"] == "boundaries.in.postal.scope=unkeyed"
    ]
    assert len(matches) == 1
    row = matches[0]
    assert (
        int(row["original_feature_count"]),
        int(row["retained_feature_count"]),
        int(row["unkeyed_count"]),
    ) == (1, 0, 1)
    assert json.loads(row["unkeyed_keys_json"]) == ["999999"]


def test_no_synthetic_row_when_every_pincode_keys(tmp_path: Path) -> None:
    kmz, directory, entities, root = _build_standard_fixtures(
        tmp_path, include_orphan=False
    )
    result = _run_ingest(kmz, directory, entities, root)

    assert result.unkeyed_count == 0
    # 4 per-state rows only — no synthetic.
    assert result.layer_count == 4
    unkeyed_shard = root / "boundaries" / "in" / "postal" / "scope=unkeyed" / "all.geojson"
    assert not unkeyed_shard.exists()


def test_null_statename_in_directory_routes_to_unkeyed(tmp_path: Path) -> None:
    kmz = _build_kmz(tmp_path, [
        _placemark("777777", "Office", "Div", "Region", "Circle", _RING_TN),
    ])
    directory = _build_directory_parquet(tmp_path, [("777777", None)])
    entities = _build_entities_parquet(tmp_path, _ENTITIES_FIXTURE)
    root = tmp_path / "datasets"
    root.mkdir(parents=True, exist_ok=True)

    result = _run_ingest(kmz, directory, entities, root)
    assert result.unkeyed_count == 1
    assert result.unkeyed_pincodes == ("777777",)
    assert result.per_state_counts == {}


# ---------------------------------------------------------------------------
# Ledger shape
# ---------------------------------------------------------------------------


def test_boundary_layers_rows_pass_denominator_invariant(tmp_path: Path) -> None:
    """compile_to_csv raises on original != retained + unkeyed.
    A successful ingest therefore proves the invariant held for every
    emitted row — but read back from CSV and double-check anyway.
    """
    kmz, directory, entities, root = _build_standard_fixtures(tmp_path)
    _run_ingest(kmz, directory, entities, root)

    ledger = root / "data" / "entities" / "boundary_layer.csv"
    with ledger.open(encoding="utf-8", newline="") as fh:
        all_rows = list(_csv.DictReader(fh))
    rows = [
        (
            r["layer_id"],
            int(r["original_feature_count"]),
            int(r["retained_feature_count"]),
            int(r["unkeyed_count"]),
            r["source_id"],
        )
        for r in all_rows
        if r["layer_id"].startswith("boundaries.in.postal.")
    ]

    assert len(rows) == 5
    for layer_id, original, retained, unkeyed, sid in rows:
        assert original == retained + unkeyed, layer_id
        assert sid == PINCODE_POLYGONS_SOURCE_ID, layer_id


def test_pincode_polygons_source_id_resolves_via_nickname() -> None:
    """The ingest constant must exactly match the nickname-derived
    source_id from the BOUNDARY_SOURCES seed. A drift here means
    layer rows would point at a stale or absent FK target.
    """
    assert (
        PINCODE_POLYGONS_SOURCE_ID
        == BOUNDARY_SOURCE_ID_BY_NICKNAME["datagovin_post_pincode_polygons_2025"]
    )
    # And the row exists in the seeded BOUNDARY_SOURCES.
    assert any(s.source_id == PINCODE_POLYGONS_SOURCE_ID for s in BOUNDARY_SOURCES)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_reingest_is_byte_identical(tmp_path: Path) -> None:
    kmz, directory, entities, root = _build_standard_fixtures(tmp_path)
    _run_ingest(kmz, directory, entities, root)

    shards = sorted(
        (root / "boundaries" / "in" / "postal").rglob("all.geojson")
    )
    ledger = root / "data" / "entities" / "boundary_layer.csv"

    hashes_before = {p.relative_to(root).as_posix(): _sha256(p) for p in shards}
    ledger_before = _sha256(ledger)

    _run_ingest(kmz, directory, entities, root)

    hashes_after = {p.relative_to(root).as_posix(): _sha256(p) for p in shards}
    assert hashes_before == hashes_after, "shard bytes drifted across re-runs"
    assert _sha256(ledger) == ledger_before, "boundary_layer.csv bytes drifted"
