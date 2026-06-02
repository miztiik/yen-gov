"""ECI Lok Sabha (PC) constituency-wise results adapter / driver.

Reads the frozen ECI Report-33 constituency-wise detailed-result CSV plus the
Report-34 AC→PC crosswalk and emits canonical PC-grain Parquet rows through
the shared BatchEnvelope writer.

The PC rows share the existing ``datasets/elections/state=<key>/`` fact family
(no ``grain=`` partition); the writer routes ``IN-PC-...`` entity_ids to the
matching ``in_<state>`` shard alongside the AC rows. ``dim_pcs.parquet`` is the
PC-grain dimension sibling of ``dim_acs.parquet``.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from yen_gov.canonical.adapters.eci.identity import Period
from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.adapters.eci.party_lookup import (
    PartyLookup,
    UnknownPartyError,
    load_party_lookup,
    party_alliance_dim_rows,
    party_dim_rows,
)
from yen_gov.canonical.adapters.eci.pc_observations import (
    dim_rows_from_pc,
    observations_from_pc,
    persons_and_candidacies_from_pc,
)
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.envelope import (
    BatchEnvelope,
    CandidacyRow,
    ObservationRow,
    PartyAllianceDimRow,
    PartyDimRow,
    PcDimRow,
    PersonDimRow,
    SourceRow,
)
from yen_gov.canonical.writer import WriteResult, write_batch
from yen_gov.sources.eci.ls_constituencywise import parse_ls_constituencywise

# The 2024 Lok Sabha general election: results declared 2024-06-04. The
# event_id MUST be parseable by ``parse_period_label`` (body+month+year), so
# the polling-month-style ``LsGenJun2024`` is the canonical id.
LS_2024_EVENT = Period(period_label="LsGenJun2024", year=2024, period_seq=6)
# Current Lok Sabha boundaries are the 2008 delimitation.
LS_2024_DELIM_YEAR = 2008
SOURCE_INPUT_ID = "eci_ls"
INVENTORY_PATH_REL = ("datasets", "elections", "_inventory.json")


@dataclass(frozen=True)
class LsIngestResult:
    write_result: WriteResult | None
    event_id: str
    pc_count: int
    inventory_path: Path
    unresolved_parties: dict[str, int]
    skipped: bool = False


class _LenientPartyLookup:
    """Maps unresolved long-tail parties to the canonical sentinel.

    Mirrors the panel adapter's lenient wrapper so a single unknown party
    string does not halt a 542-PC backfill.
    """

    def __init__(self, inner: PartyLookup, miss_counter: Counter[str]):
        self._inner = inner
        self._misses = miss_counter

    def resolve(self, **kwargs) -> str:
        try:
            return self._inner.resolve(**kwargs)
        except UnknownPartyError:
            short = kwargs.get("party_short") or kwargs.get("party_full") or "<empty>"
            self._misses[str(short)] += 1
            return "parties.IN.UNK"


def pc_source_row() -> SourceRow:
    title = (
        "General Election to Lok Sabha 2024 — Constituency Wise Detailed "
        "Result (Report 33)"
    )
    source_id = derive_source_id("Election Commission of India", title, "2024")
    return SourceRow(
        source_id=source_id,
        producer="Election Commission of India",
        title=title,
        vintage="2024",
        license="OGL-IN-1.0",
        confidence_tier="gold",
        is_issuing_authority=True,
        verification_method="transcribed",
        url_main=None,
        citation_full=None,
        notes=None,
    )


def build_pc_envelope(
    *,
    datasets_root: Path,
    csv_path: Path,
    crosswalk_path: Path,
    allow_unknown_parties: bool = False,
) -> tuple[BatchEnvelope, int, dict[str, int]]:
    """Parse the ECI Report-33 + Report-34 CSVs into a BatchEnvelope.

    Returns ``(envelope, pc_count, unresolved_parties)``.
    """
    results = parse_ls_constituencywise(
        csv_path,
        crosswalk_path=crosswalk_path,
        datasets_root=datasets_root,
    )
    unresolved: Counter[str] = Counter()
    base_lookup = load_party_lookup(datasets_root)
    lookup = (
        _LenientPartyLookup(base_lookup, unresolved)
        if allow_unknown_parties
        else base_lookup
    )
    source_row = pc_source_row()

    observations: list[ObservationRow] = []
    pc_dims: list[PcDimRow] = []
    person_payloads: dict[str, dict] = {}
    candidacy_payloads: list[dict] = []
    for result in results:
        observations.extend(observations_from_pc(
            result=result,
            period=LS_2024_EVENT,
            delim_year=LS_2024_DELIM_YEAR,
            party_lookup=lookup,
            source_id=source_row.source_id,
        ))
        pc_dims.extend(
            PcDimRow(**row)
            for row in dim_rows_from_pc(
                result=result,
                delim_year=LS_2024_DELIM_YEAR,
                source_id=source_row.source_id,
            )
        )
        persons, candidacies = persons_and_candidacies_from_pc(
            result=result,
            period=LS_2024_EVENT,
            delim_year=LS_2024_DELIM_YEAR,
            party_lookup=lookup,
            source_id=source_row.source_id,
        )
        for p in persons:
            person_payloads[p["person_id"]] = p
        candidacy_payloads.extend(candidacies)

    envelope = BatchEnvelope(
        target_family="elections",
        schema_version="1.0",
        source_rows=[source_row],
        observation_rows=observations,
        pc_dim_rows=pc_dims,
        person_dim_rows=[PersonDimRow(**p) for p in person_payloads.values()],
        candidacy_rows=[CandidacyRow(**c) for c in candidacy_payloads],
        party_dim_rows=[
            PartyDimRow(**r)
            for r in party_dim_rows(base_lookup, source_id=source_row.source_id)
        ],
        party_alliance_dim_rows=[
            PartyAllianceDimRow(**r)
            for r in party_alliance_dim_rows(base_lookup, source_id=source_row.source_id)
        ],
    )
    return envelope, len(results), dict(sorted(unresolved.items()))


def ingest_ls(
    *,
    repo_root: Path,
    csv_path: Path,
    crosswalk_path: Path,
    force: bool = False,
    ingested_at: str = "2026-05-31",
    allow_unknown_parties: bool = False,
) -> LsIngestResult:
    datasets_root = repo_root / "datasets"
    inventory_path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not force and _inventory_has_event(repo_root):
        return LsIngestResult(
            write_result=None,
            event_id=LS_2024_EVENT.period_label,
            pc_count=0,
            inventory_path=inventory_path,
            unresolved_parties={},
            skipped=True,
        )
    envelope, pc_count, unresolved = build_pc_envelope(
        datasets_root=datasets_root,
        csv_path=csv_path,
        crosswalk_path=crosswalk_path,
        allow_unknown_parties=allow_unknown_parties,
    )
    write_result = write_batch(envelope, datasets_root)
    states = sorted({row.state_code for row in envelope.pc_dim_rows})
    inventory_path = _upsert_inventory(
        repo_root=repo_root,
        states=states,
        ingested_at=ingested_at,
    )
    return LsIngestResult(
        write_result=write_result,
        event_id=LS_2024_EVENT.period_label,
        pc_count=pc_count,
        inventory_path=inventory_path,
        unresolved_parties=unresolved,
    )


def _inventory_has_event(repo_root: Path) -> bool:
    path = repo_root.joinpath(*INVENTORY_PATH_REL)
    if not path.is_file():
        return False
    existing = json.loads(path.read_text(encoding="utf-8")).get("ingested") or []
    return any(
        row.get("election_id") == LS_2024_EVENT.period_label
        and row.get("source_input") == SOURCE_INPUT_ID
        for row in existing
    )


def _upsert_inventory(*, repo_root: Path, states: list[str], ingested_at: str) -> Path:
    path = repo_root.joinpath(*INVENTORY_PATH_REL)
    payload: dict = {"ingested": []}
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("ingested", [])
    filtered = [
        row for row in payload["ingested"]
        if not (
            row.get("election_id") == LS_2024_EVENT.period_label
            and row.get("source_input") == SOURCE_INPUT_ID
        )
    ]
    # National Lok Sabha event recorded as one inventory slice per state.
    # Schema v2.0 (ADR-0050): state field carries LGD-name slug, not ECI st_code.
    # Callers pass ECI st_code (relational join-key); translate at the write boundary.
    for state in states:
        filtered.append({
            "election_id": LS_2024_EVENT.period_label,
            "state": eci_to_lgd_slug(state),
            "source_input": SOURCE_INPUT_ID,
            "ingested_at": ingested_at,
        })
    payload["ingested"] = filtered
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
