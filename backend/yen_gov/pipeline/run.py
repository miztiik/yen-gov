"""End-to-end pipeline orchestrator for one (event, state) slice.

Glues together: ECI fetch → parse partywise → fetch each constituencywise →
parse + map → compose ResultSummary → write all artifacts. This is the only
module allowed to import from `core/`, `sources/`, AND `pipeline/compose`
together.

Output layout under `output_dir`:

    parties.json                 # PartiesSnapshot built from partywise
    result.summary.json          # ResultSummary aggregate
    results/<eci_no>.json        # one ConstituencyResult per AC

Per CLAUDE.md §6 fail-loud: a single AC failure aborts the run. We don't ship
a partial summary that silently elides constituencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from yen_gov.core.http import Fetcher
from yen_gov.core.io import write_artifact
from yen_gov.core.models import (
    ConstituencyResult,
    PartiesSnapshot,
    PartyEntry,
    ResultSummary,
    SourceRef,
)
from yen_gov.pipeline.compose import (
    compose_result_summary,
    party_lookup_from_partywise,
    reconcile_winners_against_partywise,
)
from yen_gov.sources.eci.constituencywise import (
    parse_constituencywise,
    to_constituency_result,
)
from yen_gov.sources.eci.partywise import PartywiseSnapshot, parse_partywise
from yen_gov.sources.eci.urls import constituencywise_url, partywise_state_url


@dataclass(frozen=True)
class RunPaths:
    parties: Path
    summary: Path
    results_dir: Path


@dataclass(frozen=True)
class RunResult:
    snapshot: PartywiseSnapshot
    constituencies: list[ConstituencyResult]
    summary: ResultSummary
    parties: PartiesSnapshot
    paths: RunPaths


def run_state_slice(
    *,
    event_id: str,
    state_code: str,
    output_dir: Path,
    schema_dir: Path,
    fetcher: Fetcher,
    top_n: int,
    collapse_others: bool,
) -> RunResult:
    """Fetch + parse + compose + write one (event, state) slice."""
    snapshot, snapshot_src = _fetch_partywise(fetcher, event_id, state_code)
    lookup = party_lookup_from_partywise(snapshot)

    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    cr_schema = _load_schema(schema_dir, "result.constituency.schema.json")

    constituencies: list[ConstituencyResult] = []
    constituency_sources: list[SourceRef] = []
    for n in range(1, snapshot.total_seats + 1):
        cr, src = _fetch_constituency(
            fetcher, event_id=event_id, state_code=state_code, eci_no=n,
            top_n=top_n, collapse_others=collapse_others, party_lookup=lookup,
        )
        constituencies.append(cr)
        constituency_sources.append(src)
        write_artifact(
            path=results_dir / f"{n}.json",
            schema_id=cr._schema_id, schema_version=cr._schema_version,
            payload=cr.body_payload(), sources=cr.sources_payload(),
            schema_for_validation=cr_schema,
        )

    summary = compose_result_summary(
        election=event_id, state=state_code, body="AC",
        partywise=snapshot, constituencies=constituencies,
        sources=[snapshot_src, *constituency_sources],
    )
    reconcile_winners_against_partywise(
        partywise=snapshot, constituencies=constituencies,
    )
    summary_path = output_dir / "result.summary.json"
    write_artifact(
        path=summary_path,
        schema_id=summary._schema_id, schema_version=summary._schema_version,
        payload=summary.body_payload(), sources=summary.sources_payload(),
        schema_for_validation=_load_schema(schema_dir, "result.summary.schema.json"),
    )

    parties = parties_snapshot_from_partywise(
        snapshot, election=event_id, sources=[snapshot_src],
    )
    parties_path = output_dir / "parties.json"
    write_artifact(
        path=parties_path,
        schema_id=parties._schema_id, schema_version=parties._schema_version,
        payload=parties.body_payload(), sources=parties.sources_payload(),
        schema_for_validation=_load_schema(schema_dir, "party.schema.json"),
    )

    return RunResult(
        snapshot=snapshot,
        constituencies=constituencies,
        summary=summary,
        parties=parties,
        paths=RunPaths(parties=parties_path, summary=summary_path, results_dir=results_dir),
    )


def _fetch_partywise(
    fetcher: Fetcher, event_id: str, state_code: str,
) -> tuple[PartywiseSnapshot, SourceRef]:
    url = partywise_state_url(event_id, state_code)
    fr = fetcher.fetch(url)
    snapshot = parse_partywise(fr.content)
    return snapshot, SourceRef(url=fr.url, fetched_at=fr.fetched_at)


def _fetch_constituency(
    fetcher: Fetcher, *, event_id: str, state_code: str, eci_no: int,
    top_n: int, collapse_others: bool,
    party_lookup: dict[str, tuple[str, str | None]],
) -> tuple[ConstituencyResult, SourceRef]:
    url = constituencywise_url(event_id, state_code, eci_no)
    fr = fetcher.fetch(url)
    raw = parse_constituencywise(fr.content)
    src = SourceRef(url=fr.url, fetched_at=fr.fetched_at)
    cr = to_constituency_result(
        raw,
        election=event_id, state=state_code, body="AC", eci_no=eci_no,
        top_n=top_n, collapse_others=collapse_others,
        sources=[src], party_lookup=party_lookup,
    )
    return cr, src


def parties_snapshot_from_partywise(
    snapshot: PartywiseSnapshot, *, election: str, sources: list[SourceRef],
) -> PartiesSnapshot:
    # Drop rows whose ECI numeric code we couldn't extract — party.schema.json
    # requires it. Those parties will still be visible in result.summary.json
    # via party_short, but won't appear in the canonical parties roster until
    # a future adapter (e.g. notification.eci.gov.in) supplies missing codes.
    entries = [
        PartyEntry(
            eci_code=row.eci_code,
            short_name=row.short_name,
            full_name=row.full_name,
        )
        for row in snapshot.parties
        if row.eci_code is not None
    ]
    if not entries:
        raise ValueError("partywise snapshot yielded zero parties with ECI codes")
    return PartiesSnapshot(sources=sources, election=election, parties=entries)


def _load_schema(schema_dir: Path, name: str) -> dict:
    return json.loads((schema_dir / name).read_text(encoding="utf-8"))
