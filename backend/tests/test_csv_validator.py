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


# --- B2b.5.1 election file-class fk-validator passthrough ------------------
#
# Sub-sub-plan B2b.5.1 pins the validator's FK chain for the four election
# file classes declared in columns.json:
#
# - entity_id -> entities/electoral.csv.entity_id
# - party_id  -> entities/parties.csv.party_id
# - source_id -> entities/source.csv.source_id
#
# Plus closed-enum membership on `result`, `sex`, `candidate_type`.
# Plus state-mandatory on parliament CSVs (plan section 23.4).
# tmp_path fixtures only; no real-corpus walk (CLAUDE.md anti-pattern).


_ASSEMBLY_CANDIDACIES_FC = (
    "datasets/elections/assembly/state=*/election=*/candidacies.csv"
)
_PARLIAMENT_CANDIDACIES_FC = (
    "datasets/elections/parliament/election=*/candidacies.csv"
)
_PARLIAMENT_SUMMARY_FC = (
    "datasets/elections/parliament/election=*/summary.csv"
)


_CANDIDACIES_HEADER = [
    "entity_id", "state", "election_year", "constituency_no",
    "constituency_name", "candidate_name", "party_id", "party_short_raw",
    "votes", "vote_share_pct", "position", "result", "sex", "age",
    "education", "profession", "candidate_type", "source_id",
    "processing_level", "processing_note",
]
_PARLIAMENT_SUMMARY_HEADER = [
    "entity_id", "state", "election_year", "constituency_name", "electors",
    "votes_polled", "turnout_pct", "winner_candidate", "winner_party_id",
    "winner_party_short_raw", "winner_votes", "winner_share_pct",
    "runnerup_candidate", "runnerup_party_id", "runnerup_party_short_raw",
    "runnerup_votes", "margin_votes", "margin_pct", "source_id",
    "processing_level", "processing_note",
]


def _stage_electoral_entities(root: Path, ids: list[str]) -> Path:
    target = root / "datasets" / "data" / "entities" / "electoral.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["entity_id,name,entity_kind,delim_year,state,parent,reservation"]
    for entity_id in ids:
        kind = "ac" if "-AC-" in entity_id else "pc"
        lines.append(f"{entity_id},{entity_id},{kind},2008,tamil-nadu,,GEN")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _stage_geo_for_electoral(root: Path) -> Path:
    # electoral.csv FKs state -> geo.csv.entity_id; even though THIS test only
    # validates the elections file class, the validator will (indirectly via
    # the FK target's own FK chain) try to load geo.csv only if it follows
    # transitive FKs; today it does not, but stage geo.csv to keep the fixture
    # honest if that ever lands.
    target = root / "datasets" / "data" / "entities" / "geo.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "entity_id,name,parent,entity_kind,aliases\n"
        "tamil-nadu,Tamil Nadu,IN,state,\n"
        "IN,India,,country,\n",
        encoding="utf-8",
    )
    return target


def _stage_party_entities(root: Path, ids: list[str]) -> Path:
    target = root / "datasets" / "data" / "entities" / "parties.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,aliases"]
    for party_id in ids:
        lines.append(f"{party_id},{party_id},{party_id},,,,,")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _candidacy_row(
    *,
    entity_id: str,
    party_id: str,
    source_id: str,
    state: str = "tamil-nadu",
    position: int = 1,
    result: str = "won",
    sex: str = "M",
) -> list[str]:
    return [
        entity_id, state, "2021", "234", "Kanyakumari",
        f"Candidate {position}", party_id, party_id, str(50000 - position),
        str(45.5 - position), str(position), result, sex, str(45 + position),
        "Graduate", "Politics", "incumbent", source_id,
        "minor", "",
    ]


