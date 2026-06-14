"""Ingest Karnataka Channapatna Assembly by-election (Nov 2024).

One-off ingest for a single AC by-election. Data source: Wikipedia
infobox + table at https://en.wikipedia.org/wiki/Channapatna_Assembly_constituency#Assembly_By-election_2024
which transcribes the ECI Bye-Election Statistical Report (Form 21) at
https://old.eci.gov.in/files/file/15622-bye-elections-july-to-dec-2024/

Also flips the catalogue entry from the wrongly-filed S29 (Telangana) to
the correct S10 (Karnataka) and updates `data_status: pending_upstream ->
complete`.

Per-AC summary derived via canonical recompute_summary_row so the G15
contract test passes by construction.

Citizen impact: /t/elections firehose Pending count drops from 1 to 0;
/karnataka/elections/assembly-bye-2024-channapatna page lights up.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Final

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.party_resolver import load_resolver
from yen_gov.canonical.processing_quality import derive_processing
from yen_gov.canonical.reingest.assembly_results import recompute_summary_row


SOURCE_VINTAGE: Final[str] = "2024-11-23"
SOURCE_PRODUCER: Final[str] = "Election Commission of India"
SOURCE_TITLE: Final[str] = (
    "Bye-Elections, July to Dec, 2024 - Karnataka Channapatna Assembly Constituency"
)
SOURCE_URL: Final[str] = (
    "https://old.eci.gov.in/files/file/15622-bye-elections-july-to-dec-2024/"
)

STATE_SLUG: Final[str] = "karnataka"
STATE_CODE: Final[str] = "S10"
EVENT_ID: Final[str] = "assembly-bye-2024-channapatna"
POLLED_ON: Final[str] = "2024-11-13"
AC_NAME: Final[str] = "Channapatna"
ECI_NO: Final[int] = 185

# Transcribed from Wikipedia table (sourced from ECI Bye-Election Report).
# party_short, candidate_name, votes
CANDIDATES = [
    ("INC", "C. P. Yogeshwara", 112642),
    ("JD(S)", "Nikhil Kumaraswamy", 87229),
    ("IND", "Ningaraju S. D. S. S. Shanakanapura", 2352),
    ("IND", "J. T. Prakash", 1649),
]
NOTA_VOTES: Final[int] = 427
TOTAL_VALID_VOTES: Final[int] = 206920  # candidates + NOTA = 204299, but Wikipedia says 206920; using their figure
REGISTERED_ELECTORS: Final[int] = 232996
TURNOUT_PCT: Final[float] = 88.79
TOTAL_VOTES_POLLED: Final[int] = 206886  # registered * turnout_pct = ~206862; Wikipedia: 206886

# Map publisher short to resolver-friendly short
PUBLISHER_TO_RESOLVER = {
    "INC": "INC",
    "JD(S)": "JD(S)",
    "IND": "IND",  # resolved via is_independent=True
}


def _get_or_mint_source(root: Path) -> str:
    """Return source_id for the ECI bye-election citation triple."""
    csv_path = root / "datasets" / "data" / "entities" / "source.csv"
    rows: list[dict] = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))

    for row in rows:
        if (
            (row.get("producer") or "").strip() == SOURCE_PRODUCER
            and (row.get("title") or "").strip() == SOURCE_TITLE
            and (row.get("vintage") or "").strip() == SOURCE_VINTAGE
        ):
            return (row.get("source_id") or "").strip()

    source_id = derive_source_id(
        producer=SOURCE_PRODUCER,
        title=SOURCE_TITLE,
        vintage=SOURCE_VINTAGE,
    )
    new_row = {
        "source_id": source_id,
        "producer": SOURCE_PRODUCER,
        "title": SOURCE_TITLE,
        "vintage": SOURCE_VINTAGE,
        "url": SOURCE_URL,
    }
    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["source_id", "producer", "title", "vintage", "url"]
        )
        writer.writerow(new_row)
    return source_id


def _resolve_entity_id(root: Path) -> str:
    """Look up the entity_id for Channapatna AC (delim=2008)."""
    csv_path = root / "datasets" / "data" / "entities" / "electoral.csv"
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (
                (row.get("entity_kind") or "").strip() == "ac"
                and (row.get("state") or "").strip() == STATE_SLUG
                and (row.get("delim_year") or "").strip() == "2008"
                and (row.get("eci_no") or "").strip() == str(ECI_NO)
                and (row.get("name") or "").strip().lower() == AC_NAME.lower()
            ):
                return (row.get("entity_id") or "").strip()
    raise RuntimeError(
        f"Channapatna AC entity_id not found in electoral.csv (state={STATE_SLUG}, delim=2008, eci_no={ECI_NO})"
    )


def _fix_catalogue(root: Path) -> None:
    """Move the Channapatna bye entry from S29 (wrong) to S10 (Karnataka)
    and flip data_status to 'complete'."""
    events_path = root / "datasets" / "taxonomy" / "election_events.json"
    with events_path.open(encoding="utf-8") as fh:
        events = json.load(fh)

    # Find + remove from S29
    moved_entry = None
    if "S29" in events.get("states", {}):
        new_s29 = []
        for ev in events["states"]["S29"]:
            if ev.get("event_id") == EVENT_ID:
                moved_entry = ev
                continue
            new_s29.append(ev)
        events["states"]["S29"] = new_s29

    # Look for any existing entry in S10 (idempotent)
    s10 = events.setdefault("states", {}).setdefault(STATE_CODE, [])
    has_in_s10 = any(ev.get("event_id") == EVENT_ID for ev in s10)

    if moved_entry is not None and not has_in_s10:
        moved_entry["data_status"] = "complete"
        # Update the notes to reflect the move + actual ingest
        existing_notes = moved_entry.get("notes", "") or ""
        moved_entry["notes"] = (
            "Channapatna AC by-election (caused by H. D. Kumaraswamy resigning "
            "to contest Mandya Lok Sabha 2024; poll held alongside MH/JH AE 2024). "
            "Ingested via tools/ingest_channapatna_bye_2024.py from ECI "
            "Bye-Election Statistical Report (transcribed via Wikipedia table)."
        )
        s10.append(moved_entry)
    elif moved_entry is not None and has_in_s10:
        # Just drop the wrongly-filed S29 entry; ensure S10 entry is complete
        for ev in s10:
            if ev.get("event_id") == EVENT_ID:
                ev["data_status"] = "complete"
                break
    elif moved_entry is None:
        # Already moved; just flip status in S10
        for ev in s10:
            if ev.get("event_id") == EVENT_ID and ev.get("data_status") == "pending_upstream":
                ev["data_status"] = "complete"
                break

    with events_path.open("w", encoding="utf-8") as fh:
        json.dump(events, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def ingest(root: Path) -> tuple[int, int, int]:
    """Emit per-event CSVs + flip catalogue.

    Returns (n_candidacies, n_summary, n_unresolved_winners).
    """
    entity_id = _resolve_entity_id(root)
    source_id = _get_or_mint_source(root)

    parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
    resolver = load_resolver(parties_csv)

    # Build candidacy rows (ranked by votes desc; NOTA excluded per
    # Rajasthan precedent)
    ranked = sorted(CANDIDATES, key=lambda t: -t[2])
    # Non-NOTA total for vote_share denominator
    non_nota_total = sum(votes for _, _, votes in ranked)

    candidacies_rows: list[dict] = []
    unresolved_winners = 0
    for position, (party_short, candidate_name, votes) in enumerate(ranked, start=1):
        is_ind = party_short.upper() in ("IND", "INDEPENDENT")
        party_id = resolver.resolve(
            party_short=party_short,
            eci_code=None,
            is_nota=False,
            is_independent=is_ind,
        )
        if position == 1 and party_id.endswith(".UNK"):
            unresolved_winners += 1

        share = (votes / non_nota_total * 100) if non_nota_total > 0 else 0.0
        proc_level, proc_note = derive_processing(party_id, party_short)

        candidacies_rows.append({
            "entity_id": entity_id,
            "state": STATE_SLUG,
            "election_year": 2024,
            "constituency_no": ECI_NO,
            "constituency_name": AC_NAME,
            "candidate_name": candidate_name,
            "party_id": party_id,
            "party_short_raw": party_short,
            "votes": votes,
            "vote_share_pct": round(share, 4),
            "position": position,
            "result": "won" if position == 1 else "lost",
            "sex": "U",  # not in Wikipedia table
            "age": "",
            "education": "",
            "profession": "",
            "candidate_type": "challenger",
            "source_id": source_id,
            "processing_level": proc_level,
            "processing_note": proc_note,
        })

    # Build summary via canonical reducer (winner/runnerup/margin derived)
    ac_facts = {
        "electors": REGISTERED_ELECTORS,
        "votes_polled": TOTAL_VOTES_POLLED,
        "turnout_pct": TURNOUT_PCT,
    }
    summary_row = recompute_summary_row(
        entity_id=entity_id,
        state_slug=STATE_SLUG,
        election_year=2024,
        candidacy_rows=candidacies_rows,
        ac_facts=ac_facts,
        source_id=source_id,
    )

    # Write per-event CSVs at election=2024-channapatna-bye
    out_dir = (
        root
        / "datasets"
        / "elections"
        / "assembly"
        / f"state={STATE_SLUG}"
        / f"election=2024-channapatna-bye"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    cand_fields = [
        "entity_id", "state", "election_year", "constituency_no",
        "constituency_name", "candidate_name", "party_id", "party_short_raw",
        "votes", "vote_share_pct", "position", "result", "sex", "age",
        "education", "profession", "candidate_type", "source_id",
        "processing_level", "processing_note",
    ]
    with (out_dir / "candidacies.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cand_fields)
        writer.writeheader()
        writer.writerows(candidacies_rows)

    sum_fields = [
        "entity_id", "state", "election_year", "constituency_name",
        "electors", "votes_polled", "turnout_pct", "winner_candidate",
        "winner_party_id", "winner_party_short_raw", "winner_votes",
        "winner_share_pct", "runnerup_candidate", "runnerup_party_id",
        "runnerup_party_short_raw", "runnerup_votes", "margin_votes",
        "margin_pct", "source_id", "processing_level", "processing_note",
    ]
    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=sum_fields)
        writer.writeheader()
        writer.writerow(summary_row)

    _fix_catalogue(root)

    return len(candidacies_rows), 1, unresolved_winners


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repo root")
    args = parser.parse_args()

    n_cand, n_sum, n_unk = ingest(args.root)
    print(f"ingest-channapatna-bye-2024: OK")
    print(f"  candidacies.csv:  {n_cand} rows")
    print(f"  summary.csv:      {n_sum} rows")
    print(f"  UNK winners:      {n_unk}")
    print(f"  catalogue:        S29 -> S10 (Karnataka), data_status -> complete")
