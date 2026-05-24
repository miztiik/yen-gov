"""ECI Assembly Election panel CSV adapter.

Reads frozen ECI Statistical Report transcriptions and emits canonical
Parquet rows through the shared BatchEnvelope writer. The adapter is generic
by `(state_code, csv_path)`; state-specific differences live in input data,
not in branchy adapter logic.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from yen_gov.canonical.adapters.eci.identity import (
    Period,
    ac_entity_id,
    candidate_entity_id,
    layer1_person_id,
    layer1_person_id_collision_tiebreak,
    state_rollup_entity_id,
)
from yen_gov.canonical.adapters.eci.party_lookup import (
    PartyLookup,
    load_party_lookup,
    party_alliance_dim_rows,
    party_dim_rows,
)
from yen_gov.canonical.adapters.eci.rollups import ACContestSummary, state_rollup_observations
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.envelope import (
    AcDimRow,
    BatchEnvelope,
    CandidacyRow,
    ObservationRow,
    PartyAllianceDimRow,
    PartyDimRow,
    PersonDimRow,
    SourceRow,
)
from yen_gov.canonical.writer import WriteResult, write_batch
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.core.io import write_artifact
from yen_gov.sources.eci.events import event_id_for as registered_event_id_for

MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

STATE_NAME_BY_CODE = {
    "S22": "Tamil_Nadu",
    "S06": "Gujarat",
    "S13": "Maharashtra",
}

STATE_TITLE_BY_CODE = {
    "S22": "Tamil Nadu",
    "S06": "Gujarat",
    "S13": "Maharashtra",
}

POLL_DATE_OVERRIDES = {
    ("S22", 2016): "2016-05-16",
    ("S22", 2021): "2021-04-06",
}

INVENTORY_SCHEMA_FILE = "elections-inventory.schema.json"
INVENTORY_PATH_REL = ("datasets", "elections", "_inventory.json")
REPORTS_DIR_REL = (".runtime", "reports")
SOURCE_INPUT_ID = "eci_ae_panel"

_NOTA_TOKENS = {"NOTA", "NONE OF THE ABOVE", "NONE OF THE ABOVE"}


@dataclass(frozen=True)
class PanelCandidate:
    state_code: str
    year: int
    month: int
    ac_no: int
    ac_name: str
    delim_year: int
    name: str
    party_short: str
    votes: int
    electors: int | None
    valid_votes: int | None
    turnout_pct: float | None
    sex: str | None
    age: int | None
    education: str | None
    profession: str | None
    constituency_type: str | None
    party_type: str | None
    is_nota: bool


@dataclass(frozen=True)
class PanelIngestResult:
    write_result: WriteResult | None
    events: tuple[str, ...]
    report_path: Path
    inventory_path: Path
    skipped: bool = False


def event_id_for(state_code: str, year: int, month: int) -> str:
    return registered_event_id_for(state_code, year)


def delim_year_for(raw: str, year: int) -> int:
    token = (raw or "").strip()
    if token == "4" or year >= 2011:
        return 2008
    return 1976


def parse_panel_csv(csv_path: Path, *, state_code: str) -> list[PanelCandidate]:
    state_name = STATE_NAME_BY_CODE[state_code]
    rows: list[PanelCandidate] = []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            if raw.get("State_Name") != state_name:
                continue
            if not (raw.get("month") or "").strip():
                continue
            year = _as_int(raw["Year"])
            month = _as_int(raw["month"])
            if year > 2021:
                continue
            name = (raw.get("Candidate") or "").strip()
            party_short = (raw.get("Party") or "").strip() or "IND"
            rows.append(PanelCandidate(
                state_code=state_code,
                year=year,
                month=month,
                ac_no=_as_int(raw["Constituency_No"]),
                ac_name=(raw.get("Constituency_Name") or "").strip(),
                delim_year=delim_year_for(raw.get("DelimID", ""), year),
                name=name,
                party_short=party_short,
                votes=_as_int(raw["Votes"]),
                electors=_as_int(raw.get("Electors", ""), allow_blank=True),
                valid_votes=_as_int(raw.get("Valid_Votes", ""), allow_blank=True),
                turnout_pct=_as_float(raw.get("Turnout_Percentage", ""), allow_blank=True),
                sex=_normalise_sex(raw.get("Sex", "")),
                age=_normalise_age(raw.get("Age", "")),
                education=_clean_optional(raw.get("MyNeta_education", "")),
                profession=_clean_optional(_value_by_suffix(raw, "Prof_Main")),
                constituency_type=_normalise_constituency_type(raw.get("Constituency_Type", "")),
                party_type=_normalise_party_type(_value_by_prefix(raw, "Party_Type"), party_short),
                is_nota=_is_nota(name, party_short),
            ))
    return rows


def build_envelope(
    *,
    datasets_root: Path,
    csv_path: Path,
    state_code: str,
) -> tuple[BatchEnvelope, tuple[str, ...], dict]:
    panel_rows = parse_panel_csv(csv_path, state_code=state_code)
    lookup = load_party_lookup(datasets_root)
    by_event: dict[tuple[int, int], list[PanelCandidate]] = defaultdict(list)
    for row in panel_rows:
        by_event[(row.year, row.month)].append(row)

    observations: list[ObservationRow] = []
    sources: dict[str, SourceRow] = {}
    persons: list[PersonDimRow] = []
    candidacies: list[CandidacyRow] = []
    ac_dims: dict[str, AcDimRow] = {}
    discrepancy_report: dict = {"events": []}

    existing = _existing_ac_totals(datasets_root, state_code)

    for (year, month), event_rows in sorted(by_event.items()):
        period = Period(event_id_for(state_code, year, month), year, month)
        source_row = source_row_for(state_code=state_code, year=year)
        sources[source_row.source_id] = source_row
        event_discrepancies = []
        summaries: list[ACContestSummary] = []
        by_ac: dict[int, list[PanelCandidate]] = defaultdict(list)
        for row in event_rows:
            by_ac[row.ac_no].append(row)

        for ac_no, ac_rows in sorted(by_ac.items()):
            ac_id = ac_entity_id(state_code, ac_rows[0].delim_year, ac_no)
            ac_dims[ac_id] = AcDimRow(
                ac_id=ac_id,
                state_code=state_code,
                delim_year=ac_rows[0].delim_year,
                eci_no=ac_no,
                name=ac_rows[0].ac_name or None,
                source_id=source_row.source_id,
            )
            non_nota = [r for r in ac_rows if not r.is_nota]
            nota_votes = sum(r.votes for r in ac_rows if r.is_nota)
            ranked = sorted(non_nota, key=lambda r: (-r.votes, r.name, r.party_short))
            votes_polled = sum(r.votes for r in ac_rows)
            valid_votes = _first_not_none([r.valid_votes for r in ac_rows]) or votes_polled
            total_electors = _first_not_none([r.electors for r in ac_rows])
            turnout_pct = _first_not_none([r.turnout_pct for r in ac_rows])

            winner = ranked[0]
            runner_up = ranked[1] if len(ranked) > 1 else None
            winner_party_id = resolve_party(lookup, winner)
            candidate_ids_by_rank: dict[int, str] = {}
            seen_person_ids: set[str] = set()
            votes_by_party: dict[str, int] = defaultdict(int)
            party_was_on_ballot: set[str] = set()
            forfeitures_by_party: dict[str, int] = defaultdict(int)

            for rank, candidate in enumerate(ranked, start=1):
                party_id = resolve_party(lookup, candidate)
                party_was_on_ballot.add(party_id)
                votes_by_party[party_id] += candidate.votes
                share_pct = round((candidate.votes / valid_votes * 100), 4) if valid_votes else 0.0
                if share_pct < 16.67:
                    forfeitures_by_party[party_id] += 1
                candidacy_key = candidate_entity_id(ac_id, period.period_label, rank)
                candidate_ids_by_rank[rank] = candidacy_key
                person_id = layer1_person_id(
                    state_code=state_code,
                    ac_id=ac_id,
                    election_id=period.period_label,
                    candidate_name=candidate.name,
                )
                if person_id in seen_person_ids:
                    person_id = layer1_person_id_collision_tiebreak(person_id, candidacy_key)
                seen_person_ids.add(person_id)
                persons.append(PersonDimRow(
                    person_id=person_id,
                    display_name=candidate.name,
                    source_id=source_row.source_id,
                    sex=candidate.sex,
                    age=candidate.age,
                    education=candidate.education,
                    profession=candidate.profession,
                ))
                candidacies.append(CandidacyRow(
                    candidacy_key=candidacy_key,
                    person_id=person_id,
                    ac_id=ac_id,
                    election_id=period.period_label,
                    ballot_serial=rank,
                    party_id=party_id,
                    rank=rank,
                    votes_polled=float(candidate.votes),
                    vote_share_pct=share_pct,
                    won=rank == 1,
                    source_id=source_row.source_id,
                    party_short_raw=candidate.party_short,
                    constituency_type=candidate.constituency_type,
                    party_type=candidate.party_type,
                ))
                observations.extend(candidate_observations(
                    candidacy_key=candidacy_key,
                    period=period,
                    votes=candidate.votes,
                    vote_share_pct=share_pct,
                    rank=rank,
                    source_id=source_row.source_id,
                ))

            observations.extend(ac_observations(
                ac_id=ac_id,
                period=period,
                total_electors=total_electors,
                votes_polled=votes_polled,
                turnout_pct=turnout_pct,
                nota_votes=nota_votes,
                winner_candidate_id=candidate_ids_by_rank[1],
                winner_party_id=winner_party_id,
                margin_votes=winner.votes - (runner_up.votes if runner_up else 0),
                source_id=source_row.source_id,
                candidate_count=len(ranked),
                shares=[r.votes / valid_votes for r in ranked if valid_votes],
            ))
            summaries.append(ACContestSummary(
                state_code=state_code,
                eci_no=ac_no,
                delim_year=ac_rows[0].delim_year,
                period=period,
                total_electors=total_electors,
                votes_polled=votes_polled,
                nota_votes=nota_votes,
                winner_party_id=winner_party_id,
                source_id=source_row.source_id,
                votes_by_party=dict(votes_by_party),
                party_was_on_ballot=party_was_on_ballot,
                forfeitures_by_party=dict(forfeitures_by_party),
            ))
            prior = existing.get((period.period_label, ac_id))
            if prior and (prior.get("votes_polled") != votes_polled or prior.get("winner_votes") != winner.votes):
                event_discrepancies.append({
                    "ac_no": ac_no,
                    "prior_votes_polled": prior.get("votes_polled"),
                    "panel_votes_polled": votes_polled,
                    "prior_winner_votes": prior.get("winner_votes"),
                    "panel_winner_votes": winner.votes,
                })

        observations.extend(state_rollup_observations(summaries=summaries))
        discrepancy_report["events"].append({
            "event_id": period.period_label,
            "year": year,
            "acs_total": len(by_ac),
            "mismatches": event_discrepancies,
            "halted": False,
        })

    first_source_id = sorted(sources)[0]
    envelope = BatchEnvelope(
        target_family="elections",
        schema_version="1.0",
        source_rows=sorted(sources.values(), key=lambda s: s.source_id),
        observation_rows=observations,
        person_dim_rows=persons,
        candidacy_rows=candidacies,
        ac_dim_rows=list(ac_dims.values()),
        party_dim_rows=[PartyDimRow(**r) for r in party_dim_rows(lookup, source_id=first_source_id)],
        party_alliance_dim_rows=[
            PartyAllianceDimRow(**r) for r in party_alliance_dim_rows(lookup, source_id=first_source_id)
        ],
    )
    return envelope, tuple(sorted({event_id_for(state_code, y, m) for y, m in by_event})), discrepancy_report


def ingest_panel(
    *,
    repo_root: Path,
    csv_path: Path,
    state_code: str,
    force: bool = False,
    ingested_at: str = "2026-05-24",
) -> PanelIngestResult:
    datasets_root = repo_root / "datasets"
    envelope, events, report = build_envelope(
        datasets_root=datasets_root,
        csv_path=csv_path,
        state_code=state_code,
    )
    inventory_path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not force and inventory_has_entries(
        repo_root=repo_root,
        events=events,
        state_code=state_code,
        source_input=SOURCE_INPUT_ID,
    ):
        return PanelIngestResult(
            write_result=None,
            events=events,
            report_path=Path(),
            inventory_path=inventory_path,
            skipped=True,
        )
    write_result = write_batch(envelope, datasets_root)
    report_path = write_discrepancy_report(repo_root=repo_root, state_code=state_code, report=report)
    inventory_path = upsert_inventory_entries(
        repo_root=repo_root,
        events=events,
        state_code=state_code,
        source_input=SOURCE_INPUT_ID,
        ingested_at=ingested_at,
        report=report,
    )
    return PanelIngestResult(
        write_result=write_result,
        events=events,
        report_path=report_path,
        inventory_path=inventory_path,
    )


def inventory_has_entries(
    *,
    repo_root: Path,
    events: Iterable[str],
    state_code: str,
    source_input: str,
) -> bool:
    path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not path.is_file():
        return False
    existing = json.loads(path.read_text(encoding="utf-8")).get("ingested") or []
    triples = {
        (row.get("election_id"), row.get("state"), row.get("source_input"))
        for row in existing
    }
    return all((event, state_code, source_input) in triples for event in events)


def candidate_observations(*, candidacy_key: str, period: Period, votes: int, vote_share_pct: float, rank: int, source_id: str) -> list[ObservationRow]:
    return [
        obs(candidacy_key, period, "candidate-votes-polled", source_id, "raw", value_numeric=float(votes)),
        obs(candidacy_key, period, "candidate-vote-share-pct", source_id, "ratio_pct", value_numeric=vote_share_pct),
        obs(candidacy_key, period, "candidate-rank", source_id, "raw", value_numeric=float(rank)),
    ]


def ac_observations(
    *,
    ac_id: str,
    period: Period,
    total_electors: int | None,
    votes_polled: int,
    turnout_pct: float | None,
    nota_votes: int,
    winner_candidate_id: str,
    winner_party_id: str,
    margin_votes: int,
    source_id: str,
    candidate_count: int,
    shares: list[float],
) -> list[ObservationRow]:
    rows = [
        obs(ac_id, period, "ac-votes-polled", source_id, "sum", value_numeric=float(votes_polled)),
        obs(ac_id, period, "ac-winner-candidate-id", source_id, "argmax", value_text=winner_candidate_id),
        obs(ac_id, period, "ac-winner-party-id", source_id, "join", value_text=winner_party_id),
        obs(ac_id, period, "ac-margin-votes", source_id, "diff", value_numeric=float(margin_votes)),
        obs(ac_id, period, "ac-margin-pct", source_id, "ratio_pct", value_numeric=round(margin_votes / votes_polled * 100, 4) if votes_polled else 0.0),
        obs(ac_id, period, "ac-candidates-total", source_id, "count", value_numeric=float(candidate_count)),
    ]
    if total_electors is not None:
        rows.append(obs(ac_id, period, "ac-total-electors", source_id, "raw", value_numeric=float(total_electors)))
    if turnout_pct is not None:
        rows.append(obs(ac_id, period, "ac-turnout-pct", source_id, "ratio_pct", value_numeric=turnout_pct))
    if period.year >= 2013:
        rows.append(obs(ac_id, period, "ac-nota-votes", source_id, "raw", value_numeric=float(nota_votes)))
        rows.append(obs(ac_id, period, "ac-nota-pct", source_id, "ratio_pct", value_numeric=round(nota_votes / votes_polled * 100, 4) if votes_polled else 0.0))
    ssq = sum(s * s for s in shares)
    if period.year >= 2013 and votes_polled:
        nota_share = nota_votes / votes_polled
        ssq += nota_share * nota_share
    if ssq > 0:
        rows.append(obs(ac_id, period, "ac-effective-candidates-laakso", source_id, "laakso_taagepera", value_numeric=round(1.0 / ssq, 4)))
    return rows


def obs(entity_id: str, period: Period, indicator_id: str, source_id: str, derivation: str, *, value_numeric: float | None = None, value_text: str | None = None) -> ObservationRow:
    return ObservationRow(
        entity_id=entity_id,
        year=period.year,
        period_label=period.period_label,
        period_seq=period.period_seq,
        indicator_id=indicator_id,
        value_numeric=value_numeric,
        value_text=value_text,
        source_id=source_id,
        derivation=derivation,
    )


def source_row_for(*, state_code: str, year: int) -> SourceRow:
    state_title = STATE_TITLE_BY_CODE[state_code]
    title = f"Statistical Report on General Election to the Legislative Assembly of {state_title}, {year}"
    source_id = derive_source_id("Election Commission of India", title, str(year))
    return SourceRow(
        source_id=source_id,
        producer="Election Commission of India",
        title=title,
        vintage=str(year),
        license="OGL-IN-1.0",
        confidence_tier="gold",
        is_issuing_authority=True,
        verification_method="transcribed",
        url_main=None,
        citation_full=None,
        notes=None,
    )


def resolve_party(lookup: PartyLookup, row: PanelCandidate) -> str:
    return lookup.resolve(
        party_short=row.party_short,
        is_independent=row.party_short.strip().upper() in {"IND", "INDEPENDENT"},
        is_nota=row.is_nota,
    )


def _existing_ac_totals(datasets_root: Path, state_code: str) -> dict[tuple[str, str], dict[str, int]]:
    import duckdb

    election_dir = datasets_root / "elections"
    glob = (election_dir / f"state=in_{state_code.lower()}" / "election_results.parquet").as_posix()
    if not Path(glob.replace("*", "")).exists() and not (election_dir / f"state=in_{state_code.lower()}" / "election_results.parquet").is_file():
        return {}
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"""
            WITH winners AS (
              SELECT period_label, entity_id AS ac_id, value_text AS winner_id
              FROM read_parquet('{glob}')
              WHERE indicator_id = 'ac-winner-candidate-id'
            ), winner_votes AS (
              SELECT period_label, entity_id AS candidate_id, CAST(value_numeric AS BIGINT) AS winner_votes
              FROM read_parquet('{glob}')
              WHERE indicator_id = 'candidate-votes-polled'
            ), totals AS (
              SELECT period_label, entity_id AS ac_id, CAST(value_numeric AS BIGINT) AS votes_polled
              FROM read_parquet('{glob}')
              WHERE indicator_id = 'ac-votes-polled'
            )
            SELECT w.period_label, w.ac_id, v.winner_votes, t.votes_polled
            FROM winners w
            LEFT JOIN winner_votes v ON v.period_label = w.period_label AND v.candidate_id = w.winner_id
            LEFT JOIN totals t ON t.period_label = w.period_label AND t.ac_id = w.ac_id
            """
        ).fetchall()
    finally:
        con.close()
    return {
        (period_label, ac_id): {"winner_votes": int(winner_votes or 0), "votes_polled": int(votes_polled or 0)}
        for period_label, ac_id, winner_votes, votes_polled in rows
    }


def upsert_inventory_entries(*, repo_root: Path, events: Iterable[str], state_code: str, source_input: str, ingested_at: str, report: dict) -> Path:
    path = repo_root.joinpath(*INVENTORY_PATH_REL)
    existing = []
    if path.is_file():
        existing = list(json.loads(path.read_text(encoding="utf-8")).get("ingested") or [])
    event_report = {row["event_id"]: row for row in report.get("events", [])}
    filtered = [
        row for row in existing
        if not (row.get("state") == state_code and row.get("election_id") in set(events) and row.get("source_input") == source_input)
    ]
    for event in events:
        er = event_report.get(event, {})
        filtered.append({
            "election_id": event,
            "state": state_code,
            "source_input": source_input,
            "ingested_at": ingested_at,
            "discrepancy_summary": {
                "acs_total": int(er.get("acs_total", 0)),
                "acs_with_mismatch": len(er.get("mismatches") or []),
                "coverage_pct": round(100 * len(er.get("mismatches") or []) / int(er.get("acs_total", 1) or 1), 4),
                "mean_delta_pp": 0,
                "halted": False,
            },
        })
    filtered.sort(key=lambda r: (r["state"], r["election_id"], r["source_input"]))
    write_artifact(
        path=path,
        schema_id=schema_id(INVENTORY_SCHEMA_FILE),
        schema_version=schema_version(INVENTORY_SCHEMA_FILE),
        payload={"ingested": filtered},
        sources=[],
        schema_for_validation=schema_doc(INVENTORY_SCHEMA_FILE),
    )
    return path


def write_discrepancy_report(*, repo_root: Path, state_code: str, report: dict) -> Path:
    out_dir = repo_root.joinpath(*REPORTS_DIR_REL)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"ingest-discrepancies-{state_code.lower()}-ae-panel.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out


def _as_int(raw: str, *, allow_blank: bool = False) -> int | None:
    token = (raw or "").strip()
    if not token:
        if allow_blank:
            return None
        raise ValueError("expected integer, got blank")
    return int(float(token))


def _as_float(raw: str, *, allow_blank: bool = False) -> float | None:
    token = (raw or "").strip()
    if not token:
        if allow_blank:
            return None
        raise ValueError("expected float, got blank")
    return float(token)


def _clean_optional(raw: str) -> str | None:
    token = (raw or "").strip()
    return token or None


def _normalise_sex(raw: str) -> str | None:
    token = (raw or "").strip().upper()
    return {"M": "Male", "MALE": "Male", "F": "Female", "FEMALE": "Female", "O": "Other", "": None}.get(token, token.title() if token else None)


def _normalise_age(raw: str) -> int | None:
    value = _as_int(raw, allow_blank=True)
    if value is None or value < 18 or value > 120:
        return None
    return value


def _normalise_party_type(raw: str, party_short: str) -> str | None:
    if party_short.strip().upper() in {"IND", "INDEPENDENT"}:
        return "INDEPENDENT"
    token = (raw or "").strip().upper()
    if not token:
        return None
    token = token.replace("-", "_").replace(" ", "_")
    mapping = {
        "NATIONAL_PARTY": "NATIONAL",
        "STATE_PARTY": "STATE",
        "OTHER_STATE_PARTY": "OTHER_STATE",
        "REGISTERED_UNRECOGNISED_PARTY": "REGISTERED_UNRECOGNISED",
        "REGISTERED_UNRECOGNIZED_PARTY": "REGISTERED_UNRECOGNISED",
        "INDEPENDENT": "INDEPENDENT",
    }
    return mapping.get(token, token)


def _normalise_constituency_type(raw: str) -> str | None:
    token = (raw or "").strip().upper()
    return token or None


def _is_nota(candidate: str, party_short: str) -> bool:
    return candidate.strip().upper() in _NOTA_TOKENS or party_short.strip().upper() == "NOTA"


def _first_not_none(values: Iterable[int | float | None]):
    for value in values:
        if value is not None:
            return value
    return None


def _value_by_suffix(row: dict[str, str], suffix: str) -> str:
    for key, value in row.items():
        if key.endswith(suffix):
            return value
    return ""


def _value_by_prefix(row: dict[str, str], prefix: str) -> str:
    for key, value in row.items():
        if key.startswith(prefix):
            return value
    return ""


__all__ = ["PanelIngestResult", "build_envelope", "ingest_panel", "parse_panel_csv"]
