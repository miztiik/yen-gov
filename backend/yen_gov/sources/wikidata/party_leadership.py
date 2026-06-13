"""Wikidata party-leadership ingester (PR-7 scaffolding; PR-9 will pin data).

Reads a pinned SPARQL JSON response saved at
``datasets/ephemeral/wikidata-party-leadership-<YYYY-MM-DD>.json`` and emits
rows for ``datasets/data/entities/parties_leadership.csv`` (term-shape:
``(party_id, role, person_name, person_wikidata_qid, valid_from, valid_to,
source_id)``; composite PK ``(party_id, valid_from)``).

Per PR-7 of TODO/20260613-party-deferred-followups-plan.md + Max 2a / 2d /
2e verdicts:

  * Wikidata data is consumed OFFLINE only. We never fetch live (Holy Law
    #1; backend deletes the network-fetch code). The operator runs the
    pinned SPARQL query at https://query.wikidata.org , downloads the JSON
    response, and drops it in ``datasets/ephemeral/`` (gitignored). PR-9
    pins the first snapshot.
  * Property selection: P488 (chairperson) is the PRIMARY signal for
    "leader of party"; P3975 (secretary general) is the FALLBACK when a
    party has no P488 statement (typical for cadre-led parties).
  * Time bounds: P580 (start time) -> ``valid_from``; P582 (end time) ->
    ``valid_to``. ``valid_to`` is null when the statement carries no P582
    (currently serving) - never substitute datetime.now per CLAUDE.md
    anti-pattern.
  * Position label: P39 (position held) qualifier carries the actual role
    name ("President", "General Secretary", "National Convenor"). Free-
    text - we do NOT enum-close ``role`` because Wikidata labels are open.
  * Preferred rank only: ``wikibase:rank wikibase:PreferredRank`` filters
    out historical statements that have been superseded.

The pinned SPARQL query shape (paste this into query.wikidata.org and save
the JSON response in the ephemeral fixture path):

.. code-block:: sparql

    SELECT ?party ?partyLabel ?chief ?chiefLabel ?role ?roleLabel
           ?startTime ?endTime WHERE {
      VALUES ?party { wd:Q748724 wd:Q83294 wd:Q482156 }
      ?party p:P488|p:P3975 ?stmt.
      ?stmt ps:P488|ps:P3975 ?chief.
      OPTIONAL { ?stmt pq:P580 ?startTime. }
      OPTIONAL { ?stmt pq:P582 ?endTime. }
      OPTIONAL { ?stmt pq:P39 ?role. }
      ?stmt wikibase:rank wikibase:PreferredRank.
      SERVICE wikibase:label {
        bd:serviceParam wikibase:language "en".
      }
    }

The VALUES list is built from ``datasets/data/entities/parties.csv`` by the
operator before running the query: extract every party row whose
``wikipedia`` column is populated, resolve the Wikipedia article to its
Wikidata Q-id, and paste the Q-ids into the VALUES clause.

Date handling: SPARQL returns ISO timestamps like ``2020-01-20T00:00:00Z``;
we truncate to ``YYYY-MM-DD`` by splitting at ``T``. If ``startTime`` is
null (no P580 qualifier), the row is SKIPPED - we cannot place a term-shape
row on the timeline without a start date. PR-9 may add a hand-curated
override path for the small set of parties whose P488/P3975 statement
lacks P580.

Deduplication: SPARQL returns one row per matching statement, so a person
who is both chairperson (P488) and secretary general (P3975) of the same
party shows up twice. We dedupe by ``(party_id, valid_from)`` keeping the
first encountered row - the second row's ``role`` would be the alternative
label and we have no reason to prefer one over the other; the operator can
land a hand-curated correction in the source ledger if needed.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable


_CSV_HEADER: Final[tuple[str, ...]] = (
    "party_id",
    "role",
    "person_name",
    "person_wikidata_qid",
    "valid_from",
    "valid_to",
    "source_id",
)


@dataclass(frozen=True)
class WikidataLeadershipRow:
    """One row in ``parties_leadership.csv``, as emitted by the ingester.

    Mirrors the 7-column shape declared in
    ``datasets/data/_schema/columns.json`` for
    ``datasets/data/entities/parties_leadership.csv``. Composite PK is
    ``(party_id, valid_from)``.
    """

    party_id: str
    role: str  # actual P39 position label (e.g. "President", "General Secretary")
    person_name: str
    person_wikidata_qid: str | None  # may be None for hand-curated overrides
    valid_from: str  # ISO date YYYY-MM-DD
    valid_to: str | None  # ISO date YYYY-MM-DD; None = currently serving
    source_id: str  # FK to source.csv


def _truncate_iso_datetime(value: str | None) -> str | None:
    """Truncate a SPARQL ISO datetime payload to a YYYY-MM-DD date.

    Wikidata's SPARQL endpoint returns datetimes like
    ``2020-01-20T00:00:00Z`` even when the underlying claim is date-grain
    (P580/P582 typically carry day precision). Strip everything from the
    first ``T`` onward.

    Returns ``None`` when ``value`` is ``None`` or empty.
    """
    if value is None or value == "":
        return None
    return value.split("T", 1)[0]


def _qid_from_uri(uri: str | None) -> str | None:
    """Extract the trailing ``Q\\d+`` Q-id from a Wikidata entity URI.

    SPARQL ``?chief`` bindings come back as ``{"type": "uri", "value":
    "http://www.wikidata.org/entity/Q3104873"}``; we strip the path prefix
    and keep the final segment.

    Returns ``None`` when ``uri`` is falsy.
    """
    if not uri:
        return None
    return uri.rsplit("/", 1)[-1]


def _binding_value(binding: dict[str, dict[str, str]], key: str) -> str | None:
    """Pull the ``value`` out of a SPARQL JSON ``binding`` for ``key``.

    Returns ``None`` when the key is absent (OPTIONAL block returned no
    result) or its value is empty.
    """
    entry = binding.get(key)
    if not entry:
        return None
    value = entry.get("value")
    if not value:
        return None
    return value


def parse_sparql_fixture(
    json_path: Path,
    party_qid_to_party_id: dict[str, str],
    source_id: str,
) -> list[WikidataLeadershipRow]:
    """Parse a pinned SPARQL JSON response into typed rows.

    Args:
        json_path: Local pinned fixture file (e.g.
            ``ephemeral/wikidata-party-leadership-2026-06-13.json``).
        party_qid_to_party_id: Map from Wikidata Q-id (e.g. ``"Q748724"``)
            to yen-gov party_id (e.g. ``"parties.IN.BJP"``). Built by the
            caller from ``parties.csv.wikipedia`` -> Wikipedia article ->
            Q-id resolution.
        source_id: ``source.csv`` row src-id to attribute these rows to.
            Derived via ``backend.yen_gov.canonical.citation.derive_source_id``
            per CLAUDE.md section 12.

    Returns:
        List of ``WikidataLeadershipRow``, deduped by
        ``(party_id, valid_from)`` keeping the first encountered row.
        Rows whose source party is not in ``party_qid_to_party_id`` are
        silently skipped (the operator's VALUES list and the resolution
        map are derived from the same parties.csv slice, so any miss is a
        Wikidata-side data quality smell to surface in PR-9).
        Rows whose ``startTime`` qualifier is missing are also skipped:
        we cannot place a term-shape row on the timeline without a start
        date.
    """
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    bindings = payload.get("results", {}).get("bindings", [])

    seen_pk: set[tuple[str, str]] = set()
    rows: list[WikidataLeadershipRow] = []
    for binding in bindings:
        party_uri = _binding_value(binding, "party")
        party_qid = _qid_from_uri(party_uri)
        if party_qid is None:
            continue
        party_id = party_qid_to_party_id.get(party_qid)
        if party_id is None:
            continue

        start_time = _truncate_iso_datetime(_binding_value(binding, "startTime"))
        if start_time is None:
            # Cannot place a term-shape row without a start date; PR-9 may
            # add a hand-curated override path for these cases.
            continue

        pk = (party_id, start_time)
        if pk in seen_pk:
            continue
        seen_pk.add(pk)

        person_name = _binding_value(binding, "chiefLabel")
        if person_name is None:
            continue

        chief_qid = _qid_from_uri(_binding_value(binding, "chief"))
        role_label = _binding_value(binding, "roleLabel") or "President"
        end_time = _truncate_iso_datetime(_binding_value(binding, "endTime"))

        rows.append(
            WikidataLeadershipRow(
                party_id=party_id,
                role=role_label,
                person_name=person_name,
                person_wikidata_qid=chief_qid,
                valid_from=start_time,
                valid_to=end_time,
                source_id=source_id,
            )
        )

    return rows


def _read_existing_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read existing parties_leadership.csv rows for upsert.

    Returns an empty list when the file is missing or header-only.
    """
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _row_to_dict(row: WikidataLeadershipRow) -> dict[str, str]:
    """Serialise one ``WikidataLeadershipRow`` to a CSV-shaped dict.

    Empty cells (``""``) encode SQL NULL per the CSV column contract
    (csv-column-contract.md section 2). The writer's nullable flags in
    ``columns.json`` mark which columns may carry the empty string.
    """
    return {
        "party_id": row.party_id,
        "role": row.role,
        "person_name": row.person_name,
        "person_wikidata_qid": row.person_wikidata_qid or "",
        "valid_from": row.valid_from,
        "valid_to": row.valid_to or "",
        "source_id": row.source_id or "",
    }


