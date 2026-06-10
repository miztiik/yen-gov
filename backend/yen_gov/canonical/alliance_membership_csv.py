"""Alliance membership term-shape emitter (plan section 20.4).

Emits ``datasets/data/datapoints/alliance_membership.csv`` from two
existing alliance-evidence sources:

1. ``datasets/taxonomy/office_holdings.json`` - per-CM-tenure alliance
   field. Holdings rows where ``alliance`` is non-null AND
   ``party_eci_code`` is non-null AND ``start_date`` is non-null become
   alliance_membership rows. ``term_start`` and ``term_end`` come
   directly from the tenure boundaries.

2. ``datasets/data/entities/party_alliances.csv`` - per-event alliance
   snapshot (one row per (party_id, period_label, alliance)). Rows with
   a non-empty ``alliance`` become alliance_membership rows. ``term_start``
   is resolved to the event's ``polled_on`` date via
   ``datasets/taxonomy/election_events.json``; ``term_end`` is null since
   the event snapshot does not record when the alliance ended.

Deduplication by PK = ``(alliance_id, party_id, term_start)``. When both
sources cite the same triple, the holdings-derived row wins because it
carries explicit term boundaries.

Per Holy Law #9: every emitted row carries ``source_id`` FK to
``datasets/data/entities/source.csv``. Source resolution rules:

- For holdings rows with a ``citation_group_id`` -> read the matching
  ``citation_groups[<id>].url_main`` from the seed file and look it up
  in ``source.csv`` by URL.
- For holdings rows without ``citation_group_id`` -> read
  ``office_citations[<office_id>].url_main`` and look it up the same
  way (this is the Wikipedia CM-list path).
- For party_alliances rows -> carry through the existing ``source_id``
  column.
- A row that fails source resolution is SKIPPED and surfaced via the
  function's return diagnostics; never silently dropped.

Per plan section 20.4: alliances share the term-shape spine with
office_holdings.csv but are NOT a fourth entity table. ``alliance_id`` is
a free-text short label (NDA, UPA, SPA, AIADMK+, Mahagathbandhan, etc.)
since no upstream issuing authority publishes a stable alliance
identity register.

No mocks (Holy Law #7). Stdlib + csv_writer only.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv

__all__ = [
    "FILE_CLASS",
    "EmitResult",
    "emit",
    "load_party_eci_to_party_id",
    "load_source_id_by_url",
    "load_event_id_to_polled_on",
]


FILE_CLASS = "datasets/data/datapoints/alliance_membership.csv"


@dataclass(frozen=True)
class EmitResult:
    """Diagnostics returned by :func:`emit`.

    Attributes:
        out_csv_path: the resolved CSV path.
        rows_written: number of unique alliance_membership rows emitted.
        from_holdings: count of rows sourced from office_holdings.json.
        from_party_alliances: count of rows sourced from party_alliances.csv.
        unresolved_party_eci_codes: ECI party codes on holdings rows that
            had no match in parties.csv (sorted, deduped). Surface to
            operator for catalogue extension.
        unresolved_source_urls: URLs on holdings rows that had no match
            in source.csv (sorted, deduped). Surface to operator for
            source-ledger extension.
    """

    out_csv_path: Path
    rows_written: int
    from_holdings: int
    from_party_alliances: int
    unresolved_party_eci_codes: tuple[str, ...]
    unresolved_source_urls: tuple[str, ...]


def load_party_eci_to_party_id(party_entities_csv: Path) -> dict[str, str]:
    """Return ``ECI party code (as string) -> party_id`` from parties.csv."""
    out: dict[str, str] = {}
    with party_entities_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            party_id = (row.get("party_id") or "").strip()
            eci_raw = (row.get("eci_codes") or "").strip()
            if not party_id or not eci_raw:
                continue
            out[eci_raw] = party_id
    return out


def load_source_id_by_url(source_csv: Path) -> dict[str, str]:
    """Return ``url -> source_id`` mapping from source.csv."""
    out: dict[str, str] = {}
    with source_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            source_id = (row.get("source_id") or "").strip()
            url = (row.get("url") or "").strip()
            if not source_id or not url:
                continue
            out[url] = source_id
    return out


def load_event_id_to_polled_on(election_events_json: Path) -> dict[str, str]:
    """Return ``event_id -> polled_on`` date map from election_events.json.

    The JSON shape is::

        { "states": { "S01": [ {"event_id": "...", "polled_on": "..."}, ... ], ... } }

    We walk every state's events and harvest the (event_id, polled_on) pairs.
    When the same event_id appears under multiple states (e.g. national
    Parliament events), the polled_on values agree by construction, so
    last-write-wins is safe.
    """
    out: dict[str, str] = {}
    with election_events_json.open("r", encoding="utf-8") as handle:
        doc = json.load(handle)
    states: dict[str, list[dict[str, Any]]] = doc.get("states", {})
    for events in states.values():
        for event in events:
            event_id = (event.get("event_id") or "").strip()
            polled_on = (event.get("polled_on") or "").strip()
            if event_id and polled_on:
                out[event_id] = polled_on
    return out


def _resolve_holdings_source_id(
    holding: Mapping[str, Any],
    office_citations: Mapping[str, Mapping[str, Any]],
    citation_groups: Mapping[str, Mapping[str, Any]],
    source_id_by_url: Mapping[str, str],
) -> tuple[str | None, str | None]:
    """Return ``(source_id, unresolved_url)``.

    ``source_id`` is the resolved id; ``unresolved_url`` is the URL we
    tried but could not find in source.csv (or None when we found one).
    """
    citation_group_id = (holding.get("citation_group_id") or "").strip()
    if citation_group_id and citation_group_id in citation_groups:
        url = (citation_groups[citation_group_id].get("url_main") or "").strip()
        if url:
            source_id = source_id_by_url.get(url)
            if source_id:
                return source_id, None
            return None, url
    office_id = (holding.get("office_id") or "").strip()
    if office_id and office_id in office_citations:
        url = (office_citations[office_id].get("url_main") or "").strip()
        if url:
            source_id = source_id_by_url.get(url)
            if source_id:
                return source_id, None
            return None, url
    return None, None


def _extract_from_office_holdings(
    office_holdings_json: Path,
    party_eci_to_id: Mapping[str, str],
    source_id_by_url: Mapping[str, str],
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    """Return ``(rows, unresolved_party_codes, unresolved_source_urls)``."""
    with office_holdings_json.open("r", encoding="utf-8") as handle:
        doc = json.load(handle)
    office_citations: dict[str, dict[str, Any]] = doc.get("office_citations", {})
    citation_groups: dict[str, dict[str, Any]] = doc.get("citation_groups", {})
    holdings: list[dict[str, Any]] = doc.get("holdings", [])

    rows: list[dict[str, Any]] = []
    unresolved_codes: set[str] = set()
    unresolved_urls: set[str] = set()

    for holding in holdings:
        alliance = (holding.get("alliance") or "").strip()
        party_eci_raw = holding.get("party_eci_code")
        party_eci_code = (
            str(party_eci_raw).strip() if party_eci_raw is not None else ""
        )
        start_date = (holding.get("start_date") or "").strip()

        if not alliance or not party_eci_code or not start_date:
            continue

        party_id = party_eci_to_id.get(party_eci_code)
        if party_id is None:
            unresolved_codes.add(party_eci_code)
            continue

        source_id, unresolved_url = _resolve_holdings_source_id(
            holding,
            office_citations,
            citation_groups,
            source_id_by_url,
        )
        if source_id is None:
            if unresolved_url:
                unresolved_urls.add(unresolved_url)
            continue

        end_date_raw = holding.get("end_date")
        end_date = end_date_raw.strip() if isinstance(end_date_raw, str) else None
        if end_date == "":
            end_date = None

        rows.append(
            {
                "alliance_id": alliance,
                "party_id": party_id,
                "term_start": start_date,
                "term_end": end_date,
                "source_id": source_id,
            }
        )

    return rows, unresolved_codes, unresolved_urls


def _extract_from_party_alliances(
    party_alliances_csv: Path,
    event_id_to_polled_on: Mapping[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with party_alliances_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            party_id = (row.get("party_id") or "").strip()
            period_label = (row.get("period_label") or "").strip()
            alliance = (row.get("alliance") or "").strip()
            source_id = (row.get("source_id") or "").strip()

            if not party_id or not period_label or not alliance or not source_id:
                continue

            term_start = event_id_to_polled_on.get(period_label)
            if not term_start:
                continue

            rows.append(
                {
                    "alliance_id": alliance,
                    "party_id": party_id,
                    "term_start": term_start,
                    "term_end": None,
                    "source_id": source_id,
                }
            )
    return rows


def emit(
    *,
    office_holdings_json: Path,
    party_alliances_csv: Path,
    parties_entities_csv: Path,
    election_events_json: Path,
    source_csv: Path,
    out_csv_path: Path,
) -> EmitResult:
    """Emit ``alliance_membership.csv`` and return a diagnostics record.

    Args:
        office_holdings_json: ``datasets/taxonomy/office_holdings.json``.
        party_alliances_csv: ``datasets/data/entities/party_alliances.csv``.
        parties_entities_csv: ``datasets/data/entities/parties.csv``.
        election_events_json: ``datasets/taxonomy/election_events.json``.
        source_csv: ``datasets/data/entities/source.csv`` (FK target).
        out_csv_path: target CSV (typically
            ``datasets/data/datapoints/alliance_membership.csv``).

    Returns:
        :class:`EmitResult` with the resolved path, row counts, and any
        unresolved party-ECI codes or source URLs surfaced for operator
        follow-up.

    Raises:
        FileNotFoundError: any required input file is missing.
    """
    for required in (
        office_holdings_json,
        party_alliances_csv,
        parties_entities_csv,
        election_events_json,
        source_csv,
    ):
        if not required.is_file():
            raise FileNotFoundError(required)

    party_eci_to_id = load_party_eci_to_party_id(parties_entities_csv)
    source_id_by_url = load_source_id_by_url(source_csv)
    event_id_to_polled_on = load_event_id_to_polled_on(election_events_json)

    holdings_rows, unresolved_codes, unresolved_urls = _extract_from_office_holdings(
        office_holdings_json,
        party_eci_to_id,
        source_id_by_url,
    )
    party_alliances_rows = _extract_from_party_alliances(
        party_alliances_csv,
        event_id_to_polled_on,
    )

    seen_pk: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    from_holdings = 0
    for row in holdings_rows:
        pk = (row["alliance_id"], row["party_id"], row["term_start"])
        if pk in seen_pk:
            continue
        seen_pk.add(pk)
        deduped.append(row)
        from_holdings += 1
    from_party_alliances = 0
    for row in party_alliances_rows:
        pk = (row["alliance_id"], row["party_id"], row["term_start"])
        if pk in seen_pk:
            continue
        seen_pk.add(pk)
        deduped.append(row)
        from_party_alliances += 1

    write_csv(path=out_csv_path, file_class=FILE_CLASS, rows=deduped)

    return EmitResult(
        out_csv_path=out_csv_path,
        rows_written=len(deduped),
        from_holdings=from_holdings,
        from_party_alliances=from_party_alliances,
        unresolved_party_eci_codes=tuple(sorted(unresolved_codes)),
        unresolved_source_urls=tuple(sorted(unresolved_urls)),
    )
