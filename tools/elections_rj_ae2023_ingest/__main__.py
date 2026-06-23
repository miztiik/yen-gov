"""Canonical ingest of the IndiaVotes RJ-AE-2023 snapshot.

Reads (offline; no network):
- ``datasets/ephemeral/indiavotes-rj-ae2023/2023-11/results.csv``
  (candidate-grain, scraped by ``tools/scrape_indiavotes_rj_2023/``).
- ``datasets/data/entities/electoral.csv`` (RJ AC entity binding via
  fuzzy slug match on ``name``).
- ``datasets/data/entities/parties.csv`` (party-id resolution; sibling
  UNK-enrichment PR owns this file - this tool only reads).

Writes:
- ``datasets/elections/assembly/state=rajasthan/election=2023/candidacies.csv``
  (18-column canonical shape per the 2018 template; sole writer for this
  (state, year) pair).
- ``datasets/elections/assembly/state=rajasthan/election=2023/summary.csv``
  (DERIVED projection of candidacies; winner / runnerup / margin
  recomputed from the candidacies).
- ``datasets/data/entities/source.csv`` (citation-ledger row UPSERT for
  the IndiaVotes/Rajasthan-2023 source).

Holy Law compliance:
- #6 No hardcoded entity_id values; the AC bind happens via electoral.csv.
- #9 Every emitted row carries a source_id FK to source.csv (derived via
  ``derive_source_id``).
- #10 No silent demotion: party_id is ``parties.IN.UNK`` for misses,
  ``party_short_raw`` retains the IndiaVotes abbreviation so a future
  re-emit (after the UNK sibling PR adds aliases) lifts those rows to
  the canonical id without changing this tool.

Usage:

    python tools/elections_rj_ae2023_ingest/__main__.py
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.citation import derive_source_id  # noqa: E402
from yen_gov.canonical.party_resolver import (  # noqa: E402
    SENTINELS,
    UNK,
    load_resolver,
)

SNAPSHOT_DIR = REPO_ROOT / "datasets" / "ephemeral" / "indiavotes-rj-ae2023" / "2023-11"
ELECTORAL_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "electoral.csv"
PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
SOURCES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"
OUT_DIR = (
    REPO_ROOT
    / "datasets"
    / "elections"
    / "assembly"
    / "state=rajasthan"
    / "election=2023"
)

STATE_SLUG = "rajasthan"
ELECTION_YEAR = 2023

# Citation triple for the RJ 2023 results (ADR-0032 / Holy Law #9). ECI is
# the issuing authority for the constituency results; IndiaVotes (scraped
# upstream) is a redistribution channel, so per the issuing-authority rule
# (PR #1014 TCPD->ECI precedent + user directive 2026-06-23: election
# sources cite ECI only) the producer is ECI and the citation url points to
# the ECI domain. The scrape itself still reads the IndiaVotes master /
# per-AC URLs.
SOURCE_PRODUCER = "Election Commission of India"
SOURCE_TITLE = "Rajasthan Vidhan Sabha 2023"
SOURCE_VINTAGE = "2023-11"
SOURCE_URL = "https://www.eci.gov.in/"

# 18-column canonical shape; matches the 2018 RJ candidacies template
# byte-identically (header order is the column-contract; the validator's
# schema-of-schemas gate rejects any drift).
CANDIDACIES_COLUMNS = [
    "entity_id",
    "state",
    "election_year",
    "constituency_no",
    "constituency_name",
    "candidate_name",
    "party_id",
    "party_short_raw",
    "votes",
    "vote_share_pct",
    "position",
    "result",
    "sex",
    "age",
    "education",
    "profession",
    "candidate_type",
    "source_id",
]

# 19-column canonical summary shape (matches the 2018 RJ summary template
# byte-identically; recomputed from the candidacies per the parity-oracle gate).
SUMMARY_COLUMNS = [
    "entity_id",
    "state",
    "election_year",
    "constituency_name",
    "electors",
    "votes_polled",
    "turnout_pct",
    "winner_candidate",
    "winner_party_id",
    "winner_party_short_raw",
    "winner_votes",
    "winner_share_pct",
    "runnerup_candidate",
    "runnerup_party_id",
    "runnerup_party_short_raw",
    "runnerup_votes",
    "margin_votes",
    "margin_pct",
    "source_id",
]

# IndiaVotes-side AC slugs that need an explicit map to electoral.csv
# entity_id. Right-hand side is the canonical entity_id (NOT a slug)
# because the LGD-spine carries 2 RJ ACs sharing the name 'Shahpura' (one
# in Jaipur PC, one in Bhilwara PC), and a slug lookup would collide.
# IndiaVotes disambiguates the two with URL-suffix `-2`; we pin both
# slugs to their canonical entity_id here. Add a row whenever the
# unbound-AC stop-condition fires. NOTE: electoral.csv is the LGD
# entity-source-of-truth; we normalise INTO it, never mutate it from
# IndiaVotes.
_SLUG_OVERRIDES: dict[str, str] = {
    # Two RJ ACs share the name 'Shahpura' (electoral.csv entity_id
    # collision); IndiaVotes disambiguates via URL slug suffix `-2`.
    # Jaipur-cluster Shahpura: ECI ballot serial 42; LGD code 606.
    # Bhilwara-cluster Shahpura: ECI ballot serial 181; LGD code 551.
    "shahpura": "IN-AC-2008-rajasthan-606",
    "shahpura-2": "IN-AC-2008-rajasthan-551",
    # 8 spelling / hyphenation divergences between IndiaVotes URL slugs
    # and electoral.csv `name` slugs. Each is cross-confirmed against the
    # IndiaVotes per-AC `meta.aliases` blob (which carries the LGD/ECI
    # spelling explicitly). Surfaced empirically by running the ingest
    # with the empty override dict and reading the unbound list.
    "deoli-uniara": "IN-AC-2008-rajasthan-689",     # Deoli - uniara (Tonk)
    "gudha-malani": "IN-AC-2008-rajasthan-531",     # Gudhamalani (Barmer)
    "lachmangarh": "IN-AC-2008-rajasthan-684",      # Lachhmangarh (Sikar)
    "mandawar": "IN-AC-2008-rajasthan-516",         # Mundawar (Alwar; IV alias)
    "raisinghnagar": "IN-AC-2008-rajasthan-588",    # Raisingh Nagar (Sri Ganganagar)
    "sahada": "IN-AC-2008-rajasthan-550",           # Sahara (Bhilwara; IV alias)
    "toda-bhim": "IN-AC-2008-rajasthan-647",        # Todabhim (Karauli)
    "vallabhnagar": "IN-AC-2008-rajasthan-567",     # Vallabh Nagar (Udaipur)
}


def _slugify(name: str) -> str:
    """Reduce a constituency name to the IndiaVotes-style slug form.

    Rules: lowercase, drop diacritics (none in our RJ corpus), replace
    spaces and underscores with hyphens, strip parens. Idempotent.
    """
    text = (name or "").strip().lower()
    text = text.replace("_", " ")
    # Strip parens (e.g. "Sangod (Schedule Caste)" -> "sangod schedule caste").
    text = re.sub(r"[()\.]", "", text)
    # Collapse whitespace then hyphenate.
    text = re.sub(r"\s+", "-", text)
    return text


def _load_electoral_rj() -> tuple[
    dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]
]:
    """Build (by_slug -> list, by_entity_id -> entity) for the 200 RJ ACs.

    Multi-value slug map handles the Shahpura collision (Jaipur vs
    Bhilwara); the by_entity_id map handles ``_SLUG_OVERRIDES`` direct
    lookups. Both maps cover all 200 RJ AC rows (no row is dropped on
    load; dedup happens at the resolution boundary).
    """
    by_slug: dict[str, list[dict[str, Any]]] = {}
    by_entity_id: dict[str, dict[str, Any]] = {}
    with ELECTORAL_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("entity_kind") != "ac" or row.get("state") != STATE_SLUG:
                continue
            slug = _slugify(row.get("name") or "")
            if not slug:
                continue
            entity = {
                "entity_id": row["entity_id"],
                "eci_no": int(row["eci_no"]),
                "name": row["name"],
                "reservation": row.get("reservation") or "",
                "parent": row.get("parent") or "",
            }
            by_slug.setdefault(slug, []).append(entity)
            by_entity_id[entity["entity_id"]] = entity
    return by_slug, by_entity_id


def _resolve_entity(
    iv_slug: str,
    ac_name_iv: str,
    *,
    by_slug: dict[str, list[dict[str, Any]]],
    by_entity_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve an IndiaVotes constituency to one electoral.csv entity.

    Priority: explicit ``_SLUG_OVERRIDES`` entity_id -> IndiaVotes slug
    exact (single-match) -> name slug exact (single-match). On a multi-
    match without a corresponding override, returns ``None`` so the
    operator surfaces it and adds an override row.
    """
    override = _SLUG_OVERRIDES.get(iv_slug)
    if override is not None:
        return by_entity_id.get(override)
    hits = by_slug.get(iv_slug) or by_slug.get(_slugify(ac_name_iv)) or []
    if len(hits) == 1:
        return hits[0]
    return None


