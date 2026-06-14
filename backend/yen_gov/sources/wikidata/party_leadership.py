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
  * Preferred rank only: Originally the query carried a
    ``wikibase:rank wikibase:PreferredRank`` filter to keep current
    leaders only. PR-9 (2026-06-14) discovered that almost no Indian
    party Wikidata items mark statements as preferred rank (5 of 75
    parties resolved); dropping the filter widens to the full term-shape
    history (past + present) which is what the leadership table needs.
    The ``(party_id, valid_from)`` dedup in :func:`parse_sparql_fixture`
    correctly handles same-person-under-both-P488-and-P3975 duplicates.

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
import time
import urllib.error
import urllib.parse
import urllib.request
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


# ---------------------------------------------------------------------------
# PR-9: Live SPARQL snapshot (operator-named carve-out from Holy Law #1)
# ---------------------------------------------------------------------------
#
# PR-9 of TODO/20260613-party-deferred-followups-plan.md (closure ledger
# section 18 item 6). User explicitly authorised the live-fetch path:
# "happy to relax cache doctrine". The operator runs this CLI locally
# (NEVER in production / CI / GitHub Pages — they don't have a backend at
# runtime per Holy Law #1); the committed artefact is the CSV.
#
# The Wikipedia summary REST API resolves an article URL to its
# wikibase_item Q-id (one round-trip per party); the resulting Q-id map is
# committed at datasets/_ops/wikidata-party-qids.json so subsequent
# refreshes don't re-resolve already-known parties. The SPARQL query is
# the same one documented in the module-level docstring.


_WIKIDATA_SPARQL_URL: Final[str] = "https://query.wikidata.org/sparql"
_WIKIPEDIA_SUMMARY_API: Final[str] = "https://en.wikipedia.org/api/rest_v1/page/summary"
_USER_AGENT: Final[str] = (
    "yen-gov/1.0 (https://github.com/miztiik/yen-gov; "
    "Wikidata SPARQL operator-snapshot tool for party-leadership ingest)"
)
_HTTP_TIMEOUT_SECS: Final[int] = 60
_INTER_REQUEST_SLEEP_SECS: Final[float] = 0.2  # be polite to en.wikipedia REST


