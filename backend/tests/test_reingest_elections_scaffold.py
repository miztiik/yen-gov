"""Unit tests for the B2b.5 elections scaffolding (sub-sub-plan B2b.5.1).

Gate: docs-review + fk-validator-dry-run. Asserts:

- the four FILE_CLASS constants resolve via ``file_class_for`` to the
  matching glob keys in ``datasets/data/_schema/columns.json``;
- the four path-builders produce paths that ``file_class_for`` then
  resolves back to the FILE_CLASS the path was built from (round-trip).

No mocks (Holy Law #7). Path-builders are pure-functional; tests pass
``tmp_path`` as the ``out_root`` anchor.
"""

from __future__ import annotations

import pytest

from yen_gov.canonical.csv_columns import file_class_for
from yen_gov.canonical.reingest.elections import (
    ASSEMBLY_CANDIDACIES_FC,
    ASSEMBLY_SUMMARY_FC,
    PARLIAMENT_CANDIDACIES_FC,
    PARLIAMENT_SUMMARY_FC,
    assembly_candidacies_path,
    assembly_summary_path,
    parliament_candidacies_path,
    parliament_summary_path,
)


def test_assembly_candidacies_constant_matches_columns_json():
    assert ASSEMBLY_CANDIDACIES_FC == (
        "datasets/elections/assembly/state=*/election=*/candidacies.csv"
    )


def test_assembly_summary_constant_matches_columns_json():
    assert ASSEMBLY_SUMMARY_FC == (
        "datasets/elections/assembly/state=*/election=*/summary.csv"
    )


def test_parliament_candidacies_constant_matches_columns_json():
    assert PARLIAMENT_CANDIDACIES_FC == (
        "datasets/elections/parliament/election=*/candidacies.csv"
    )


def test_parliament_summary_constant_matches_columns_json():
    assert PARLIAMENT_SUMMARY_FC == (
        "datasets/elections/parliament/election=*/summary.csv"
    )


@pytest.mark.parametrize(
    "file_class",
    [
        ASSEMBLY_CANDIDACIES_FC,
        ASSEMBLY_SUMMARY_FC,
        PARLIAMENT_CANDIDACIES_FC,
        PARLIAMENT_SUMMARY_FC,
    ],
)
def test_each_file_class_constant_is_a_known_glob(file_class):
    # Pick any concrete path matching the glob and confirm resolution.
    sample = file_class.replace("state=*", "state=tamil-nadu").replace(
        "election=*", "election=2021"
    )
    fc = file_class_for(sample)
    assert fc.glob == file_class


def test_assembly_candidacies_path_roundtrips_through_file_class_for(tmp_path):
    path = assembly_candidacies_path(
        out_root=tmp_path, state_slug="tamil-nadu", election_year=2021
    )
    rel = path.relative_to(tmp_path).as_posix()
    assert rel == (
        "datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv"
    )
    assert file_class_for(rel).glob == ASSEMBLY_CANDIDACIES_FC


def test_assembly_summary_path_roundtrips_through_file_class_for(tmp_path):
    path = assembly_summary_path(
        out_root=tmp_path, state_slug="kerala", election_year=2016
    )
    rel = path.relative_to(tmp_path).as_posix()
    assert rel == (
        "datasets/elections/assembly/state=kerala/election=2016/summary.csv"
    )
    assert file_class_for(rel).glob == ASSEMBLY_SUMMARY_FC


def test_parliament_candidacies_path_roundtrips_through_file_class_for(tmp_path):
    path = parliament_candidacies_path(out_root=tmp_path, election_year=2024)
    rel = path.relative_to(tmp_path).as_posix()
    assert rel == (
        "datasets/elections/parliament/election=2024/candidacies.csv"
    )
    assert file_class_for(rel).glob == PARLIAMENT_CANDIDACIES_FC


def test_parliament_summary_path_roundtrips_through_file_class_for(tmp_path):
    path = parliament_summary_path(out_root=tmp_path, election_year=1957)
    rel = path.relative_to(tmp_path).as_posix()
    assert rel == (
        "datasets/elections/parliament/election=1957/summary.csv"
    )
    assert file_class_for(rel).glob == PARLIAMENT_SUMMARY_FC

