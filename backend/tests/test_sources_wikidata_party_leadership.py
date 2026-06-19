"""Tests for backend.yen_gov.canonical.adapters.wikidata.party_leadership.

PR-7 of TODO/20260613-party-deferred-followups-plan.md (Max 2a / 2d / 2e
verdicts). Hand-authored mini-fixtures inside the test file (no on-disk
JSON fixture required); pure Python via ``tmp_path`` per CLAUDE.md section
15 / 10 (real fixtures, no mocks).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from yen_gov.canonical.adapters.wikidata.party_leadership import (
    WikidataLeadershipRow,
    parse_sparql_fixture,
    write_leadership_csv,
)


# Minimal Q-id -> party_id resolution maps used by the parse tests.
_BJP_RESOLUTION = {"Q748724": "parties.IN.BJP"}
_BJP_INC_RESOLUTION = {
    "Q748724": "parties.IN.BJP",
    "Q83294": "parties.IN.INC",
}
_SOURCE_ID = "src-aaaaaaaaaaaa"


def _sparql_payload(bindings: list[dict[str, dict[str, str]]]) -> dict:
    """Wrap a list of bindings in a SPARQL JSON envelope."""
    return {
        "head": {
            "vars": [
                "party",
                "partyLabel",
                "chief",
                "chiefLabel",
                "role",
                "roleLabel",
                "startTime",
                "endTime",
            ]
        },
        "results": {"bindings": bindings},
    }


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    """Persist ``payload`` to a SPARQL JSON file under tmp_path."""
    path = tmp_path / "wikidata-fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_parse_sparql_fixture_basic(tmp_path: Path) -> None:
    """One party + one leader + minimal P580 -> one typed row."""
    payload = _sparql_payload(
        [
            {
                "party": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q748724",
                },
                "chief": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q3104873",
                },
                "chiefLabel": {
                    "xml:lang": "en",
                    "type": "literal",
                    "value": "J. P. Nadda",
                },
                "roleLabel": {
                    "xml:lang": "en",
                    "type": "literal",
                    "value": "President",
                },
                "startTime": {
                    "datatype": "http://www.w3.org/2001/XMLSchema#dateTime",
                    "type": "literal",
                    "value": "2020-01-20T00:00:00Z",
                },
            }
        ]
    )
    path = _write_fixture(tmp_path, payload)

    rows = parse_sparql_fixture(path, _BJP_RESOLUTION, _SOURCE_ID)

    assert len(rows) == 1
    row = rows[0]
    assert row.party_id == "parties.IN.BJP"
    assert row.role == "President"
    assert row.person_name == "J. P. Nadda"
    assert row.person_wikidata_qid == "Q3104873"
    assert row.valid_from == "2020-01-20"
    assert row.valid_to is None
    assert row.source_id == _SOURCE_ID


def test_parse_sparql_fixture_with_p580_p582(tmp_path: Path) -> None:
    """A binding carrying both startTime (P580) and endTime (P582) populates
    valid_from + valid_to correctly (both truncated to YYYY-MM-DD)."""
    payload = _sparql_payload(
        [
            {
                "party": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q748724",
                },
                "chief": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q1639332",
                },
                "chiefLabel": {"type": "literal", "value": "Amit Shah"},
                "roleLabel": {"type": "literal", "value": "President"},
                "startTime": {
                    "type": "literal",
                    "value": "2014-07-09T00:00:00Z",
                },
                "endTime": {
                    "type": "literal",
                    "value": "2020-01-20T00:00:00Z",
                },
            }
        ]
    )
    path = _write_fixture(tmp_path, payload)

    rows = parse_sparql_fixture(path, _BJP_RESOLUTION, _SOURCE_ID)

    assert len(rows) == 1
    row = rows[0]
    assert row.valid_from == "2014-07-09"
    assert row.valid_to == "2020-01-20"
    assert row.person_name == "Amit Shah"


def test_parse_sparql_fixture_dedup_on_dual_property(tmp_path: Path) -> None:
    """When the same person appears under both P488 (chairperson) and P3975
    (secretary general) for the same party + start date, dedup to one row
    keeping the first encountered."""
    payload = _sparql_payload(
        [
            {
                "party": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q748724",
                },
                "chief": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q3104873",
                },
                "chiefLabel": {"type": "literal", "value": "J. P. Nadda"},
                "roleLabel": {"type": "literal", "value": "President"},
                "startTime": {
                    "type": "literal",
                    "value": "2020-01-20T00:00:00Z",
                },
            },
            # Same (party, person, start_date) tuple, different role label
            # (this is what the dual-property SPARQL query returns when a
            # cadre-leader is technically also the secretary general).
            {
                "party": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q748724",
                },
                "chief": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q3104873",
                },
                "chiefLabel": {"type": "literal", "value": "J. P. Nadda"},
                "roleLabel": {"type": "literal", "value": "General Secretary"},
                "startTime": {
                    "type": "literal",
                    "value": "2020-01-20T00:00:00Z",
                },
            },
        ]
    )
    path = _write_fixture(tmp_path, payload)

    rows = parse_sparql_fixture(path, _BJP_RESOLUTION, _SOURCE_ID)

    assert len(rows) == 1
    assert rows[0].role == "President"  # first encountered wins


def test_parse_sparql_fixture_currently_serving(tmp_path: Path) -> None:
    """A binding with P580 but no P582 means currently serving:
    ``valid_to`` is None (never datetime.now per CLAUDE.md)."""
    payload = _sparql_payload(
        [
            {
                "party": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q83294",
                },
                "chief": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q174843",
                },
                "chiefLabel": {"type": "literal", "value": "Mallikarjun Kharge"},
                "roleLabel": {"type": "literal", "value": "President"},
                "startTime": {
                    "type": "literal",
                    "value": "2022-10-26T00:00:00Z",
                },
                # NO endTime binding - the OPTIONAL { ?stmt pq:P582 ... }
                # block matched nothing.
            }
        ]
    )
    path = _write_fixture(tmp_path, payload)

    rows = parse_sparql_fixture(path, _BJP_INC_RESOLUTION, _SOURCE_ID)

    assert len(rows) == 1
    assert rows[0].valid_to is None
    assert rows[0].valid_from == "2022-10-26"


def test_parse_handles_truncated_iso_timestamp(tmp_path: Path) -> None:
    """SPARQL returns ``2020-01-20T00:00:00Z`` style timestamps; the
    parser truncates to ``2020-01-20``."""
    payload = _sparql_payload(
        [
            {
                "party": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q748724",
                },
                "chief": {
                    "type": "uri",
                    "value": "http://www.wikidata.org/entity/Q3104873",
                },
                "chiefLabel": {"type": "literal", "value": "J. P. Nadda"},
                "roleLabel": {"type": "literal", "value": "President"},
                "startTime": {"type": "literal", "value": "2020-01-20T00:00:00Z"},
                "endTime": {"type": "literal", "value": "2023-01-20T12:34:56Z"},
            }
        ]
    )
    path = _write_fixture(tmp_path, payload)

    rows = parse_sparql_fixture(path, _BJP_RESOLUTION, _SOURCE_ID)

    assert len(rows) == 1
    assert rows[0].valid_from == "2020-01-20"
    assert rows[0].valid_to == "2023-01-20"


def test_write_leadership_csv_writes_header_and_rows(tmp_path: Path) -> None:
    """Round-trip: write 2 rows -> CSV has header + 2 data rows in PK
    order; the 7-column header matches the on-disk seed file exactly."""
    csv_path = tmp_path / "parties_leadership.csv"
    rows = [
        WikidataLeadershipRow(
            party_id="parties.IN.INC",
            role="President",
            person_name="Mallikarjun Kharge",
            person_wikidata_qid="Q174843",
            valid_from="2022-10-26",
            valid_to=None,
            source_id=_SOURCE_ID,
        ),
        WikidataLeadershipRow(
            party_id="parties.IN.BJP",
            role="President",
            person_name="J. P. Nadda",
            person_wikidata_qid="Q3104873",
            valid_from="2020-01-20",
            valid_to=None,
            source_id=_SOURCE_ID,
        ),
    ]

    count = write_leadership_csv(rows, csv_path)
    assert count == 2

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        data_rows = list(reader)

    assert header == [
        "party_id",
        "role",
        "person_name",
        "person_wikidata_qid",
        "valid_from",
        "valid_to",
        "source_id",
    ]
    # PK sort: parties.IN.BJP comes before parties.IN.INC alphabetically.
    assert data_rows[0][0] == "parties.IN.BJP"
    assert data_rows[1][0] == "parties.IN.INC"
    # valid_to None encoded as empty string per CSV column contract.
    assert data_rows[0][5] == ""
    assert data_rows[1][5] == ""


def test_write_leadership_csv_upserts_on_pk(tmp_path: Path) -> None:
    """Existing CSV with 2 rows; write a new batch with 1 PK-overlap row +
    1 brand-new row -> final state has the upserted row's new values + the
    untouched existing row + the brand-new row (3 rows total)."""
    csv_path = tmp_path / "parties_leadership.csv"

    # Seed with 2 existing rows.
    seed = [
        WikidataLeadershipRow(
            party_id="parties.IN.BJP",
            role="President",
            person_name="OLD NAME",  # will be overwritten by the upsert
            person_wikidata_qid="Q999999",
            valid_from="2020-01-20",
            valid_to=None,
            source_id=_SOURCE_ID,
        ),
        WikidataLeadershipRow(
            party_id="parties.IN.INC",
            role="President",
            person_name="Mallikarjun Kharge",
            person_wikidata_qid="Q174843",
            valid_from="2022-10-26",
            valid_to=None,
            source_id=_SOURCE_ID,
        ),
    ]
    write_leadership_csv(seed, csv_path)

    # New batch: 1 PK-overlap with corrected name + 1 brand-new row.
    new_batch = [
        WikidataLeadershipRow(
            party_id="parties.IN.BJP",
            role="President",
            person_name="J. P. Nadda",  # corrected
            person_wikidata_qid="Q3104873",
            valid_from="2020-01-20",  # same PK as the seed row -> upsert
            valid_to=None,
            source_id=_SOURCE_ID,
        ),
        WikidataLeadershipRow(
            party_id="parties.IN.AAP",
            role="National Convenor",
            person_name="Arvind Kejriwal",
            person_wikidata_qid="Q272188",
            valid_from="2012-11-26",
            valid_to=None,
            source_id=_SOURCE_ID,
        ),
    ]
    count = write_leadership_csv(new_batch, csv_path)

    # Existing INC row preserved + BJP row upserted + AAP row appended.
    assert count == 3

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows_by_party = {r["party_id"]: r for r in reader}

    assert set(rows_by_party.keys()) == {
        "parties.IN.AAP",
        "parties.IN.BJP",
        "parties.IN.INC",
    }
    assert rows_by_party["parties.IN.BJP"]["person_name"] == "J. P. Nadda"
    assert rows_by_party["parties.IN.BJP"]["person_wikidata_qid"] == "Q3104873"
    assert rows_by_party["parties.IN.INC"]["person_name"] == "Mallikarjun Kharge"
    assert rows_by_party["parties.IN.AAP"]["role"] == "National Convenor"


# ---------------------------------------------------------------------------
# PR-9: live-fetch helpers (Wikipedia REST + Wikidata SPARQL).
# ---------------------------------------------------------------------------
#
# The HTTP transport is stubbed via monkeypatch on the private _http_*
# helpers. CLAUDE.md section 15 + 7 carve out mocks for genuinely-external
# I/O boundaries; pinning the transport keeps the test deterministic and
# offline while still exercising the request-shape + response-parse glue.


def test_wikipedia_url_to_article_title_strips_prefix() -> None:
    from yen_gov.canonical.adapters.wikidata.party_leadership import (
        _wikipedia_url_to_article_title,
    )

    assert (
        _wikipedia_url_to_article_title(
            "https://en.wikipedia.org/wiki/Aam_Aadmi_Party"
        )
        == "Aam_Aadmi_Party"
    )
    assert (
        _wikipedia_url_to_article_title(
            "https://en.wikipedia.org/wiki/Apna_Dal_(Sonelal)"
        )
        == "Apna_Dal_(Sonelal)"
    )
    # Non-Wikipedia URL or off-language wiki returns None.
    assert _wikipedia_url_to_article_title("https://example.org/wiki/Foo") is None
    assert (
        _wikipedia_url_to_article_title("https://hi.wikipedia.org/wiki/Foo") is None
    )
    # Empty / None passthroughs.
    assert _wikipedia_url_to_article_title("") is None


def test_resolve_qids_caches_to_disk_and_skips_already_known(
    tmp_path: Path, monkeypatch
) -> None:
    """Live-resolution helper writes the QID map atomically and re-runs
    skip parties whose Q-id is already cached."""
    from yen_gov.canonical.adapters.wikidata import party_leadership as pl

    cache_path = tmp_path / "qid-cache.json"

    # Pre-populate cache with one entry; only the second party should be
    # fetched on the next call.
    cache_path.write_text(json.dumps({"Q748724": "parties.IN.BJP"}), encoding="utf-8")

    calls: list[str] = []

    def fake_get(url: str) -> dict:
        calls.append(url)
        # Return a minimal Wikipedia REST summary shape.
        return {"wikibase_item": "Q129844"}

    monkeypatch.setattr(pl, "_http_get_json", fake_get)
    # Skip the polite sleep in tests.
    monkeypatch.setattr(pl, "_INTER_REQUEST_SLEEP_SECS", 0.0)

    result = pl.resolve_qids_from_wikipedia(
        {
            "parties.IN.BJP": "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party",
            "parties.IN.AAP": "https://en.wikipedia.org/wiki/Aam_Aadmi_Party",
        },
        cached_map_path=cache_path,
    )

    # BJP already cached -> 1 HTTP call (for AAP only).
    assert len(calls) == 1
    assert "Aam_Aadmi_Party" in calls[0]
    assert result == {
        "Q748724": "parties.IN.BJP",
        "Q129844": "parties.IN.AAP",
    }

    # Cache file on disk reflects the merged map.
    on_disk = json.loads(cache_path.read_text(encoding="utf-8"))
    assert on_disk == {
        "Q129844": "parties.IN.AAP",
        "Q748724": "parties.IN.BJP",
    }


def test_resolve_qids_skips_404_and_missing_wikibase_item(
    tmp_path: Path, monkeypatch
) -> None:
    """Wikipedia REST 404s and pages without a wikibase_item are skipped
    silently — they do NOT abort the run nor poison the cache."""
    import urllib.error

    from yen_gov.canonical.adapters.wikidata import party_leadership as pl

    cache_path = tmp_path / "qid-cache.json"

    def fake_get(url: str) -> dict:
        if "GGP" in url:
            raise urllib.error.HTTPError(
                url, 404, "Not Found", hdrs=None, fp=None  # type: ignore[arg-type]
            )
        if "Bare" in url:
            return {}  # no wikibase_item
        return {"wikibase_item": "Q129844"}

    monkeypatch.setattr(pl, "_http_get_json", fake_get)
    monkeypatch.setattr(pl, "_INTER_REQUEST_SLEEP_SECS", 0.0)

    result = pl.resolve_qids_from_wikipedia(
        {
            "parties.IN.AAP": "https://en.wikipedia.org/wiki/Aam_Aadmi_Party",
            "parties.IN.GGP": "https://en.wikipedia.org/wiki/GGP_Stale",
            "parties.IN.BARE": "https://en.wikipedia.org/wiki/Bare_Stub",
        },
        cached_map_path=cache_path,
    )

    # Only AAP resolved; GGP + BARE silently skipped.
    assert result == {"Q129844": "parties.IN.AAP"}


def test_fetch_sparql_snapshot_posts_query_and_writes_pretty_json(
    tmp_path: Path, monkeypatch
) -> None:
    """The SPARQL POST helper builds a VALUES clause from the qids,
    submits via the stubbed HTTP layer, and writes the JSON snapshot in
    deterministic pretty form."""
    from yen_gov.canonical.adapters.wikidata import party_leadership as pl

    captured: dict[str, object] = {}

    def fake_post(url: str, fields: dict[str, str]) -> dict:
        captured["url"] = url
        captured["query"] = fields["query"]
        return {
            "head": {"vars": ["party"]},
            "results": {
                "bindings": [
                    {
                        "party": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q10230",
                        }
                    }
                ]
            },
        }

    monkeypatch.setattr(pl, "_http_post_form_json", fake_post)

    out = tmp_path / "snapshot.json"
    n = pl.fetch_sparql_snapshot(["Q10230", "Q10225", "Q129844"], out)

    assert n == 1
    assert captured["url"] == "https://query.wikidata.org/sparql"
    # VALUES list is alphabetised so the snapshot is deterministic regardless
    # of caller iteration order.
    query = captured["query"]
    assert isinstance(query, str)
    assert "wd:Q10225 wd:Q10230 wd:Q129844" in query
    # PreferredRank rank filter was deliberately dropped in PR-9 — the wider
    # query covers the full term-shape history.
    assert "wikibase:PreferredRank" not in query

    # The snapshot file should be pretty-printed + sorted-keys so diffs
    # across runs are deterministic.
    on_disk = out.read_text(encoding="utf-8")
    assert on_disk.endswith("\n")
    assert "\n  " in on_disk  # indented JSON