def test_assembly_candidacies_happy_path(tmp_path):
    _stage_electoral_entities(tmp_path, ["IN-AC-2008-S22-234"])
    _stage_geo_for_electoral(tmp_path)
    _stage_party_entities(tmp_path, ["p-bjp", "p-dmk"])
    _stage_sources(tmp_path, ["tcpd-ae-2021"])
    path = (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    _write_csv(
        path,
        _CANDIDACIES_HEADER,
        [
            _candidacy_row(
                entity_id="IN-AC-2008-S22-234", party_id="p-bjp",
                source_id="tcpd-ae-2021", position=1, result="won",
            ),
            _candidacy_row(
                entity_id="IN-AC-2008-S22-234", party_id="p-dmk",
                source_id="tcpd-ae-2021", position=2, result="lost",
            ),
        ],
    )
    validate_csv(
        path=path, file_class=_ASSEMBLY_CANDIDACIES_FC, repo_root=tmp_path,
    )


def test_assembly_candidacies_rejects_unknown_entity_id(tmp_path):
    _stage_electoral_entities(tmp_path, ["IN-AC-2008-S22-001"])
    _stage_geo_for_electoral(tmp_path)
    _stage_party_entities(tmp_path, ["p-bjp"])
    _stage_sources(tmp_path, ["tcpd-ae-2021"])
    path = (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    _write_csv(
        path,
        _CANDIDACIES_HEADER,
        [
            _candidacy_row(
                entity_id="IN-AC-2008-S22-999", party_id="p-bjp",
                source_id="tcpd-ae-2021",
            ),
        ],
    )
    with pytest.raises(CsvValidationError, match="entity_id"):
        validate_csv(
            path=path, file_class=_ASSEMBLY_CANDIDACIES_FC, repo_root=tmp_path,
        )


def test_assembly_candidacies_rejects_unknown_party_id(tmp_path):
    _stage_electoral_entities(tmp_path, ["IN-AC-2008-S22-234"])
    _stage_geo_for_electoral(tmp_path)
    _stage_party_entities(tmp_path, ["p-bjp"])
    _stage_sources(tmp_path, ["tcpd-ae-2021"])
    path = (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    _write_csv(
        path,
        _CANDIDACIES_HEADER,
        [
            _candidacy_row(
                entity_id="IN-AC-2008-S22-234", party_id="p-missing",
                source_id="tcpd-ae-2021",
            ),
        ],
    )
    with pytest.raises(CsvValidationError, match="party_id"):
        validate_csv(
            path=path, file_class=_ASSEMBLY_CANDIDACIES_FC, repo_root=tmp_path,
        )


def test_assembly_candidacies_rejects_unknown_source_id(tmp_path):
    _stage_electoral_entities(tmp_path, ["IN-AC-2008-S22-234"])
    _stage_geo_for_electoral(tmp_path)
    _stage_party_entities(tmp_path, ["p-bjp"])
    _stage_sources(tmp_path, ["tcpd-ae-2021"])
    path = (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    _write_csv(
        path,
        _CANDIDACIES_HEADER,
        [
            _candidacy_row(
                entity_id="IN-AC-2008-S22-234", party_id="p-bjp",
                source_id="tcpd-ae-1999",
            ),
        ],
    )
    with pytest.raises(CsvValidationError, match="source_id"):
        validate_csv(
            path=path, file_class=_ASSEMBLY_CANDIDACIES_FC, repo_root=tmp_path,
        )


def test_assembly_candidacies_rejects_bad_result_enum(tmp_path):
    _stage_electoral_entities(tmp_path, ["IN-AC-2008-S22-234"])
    _stage_geo_for_electoral(tmp_path)
    _stage_party_entities(tmp_path, ["p-bjp"])
    _stage_sources(tmp_path, ["tcpd-ae-2021"])
    path = (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=tamil-nadu" / "election=2021" / "candidacies.csv"
    )
    _write_csv(
        path,
        _CANDIDACIES_HEADER,
        [
            _candidacy_row(
                entity_id="IN-AC-2008-S22-234", party_id="p-bjp",
                source_id="tcpd-ae-2021", result="tied",
            ),
        ],
    )
    with pytest.raises(CsvValidationError, match="result"):
        validate_csv(
            path=path, file_class=_ASSEMBLY_CANDIDACIES_FC, repo_root=tmp_path,
        )


def test_parliament_summary_rejects_missing_state_column(tmp_path):
    # The validator only catches the empty-string non-nullable case at row
    # level; the header-mismatch case is caught earlier. plan section 23.4:
    # state is MANDATORY on PC files.
    _stage_electoral_entities(tmp_path, ["IN-PC-2008-S22-39"])
    _stage_geo_for_electoral(tmp_path)
    _stage_party_entities(tmp_path, ["p-bjp", "p-dmk"])
    _stage_sources(tmp_path, ["tcpd-ge-2024"])
    path = (
        tmp_path / "datasets" / "elections" / "parliament"
        / "election=2024" / "summary.csv"
    )
    _write_csv(
        path,
        _PARLIAMENT_SUMMARY_HEADER,
        [
            [
                "IN-PC-2008-S22-39", "", "2024", "Kanyakumari", "1500000",
                "1100000", "73.33", "Eve", "p-bjp", "BJP", "550000", "50.0", "Frank",
                "p-dmk", "DMK", "400000", "150000", "13.64", "tcpd-ge-2024",
                "minor", "",
            ],
        ],
    )
    with pytest.raises(CsvValidationError, match="non-nullable"):
        validate_csv(
            path=path, file_class=_PARLIAMENT_SUMMARY_FC, repo_root=tmp_path,
        )


def test_parliament_candidacies_happy_path_with_state_column(tmp_path):
    _stage_electoral_entities(tmp_path, ["IN-PC-2008-S22-39"])
    _stage_geo_for_electoral(tmp_path)
    _stage_party_entities(tmp_path, ["p-bjp"])
    _stage_sources(tmp_path, ["tcpd-ge-2024"])
    path = (
        tmp_path / "datasets" / "elections" / "parliament"
        / "election=2024" / "candidacies.csv"
    )
    _write_csv(
        path,
        _CANDIDACIES_HEADER,
        [
            _candidacy_row(
                entity_id="IN-PC-2008-S22-39", party_id="p-bjp",
                source_id="tcpd-ge-2024", state="tamil-nadu", position=1,
            ),
        ],
    )
    validate_csv(
        path=path, file_class=_PARLIAMENT_CANDIDACIES_FC, repo_root=tmp_path,
    )
