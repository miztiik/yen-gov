"""Wikipedia reference scrape: districts + constituencies for one state.

Companion to `pipeline/run.py`. Where `run` orchestrates ECI result fetching,
this module orchestrates the one-shot Wikipedia reference scrape that
populates `datasets/reference/in/states/<S>/{districts,constituencies}.json`.

Kept separate because:
  - The Wikipedia adapter is a one-shot per state per delimitation cycle, not
    a per-event run. Different cadence, different output tree.
  - It needs a different UA string (descriptive, per Wikipedia bot etiquette
    — see docs/architecture/backend/sources-wikipedia.md) than the ECI fetcher.
  - It writes under `datasets/reference/`, not `datasets/elections/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from yen_gov.core.http import Fetcher
from yen_gov.core.io import write_artifact
from yen_gov.core.models import (
    ConstituenciesCollection,
    ConstituencyEntry,
    DistrictsCollection,
    SourceRef,
)
from yen_gov.sources.wikipedia.constituencies import (
    build_district_lookup, parse_ac_constituencies,
)
from yen_gov.sources.wikipedia.districts import parse_districts
from yen_gov.sources.wikipedia.urls import (
    ac_constituencies_url,
    districts_url,
)


@dataclass(frozen=True)
class ReferencePaths:
    districts: Path
    constituencies: Path


@dataclass(frozen=True)
class ReferenceResult:
    districts: DistrictsCollection
    constituencies: ConstituenciesCollection
    paths: ReferencePaths


def scrape_state_reference(
    *,
    state_code: str,
    output_dir: Path,
    schema_dir: Path,
    fetcher: Fetcher,
) -> ReferenceResult:
    """Fetch + parse + emit districts.json and constituencies.json for one state."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Districts
    d_url = districts_url(state_code)
    d_fr = fetcher.fetch(d_url)
    d_src = SourceRef(url=d_fr.url, fetched_at=d_fr.fetched_at)
    districts = parse_districts(d_fr.content, state_code=state_code, sources=[d_src])
    districts_path = output_dir / "districts.json"
    write_artifact(
        path=districts_path,
        schema_id=districts._schema_id,
        schema_version=districts._schema_version,
        payload=districts.body_payload(),
        sources=districts.sources_payload(),
        schema_for_validation=_load_schema(schema_dir, "district.schema.json"),
    )

    # Constituencies — pass districts down so the parser can resolve the
    # 'District' column to a district id (see docs/architecture/data-model.md hierarchy fields).
    # Status stays 'provisional' because pc_id still needs a separate source.
    district_id_by_name = build_district_lookup(
        [(d.name, d.id) for d in districts.districts]
    )
    c_url = ac_constituencies_url(state_code)
    c_fr = fetcher.fetch(c_url)
    c_src = SourceRef(url=c_fr.url, fetched_at=c_fr.fetched_at)
    constituencies = parse_ac_constituencies(
        c_fr.content, state_code=state_code, sources=[c_src],
        district_id_by_name=district_id_by_name,
    )
    constituencies_path = output_dir / "constituencies.json"
    write_artifact(
        path=constituencies_path,
        schema_id=constituencies._schema_id,
        schema_version=constituencies._schema_version,
        payload=constituencies.body_payload(),
        sources=constituencies.sources_payload(),
        schema_for_validation=_load_schema(schema_dir, "constituency.schema.json"),
    )

    return ReferenceResult(
        districts=districts,
        constituencies=constituencies,
        paths=ReferencePaths(districts=districts_path, constituencies=constituencies_path),
    )


def _load_schema(schema_dir: Path, name: str) -> dict:
    return json.loads((schema_dir / name).read_text(encoding="utf-8"))
