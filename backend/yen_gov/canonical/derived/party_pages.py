"""Party-page derived marts.

The citizen `/parties/<slug>` route must not scan the whole electoral corpus
in the browser. This module materialises the party detail read model from the
canonical electoral CSVs into small CSV contracts under
`datasets/data/marts/party_pages/`.

Inputs remain the source of truth:

- `datasets/data/entities/parties.csv`
- `datasets/data/entities/electoral.csv`
- `datasets/taxonomy/lgd_states.json`
- `datasets/data/datapoints/electoral/*_election_results.csv`

Outputs are deterministic derived views. Re-run after any electoral ingest.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

from yen_gov.canonical.csv_writer import write_csv

HISTORY_REL = PurePosixPath("datasets/data/marts/party_pages/history.csv")
STRONGHOLDS_REL = PurePosixPath("datasets/data/marts/party_pages/strongholds.csv")
MANIFEST_REL = PurePosixPath("datasets/data/marts/party_pages/manifest.csv")

HISTORY_FILE_CLASS = HISTORY_REL.as_posix()
STRONGHOLDS_FILE_CLASS = STRONGHOLDS_REL.as_posix()
MANIFEST_FILE_CLASS = MANIFEST_REL.as_posix()

PARTIES_REL = PurePosixPath("datasets/data/entities/parties.csv")
ELECTORAL_ENTITIES_REL = PurePosixPath("datasets/data/entities/electoral.csv")
LGD_STATES_REL = PurePosixPath("datasets/taxonomy/lgd_states.json")
ELECTORAL_DATAPOINTS_REL = PurePosixPath("datasets/data/datapoints/electoral")

HISTORY_INDICATORS = {
    "party-seats-won",
    "party-votes-polled",
    "party-vote-share-pct",
    "party-contested-acs",
    "party-contested-pcs",
}
WINNER_INDICATORS = {"ac-winner-party-id", "pc-winner-party-id"}


@dataclass(frozen=True)
class PartyPageMartResult:
    """Summary of one party-page mart refresh."""

    input_signature: str
    input_file_count: int
    party_count: int
    history_rows: int
    stronghold_rows: int
    history_path: Path
    strongholds_path: Path
    manifest_path: Path


@dataclass
class _HistoryAgg:
    party_id: str
    body: str
    period_label: str
    state: str
    year: int
    seats: float = 0.0
    contested: float | None = None
    party_votes: float | None = None
    pct_values: list[float] = field(default_factory=list)
    source_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class _PeerEntityKey:
    kind: str
    delim_year: int
    state_slug: str
    eci_no: int


@dataclass(frozen=True)
class _WinnerEvent:
    period_label: str
    winner_party_id: str
    source_id: str


def refresh_party_page_marts(repo_root: Path) -> PartyPageMartResult:
    """Regenerate all party-page derived CSVs."""
    root = repo_root.resolve()
    party_ids = _load_page_party_ids(root / PARTIES_REL)
    eci_to_slug = _load_eci_to_slug(root / LGD_STATES_REL)
    electoral_lookup = _load_electoral_entity_lookup(root / ELECTORAL_ENTITIES_REL)

    input_rels = _input_rels(root)
    input_signature = compute_input_signature(root, input_rels)

    history_aggs: dict[tuple[str, str, str, str], _HistoryAgg] = {}
    total_votes_direct: dict[tuple[str, str, str], float] = defaultdict(float)
    total_votes_fallback: dict[tuple[str, str, str], float] = defaultdict(float)
    winner_events: dict[tuple[str, str], list[_WinnerEvent]] = defaultdict(list)

    for rel in _electoral_datapoint_rels(root):
        with (root / rel).open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                indicator_id = row.get("indicator_id", "")
                period_label = row.get("period_label", "")
                body = _body_for_period_label(period_label)
                if body is None:
                    continue

                value_numeric = _float_or_none(row.get("value_numeric"))
                entity_id = row.get("entity_id", "")
                source_id = row.get("source_id", "")

                if indicator_id in ("ac-votes-polled", "pc-votes-polled"):
                    if value_numeric is not None:
                        state_code = _state_code_from_entity_id(entity_id)
                        state_slug = eci_to_slug.get(state_code) if state_code else None
                        if state_slug is None:
                            continue
                        total_votes_direct[(body, period_label, state_slug)] += value_numeric
                    continue
                if indicator_id == "votes-polled":
                    if value_numeric is not None:
                        state_code = _state_code_from_entity_id(entity_id)
                        state_slug = eci_to_slug.get(state_code) if state_code else None
                        if state_slug is None:
                            continue
                        total_votes_fallback[(body, period_label, state_slug)] += value_numeric
                    continue

                if indicator_id in HISTORY_INDICATORS:
                    party_id = _party_id_from_aggregate_entity(entity_id)
                    if party_id is None or party_id not in party_ids:
                        continue
                    state_code = _state_code_from_entity_id(entity_id)
                    state_slug = eci_to_slug.get(state_code) if state_code else None
                    if state_slug is None:
                        continue
                    key = (party_id, body, period_label, state_slug)
                    agg = history_aggs.get(key)
                    if agg is None:
                        agg = _HistoryAgg(
                            party_id=party_id,
                            body=body,
                            period_label=period_label,
                            state=state_slug,
                            year=int(row.get("year") or 0),
                        )
                        history_aggs[key] = agg
                    if source_id:
                        agg.source_ids.add(source_id)
                    if indicator_id == "party-seats-won" and value_numeric is not None:
                        agg.seats += value_numeric
                    elif indicator_id in ("party-contested-acs", "party-contested-pcs") and value_numeric is not None:
                        agg.contested = (agg.contested or 0.0) + value_numeric
                    elif indicator_id == "party-votes-polled" and value_numeric is not None:
                        agg.party_votes = (agg.party_votes or 0.0) + value_numeric
                    elif indicator_id == "party-vote-share-pct" and value_numeric is not None:
                        agg.pct_values.append(value_numeric)
                    continue

                if indicator_id in WINNER_INDICATORS:
                    winner_party_id = (row.get("value_text") or "").strip()
                    if not winner_party_id or winner_party_id not in party_ids:
                        continue
                    winner_events[(body, entity_id)].append(
                        _WinnerEvent(
                            period_label=period_label,
                            winner_party_id=winner_party_id,
                            source_id=source_id,
                        )
                    )

    history_rows = _history_rows(
        history_aggs.values(),
        total_votes_direct=total_votes_direct,
        total_votes_fallback=total_votes_fallback,
    )
    stronghold_rows = _stronghold_rows(
        winner_events,
        eci_to_slug=eci_to_slug,
        electoral_lookup=electoral_lookup,
    )

    history_path = root / HISTORY_REL
    strongholds_path = root / STRONGHOLDS_REL
    manifest_path = root / MANIFEST_REL

    write_csv(path=history_path, file_class=HISTORY_FILE_CLASS, rows=history_rows)
    write_csv(path=strongholds_path, file_class=STRONGHOLDS_FILE_CLASS, rows=stronghold_rows)
    manifest_rows = [
        {
            "surface": "party_pages",
            "input_signature": input_signature,
            "input_file_count": len(input_rels),
            "party_count": len(party_ids),
            "history_rows": len(history_rows),
            "stronghold_rows": len(stronghold_rows),
        }
    ]
    write_csv(path=manifest_path, file_class=MANIFEST_FILE_CLASS, rows=manifest_rows)

    return PartyPageMartResult(
        input_signature=input_signature,
        input_file_count=len(input_rels),
        party_count=len(party_ids),
        history_rows=len(history_rows),
        stronghold_rows=len(stronghold_rows),
        history_path=history_path,
        strongholds_path=strongholds_path,
        manifest_path=manifest_path,
    )


def party_page_mart_freshness_failures(repo_root: Path) -> list[str]:
    """Return freshness failures for the party-page derived mart."""
    root = repo_root.resolve()
    source_prereqs = [PARTIES_REL, ELECTORAL_ENTITIES_REL, LGD_STATES_REL]
    if not all((root / rel).exists() for rel in source_prereqs):
        # Small validator fixture roots may omit the electoral corpus entirely.
        # The real repo carries all source inputs, so absence here means
        # "surface out of scope for this fixture", not a stale mart.
        return []
    if not _electoral_datapoint_rels(root):
        return []

    required = [HISTORY_REL, STRONGHOLDS_REL, MANIFEST_REL]
    missing = [rel.as_posix() for rel in required if not (root / rel).exists()]
    if missing:
        return [
            "party-page mart missing output(s): "
            + ", ".join(missing)
            + "; run `python -m yen_gov derive-party-pages --root .`"
        ]

    expected = compute_input_signature(root, _input_rels(root))
    manifest = _read_manifest(root / MANIFEST_REL)
    actual = manifest.get("party_pages")
    if actual is None:
        return [
            "party-page mart manifest has no surface='party_pages' row; "
            "run `python -m yen_gov derive-party-pages --root .`"
        ]
    if actual != expected:
        return [
            "party-page mart is stale: manifest input_signature "
            f"{actual} != current {expected}; run "
            "`python -m yen_gov derive-party-pages --root .`"
        ]
    return []


def compute_input_signature(repo_root: Path, rels: Iterable[PurePosixPath]) -> str:
    """Compute a deterministic signature over input paths and file bytes."""
    root = repo_root.resolve()
    digest = hashlib.sha256()
    for rel in sorted(rels, key=lambda p: p.as_posix()):
        path = root / rel
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _input_rels(root: Path) -> list[PurePosixPath]:
    rels = [PARTIES_REL, ELECTORAL_ENTITIES_REL, LGD_STATES_REL]
    rels.extend(_electoral_datapoint_rels(root))
    return rels


def _electoral_datapoint_rels(root: Path) -> list[PurePosixPath]:
    base = root / ELECTORAL_DATAPOINTS_REL
    return [
        PurePosixPath(path.relative_to(root).as_posix())
        for path in sorted(base.glob("*_election_results.csv"))
    ]


def _load_page_party_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            row["party_id"].strip()
            for row in csv.DictReader(fh)
            if row.get("party_id") and row["party_id"].strip() != "parties.IN.UNK"
        }


def _load_eci_to_slug(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row["eci_st_code"]): str(row["slug"])
        for row in payload.get("states", [])
        if row.get("eci_st_code") and row.get("slug")
    }


def _load_electoral_entity_lookup(path: Path) -> dict[_PeerEntityKey, tuple[str, str]]:
    lookup: dict[_PeerEntityKey, tuple[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            eci_no = _int_or_none(row.get("eci_no"))
            delim_year = _int_or_none(row.get("delim_year"))
            kind = row.get("entity_kind")
            state = row.get("state")
            if eci_no is None or delim_year is None or kind not in {"ac", "pc"} or not state:
                continue
            lookup[_PeerEntityKey(kind, delim_year, state, eci_no)] = (
                row.get("name") or "",
                state,
            )
    return lookup


def _read_manifest(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            row.get("surface", ""): row.get("input_signature", "")
            for row in csv.DictReader(fh)
        }


def _body_for_period_label(period_label: str) -> str | None:
    if period_label.startswith("Ls"):
        return "parliament"
    if period_label.startswith("Ac"):
        return "assembly"
    return None


def _party_id_from_aggregate_entity(entity_id: str) -> str | None:
    marker = "-PARTY-"
    if marker not in entity_id:
        return None
    tail = entity_id.rsplit(marker, 1)[-1].strip()
    if not tail:
        return None
    return f"parties.IN.{tail}"


_STATE_CODE_RE = re.compile(r"^[SU]\d{2}$")


def _state_code_from_entity_id(entity_id: str) -> str | None:
    """Extract the state code (S## / U##) from any electoral entity_id.

    Handles three on-disk shapes:

    - ``IN-S22-AcGenApr2021-PARTY-DMK`` (party-aggregate; state at parts[1])
    - ``IN-S22-AC-1976-1`` / ``IN-S22-AcGenApr2021`` (AC entity / votes-polled
      fallback; state at parts[1])
    - ``IN-PC-1976-S22-1`` / ``IN-PC-1976-S22-1-LsGenMay2004-C01`` (PC entity;
      state at parts[3])

    Returns None when the shape is unrecognised; callers MUST skip such rows
    so the per-state mart never carries a phantom row with no state.
    """
    parts = entity_id.split("-")
    if len(parts) < 3 or parts[0] != "IN":
        return None
    if _STATE_CODE_RE.match(parts[1]):
        return parts[1]
    if parts[1] == "PC" and len(parts) >= 4 and _STATE_CODE_RE.match(parts[3]):
        return parts[3]
    return None


def _history_rows(
    aggs: Iterable[_HistoryAgg],
    *,
    total_votes_direct: dict[tuple[str, str, str], float],
    total_votes_fallback: dict[tuple[str, str, str], float],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for agg in aggs:
        denominator = total_votes_direct.get((agg.body, agg.period_label, agg.state), 0.0)
        if denominator <= 0:
            denominator = total_votes_fallback.get((agg.body, agg.period_label, agg.state), 0.0)
        vote_share = None
        if denominator > 0 and agg.party_votes is not None:
            vote_share = round(agg.party_votes / denominator * 100.0, 6)
        elif len(agg.pct_values) == 1:
            vote_share = round(agg.pct_values[0], 6)
        elif len(agg.pct_values) > 1:
            vote_share = round(sum(agg.pct_values) / len(agg.pct_values), 6)

        rows.append(
            {
                "party_id": agg.party_id,
                "body": agg.body,
                "period_label": agg.period_label,
                "state": agg.state,
                "year": agg.year,
                "seats": int(agg.seats),
                "vote_share_pct": vote_share,
                "contested": int(agg.contested) if agg.contested is not None else None,
                "party_votes": int(agg.party_votes) if agg.party_votes is not None else None,
                "total_votes": int(denominator) if denominator > 0 else None,
                "source_ids": "|".join(sorted(agg.source_ids)) or None,
                "derivation": "computed_from_canonical_electoral_rows",
            }
        )
    return rows


def _stronghold_rows(
    winner_events: dict[tuple[str, str], list[_WinnerEvent]],
    *,
    eci_to_slug: dict[str, str],
    electoral_lookup: dict[_PeerEntityKey, tuple[str, str]],
) -> list[dict[str, object]]:
    per_party_body: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)

    for (body, entity_id), events_unsorted in winner_events.items():
        events = sorted(events_unsorted, key=lambda e: _chronological_sort_key(e.period_label))
        winners = sorted({event.winner_party_id for event in events})
        peer_key = _parse_peer_entity_id(entity_id, eci_to_slug)
        name = ""
        state = ""
        if peer_key is not None:
            name, state = electoral_lookup.get(peer_key, ("", peer_key.state_slug))
        source_ids = "|".join(sorted({event.source_id for event in events if event.source_id})) or None
        for party_id in winners:
            wins = sum(1 for event in events if event.winner_party_id == party_id)
            if wins <= 0:
                continue
            results = "".join("W" if event.winner_party_id == party_id else "L" for event in events)
            per_party_body[(party_id, body)].append(
                {
                    "party_id": party_id,
                    "body": body,
                    "rank": 0,
                    "entity_id": entity_id,
                    "constituency_name": name,
                    "state": state,
                    "wins": wins,
                    "contested": len(events),
                    "results": results,
                    "source_ids": source_ids,
                    "derivation": "computed_from_canonical_winner_rows",
                }
            )

    out: list[dict[str, object]] = []
    for rows in per_party_body.values():
        rows.sort(
            key=lambda row: (
                -int(row["wins"]),
                -(int(row["wins"]) / int(row["contested"])),
                str(row["entity_id"]),
            )
        )
        for rank, row in enumerate(rows[:10], start=1):
            row = dict(row)
            row["rank"] = rank
            out.append(row)
    return out


def _parse_peer_entity_id(entity_id: str, eci_to_slug: dict[str, str]) -> _PeerEntityKey | None:
    ac_match = re.match(r"^IN-(S\d{2}|U\d{2})-AC-(\d{4})-(\d+)$", entity_id)
    if ac_match:
        slug = eci_to_slug.get(ac_match.group(1))
        if not slug:
            return None
        return _PeerEntityKey("ac", int(ac_match.group(2)), slug, int(ac_match.group(3)))
    pc_match = re.match(r"^IN-PC-(\d{4})-(S\d{2}|U\d{2})-(\d+)$", entity_id)
    if pc_match:
        slug = eci_to_slug.get(pc_match.group(2))
        if not slug:
            return None
        return _PeerEntityKey("pc", int(pc_match.group(1)), slug, int(pc_match.group(3)))
    return None


_MONTH_INDEX = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def _chronological_sort_key(period_label: str) -> str:
    match = re.search(r"([A-Z][a-z]{2})(\d{4})$", period_label)
    if not match:
        return f"9999-99-{period_label}"
    return f"{match.group(2)}-{_MONTH_INDEX.get(match.group(1), 99):02d}-{period_label}"


def _float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _int_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
