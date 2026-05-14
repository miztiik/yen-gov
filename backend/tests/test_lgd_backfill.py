"""Unit tests for tools.lgd.backfill_lgd_codes — name normalization + alias matching.

Per CLAUDE.md §15 and Holy Law #7 (no mocks). Uses small in-memory CSV fixtures
written into tmp_path, exercising the same `backfill_one` function the CLI runs.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "lgd"))

import backfill_lgd_codes as bf  # noqa: E402


def _write_districts_json(tmp_path: Path, items: list[dict]) -> Path:
    p = tmp_path / "districts.json"
    p.write_text(
        json.dumps(
            {
                "$schema": "https://yen-gov.github.io/schemas/district.schema.json",
                "$schema_version": "3.1",
                "sources": [
                    {"url": "https://example.test/", "fetched_at": "2026-05-13T00:00:00Z"}
                ],
                "state": "S99",
                "districts": items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return p


def test_norm_strips_punctuation_and_case() -> None:
    assert bf._norm("South 24 Parganas") == "south24parganas"
    assert bf._norm("Tirunelveli (formerly Tinnevelly)") == "tirunelveliformerlytinnevelly"
    assert bf._norm("Chhota Udaipur") == "chhotaudaipur"


def test_backfill_exact_and_alias_match(tmp_path: Path) -> None:
    items = [
        {"id": "A", "id_source": "wikipedia", "name": "Howrah"},
        {"id": "B", "id_source": "wikipedia", "name": "Maldah"},  # repo spelling
        {"id": "C", "id_source": "wikipedia", "name": "Mystery District"},
    ]
    state_path = _write_districts_json(tmp_path, items)
    lgd_districts = [
        {"code": "100", "name": "Howrah"},
        {"code": "200", "name": "Malda"},  # LGD spelling — Maldah->Malda is in aliases
    ]

    matched, total, unmatched, doc = bf.backfill_one(state_path, "19", lgd_districts)

    assert matched == 2
    assert total == 3
    assert unmatched == ["Mystery District"]
    assert doc["districts"][0]["lgd_code"] == "100"
    assert doc["districts"][1]["lgd_code"] == "200"
    assert "lgd_code" not in doc["districts"][2]
    # Schema version bumped 3.1 -> 3.2 as part of the additive change.
    assert doc["$schema_version"] == "3.2"


def test_id_and_id_source_preserved(tmp_path: Path) -> None:
    """Cross-references in constituencies.json depend on id; backfill must not touch it."""
    items = [{"id": "ARI", "id_source": "wikipedia", "name": "Howrah", "headquarters": "X"}]
    state_path = _write_districts_json(tmp_path, items)
    lgd_districts = [{"code": "100", "name": "Howrah"}]

    _, _, _, doc = bf.backfill_one(state_path, "19", lgd_districts)

    d = doc["districts"][0]
    assert d["id"] == "ARI"
    assert d["id_source"] == "wikipedia"
    assert d["lgd_code"] == "100"
    assert d["headquarters"] == "X"


def test_state_bridge_handles_canonical_names(tmp_path: Path, monkeypatch) -> None:
    """End-to-end load_state_lgd_bridge against fixture CSVs."""
    states_csv = tmp_path / "states.csv"
    with states_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["S.No.", "State Code", "State Version", "State Name (In English)",
             "State Name (In Local)", "Census 2001 Code", "Census 2011 Code", "State or UT"]
        )
        w.writerow(["1", "33", "1", "Tamil Nadu", "TAMIL NADU", "33", "33", "S"])
        w.writerow(["2", "32", "1", "Kerala", "KERALA", "32", "32", "S"])

    states_json = tmp_path / "states.json"
    states_json.write_text(
        json.dumps({"states": [
            {"eci_code": "S22", "name": "Tamil Nadu"},
            {"eci_code": "S11", "name": "Kerala"},
            {"eci_code": "S99", "name": "Phantomstan"},
        ]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(bf, "STATES_JSON", states_json)
    monkeypatch.setattr(bf, "LGD_STATES_CSV", states_csv)

    bridge = bf.load_state_lgd_bridge()

    assert bridge["S22"] == "33"
    assert bridge["S11"] == "32"
    assert "S99" not in bridge  # No matching English name in LGD CSV.
