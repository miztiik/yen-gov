"""Unit tests for the CSV validator (sub-plan B1.3).

Gate: fk-validator. Covers:

- happy-path datapoint file (FK + enum + sort all green);
- FK miss (entity_id absent from entities/geo.csv);
- FK miss (source_id absent from entities/source.csv);
- enum miss (closed-enum column);
- sort drift (rows out of PK order);
- ``__`` ban in filename;
- non-nullable empty field rejected;
- datapoint filename stem must equal a known indicator_id when
  variables.csv is present (else the check is skipped, by design).

No mocks (Holy Law #7). Uses ``tmp_path`` fixtures - never walks the real
on-disk corpus (CLAUDE.md anti-pattern).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.canonical import csv_validator
from yen_gov.canonical.csv_validator import (
    CsvValidationError,
    validate_csv,
)


_GEO_FC = "datasets/data/datapoints/geo/*.csv"


@pytest.fixture(autouse=True)
def _reset_validator_cache():
    csv_validator.clear_caches()
    yield
    csv_validator.clear_caches()


def _stage_geo_entities(root: Path, ids: list[str]) -> Path:
    target = root / "datasets" / "data" / "entities" / "geo.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["entity_id,name,parent,entity_kind,aliases"]
    for entity_id in ids:
        lines.append(f"{entity_id},{entity_id},,state,")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _stage_sources(root: Path, ids: list[str]) -> Path:
    target = root / "datasets" / "data" / "entities" / "source.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["source_id,owner,title,vintage,url"]
    for source_id in ids:
        lines.append(f"{source_id},,,,")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [",".join(header)]
    for row in rows:
        body.append(",".join(row))
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def test_happy_path_datapoint(tmp_path):
    _stage_geo_entities(tmp_path, ["IN-S01", "IN-S22"])
    _stage_sources(tmp_path, ["src-a"])
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "literacy-rate-pct-total.csv"
    _write_csv(
        path,
        ["entity_id", "time", "value", "source_id"],
        [
            ["IN-S01", "2011", "73.2", "src-a"],
            ["IN-S22", "2011", "80.1", "src-a"],
        ],
    )
    validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)


def test_fk_miss_entity_id_rejected(tmp_path):
    _stage_geo_entities(tmp_path, ["IN-S01"])
    _stage_sources(tmp_path, ["src-a"])
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "literacy-rate-pct-total.csv"
    _write_csv(
        path,
        ["entity_id", "time", "value", "source_id"],
        [["IN-S99", "2011", "1.0", "src-a"]],
    )
    with pytest.raises(CsvValidationError, match="entity_id"):
        validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)


def test_fk_miss_source_id_rejected(tmp_path):
    _stage_geo_entities(tmp_path, ["IN-S01"])
    _stage_sources(tmp_path, ["src-a"])
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "literacy-rate-pct-total.csv"
    _write_csv(
        path,
        ["entity_id", "time", "value", "source_id"],
        [["IN-S01", "2011", "1.0", "src-missing"]],
    )
    with pytest.raises(CsvValidationError, match="source_id"):
        validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)


def test_enum_miss_rejected(tmp_path):
    target = tmp_path / "datasets" / "data" / "concepts.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "concept_id,noun,unit_canonical,normalisation,entity_kinds,description\n"
        "c1,literacy,pct,not_a_real_enum,state,\n",
        encoding="utf-8",
    )
    with pytest.raises(CsvValidationError, match="normalisation"):
        validate_csv(
            path=target,
            file_class="datasets/data/concepts.csv",
            repo_root=tmp_path,
        )


def test_sort_drift_rejected(tmp_path):
    _stage_geo_entities(tmp_path, ["IN-S01", "IN-S22"])
    _stage_sources(tmp_path, ["src-a"])
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "literacy-rate-pct-total.csv"
    _write_csv(
        path,
        ["entity_id", "time", "value", "source_id"],
        [
            ["IN-S22", "2011", "80.1", "src-a"],
            ["IN-S01", "2011", "73.2", "src-a"],
        ],
    )
    with pytest.raises(CsvValidationError, match="not sorted"):
        validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)


def test_double_underscore_filename_rejected(tmp_path):
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "bad__name.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("entity_id,time,value,source_id\n", encoding="utf-8")
    with pytest.raises(CsvValidationError, match="__"):
        validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)


def test_non_nullable_empty_field_rejected(tmp_path):
    _stage_geo_entities(tmp_path, ["IN-S01"])
    _stage_sources(tmp_path, ["src-a"])
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "literacy-rate-pct-total.csv"
    _write_csv(
        path,
        ["entity_id", "time", "value", "source_id"],
        [["IN-S01", "2011", "1.0", ""]],
    )
    with pytest.raises(CsvValidationError, match="non-nullable"):
        validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)


def test_unknown_indicator_stem_rejected_when_variables_present(tmp_path):
    _stage_geo_entities(tmp_path, ["IN-S01"])
    _stage_sources(tmp_path, ["src-a"])
    variables = tmp_path / "datasets" / "data" / "variables.csv"
    variables.parent.mkdir(parents=True, exist_ok=True)
    variables.write_text(
        "indicator_id,name,concept_id,unit,derivation,topic,source_id,update_period_days,time_min,time_max,entity_kinds\n"
        "literacy-rate-pct-total,Literacy rate,c1,pct,,edu,src-a,3650,,,\n",
        encoding="utf-8",
    )
    bogus = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "not-a-known-indicator.csv"
    _write_csv(
        bogus,
        ["entity_id", "time", "value", "source_id"],
        [["IN-S01", "2011", "1.0", "src-a"]],
    )
    with pytest.raises(CsvValidationError, match="indicator_id"):
        validate_csv(path=bogus, file_class=_GEO_FC, repo_root=tmp_path)


def test_indicator_stem_check_skipped_when_variables_absent(tmp_path):
    _stage_geo_entities(tmp_path, ["IN-S01"])
    _stage_sources(tmp_path, ["src-a"])
    # No variables.csv staged - check is silently skipped (B1.3 spec).
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "anything-goes.csv"
    _write_csv(
        path,
        ["entity_id", "time", "value", "source_id"],
        [["IN-S01", "2011", "1.0", "src-a"]],
    )
    validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)


def test_fk_target_missing_only_fails_when_referenced(tmp_path):
    # No source.csv, no geo.csv, but no rows reference any FK either.
    path = tmp_path / "datasets" / "data" / "datapoints" / "geo" / "empty.csv"
    _write_csv(path, ["entity_id", "time", "value", "source_id"], [])
    # Header-only file has no FK values to verify; missing target files are
    # tolerated when no rows depend on them.
    validate_csv(path=path, file_class=_GEO_FC, repo_root=tmp_path)
