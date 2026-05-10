"""Live end-to-end smoke test for the pipeline.

Exercises the full chain on a single TN AC slice: fetch partywise → fetch
one constituencywise → compose summary → write all three artifacts and
validate them against schemas.

Network-gated like test_sources_eci_live. Restricted to AC #1 (Gummidipoondi)
so the test stays under ~3 fetches; the full 234-AC run is operator-driven
via `yen-gov run AcGenMay2026 S22`.
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import pytest

from yen_gov.core.http import Fetcher
from yen_gov.core.io import write_artifact
from yen_gov.core.models import SourceRef
from yen_gov.pipeline.compose import (
    compose_result_summary,
    party_lookup_from_partywise,
)
from yen_gov.pipeline.run import parties_snapshot_from_partywise
from yen_gov.sources.eci.constituencywise import (
    parse_constituencywise,
    to_constituency_result,
)
from yen_gov.sources.eci.partywise import parse_partywise
from yen_gov.sources.eci.urls import (
    constituencywise_url,
    partywise_state_url,
)


_EVENT = "AcGenMay2026"
_STATE = "S22"
_UA = "yen-gov-tests/0.0"

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "datasets" / "schemas"


def _network_up() -> bool:
    if os.environ.get("YEN_GOV_NO_NET") == "1":
        return False
    try:
        socket.create_connection(("results.eci.gov.in", 443), timeout=5).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _network_up(),
    reason="results.eci.gov.in not reachable (set YEN_GOV_NO_NET=1 to skip explicitly)",
)


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_pipeline_one_ac_slice(tmp_path: Path):
    with Fetcher(
        source="eci", runtime_root=tmp_path,
        timeout_seconds=20, retry_attempts=1, retry_backoff_seconds=1.0,
        user_agent=_UA,
    ) as fetcher:
        # 1. partywise
        pw_url = partywise_state_url(_EVENT, _STATE)
        pw_fr = fetcher.fetch(pw_url)
        snapshot = parse_partywise(pw_fr.content)
        snapshot_src = SourceRef(url=pw_fr.url, fetched_at=pw_fr.fetched_at)
        assert snapshot.total_seats == 234
        lookup = party_lookup_from_partywise(snapshot)

        # 2. one constituencywise
        cw_url = constituencywise_url(_EVENT, _STATE, 1)
        cw_fr = fetcher.fetch(cw_url)
        raw = parse_constituencywise(cw_fr.content)
        cw_src = SourceRef(url=cw_fr.url, fetched_at=cw_fr.fetched_at)
        cr = to_constituency_result(
            raw, election=_EVENT, state=_STATE, body="AC", eci_no=1,
            top_n=5, collapse_others=True,
            sources=[cw_src], party_lookup=lookup,
        )
        assert cr.constituency_name and "GUMMIDIPOONDI" in cr.constituency_name.upper()
        assert cr.winner.party_short  # filled from lookup
        assert cr.totals.votes_polled > 0

    # 3. compose summary against the single result
    summary = compose_result_summary(
        election=_EVENT, state=_STATE, body="AC",
        partywise=snapshot, constituencies=[cr],
        sources=[snapshot_src, cw_src],
    )
    assert summary.total_seats == 234
    assert summary.totals.votes_polled == cr.totals.votes_polled

    # 4. parties snapshot
    parties = parties_snapshot_from_partywise(
        snapshot, election=_EVENT, sources=[snapshot_src],
    )
    assert len(parties.parties) >= 1
    assert all(p.eci_code.isdigit() for p in parties.parties)

    # 5. write all three through schema validation
    out = tmp_path / "out"
    write_artifact(
        path=out / "results" / "1.json",
        schema_id=cr._schema_id, schema_version=cr._schema_version,
        payload=cr.body_payload(), sources=cr.sources_payload(),
        schema_for_validation=_load_schema("result.constituency.schema.json"),
    )
    write_artifact(
        path=out / "result.summary.json",
        schema_id=summary._schema_id, schema_version=summary._schema_version,
        payload=summary.body_payload(), sources=summary.sources_payload(),
        schema_for_validation=_load_schema("result.summary.schema.json"),
    )
    write_artifact(
        path=out / "parties.json",
        schema_id=parties._schema_id, schema_version=parties._schema_version,
        payload=parties.body_payload(), sources=parties.sources_payload(),
        schema_for_validation=_load_schema("party.schema.json"),
    )
    assert (out / "results" / "1.json").exists()
    assert (out / "result.summary.json").exists()
    assert (out / "parties.json").exists()
