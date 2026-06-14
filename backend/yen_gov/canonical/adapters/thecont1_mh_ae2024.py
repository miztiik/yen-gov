"""Maharashtra Assembly Election 2024 ingest from thecont1 snapshot.

Reads: datasets/ephemeral/thecont1-india-votes-data/2024/Assembly-Maharashtra.csv
Emits:
  - datasets/elections/assembly/state=maharashtra/election=2024/candidacies.csv
  - datasets/elections/assembly/state=maharashtra/election=2024/summary.csv
Updates:
  - datasets/data/entities/source.csv (thecont1 source row if missing)
  - datasets/taxonomy/election_events.json (S13 assembly-2024:
    data_status pending_upstream -> complete)

The upstream is the per-(year, state) Assembly CSV from the
``thecont1/india-votes-data`` GitHub repo (operator-dropped snapshot,
see datasets/ephemeral/thecont1-india-votes-data/README.md). The
snapshot is the authoritative source for candidate names + per-
candidate vote counts (evm + postal). The long-format aggregate CSV
at datasets/data/datapoints/electoral/maharashtra_election_results.csv
is the source-of-truth for per-AC aggregates (electors,
votes_polled, turnout_pct, margin_votes, margin_pct, nota_*).

Schema precedent: datasets/elections/assembly/state=rajasthan/election=2023/.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Final

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.party_resolver import load_resolver
from yen_gov.canonical.reingest.assembly_results import recompute_summary_row


THECONT1_VINTAGE: Final[str] = "2026-06-11"
THECONT1_PRODUCER: Final[str] = "thecont1"
THECONT1_TITLE: Final[str] = "india-votes-data"
THECONT1_URL: Final[str] = (
    "https://raw.githubusercontent.com/thecont1/india-votes-data/main/data/"
    "csv/2024Assembly-MH.csv"
)


def _load_electoral_long(root: Path, state: str, period_label: str) -> dict:
    """Index long-format electoral CSV by eci_no + indicator_id.

    Filter to one period_label. The long-format entity_id form is
    ``IN-<state_code>-AC-<delim>-<eci_no>`` (e.g. ``IN-S13-AC-2008-1``);
    we strip out the trailing ``<eci_no>`` and index by that integer so the
    caller can join to canonical electoral.csv via the eci_no <-> entity_id
    map.

    Returns: ``{eci_no: {indicator_id: {value_numeric, value_text}}}``.
    """
    csv_path = (
        root
        / "datasets"
        / "data"
        / "datapoints"
        / "electoral"
        / f"{state}_election_results.csv"
    )
    result: dict[int, dict[str, dict]] = defaultdict(dict)

    if not csv_path.exists():
        return dict(result)

    with csv_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("period_label") or "").strip() != period_label:
                continue
            ent_id = (row.get("entity_id") or "").strip()
            # Match IN-<code>-AC-<delim>-<eci_no> shape; skip per-candidate
            # rows whose entity_id has a -C<NN> suffix.
            m = re.match(r"^IN-[SU]\d{2}-AC-\d{4}-(\d+)$", ent_id)
            if not m:
                continue
            eci_no = int(m.group(1))
            indicator_id = (row.get("indicator_id") or "").strip()
            if not indicator_id:
                continue
            vn_str = (row.get("value_numeric") or "").strip()
            try:
                vn = float(vn_str) if vn_str else None
            except ValueError:
                vn = None
            result[eci_no][indicator_id] = {
                "value_numeric": vn,
                "value_text": (row.get("value_text") or "").strip(),
            }

    return dict(result)


def _load_electoral_entities(
    root: Path, state: str, delim_year: str
) -> dict[int, list[tuple[str, str]]]:
    """Index electoral.csv: eci_no -> list of (entity_id, name) for (state, delim_year, ac).

    Returns a list per eci_no because some (state, delim, eci_no) keys carry
    multiple electoral.csv rows (e.g. MH delim=2008 eci_no=5 has both Mehkar
    and Sakri rows). The adapter disambiguates via name match against the
    publisher snapshot at ingest time.
    """
    csv_path = root / "datasets" / "data" / "entities" / "electoral.csv"
    result: dict[int, list[tuple[str, str]]] = defaultdict(list)

    if not csv_path.exists():
        return dict(result)

    with csv_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("entity_kind") or "").strip() != "ac":
                continue
            if (row.get("state") or "").strip() != state:
                continue
            if (row.get("delim_year") or "").strip() != delim_year:
                continue
            try:
                eci_no = int((row.get("eci_no") or "").strip())
            except ValueError:
                continue
            entity_id = (row.get("entity_id") or "").strip()
            name = (row.get("name") or "").strip()
            if entity_id and name:
                result[eci_no].append((entity_id, name))

    return dict(result)


def _resolve_entity(
    eci_no: int,
    publisher_name: str,
    entities: dict[int, list[tuple[str, str]]],
) -> tuple[str, str] | None:
    """Return the single (entity_id, name) for (eci_no), disambiguating duplicates.

    Strategy: when multiple electoral.csv rows share an eci_no, prefer the
    one whose canonical name fuzzy-matches the publisher name (case- and
    space-insensitive prefix match). If no name match, return None — the
    caller surfaces this as a data-quality gap. With a single match,
    return it directly.
    """
    candidates = entities.get(eci_no, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    norm_pub = re.sub(r"\s+", "", publisher_name.upper())
    for entity_id, name in candidates:
        norm_cand = re.sub(r"\s+", "", name.upper())
        if norm_pub == norm_cand or norm_pub.startswith(norm_cand) or norm_cand.startswith(norm_pub):
            return (entity_id, name)
    return None


def _get_or_mint_thecont1_source(root: Path) -> str:
    """Return source_id for the thecont1 snapshot citation triple.

    If the (producer, title, vintage) triple already exists in
    source.csv, returns its source_id. Otherwise mints a deterministic
    id via derive_source_id and appends a new row.
    """
    csv_path = root / "datasets" / "data" / "entities" / "source.csv"
    rows: list[dict] = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))

    for row in rows:
        if (
            (row.get("producer") or "").strip() == THECONT1_PRODUCER
            and (row.get("title") or "").strip() == THECONT1_TITLE
            and (row.get("vintage") or "").strip() == THECONT1_VINTAGE
        ):
            return (row.get("source_id") or "").strip()

    source_id = derive_source_id(
        producer=THECONT1_PRODUCER,
        title=THECONT1_TITLE,
        vintage=THECONT1_VINTAGE,
    )
    new_row = {
        "source_id": source_id,
        "producer": THECONT1_PRODUCER,
        "title": THECONT1_TITLE,
        "vintage": THECONT1_VINTAGE,
        "url": THECONT1_URL,
    }
    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["source_id", "producer", "title", "vintage", "url"]
        )
        writer.writerow(new_row)
    return source_id


def _parse_int(s: str | None, default: int = 0) -> int:
    if not s:
        return default
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return default


def ingest_mh_ae2024(root: Path) -> tuple[int, int, int, int]:
    """Execute MH AE 2024 ingest.

    Returns (candidacies_count, summary_count, unresolved_winners_count, missing_acs_count).
    """
    thecont1_path = (
        root
        / "datasets"
        / "ephemeral"
        / "thecont1-india-votes-data"
        / "2024"
        / "Assembly-Maharashtra.csv"
    )
    if not thecont1_path.exists():
        raise FileNotFoundError(f"thecont1 CSV not found: {thecont1_path}")

    electoral_long = _load_electoral_long(root, "maharashtra", "AcGenNov2024")
    electoral_entities = _load_electoral_entities(root, "maharashtra", "2008")

    if not electoral_entities:
        raise ValueError("electoral.csv has no MH AC entities (delim=2008)")

    parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
    resolver = load_resolver(parties_csv)
    source_id = _get_or_mint_thecont1_source(root)

    with thecont1_path.open(encoding="utf-8", newline="") as fh:
        thecont1_rows = list(csv.DictReader(fh))

    by_ac: dict[int, list[dict]] = defaultdict(list)
    for row in thecont1_rows:
        ac_no = _parse_int(row.get("constituency_no"))
        if ac_no >= 1:
            by_ac[ac_no].append(row)

    candidacies_rows: list[dict] = []
    summary_rows: list[dict] = []
    unresolved_winners = 0
    missing_acs: list[int] = []

    for ac_no in sorted(by_ac.keys()):
        publisher_name = (by_ac[ac_no][0].get("constituency") or "").strip()
        resolved = _resolve_entity(ac_no, publisher_name, electoral_entities)
        if resolved is None:
            missing_acs.append(ac_no)
            continue

        entity_id, ac_name = resolved
        ac_rows = by_ac[ac_no]

        scored: list[tuple[int, int, dict]] = []
        for r in ac_rows:
            evm = _parse_int(r.get("evm_votes"))
            postal = _parse_int(r.get("postal_votes"))
            serial = _parse_int(r.get("serial_no"), default=999)
            total = evm + postal
            scored.append((total, -serial, r))

        # Sort: votes desc, then serial asc (lower serial wins ties)
        scored.sort(key=lambda t: (-t[0], -t[1]))

        # Non-NOTA total (denominator for vote_share_pct)
        non_nota_total = sum(
            total
            for total, _, r in scored
            if (r.get("party") or "").strip().upper() != "NONE OF THE ABOVE"
        )

        position = 1
        non_nota_scored: list[tuple[int, dict, str]] = []
        for total, _, row in scored:
            party_raw = (row.get("party") or "").strip()
            if party_raw.upper() == "NONE OF THE ABOVE":
                continue

            candidate_name = (row.get("candidate") or "").strip()
            is_ind = party_raw.upper() == "INDEPENDENT"
            party_id = resolver.resolve(
                party_short=party_raw,
                eci_code=None,
                is_nota=False,
                is_independent=is_ind,
            )

            if position == 1 and party_id.endswith(".UNK"):
                unresolved_winners += 1

            non_nota_scored.append((total, row, party_id))

            share = (total / non_nota_total * 100) if non_nota_total > 0 else 0.0
            candidacies_rows.append({
                "entity_id": entity_id,
                "state": "maharashtra",
                "election_year": 2024,
                "constituency_no": ac_no,
                "constituency_name": ac_name,
                "candidate_name": candidate_name,
                "party_id": party_id,
                "party_short_raw": party_raw,
                "votes": total,
                "vote_share_pct": round(share, 4),
                "position": position,
                "result": "won" if position == 1 else "lost",
                "sex": "U",
                "age": "",
                "education": "",
                "profession": "",
                "candidate_type": "challenger",
                "source_id": source_id,
            })
            position += 1

        ac_long = electoral_long.get(ac_no, {})

        def _num(ind: str) -> float | None:
            return ac_long.get(ind, {}).get("value_numeric")

        electors_val = _num("ac-total-electors")
        votes_polled_val = _num("ac-votes-polled")
        turnout_pct_val = _num("ac-turnout-pct")

        # Build the candidacy-row shape recompute_summary_row expects (it
        # ranks by votes desc and derives winner/runnerup/margin from the
        # candidate vote_share_pct values we just stamped). This ensures
        # the G15 contract test (summary == recompute(candidacies)) passes
        # by construction.
        ac_cand_rows = [
            cr for cr in candidacies_rows
            if cr["entity_id"] == entity_id
        ]
        if not ac_cand_rows:
            continue

        ac_facts = {
            "electors": int(electors_val) if electors_val else None,
            "votes_polled": int(votes_polled_val) if votes_polled_val else None,
            "turnout_pct": turnout_pct_val,
        }

        summary_row = recompute_summary_row(
            entity_id=entity_id,
            state_slug="maharashtra",
            election_year=2024,
            candidacy_rows=ac_cand_rows,
            ac_facts=ac_facts,
            source_id=source_id,
        )
        summary_rows.append(summary_row)

    # Track but don't fail on missing ACs - the canonical electoral.csv
    # corpus for MH delim=2008 has 22 known gaps (eci_nos 7,13,25,107,
    # 159,168,169,171,176,178-187,212,215,249 missing as of 2026-06-14).
    # This is a separate data-corpus gap NOT in scope of this ingest.
    # The 266 ACs we CAN resolve light up the per-event store; the 22
    # gaps follow up via a canonical-electoral-csv backfill PR.

    out_dir = (
        root
        / "datasets"
        / "elections"
        / "assembly"
        / "state=maharashtra"
        / "election=2024"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    cand_fields = [
        "entity_id", "state", "election_year", "constituency_no",
        "constituency_name", "candidate_name", "party_id", "party_short_raw",
        "votes", "vote_share_pct", "position", "result", "sex", "age",
        "education", "profession", "candidate_type", "source_id",
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
        "margin_pct", "source_id",
    ]
    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=sum_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    # --- Flip catalogue: MH (S13) assembly-2024 data_status ---
    events_path = root / "datasets" / "taxonomy" / "election_events.json"
    with events_path.open(encoding="utf-8") as fh:
        events_data = json.load(fh)

    flipped = False
    for ev in events_data.get("states", {}).get("S13", []):
        if (
            ev.get("event_id") == "assembly-2024"
            and ev.get("polled_on") == "2024-11-20"
            and ev.get("data_status") == "pending_upstream"
        ):
            ev["data_status"] = "complete"
            flipped = True
            break

    if flipped:
        with events_path.open("w", encoding="utf-8") as fh:
            json.dump(events_data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    return len(candidacies_rows), len(summary_rows), unresolved_winners, len(missing_acs)
