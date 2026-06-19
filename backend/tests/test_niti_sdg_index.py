"""Contract tests for the greenfield NITI SDG India Index ingest (plan Row 11).

Stages the COMMITTED real fixture
(``docs/research/niti-sdg-index-ingest/sdg-india-index-2020-21.csv``) under
``tmp_path`` and asserts the emitted datapoints + upserted catalogue rows pass
the canonical validator, the indicator/concept registration FK resolves against
the real taxonomy SOT, and a second run is a byte-for-byte no-op (idempotent).
The parser's fail-loud paths are covered directly. No network; no real-corpus
walk (CLAUDE.md anti-pattern).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.niti_sdg_index import (
    SHIPPED_SPEC,
    SdgParseError,
    ingest,
    parse_sdg_index_csv,
    spec_by_indicator_id,
)
from yen_gov.canonical.adapters.niti_sdg_index.ingest import NitiSdgIndexAdapter
from yen_gov.canonical.adapters.rbi_handbook.resolver import build_state_resolver
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.ingest.catalogue_fk import check_indicator_registration
from yen_gov.canonical.ingest.registry import OrchestrateConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_CSV = (
    _REPO_ROOT
    / "docs"
    / "research"
    / "niti-sdg-index-ingest"
    / "sdg-india-index-2020-21.csv"
)
_INDICATORS_JSON = _REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"
_CONCEPTS_JSON = _REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"

# geo.csv covering the committed fixture's states (+ All India -> IN handled by
# the resolver's all-India label set, so the country row is not required here).
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01,28,28\n"
    "assam,Assam,IN,state,IN-AS|S03,18,18\n"
    "bihar,Bihar,IN,state,IN-BR|S04,10,10\n"
    "gujarat,Gujarat,IN,state,IN-GJ|S06,24,24\n"
    "himachal-pradesh,Himachal Pradesh,IN,state,IN-HP|S08,2,2\n"
    "jharkhand,Jharkhand,IN,state,IN-JH|S07,20,20\n"
    "karnataka,Karnataka,IN,state,IN-KA|S10,29,29\n"
    "kerala,Kerala,IN,state,IN-KL|S11,32,32\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22,33,33\n"
    "uttar-pradesh,Uttar Pradesh,IN,state,IN-UP|S24,9,9\n"
)


def _write_geo(repo_root: Path) -> Path:
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    return geo


def _stage(tmp_path: Path) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / SHIPPED_SPEC.staging_filename).write_bytes(_FIXTURE_CSV.read_bytes())
    return staging


def _resolver(tmp_path: Path):
    return build_state_resolver(_write_geo(tmp_path))


def _read_datapoints(path: Path) -> dict[tuple[str, int], float]:
    out: dict[tuple[str, int], float] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out[(row["entity_id"], int(row["time"]))] = float(row["value"])
    return out


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


class TestParser:
    def test_melts_and_resolves(self, tmp_path):
        obs = parse_sdg_index_csv(
            _FIXTURE_CSV.read_bytes(), SHIPPED_SPEC, _resolver(tmp_path)
        )
        got = {(o.entity_id, o.time): o.value for o in obs}
        assert got[("IN", 2021)] == 66.0  # "All India" -> country IN
        assert got[("kerala", 2021)] == 75.0
        assert got[("bihar", 2021)] == 52.0
        # Sorted by (entity_id, time).
        keys = [(o.entity_id, o.time) for o in obs]
        assert keys == sorted(keys)

    def test_missing_header_raises(self):
        with pytest.raises(SdgParseError, match="must contain"):
            parse_sdg_index_csv(
                b"region,year,value\nKerala,2021,75\n",
                SHIPPED_SPEC,
                _StubResolver(),
            )

    def test_unresolved_state_raises(self, tmp_path):
        with pytest.raises(SdgParseError, match="unresolved state"):
            parse_sdg_index_csv(
                b"state,year,score\nAtlantis,2021,99\n",
                SHIPPED_SPEC,
                _resolver(tmp_path),
            )

    def test_non_integer_year_raises(self, tmp_path):
        with pytest.raises(SdgParseError, match="non-integer year"):
            parse_sdg_index_csv(
                b"state,year,score\nKerala,FY21,75\n",
                SHIPPED_SPEC,
                _resolver(tmp_path),
            )

    def test_unparseable_score_raises(self, tmp_path):
        with pytest.raises(SdgParseError, match="unparseable score"):
            parse_sdg_index_csv(
                b"state,year,score\nKerala,2021,high\n",
                SHIPPED_SPEC,
                _resolver(tmp_path),
            )


class _StubResolver:
    def resolve(self, label):  # pragma: no cover - header check precedes resolve
        return None


# --------------------------------------------------------------------------- #
# Full ingest -> emitted corpus validates
# --------------------------------------------------------------------------- #


class TestIngest:
    def test_emits_datapoints_and_catalogue(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))

        assert len(result.tables) == 1
        table = result.tables[0]
        assert table.indicator_id == "sdg-india-index-score"
        assert table.row_count == 11
        assert table.entity_count == 11
        assert (table.time_min, table.time_max) == (2021, 2021)

        out = tmp_path / "datasets/data/datapoints/geo/sdg-india-index-score.csv"
        assert out.read_text(encoding="utf-8").splitlines()[0] == (
            "entity_id,time,value,source_id"
        )
        got = _read_datapoints(out)
        assert got[("kerala", 2021)] == 75.0
        assert got[("IN", 2021)] == 66.0

    def test_source_id_derived_and_producer_is_niti(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        expected = derive_source_id(
            SHIPPED_SPEC.source_producer,
            SHIPPED_SPEC.source_title,
            SHIPPED_SPEC.source_vintage,
        )
        source = (tmp_path / "datasets/data/entities/source.csv").read_text(
            encoding="utf-8"
        )
        assert expected in source
        # NITI ORIGINATES the index -> producer is the issuing authority.
        assert "NITI Aayog" in source

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(
            encoding="utf-8"
        )
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(
            encoding="utf-8"
        )
        assert "sdg-india-index-score" in variables
        assert "sdg-india-index-score" in concepts

    def test_emitted_datapoints_pass_validator(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        out = tmp_path / "datasets/data/datapoints/geo/sdg-india-index-score.csv"
        validate_csv(
            path=out,
            file_class="datasets/data/datapoints/geo/*.csv",
            repo_root=tmp_path,
        )

    def test_indicator_registration_fk_resolves(self, tmp_path):
        # The adapter's IndicatorSpec must resolve in the REAL taxonomy SOT
        # (the SDG concept + indicator this PR registered) -- so an orchestrated
        # run passes the catalogue FK + concept-compatibility check.
        adapter = NitiSdgIndexAdapter()
        spec = adapter.source_specs()[0].indicators[0]
        check_indicator_registration(
            spec,
            indicators_path=_INDICATORS_JSON,
            concepts_path=_CONCEPTS_JSON,
        )  # raises on a missing FK or a unit/normalisation mismatch

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        staging = _stage(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / "datasets/data/datapoints/geo/sdg-india-index-score.csv"
        first_bytes = out.read_bytes()
        first_mtime = out.stat().st_mtime_ns

        ingest(repo_root=tmp_path, staging_dir=staging)
        assert out.read_bytes() == first_bytes
        assert out.stat().st_mtime_ns == first_mtime

    def test_run_indicator_through_adapter(self, tmp_path):
        # The orchestrator-facing path: run_indicator drives the same ingest.
        _write_geo(tmp_path)
        adapter = NitiSdgIndexAdapter()
        res = adapter.run_indicator(
            "sdg-india-index-score",
            repo_root=tmp_path,
            config=OrchestrateConfig(staging_dir=_stage(tmp_path)),
        )
        assert res.adapter_slug == "niti-sdg-index"
        assert res.indicator_id == "sdg-india-index-score"
        assert res.row_count == 11
        assert res.output_ref == (
            "datasets/data/datapoints/geo/sdg-india-index-score.csv"
        )

    def test_missing_staged_csv_raises(self, tmp_path):
        _write_geo(tmp_path)
        empty = tmp_path / "staging"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="staged SDG India Index"):
            ingest(repo_root=tmp_path, staging_dir=empty)

    def test_spec_lookup_unknown_raises(self):
        with pytest.raises(KeyError, match="unknown SDG India Index"):
            spec_by_indicator_id("not-a-real-id")
