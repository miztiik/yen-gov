"""Live tests for the Wikipedia source adapter.

Hits en.wikipedia.org with a descriptive User-Agent (their policy requires
one). Same network gating pattern as test_sources_eci_live.py.
"""

from __future__ import annotations

import os
import socket
from datetime import datetime, timezone

import httpx
import pytest

from yen_gov.core.io import write_artifact
from yen_gov.core.models import SourceRef
from yen_gov.sources.wikipedia.constituencies import parse_ac_constituencies
from yen_gov.sources.wikipedia.districts import parse_districts
from yen_gov.sources.wikipedia.urls import (
    WIKIPEDIA_BASE,
    ac_constituencies_url,
    districts_url,
)
import json
from pathlib import Path


_WIKI_UA = (
    "yen-gov-tests/0.0 (https://github.com/yen-gov/yen-gov; "
    "election data pipeline) httpx"
)
_TN = "S22"

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "datasets" / "schemas"


def _network_up() -> bool:
    if os.environ.get("YEN_GOV_NO_NET") == "1":
        return False
    try:
        socket.create_connection(("en.wikipedia.org", 443), timeout=5).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _network_up(),
    reason="en.wikipedia.org not reachable (set YEN_GOV_NO_NET=1 to skip explicitly)",
)


@pytest.fixture(scope="module")
def http() -> httpx.Client:
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": _WIKI_UA}) as c:
        yield c


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


# --- urls -------------------------------------------------------------------

def test_url_builders_for_tn():
    assert districts_url(_TN).startswith(WIKIPEDIA_BASE)
    assert "List_of_districts_of_Tamil_Nadu" in districts_url(_TN)
    assert "List_of_constituencies_of_the_Tamil_Nadu_Legislative_Assembly" in ac_constituencies_url(_TN)


def test_url_builder_rejects_unknown_state():
    with pytest.raises(ValueError, match="no Wikipedia state-name mapping"):
        districts_url("S99")


# --- districts --------------------------------------------------------------

def test_live_districts_tn(http: httpx.Client, tmp_path: Path):
    url = districts_url(_TN)
    r = http.get(url)
    assert r.status_code == 200
    sources = [SourceRef(url=url, fetched_at=datetime(2026, 5, 8, 14, 0, tzinfo=timezone.utc))]
    coll = parse_districts(r.content, state_code=_TN, sources=sources)

    assert coll.state == "S22"
    # TN had 38 districts at the time of this test. If TN gains/loses districts
    # the assertion should be updated; that's the kind of change we want to notice.
    assert 30 <= len(coll.districts) <= 50
    by_code = {d.id: d for d in coll.districts}
    # Spot-check well-known districts. Wikipedia parenthesises a few names
    # ("Chennai (formerly Madras)") so test by substring.
    names = [d.name for d in coll.districts]
    assert any("Chennai" in n for n in names)
    assert any("Coimbatore" in n for n in names)
    # Codes should be unique.
    assert len(by_code) == len(coll.districts)
    # All ids must be non-empty strings.
    for d in coll.districts:
        assert d.id and d.id_source == "wikipedia"

    # Round-trip through write_artifact validates against district.schema.json.
    schema = _load_schema("district.schema.json")
    out = tmp_path / "districts.json"
    write_artifact(
        path=out, schema_id=coll._schema_id, schema_version=coll._schema_version,
        payload=coll.body_payload(), sources=coll.sources_payload(),
        schema_for_validation=schema,
    )
    assert out.exists()


# --- constituencies ---------------------------------------------------------

def test_live_ac_constituencies_tn(http: httpx.Client, tmp_path: Path):
    url = ac_constituencies_url(_TN)
    r = http.get(url)
    assert r.status_code == 200
    sources = [SourceRef(url=url, fetched_at=datetime(2026, 5, 8, 14, 0, tzinfo=timezone.utc))]
    coll = parse_ac_constituencies(r.content, state_code=_TN, sources=sources)

    assert coll.state == "S22"
    assert coll.body == "AC"
    assert len(coll.constituencies) == 234  # TN has 234 AC seats
    nos = [c.eci_no for c in coll.constituencies]
    assert nos == list(range(1, 235))
    # AC #1 is Gummidipoondi (verified against the live ECI page).
    assert coll.constituencies[0].name == "Gummidipoondi"
    # Reservation distribution sanity: all GEN/SC/ST.
    assert {c.reservation for c in coll.constituencies} <= {"GEN", "SC", "ST"}
    # TN has 44 reserved seats (42 SC + 2 ST). Allow a small drift if Wikipedia
    # disagrees with ECI's count by a couple.
    sc = sum(1 for c in coll.constituencies if c.reservation == "SC")
    st = sum(1 for c in coll.constituencies if c.reservation == "ST")
    assert 35 <= sc <= 50
    assert 1 <= st <= 5

    # Round-trip through schema validation.
    schema = _load_schema("constituency.schema.json")
    out = tmp_path / "constituencies.json"
    write_artifact(
        path=out, schema_id=coll._schema_id, schema_version=coll._schema_version,
        payload=coll.body_payload(), sources=coll.sources_payload(),
        schema_for_validation=schema,
    )
    assert out.exists()
