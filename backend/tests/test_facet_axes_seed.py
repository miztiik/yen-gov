"""Tier-A tests for the facet-axes hand-authored taxonomy seed.

These tests assert validator/compiler **code correctness** against tmp_path
fixtures — they MUST NOT walk the real on-disk corpus per CLAUDE.md §10
"never walk the real on-disk corpus from a pytest test". The seed module
itself IS the canonical taxonomy; data-quality concerns about the literal's
contents (typos, missing axes, wrong labels) are caught at module-import
time by Pydantic v2 ValidationError — no separate data test is needed.
"""

from __future__ import annotations

import duckdb
import pytest
from pydantic import ValidationError

from yen_gov.canonical.facet_axes_seed import (
    FACET_AXES,
    FACET_AXES_PARQUET_COLUMNS,
    FACET_AXES_ROW_SCHEMA_VERSION,
    FacetAxis,
    FacetAxisValue,
    _denormalized_rows,
    compile_to_parquet,
)


def test_module_imports_without_validation_error() -> None:
    """FACET_AXES literal validates as 13 well-formed axes.

    If a future edit introduces a typo (wrong field name, invalid value_id
    pattern, empty values list, label shorter than 1 char), the import at
    the top of THIS test file will fail before this assertion ever runs.
    The assertion is a sanity check that the import path is wired.
    """
    assert isinstance(FACET_AXES, list)
    assert len(FACET_AXES) == 13
    assert all(isinstance(axis, FacetAxis) for axis in FACET_AXES)


def test_all_axis_ids_are_unique() -> None:
    axis_ids = [axis.axis_id for axis in FACET_AXES]
    assert len(axis_ids) == len(set(axis_ids))


def test_all_value_ids_unique_within_each_axis() -> None:
    for axis in FACET_AXES:
        value_ids = [v.value_id for v in axis.values]
        assert len(value_ids) == len(set(value_ids)), (
            f"axis {axis.axis_id} has duplicate value_ids"
        )


def test_expected_axes_present() -> None:
    """Hard-coded snapshot of the 13 axes shipping in 1.0.

    Bumping this list is intentional friction — adding a new axis means
    updating this assertion AND the migration ledger AND the indicator-
    catalogue rows that depend on it.
    """
    expected = {
        "fuel_type",
        "sector",
        "head_of_account",
        "transfer_type",
        "gender",
        "residence",
        "prices_basis",
        "methodology_version",
        "category",
        "crime_category",
        "cpi_category",
        "loss_type",
        "allocation_basis",
    }
    actual = {axis.axis_id for axis in FACET_AXES}
    assert actual == expected


def test_deprecated_value_present_and_flagged() -> None:
    """gsdp-base-2004-05 is the canonical deprecated example.

    Catches a regression where a future bulk-edit drops the deprecated
    flag or removes the deprecated value entirely (both are silent data
    losses — old indicator rows referencing this value_id would
    suddenly fail validation).
    """
    methodology = next(a for a in FACET_AXES if a.axis_id == "methodology_version")
    deprecated_values = [v for v in methodology.values if v.deprecated]
    assert len(deprecated_values) == 1
    assert deprecated_values[0].value_id == "gsdp-base-2004-05"


def test_pydantic_rejects_invalid_value_id_pattern() -> None:
    with pytest.raises(ValidationError):
        FacetAxisValue(value_id="Capital_Case", label="Bad")
    with pytest.raises(ValidationError):
        FacetAxisValue(value_id="has spaces", label="Bad")
    with pytest.raises(ValidationError):
        FacetAxisValue(value_id="", label="Bad")


def test_pydantic_rejects_empty_axis_values() -> None:
    with pytest.raises(ValidationError):
        FacetAxis(
            axis_id="bad",
            label="Bad",
            description="ten chars minimum here",
            allow_compute_on_read_total=False,
            values=[],
        )


def test_pydantic_rejects_extra_fields() -> None:
    """extra='forbid' catches typos in field names at import time."""
    with pytest.raises(ValidationError):
        FacetAxisValue(value_id="x", label="X", extras="rejected")  # type: ignore[call-arg]