def write_leadership_csv(
    rows: Iterable[WikidataLeadershipRow], csv_path: Path
) -> int:
    """Upsert rows into ``parties_leadership.csv`` on PK ``(party_id,
    valid_from)``.

    Preserves existing rows whose ``(party_id, valid_from)`` pair is NOT in
    the new batch (purely additive across party_ids). When the new batch
    contains a row whose PK matches an existing row, the new row REPLACES
    the existing one (upsert semantics).

    The file is rewritten with all rows sorted deterministically by the
    composite PK ``(party_id, valid_from)`` to satisfy the canonical CSV
    contract (csv_validator.py PK sort check).

    Args:
        rows: New batch of typed leadership rows.
        csv_path: Destination CSV path (e.g.
            ``datasets/data/entities/parties_leadership.csv``).

    Returns:
        Total number of rows written (existing-preserved + new-upserted),
        equal to ``len(final_rows)`` after dedup.
    """
    new_dicts = {(r.party_id, r.valid_from): _row_to_dict(r) for r in rows}

    existing = _read_existing_rows(csv_path)
    final: dict[tuple[str, str], dict[str, str]] = {}
    for ex in existing:
        pk = (ex.get("party_id", ""), ex.get("valid_from", ""))
        if pk in new_dicts:
            # New batch supersedes; skip the existing row.
            continue
        final[pk] = ex

    final.update(new_dicts)

    ordered = sorted(final.values(), key=lambda r: (r["party_id"], r["valid_from"]))

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_HEADER, lineterminator="\n")
        writer.writeheader()
        for row in ordered:
            writer.writerow(row)

    return len(ordered)