def _http_get_json(url: str) -> dict:
    """GET a URL with the polite User-Agent header and return parsed JSON.

    Raises ``urllib.error.HTTPError`` on non-2xx; the caller decides whether
    to surface (default) or skip (the resolver swallows 404 because some
    parties.csv ``wikipedia`` columns point at redirects or removed pages).
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECS) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_post_form_json(url: str, fields: dict[str, str]) -> dict:
    """POST a form to a URL expecting JSON back; polite User-Agent + Accept."""
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECS) as response:
        return json.loads(response.read().decode("utf-8"))


def _wikipedia_url_to_article_title(wikipedia_url: str) -> str | None:
    """Extract the URL-encoded article title from an en.wikipedia.org URL.

    Accepts the two forms parties.csv carries:
    ``https://en.wikipedia.org/wiki/<Title>`` and
    ``http://en.wikipedia.org/wiki/<Title>``. Returns ``None`` for any URL
    that does not match the ``en.wikipedia.org/wiki/`` shape; the caller
    skips and surfaces a warning.
    """
    if not wikipedia_url:
        return None
    parsed = urllib.parse.urlparse(wikipedia_url.strip())
    if parsed.netloc not in ("en.wikipedia.org",):
        return None
    if not parsed.path.startswith("/wiki/"):
        return None
    return parsed.path[len("/wiki/") :]


def resolve_qids_from_wikipedia(
    wikipedia_urls_by_party_id: dict[str, str],
    cached_map_path: Path | None = None,
) -> dict[str, str]:
    """Resolve each party_id -> Q-id via the Wikipedia summary REST API.

    Args:
        wikipedia_urls_by_party_id: ``{party_id: wikipedia_url}`` for every
            party whose Wikipedia URL is populated.
        cached_map_path: Optional path to a JSON file caching prior
            resolutions as ``{"Q748724": "parties.IN.BJP"}``. When set and
            the file exists, parties already in the cache (by party_id ->
            Q-id reverse lookup) are skipped. Newly-resolved entries are
            merged into the cache on disk after each successful fetch so a
            mid-run abort still preserves prior work.

    Returns:
        ``{qid: party_id}`` map — same shape the parser expects. Includes
        every cached + newly-resolved party. Parties whose Wikipedia URL
        doesn't resolve (404 / no wikibase_item) are silently skipped (a
        warning is printed to stderr).
    """
    import sys

    # Load existing cache (qid -> party_id).
    qid_to_party_id: dict[str, str] = {}
    if cached_map_path is not None and cached_map_path.exists():
        qid_to_party_id = json.loads(cached_map_path.read_text(encoding="utf-8"))

    # Build reverse lookup so we can skip already-known parties without
    # paying for another round-trip.
    known_party_ids = set(qid_to_party_id.values())

    to_resolve = {
        pid: url
        for pid, url in wikipedia_urls_by_party_id.items()
        if pid not in known_party_ids
    }
    if not to_resolve:
        return qid_to_party_id

    print(
        f"resolving {len(to_resolve)} new Wikipedia URL(s) to Q-ids "
        f"(skipped {len(known_party_ids)} already cached) ...",
        file=sys.stderr,
    )

    for party_id, wikipedia_url in sorted(to_resolve.items()):
        article_title = _wikipedia_url_to_article_title(wikipedia_url)
        if article_title is None:
            print(
                f"  skip {party_id}: not an en.wikipedia.org/wiki/ URL "
                f"({wikipedia_url!r})",
                file=sys.stderr,
            )
            continue

        # URL-encode again so spaces and parens survive
        api_url = f"{_WIKIPEDIA_SUMMARY_API}/{article_title}"
        try:
            payload = _http_get_json(api_url)
        except urllib.error.HTTPError as exc:
            print(
                f"  skip {party_id}: Wikipedia REST API {exc.code} "
                f"({api_url})",
                file=sys.stderr,
            )
            continue

        qid = payload.get("wikibase_item")
        if not qid:
            print(
                f"  skip {party_id}: no wikibase_item on Wikipedia article "
                f"({api_url})",
                file=sys.stderr,
            )
            continue

        qid_to_party_id[qid] = party_id
        print(f"  resolved {party_id} -> {qid}", file=sys.stderr)

        # Persist after each successful resolve so a mid-run abort keeps
        # prior work.
        if cached_map_path is not None:
            cached_map_path.parent.mkdir(parents=True, exist_ok=True)
            cached_map_path.write_text(
                json.dumps(
                    dict(sorted(qid_to_party_id.items())),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

        time.sleep(_INTER_REQUEST_SLEEP_SECS)

    return qid_to_party_id


def fetch_sparql_snapshot(qids: Iterable[str], output_path: Path) -> int:
    """POST the documented SPARQL query for ``qids`` and write the JSON.

    The query is the same as the module-level docstring example MINUS the
    ``wikibase:PreferredRank`` filter. PR-9 (2026-06-14) discovered that
    Wikidata's Indian-party leadership statements are almost never marked
    as preferred rank; the filter dropped 75-party coverage to 5 bindings.
    Dropping the filter widens to the full term-shape history (past +
    present); the parser's ``(party_id, valid_from)`` dedup correctly
    merges duplicate statements from the same person under both P488
    (chairperson) + P3975 (general secretary).

    Returns the number of bindings the SPARQL endpoint returned. Output
    JSON is pretty-printed with sorted keys for deterministic diffs.
    """
    qid_clause = " ".join(f"wd:{qid}" for qid in sorted(qids))
    query = (
        "SELECT ?party ?partyLabel ?chief ?chiefLabel ?role ?roleLabel "
        "?startTime ?endTime WHERE {\n"
        f"  VALUES ?party {{ {qid_clause} }}\n"
        "  ?party p:P488|p:P3975 ?stmt.\n"
        "  ?stmt ps:P488|ps:P3975 ?chief.\n"
        "  OPTIONAL { ?stmt pq:P580 ?startTime. }\n"
        "  OPTIONAL { ?stmt pq:P582 ?endTime. }\n"
        "  OPTIONAL { ?stmt pq:P39 ?role. }\n"
        '  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }\n'
        "}"
    )

    payload = _http_post_form_json(_WIKIDATA_SPARQL_URL, {"query": query})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return len(payload.get("results", {}).get("bindings", []))


def main(argv: list[str] | None = None) -> int:
    """Operator CLI for the live-snapshot path (PR-9 carve-out).

    Subcommands:
      * ``resolve-qids``: read parties.csv, resolve each populated
        wikipedia URL to a Q-id via the Wikipedia REST API, write/update
        the Q-id map at ``datasets/_ops/wikidata-party-qids.json``.
      * ``snapshot``: POST the SPARQL query with the resolved Q-ids, write
        the JSON response under
        ``datasets/ephemeral/wikidata-party-leadership-<YYYY-MM-DD>.json``.
      * ``ingest``: parse a snapshot JSON via :func:`parse_sparql_fixture`
        and write/upsert ``datasets/data/entities/parties_leadership.csv``.
      * ``refresh``: all three in one go (the operator's happy path).
    """
    import argparse
    import sys
    from datetime import date

    parser = argparse.ArgumentParser(
        prog="python -m yen_gov.sources.wikidata.party_leadership",
        description=(
            "Operator CLI for the Wikidata party-leadership snapshot "
            "(PR-9 carve-out per CLAUDE.md Holy Law #1 escape hatch)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repo root (default: cwd). Used to locate parties.csv + write paths.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("resolve-qids", help="Resolve wikipedia URLs -> Q-ids")
    subparsers.add_parser("snapshot", help="POST SPARQL query, write JSON")
    subparsers.add_parser(
        "ingest", help="Parse latest snapshot JSON, write parties_leadership.csv"
    )
    subparsers.add_parser(
        "refresh", help="resolve-qids + snapshot + ingest in one shot"
    )

    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()

    parties_csv = repo_root / "datasets" / "data" / "entities" / "parties.csv"
    qid_map_path = repo_root / "datasets" / "_ops" / "wikidata-party-qids.json"
    snapshot_dir = repo_root / "datasets" / "ephemeral"
    snapshot_path = snapshot_dir / f"wikidata-party-leadership-{date.today().isoformat()}.json"
    leadership_csv = repo_root / "datasets" / "data" / "entities" / "parties_leadership.csv"

    # Deterministic source_id per ADR-0032 / ADR-0042.
    # Producer + title + vintage are stable across snapshots; the snapshot
    # WINDOW changes daily but the citation identity is the dataset, not the
    # individual fetch (Wikidata is a continuously-edited wiki, so we cite
    # the query + endpoint as a single ongoing source rather than per-day).
    from yen_gov.canonical.citation import derive_source_id

    source_id = derive_source_id(
        producer="Wikimedia Foundation",
        title=(
            "Wikidata Query Service party leadership snapshot "
            "(P488 chairperson + P3975 secretary general + P39 role qualifier + "
            "P580 / P582 term bounds)"
        ),
        vintage="continuous",
    )

    if args.command in ("resolve-qids", "refresh"):
        wiki_by_pid: dict[str, str] = {}
        with parties_csv.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                url = (row.get("wikipedia") or "").strip()
                if url:
                    wiki_by_pid[row["party_id"]] = url
        print(f"parties.csv: {len(wiki_by_pid)} rows have wikipedia URLs", file=sys.stderr)
        qid_to_party_id = resolve_qids_from_wikipedia(wiki_by_pid, qid_map_path)
        print(
            f"qid map ({qid_map_path.name}): {len(qid_to_party_id)} entries",
            file=sys.stderr,
        )

    if args.command in ("snapshot", "refresh"):
        if not qid_map_path.exists():
            print(
                f"ERROR: {qid_map_path} not found. Run `resolve-qids` first.",
                file=sys.stderr,
            )
            return 2
        qid_to_party_id = json.loads(qid_map_path.read_text(encoding="utf-8"))
        bindings_count = fetch_sparql_snapshot(
            qid_to_party_id.keys(), snapshot_path
        )
        print(
            f"SPARQL snapshot: {bindings_count} bindings -> {snapshot_path.relative_to(repo_root)}",
            file=sys.stderr,
        )

    if args.command in ("ingest", "refresh"):
        if not qid_map_path.exists():
            print(f"ERROR: {qid_map_path} not found.", file=sys.stderr)
            return 2
        qid_to_party_id = json.loads(qid_map_path.read_text(encoding="utf-8"))
        # For `ingest`, find the most recent snapshot if not freshly fetched.
        if not snapshot_path.exists():
            candidates = sorted(snapshot_dir.glob("wikidata-party-leadership-*.json"))
            if not candidates:
                print(
                    f"ERROR: no snapshot JSON found under {snapshot_dir}/. "
                    f"Run `snapshot` first.",
                    file=sys.stderr,
                )
                return 2
            snapshot_path_to_read = candidates[-1]
        else:
            snapshot_path_to_read = snapshot_path
        print(
            f"ingest: reading {snapshot_path_to_read.relative_to(repo_root)}",
            file=sys.stderr,
        )
        rows = parse_sparql_fixture(snapshot_path_to_read, qid_to_party_id, source_id)
        written = write_leadership_csv(rows, leadership_csv)
        print(
            f"wrote {written} rows to {leadership_csv.relative_to(repo_root)} "
            f"(from {len(rows)} parsed bindings after dedup)",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