def test_denormalized_rows_match_axis_value_cardinality() -> None:
    rows = _denormalized_rows()
    expected_count = sum(len(a.values) for a in FACET_AXES)
    assert len(rows) == expected_count
    # Each row is an 8-tuple in the documented column order.
    assert all(len(row) == len(FACET_AXES_PARQUET_COLUMNS) for row in rows)


def test_denormalized_rows_carry_axis_metadata_on_every_row() -> None:
    """Denormalization rule: axis-level fields repeat on every child row.

    Lets DuckDB-WASM facet pickers query with one FROM clause.
    """
    rows = _denormalized_rows()
    # First row's axis_id should match FACET_AXES[0].axis_id after sort —
    # we don't sort here; we just check the first chunk carries the same
    # axis_label across all its children.
    fuel_rows = [r for r in rows if r[0] == "fuel_type"]
    assert fuel_rows, "fuel_type axis missing from rows"
    fuel_labels = {r[1] for r in fuel_rows}
    assert fuel_labels == {"Fuel type"}


def test_compile_to_parquet_writes_expected_row_count(tmp_path) -> None:
    out = tmp_path / "facet-axes.parquet"
    written = compile_to_parquet(out)
    assert out.exists()
    expected = sum(len(a.values) for a in FACET_AXES)
    assert written == expected


def test_compile_to_parquet_duckdb_round_trip(tmp_path) -> None:
    out = tmp_path / "facet-axes.parquet"
    compile_to_parquet(out)
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"SELECT axis_id, value_id, deprecated FROM '{out.as_posix()}' ORDER BY axis_id, value_id"
        ).fetchall()
    finally:
        con.close()

    # Spot-check a few values that exercise the contract.
    by_value = {(axis_id, value_id): deprecated for axis_id, value_id, deprecated in rows}
    assert by_value[("fuel_type", "coal")] is False
    assert by_value[("methodology_version", "gsdp-base-2004-05")] is True
    assert by_value[("loss_type", "at_and_c")] is False


def test_compile_to_parquet_column_types(tmp_path) -> None:
    out = tmp_path / "facet-axes.parquet"
    compile_to_parquet(out)
    con = duckdb.connect(":memory:")
    try:
        described = con.execute(f"DESCRIBE SELECT * FROM '{out.as_posix()}'").fetchall()
    finally:
        con.close()

    col_types = {row[0]: row[1] for row in described}
    assert col_types["axis_id"] == "VARCHAR"
    assert col_types["axis_label"] == "VARCHAR"
    assert col_types["axis_description"] == "VARCHAR"
    assert col_types["allow_compute_on_read_total"] == "BOOLEAN"
    assert col_types["value_id"] == "VARCHAR"
    assert col_types["value_label"] == "VARCHAR"
    assert col_types["value_description"] == "VARCHAR"
    assert col_types["deprecated"] == "BOOLEAN"


def test_compile_to_parquet_deterministic_byte_output(tmp_path) -> None:
    """Re-running compile_to_parquet with unchanged FACET_AXES produces
    byte-identical output. Defends Holy Law #10 anti-pattern guard against
    datetime.now()-in-data-content."""
    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    compile_to_parquet(first)
    compile_to_parquet(second)
    assert first.read_bytes() == second.read_bytes()


def test_value_description_is_nullable_in_parquet(tmp_path) -> None:
    """coal has no description (literal); transgender does. Both round-trip."""
    out = tmp_path / "facet-axes.parquet"
    compile_to_parquet(out)
    con = duckdb.connect(":memory:")
    try:
        coal_desc = con.execute(
            f"SELECT value_description FROM '{out.as_posix()}' WHERE axis_id='fuel_type' AND value_id='coal'"
        ).fetchone()
        trans_desc = con.execute(
            f"SELECT value_description FROM '{out.as_posix()}' WHERE axis_id='gender' AND value_id='transgender'"
        ).fetchone()
    finally:
        con.close()
    assert coal_desc[0] is None
    assert trans_desc[0] is not None and "Census 2011" in trans_desc[0]


def test_schema_version_constant_is_string() -> None:
    """Defends downstream callers (writer.py) that may read this constant."""
    assert isinstance(FACET_AXES_ROW_SCHEMA_VERSION, str)
    assert FACET_AXES_ROW_SCHEMA_VERSION == "1.0"
