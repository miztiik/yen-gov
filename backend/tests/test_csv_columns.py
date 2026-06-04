"""Unit tests for the CSV column-contract loader (sub-plan B1.1).

Gate: schema-of-schemas-valid. Asserts:
- the shipped ``datasets/data/_schema/columns.json`` validates against
  ``columns.schema.json``;
- every file class declared in the spec (``csv-column-contract.md`` sections
  3-4) is present with the expected pk-column set;
- closed enums match the spec;
- ``file_class_for`` resolves both exact catalogue paths and wildcard
  datapoint / election paths;
- structural rejections (bad dtype, ``__`` in column name, unknown extra key)
  fail loading via the schema-of-schemas.

No mocks; the cache is bypassed by passing fixture paths into ``load_columns``.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from yen_gov.canonical.csv_columns import (
    Column,
    FileClass,
    file_class_for,
    load_columns,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COLUMNS_PATH = REPO_ROOT / "datasets" / "data" / "_schema" / "columns.json"
COLUMNS_SCHEMA_PATH = REPO_ROOT / "datasets" / "data" / "_schema" / "columns.schema.json"


@pytest.fixture
def contract():
    # Bypass the lru_cache by passing explicit paths.
    return load_columns(path=COLUMNS_PATH, schema_path=COLUMNS_SCHEMA_PATH)


def test_shipped_columns_validates_against_schema_of_schemas(contract):
    # If load_columns returned, jsonschema.validate already passed. Re-assert
    # the artifact's own self-declared $schema points at the sibling validator.
    raw = json.loads(COLUMNS_PATH.read_text(encoding="utf-8"))
    assert raw["$schema"] == "./columns.schema.json"
    assert raw["$schema_version"] == "1.0"
    assert len(contract.file_classes) >= 14


@pytest.mark.parametrize(
    ("glob", "expected_pk"),
    [
        ("datasets/data/variables.csv", ("indicator_id",)),
        ("datasets/data/concepts.csv", ("concept_id",)),
        ("datasets/data/topics.csv", ("topic",)),
        ("datasets/data/entities/geo.csv", ("entity_id",)),
        ("datasets/data/entities/electoral.csv", ("entity_id",)),
        (
            "datasets/data/entities/electoral_lgd_xwalk.csv",
            ("electoral_id", "lgd_district_id", "delim_year"),
        ),
        ("datasets/data/entities/party.csv", ("party_id",)),
        ("datasets/data/entities/source.csv", ("source_id",)),
        ("datasets/data/datapoints/geo/*.csv", ("entity_id", "time")),
        ("datasets/data/datapoints/electoral/*.csv", ("entity_id", "time")),
    ],
)
def test_pk_columns_match_spec(contract, glob, expected_pk):
    fc = contract.for_glob(glob)
    assert tuple(c.name for c in fc.pk_columns) == expected_pk


def test_datapoints_geo_core_columns_match_spec(contract):
    fc = contract.for_glob("datasets/data/datapoints/geo/*.csv")
    names = tuple(c.name for c in fc.columns)
    assert names == ("entity_id", "time", "value", "source_id")
    assert fc.column("source_id").nullable is False
    assert fc.column("source_id").fk == "datasets/data/entities/source.csv.source_id"
    assert fc.column("value").nullable is True


def test_source_csv_has_exactly_five_columns_per_plan_section_7(contract):
    fc = contract.for_glob("datasets/data/entities/source.csv")
    names = [c.name for c in fc.columns]
    assert names == ["source_id", "owner", "title", "vintage", "url"]
    # Only PK is required.
    assert fc.column("source_id").nullable is False
    for optional in ("owner", "title", "vintage", "url"):
        assert fc.column(optional).nullable is True


def test_closed_enums_match_spec(contract):
    geo = contract.for_glob("datasets/data/entities/geo.csv")
    assert geo.column("entity_kind").enum == (
        "country", "state", "district", "sub-district", "village",
    )
    electoral = contract.for_glob("datasets/data/entities/electoral.csv")
    assert electoral.column("entity_kind").enum == ("ac", "pc")
    xwalk = contract.for_glob("datasets/data/entities/electoral_lgd_xwalk.csv")
    assert xwalk.column("overlap_kind").enum == ("wholly_inside", "majority", "partial")
    concepts = contract.for_glob("datasets/data/concepts.csv")
    assert concepts.column("normalisation").enum == (
        "absolute", "per_capita", "share", "rate", "index",
    )


def test_parliament_summary_carries_mandatory_state_column(contract):
    fc = contract.for_glob("datasets/elections/parliament/election=*/summary.csv")
    state = fc.column("state")
    assert state.nullable is False, "plan section 23.4: state is MANDATORY on PC files"


def test_file_class_for_resolves_exact_catalogue_path(contract):
    fc = file_class_for("datasets/data/variables.csv", contract=contract)
    assert fc.glob == "datasets/data/variables.csv"


def test_file_class_for_resolves_datapoint_wildcard(contract):
    fc = file_class_for(
        "datasets/data/datapoints/geo/literacy-rate-pct-total.csv",
        contract=contract,
    )
    assert fc.glob == "datasets/data/datapoints/geo/*.csv"


def test_file_class_for_resolves_assembly_election_wildcard(contract):
    fc = file_class_for(
        "datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
        contract=contract,
    )
    assert fc.glob == "datasets/elections/assembly/state=*/election=*/candidacies.csv"


def test_file_class_for_rejects_unknown_path(contract):
    with pytest.raises(ValueError, match="no file class matches"):
        file_class_for("datasets/data/datapoints/cosmic/foo.csv", contract=contract)


def test_file_class_for_rejects_backslash_path(contract):
    with pytest.raises(ValueError, match="POSIX"):
        file_class_for(r"datasets\data\variables.csv", contract=contract)


def _write_fixture(tmp_path: Path, payload: dict) -> tuple[Path, Path]:
    schema_dst = tmp_path / "columns.schema.json"
    schema_dst.write_text(COLUMNS_SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    columns_dst = tmp_path / "columns.json"
    columns_dst.write_text(json.dumps(payload), encoding="utf-8")
    return columns_dst, schema_dst


def _minimal_payload() -> dict:
    return {
        "$schema": "./columns.schema.json",
        "$schema_version": "1.0",
        "file_classes": {
            "datasets/data/variables.csv": {
                "columns": [
                    {"name": "indicator_id", "dtype": "string", "nullable": False, "pk": True},
                ],
            },
        },
    }


def test_schema_of_schemas_rejects_unknown_dtype(tmp_path):
    payload = _minimal_payload()
    payload["file_classes"]["datasets/data/variables.csv"]["columns"][0]["dtype"] = "datetime"
    columns_dst, schema_dst = _write_fixture(tmp_path, payload)
    with pytest.raises(jsonschema.ValidationError):
        load_columns.__wrapped__(path=columns_dst, schema_path=schema_dst)


def test_schema_of_schemas_rejects_double_underscore_column_name(tmp_path):
    payload = _minimal_payload()
    payload["file_classes"]["datasets/data/variables.csv"]["columns"][0]["name"] = "bad__name"
    columns_dst, schema_dst = _write_fixture(tmp_path, payload)
    with pytest.raises(jsonschema.ValidationError):
        load_columns.__wrapped__(path=columns_dst, schema_path=schema_dst)


def test_schema_of_schemas_rejects_extra_column_key(tmp_path):
    payload = _minimal_payload()
    payload["file_classes"]["datasets/data/variables.csv"]["columns"][0]["renamed_from"] = "old"
    columns_dst, schema_dst = _write_fixture(tmp_path, payload)
    with pytest.raises(jsonschema.ValidationError):
        load_columns.__wrapped__(path=columns_dst, schema_path=schema_dst)


def test_schema_of_schemas_rejects_non_csv_file_class_glob(tmp_path):
    payload = _minimal_payload()
    payload["file_classes"]["datasets/data/foo.parquet"] = payload["file_classes"].pop(
        "datasets/data/variables.csv"
    )
    columns_dst, schema_dst = _write_fixture(tmp_path, payload)
    with pytest.raises(jsonschema.ValidationError):
        load_columns.__wrapped__(path=columns_dst, schema_path=schema_dst)


def test_column_dataclass_is_frozen():
    col = Column(name="a", dtype="string", nullable=False)
    with pytest.raises(Exception):  # FrozenInstanceError subclass
        col.dtype = "integer"  # type: ignore[misc]


def test_fileclass_column_lookup_raises_on_unknown(contract):
    fc: FileClass = contract.for_glob("datasets/data/variables.csv")
    with pytest.raises(KeyError):
        fc.column("does_not_exist")