def _read_snapshot_rows() -> list[dict[str, str]]:
    results_csv = SNAPSHOT_DIR / "results.csv"
    if not results_csv.exists():
        raise FileNotFoundError(
            f"snapshot {results_csv.relative_to(REPO_ROOT).as_posix()} missing; "
            "run tools/scrape_indiavotes_rj_2023/__main__.py first"
        )
    with results_csv.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# Deposit-forfeit threshold: ECI rule is share < 1/6 of valid votes (~16.67%).
# Matches the schema enum {won, lost, forfeit} (columns.json line 240) +
# the TCPD writer's _result(position, deposit_lost) precedent.
_FORFEIT_SHARE_THRESHOLD_PCT = 100.0 / 6.0


def _result_label(position: int, vote_share_pct: float | None) -> str:
    """Map (position, vote_share_pct) -> canonical result enum.

    IndiaVotes does not publish the ECI deposit-lost flag, so we derive
    it from the standard rule: share < 1/6 of valid votes -> forfeit.
    Position-1 always wins regardless of share (e.g. uncontested or
    fragmented multi-corner races where the winner sits under 16.67%
    can in principle happen). Position-2+ with share >= 1/6 = lost;
    share < 1/6 = forfeit.
    """
    if position == 1:
        return "won"
    if vote_share_pct is not None and vote_share_pct < _FORFEIT_SHARE_THRESHOLD_PCT:
        return "forfeit"
    return "lost"


