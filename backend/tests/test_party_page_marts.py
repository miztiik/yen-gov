from __future__ import annotations

import csv
import json
from pathlib import Path

from yen_gov.canonical.derived.party_pages import (
    party_page_mart_freshness_failures,
    refresh_party_page_marts,
)


ELECTORAL_FIELDS = [
    "entity_id",
    "year",
    "period_label",
    "period_seq",
    "indicator_id",
    "value_numeric",
    "value_text",
    "source_id",
    "derivation",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _build_fixture(root: Path) -> None:
    _write_csv(
        root / "datasets" / "data" / "entities" / "parties.csv",
        ["party_id", "short", "full"],
        [
            {"party_id": "parties.IN.DMK", "short": "DMK", "full": "DMK"},
            {"party_id": "parties.IN.BJP", "short": "BJP", "full": "BJP"},
            {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unknown"},
        ],
    )
    _write_csv(
        root / "datasets" / "data" / "entities" / "electoral.csv",
        ["entity_id", "name", "entity_kind", "delim_year", "state", "eci_no"],
        [
            {
                "entity_id": "IN-AC-2008-tamil-nadu-1",
                "name": "First Seat",
                "entity_kind": "ac",
                "delim_year": 2008,
                "state": "tamil-nadu",
                "eci_no": 1,
            },
            {
                "entity_id": "IN-AC-2008-tamil-nadu-2",
                "name": "Second Seat",
                "entity_kind": "ac",
                "delim_year": 2008,
                "state": "tamil-nadu",
                "eci_no": 2,
            },
        ],
    )
    states_path = root / "datasets" / "taxonomy" / "lgd_states.json"
    states_path.parent.mkdir(parents=True, exist_ok=True)
    states_path.write_text(
        json.dumps(
            {
                "states": [
                    {"eci_st_code": "S22", "slug": "tamil-nadu"},
                ]
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        root
        / "datasets"
        / "data"
        / "datapoints"
        / "electoral"
        / "tamil-nadu_election_results.csv",
        ELECTORAL_FIELDS,
        [
            {
                "entity_id": "IN-S22-AcGenApr2021-PARTY-DMK",
                "year": 2021,
                "period_label": "AcGenApr2021",
                "period_seq": 1,
                "indicator_id": "party-seats-won",
                "value_numeric": 2,
                "value_text": "",
                "source_id": "src-a",
                "derivation": "count_where",
            },
            {
                "entity_id": "IN-S22-AcGenApr2021-PARTY-DMK",
                "year": 2021,
                "period_label": "AcGenApr2021",
                "period_seq": 1,
                "indicator_id": "party-contested-acs",
                "value_numeric": 3,
                "value_text": "",
                "source_id": "src-a",
                "derivation": "count_where",
            },
            {
                "entity_id": "IN-S22-AcGenApr2021-PARTY-DMK",
                "year": 2021,
                "period_label": "AcGenApr2021",
                "period_seq": 1,
                "indicator_id": "party-votes-polled",
                "value_numeric": 120,
                "value_text": "",
                "source_id": "src-a",
                "derivation": "sum",
            },
            {
                "entity_id": "IN-S22-AC-2008-1",
                "year": 2021,
                "period_label": "AcGenApr2021",
                "period_seq": 1,
                "indicator_id": "ac-votes-polled",
                "value_numeric": 100,
                "value_text": "",
                "source_id": "src-a",
                "derivation": "sum",
            },
            {
                "entity_id": "IN-S22-AC-2008-2",
                "year": 2021,
                "period_label": "AcGenApr2021",
                "period_seq": 1,
                "indicator_id": "ac-votes-polled",
                "value_numeric": 200,
                "value_text": "",
                "source_id": "src-a",
                "derivation": "sum",
            },
            {
                "entity_id": "IN-S22-AC-2008-1",
                "year": 2021,
                "period_label": "AcGenApr2021",
                "period_seq": 1,
                "indicator_id": "ac-winner-party-id",
                "value_numeric": "",
                "value_text": "parties.IN.DMK",
                "source_id": "src-a",
                "derivation": "argmax_votes",
            },
            {
                "entity_id": "IN-S22-AC-2008-1",
                "year": 2026,
                "period_label": "AcGenMay2026",
                "period_seq": 2,
                "indicator_id": "ac-winner-party-id",
                "value_numeric": "",
                "value_text": "parties.IN.BJP",
                "source_id": "src-b",
                "derivation": "argmax_votes",
            },
            {
                "entity_id": "IN-S22-AC-2008-2",
                "year": 2021,
                "period_label": "AcGenApr2021",
                "period_seq": 1,
                "indicator_id": "ac-winner-party-id",
                "value_numeric": "",
                "value_text": "parties.IN.DMK",
                "source_id": "src-a",
                "derivation": "argmax_votes",
            },
        ],
    )


def test_refresh_party_page_marts_writes_history_and_strongholds(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    result = refresh_party_page_marts(tmp_path)

    assert result.history_rows == 1
    assert result.stronghold_rows == 3
    history = _read_csv(result.history_path)
    assert history == [
        {
            "party_id": "parties.IN.DMK",
            "body": "assembly",
            "period_label": "AcGenApr2021",
            "year": "2021",
            "seats": "2",
            "vote_share_pct": "40",
            "contested": "3",
            "source_ids": "src-a",
            "derivation": "computed_from_canonical_electoral_rows",
        }
    ]

    strongholds = _read_csv(result.strongholds_path)
    dmk_rows = [r for r in strongholds if r["party_id"] == "parties.IN.DMK"]
    assert [r["entity_id"] for r in dmk_rows] == [
        "IN-S22-AC-2008-2",
        "IN-S22-AC-2008-1",
    ]
    assert dmk_rows[0]["constituency_name"] == "Second Seat"
    assert dmk_rows[0]["results"] == "W"
    assert dmk_rows[1]["results"] == "WL"

    assert party_page_mart_freshness_failures(tmp_path) == []


def test_party_page_mart_freshness_fails_when_input_changes(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    refresh_party_page_marts(tmp_path)

    result_csv = (
        tmp_path
        / "datasets"
        / "data"
        / "datapoints"
        / "electoral"
        / "tamil-nadu_election_results.csv"
    )
    result_csv.write_text(result_csv.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    failures = party_page_mart_freshness_failures(tmp_path)
    assert len(failures) == 1
    assert "party-page mart is stale" in failures[0]
    assert "derive-party-pages" in failures[0]