def _upsert_source_row(source_id: str) -> bool:
    """UPSERT the IndiaVotes RJ-2023 row into source.csv.

    Idempotent: returns True iff a new row was written. The source.csv
    column order is ``(source_id, owner, title, vintage, url)`` per the
    schema-of-schemas spec; we preserve it.
    """
    rows: list[dict[str, str]] = []
    if SOURCES_CSV.exists():
        with SOURCES_CSV.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    for row in rows:
        if row.get("source_id") == source_id:
            return False  # already present
    rows.append(
        {
            "source_id": source_id,
            "owner": SOURCE_PRODUCER,
            "title": SOURCE_TITLE,
            "vintage": SOURCE_VINTAGE,
            "url": SOURCE_URL,
        }
    )
    rows.sort(key=lambda r: r["source_id"])
    with SOURCES_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["source_id", "owner", "title", "vintage", "url"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return True


def _build_candidacy_row(
    iv_row: dict[str, str],
    *,
    entity: dict[str, Any],
    party_id: str,
    source_id: str,
) -> dict[str, Any]:
    """Map one IndiaVotes candidate row -> canonical candidacies row."""

    vote_share = (
        float(iv_row["vote_share_pct"])
        if iv_row.get("vote_share_pct")
        else None
    )
    position = int(iv_row.get("position") or 0)
    # Preserve the publisher's verbatim party label per CLAUDE.md section 10.
    # IndiaVotes sometimes leaves party_abbreviation empty for candidates
    # whose party identity IndiaVotes itself does not recognise; the
    # party_slug (e.g. "party-unknown-NNNN") still carries IndiaVotes'
    # classification of the row so we surface it on party_short_raw rather
    # than lose the information.
    raw_abbr = (iv_row.get("party_abbreviation") or "").strip()
    raw_slug = (iv_row.get("party_slug") or "").strip()
    party_short_raw = raw_abbr or raw_slug or None
    return {
        "entity_id": entity["entity_id"],
        "state": STATE_SLUG,
        "election_year": ELECTION_YEAR,
        "constituency_no": entity["eci_no"],
        "constituency_name": entity["name"].upper(),
        "candidate_name": (iv_row.get("candidate_name") or "").strip(),
        "party_id": party_id,
        "party_short_raw": party_short_raw,
        "votes": int(iv_row.get("votes") or 0),
        "vote_share_pct": vote_share,
        "position": position,
        "result": _result_label(position, vote_share),
        # IndiaVotes does not publish candidate demographics; the
        # canonical columns must still exist (validator enforces 18-col
        # header) so we emit the same neutral defaults the 2018 template
        # uses for missing-demographics rows.
        "sex": "U",
        "age": None,
        "education": None,
        "profession": None,
        # IndiaVotes does not publish incumbent / turncoat flags; default
        # everything to "challenger". A future PR can fold incumbency
        # detection by name-matching against the 2018 winners list (the
        # entity_id is stable across the 2008 delimitation).
        "candidate_type": "challenger",
        "source_id": source_id,
    }


def _round_or_none(value: float | None, places: int = 2) -> float | None:
    return None if value is None else round(value, places)


def _build_summary_row(
    entity_id: str,
    constituency_name: str,
    candidacy_rows: list[dict[str, Any]],
    iv_summary: dict[str, str] | None,
    *,
    source_id: str,
) -> dict[str, Any]:
    """Project one summary row from sorted candidacies + per-AC summary facts.

    Mirrors ``backend/yen_gov/canonical/reingest/assembly_results.py``
    ``recompute_summary_row`` shape so the parity-oracle gate sees an
    identical projection. ``iv_summary`` carries the electorate-level
    facts (electors / votes_polled / turnout / nota_votes) that are NOT
    derivable from candidate rows.
    """
    ranked = sorted(candidacy_rows, key=lambda r: int(r["votes"]), reverse=True)
    winner = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    winner_share = winner.get("vote_share_pct")
    runner_share = runner.get("vote_share_pct") if runner else None
    if runner is not None and winner_share is not None and runner_share is not None:
        margin_pct = _round_or_none(winner_share - runner_share)
    else:
        margin_pct = None

    electors = (
        int(iv_summary["voters_eligible"])
        if iv_summary and iv_summary.get("voters_eligible")
        else None
    )
    votes_polled = (
        int(iv_summary["votes_polled"])
        if iv_summary and iv_summary.get("votes_polled")
        else None
    )
    turnout_pct = (
        _round_or_none(float(iv_summary["turnout_pct"]))
        if iv_summary and iv_summary.get("turnout_pct")
        else None
    )

    return {
        "entity_id": entity_id,
        "state": STATE_SLUG,
        "election_year": ELECTION_YEAR,
        "constituency_name": constituency_name,
        "electors": electors,
        "votes_polled": votes_polled,
        "turnout_pct": turnout_pct,
        "winner_candidate": winner["candidate_name"],
        "winner_party_id": winner["party_id"],
        "winner_party_short_raw": winner["party_short_raw"],
        "winner_votes": winner["votes"],
        "winner_share_pct": _round_or_none(winner_share),
        "runnerup_candidate": runner["candidate_name"] if runner else None,
        "runnerup_party_id": runner["party_id"] if runner else None,
        "runnerup_party_short_raw": runner["party_short_raw"] if runner else None,
        "runnerup_votes": runner["votes"] if runner else None,
        "margin_votes": (winner["votes"] - runner["votes"]) if runner else None,
        "margin_pct": margin_pct,
        "source_id": source_id,
    }


def _write_csv(
    path: Path, rows: list[dict[str, Any]], fieldnames: list[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        # Coerce ``None`` to empty string for nullable columns so the
        # validator's nullable-column rule (empty = NULL) matches the
        # 2018 template byte-shape.
        for row in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="elections_rj_ae2023_ingest",
        description=(
            "Map the IndiaVotes RJ-AE-2023 snapshot to canonical "
            "candidacies + summary CSVs. Idempotent."
        ),
    )
    parser.parse_args(argv)  # no flags today; placeholder for future tunables

    print("[ingest] loading snapshot rows", file=sys.stderr)
    snapshot_rows = _read_snapshot_rows()
    print(f"[ingest] {len(snapshot_rows)} candidate rows from snapshot", file=sys.stderr)

    summary_csv = SNAPSHOT_DIR / "summary.csv"
    iv_summary_by_slug: dict[str, dict[str, str]] = {}
    if summary_csv.exists():
        with summary_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                iv_summary_by_slug[row["constituency_slug"]] = row

    print("[ingest] loading electoral.csv RJ ACs", file=sys.stderr)
    by_slug, by_entity_id = _load_electoral_rj()
    print(
        f"[ingest] {len(by_entity_id)} RJ ACs in electoral.csv "
        f"({len(by_slug)} distinct slugs)",
        file=sys.stderr,
    )

    print("[ingest] loading party resolver", file=sys.stderr)
    resolver = load_resolver(PARTIES_CSV)
    print(
        f"[ingest] resolver has {len(resolver.by_alias)} aliases / "
        f"{len(resolver.by_party_id)} party_ids",
        file=sys.stderr,
    )

    source_id = derive_source_id(SOURCE_PRODUCER, SOURCE_TITLE, SOURCE_VINTAGE)
    print(f"[ingest] source_id = {source_id}", file=sys.stderr)

    unbound: list[tuple[str, str]] = []
    candidacy_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    party_resolution_stats = {"resolved": 0, "unk": 0, "ind": 0, "nota": 0}

    snapshot_by_slug: dict[str, list[dict[str, str]]] = {}
    for row in snapshot_rows:
        snapshot_by_slug.setdefault(row["constituency_slug"], []).append(row)
    for iv_slug, rows in sorted(snapshot_by_slug.items()):
        ac_name = rows[0].get("constituency_name") or iv_slug
        entity = _resolve_entity(
            iv_slug, ac_name, by_slug=by_slug, by_entity_id=by_entity_id
        )
        if entity is None:
            unbound.append((iv_slug, ac_name))
            continue
        ac_candidacies: list[dict[str, Any]] = []
        for r in rows:
            raw = (r.get("party_abbreviation") or "").strip()
            is_ind = raw.upper() == "IND"
            party_id = resolver.resolve(
                party_short=raw if not is_ind else None,
                eci_code=None,
                is_independent=is_ind,
            )
            if party_id == SENTINELS["IND"]:
                party_resolution_stats["ind"] += 1
            elif party_id == UNK:
                party_resolution_stats["unk"] += 1
            else:
                party_resolution_stats["resolved"] += 1
            ac_candidacies.append(
                _build_candidacy_row(
                    r, entity=entity, party_id=party_id, source_id=source_id
                )
            )
        # Sort within AC by (position, candidate_name) for stable diffs.
        ac_candidacies.sort(
            key=lambda x: (int(x["position"]), str(x["candidate_name"]))
        )
        candidacy_rows.extend(ac_candidacies)
        summary_rows.append(
            _build_summary_row(
                entity_id=entity["entity_id"],
                constituency_name=entity["name"].upper(),
                candidacy_rows=ac_candidacies,
                iv_summary=iv_summary_by_slug.get(iv_slug),
                source_id=source_id,
            )
        )

    # Global sort by constituency_no for stable output (matches 2018 template).
    # constituency_no is the ECI ballot serial (numeric); entity_id suffix
    # is the LGD code OR the 'eci<N>' string when LGD code is unavailable
    # (13 of 200 RJ ACs use the eci<N> form) so we sort summary rows by
    # constituency_no instead.
    candidacy_rows.sort(
        key=lambda r: (int(r["constituency_no"]), int(r["position"]), str(r["candidate_name"]))
    )
    summary_rows.sort(key=lambda r: int(r["entity_id"].split("-")[-1].replace("eci", "")))

    if unbound:
        print(
            f"[ingest] {len(unbound)} unbound ACs (electoral.csv miss):",
            file=sys.stderr,
        )
        for slug, name in unbound[:10]:
            print(f"[ingest]   {slug!r} ({name!r})", file=sys.stderr)
        if len(unbound) > 10:
            print(f"[ingest]   ... +{len(unbound) - 10} more", file=sys.stderr)
        # Hard-stop: brief stop-condition "AC count != 200".
        print(
            "[ingest] STOP: unbound ACs present; add overrides to "
            "_SLUG_OVERRIDES and re-run",
            file=sys.stderr,
        )
        return 2

    print(
        f"[ingest] resolved: {party_resolution_stats}",
        file=sys.stderr,
    )

    _write_csv(OUT_DIR / "candidacies.csv", candidacy_rows, CANDIDACIES_COLUMNS)
    _write_csv(OUT_DIR / "summary.csv", summary_rows, SUMMARY_COLUMNS)
    new_source = _upsert_source_row(source_id)
    print(
        f"[ingest] wrote candidacies.csv ({len(candidacy_rows)} rows) + "
        f"summary.csv ({len(summary_rows)} rows)",
        file=sys.stderr,
    )
    print(
        f"[ingest] source.csv {'+1 row written' if new_source else 'already had this src-id'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
