"""Unit tests for `tools/iced_parity/` — step 6 substrate.

Eight named test cases cover `classify.py` (the six-value enum plus
two tolerance-aware boundary cases) per Fowler's §4 brief. Additional
tests cover `sample.py` (deterministic stratified sampling), `ledger.py`
(append + prior-upstream lookup), and `banner.py` (zero-sample shape +
mixed-status roll-up).

Per Holy Law #7: no mocks. Tests use real `tmp_path` files and real
dict fixtures; the `UpstreamFetcher` Protocol is tested by passing a
plain function (structural typing — no class needed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from iced_parity import (  # noqa: E402  (after sys.path manipulation)
    Cell,
    DEFAULT_REL_TOLERANCE,
    ParityObservation,
    all_cells,
    append,
    classify,
    last_upstream_value,
    ledger_path,
    read_lines,
    stratified_sample,
    summarise,
)


# ---------------------------------------------------------------------------
# Eight named classify cases (Fowler §4).
# ---------------------------------------------------------------------------


def test_classify_case_1_exact_match():
    assert classify(42.0, 42.0) == "match"


def test_classify_case_2_near_match_within_tolerance():
    # 0.001 % delta is well under the 0.01 % default rel tolerance.
    assert classify(100.0, 100.0001) == "near_match"


def test_classify_case_3_diverge_with_no_prior_history():
    # First-ever observation; no prior_upstream to disambiguate.
    assert classify(80.0, 90.0) == "diverge"


def test_classify_case_4_diverge_with_prior_ours_differs_from_prior():
    # Both sides moved differently — operator regression suspect.
    assert (
        classify(80.0, 90.0, value_prior_upstream=85.0) == "diverge"
    )


def test_classify_case_5_revised_upstream_ours_still_matches_prior():
    # Upstream silently revised; our pipeline still emits the old value.
    assert (
        classify(85.0, 90.0, value_prior_upstream=85.0) == "revised_upstream"
    )


def test_classify_case_6_missing_upstream():
    assert classify(42.0, None) == "missing_upstream"


def test_classify_case_7_missing_ours():
    assert classify(None, 42.0) == "missing_ours"


def test_classify_case_8_revised_upstream_uses_tolerance_against_prior():
    # Our value matches prior_upstream within tolerance, upstream
    # has moved well outside tolerance — still classified as a
    # revision, not a divergence. Defends the tolerance-aware path
    # of resolution §5(a).
    assert (
        classify(
            value_ours=85.000_05,             # ~6e-7 off prior — well inside default rel tol
            value_upstream=90.0,
            value_prior_upstream=85.0,
        )
        == "revised_upstream"
    )


# ---------------------------------------------------------------------------
# Both-None edge case: prefer the upstream-perspective label.
# ---------------------------------------------------------------------------


def test_classify_both_none_is_missing_upstream():
    # Documented behaviour: missing-upstream wins when both sides are None.
    assert classify(None, None) == "missing_upstream"


# ---------------------------------------------------------------------------
# sample.py
# ---------------------------------------------------------------------------


def _artifact(rows: list[dict]) -> dict:
    return {"rows": rows}


def test_all_cells_preserves_artifact_order_and_carries_facet():
    art = _artifact(
        [
            {"entity_id": "S22", "time": "2024", "value": 1.0, "facet": "coal"},
            {"entity_id": "S22", "time": "2024", "value": 2.0, "facet": "hydro"},
            {"entity_id": "S29", "time": "2024", "value": 3.0},
        ]
    )
    cells = all_cells(art)
    assert cells == [
        Cell("S22", "2024", "coal"),
        Cell("S22", "2024", "hydro"),
        Cell("S29", "2024", None),
    ]


def test_stratified_sample_is_deterministic_and_capped_per_entity():
    art = _artifact(
        [{"entity_id": "S22", "time": str(2000 + i), "value": float(i)} for i in range(10)]
        + [{"entity_id": "S29", "time": "2024", "value": 99.0}]
    )
    first = stratified_sample(art, n_per_entity=3, seed=42)
    second = stratified_sample(art, n_per_entity=3, seed=42)
    assert first == second                               # determinism
    by_entity: dict[str, int] = {}
    for cell in first:
        by_entity[cell.entity_id] = by_entity.get(cell.entity_id, 0) + 1
    assert by_entity["S22"] == 3                         # cap honoured
    assert by_entity["S29"] == 1                         # below-cap entity emits all its cells


def test_stratified_sample_rejects_zero_n_per_entity():
    with pytest.raises(ValueError):
        stratified_sample(_artifact([]), n_per_entity=0)


# ---------------------------------------------------------------------------
# ledger.py
# ---------------------------------------------------------------------------


def _observation(**overrides) -> dict:
    base = ParityObservation(
        entity_id="S22",
        time="2024",
        value_ours=80.0,
        value_upstream=80.0,
        status="match",
        sampled_at="2026-05-17T10:00:00Z",
        upstream_url="https://icedapi.niti.gov.in/v1/example",
    ).to_jsonl_dict()
    base.update(overrides)
    return base


def test_ledger_path_composes_indicator_slug_under_repo_root(tmp_path: Path):
    p = ledger_path(tmp_path, "energy/state_atc_losses_pct")
    assert p == tmp_path / "datasets/parity/in/energy/state_atc_losses_pct.ledger.jsonl"


def test_ledger_append_creates_parents_and_writes_one_line_per_call(tmp_path: Path):
    p = ledger_path(tmp_path, "energy/example")
    append(p, _observation(sampled_at="2026-05-17T10:00:00Z"))
    append(p, _observation(sampled_at="2026-05-17T11:00:00Z"))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["status"] == "match" for line in lines)


def test_read_lines_yields_records_in_file_order(tmp_path: Path):
    p = ledger_path(tmp_path, "energy/example")
    append(p, _observation(time="2022"))
    append(p, _observation(time="2023"))
    append(p, _observation(time="2024"))
    times = [rec["time"] for rec in read_lines(p)]
    assert times == ["2022", "2023", "2024"]


def test_last_upstream_value_walks_newest_first(tmp_path: Path):
    p = ledger_path(tmp_path, "energy/example")
    append(p, _observation(value_upstream=80.0, sampled_at="2026-05-15T10:00:00Z"))
    append(p, _observation(value_upstream=85.0, sampled_at="2026-05-16T10:00:00Z"))
    append(p, _observation(value_upstream=90.0, sampled_at="2026-05-17T10:00:00Z"))
    assert last_upstream_value(p, "S22", "2024") == 90.0


def test_last_upstream_value_returns_none_when_cell_unseen(tmp_path: Path):
    p = ledger_path(tmp_path, "energy/example")
    append(p, _observation(entity_id="S22", time="2024"))
    assert last_upstream_value(p, "S29", "2024") is None


def test_last_upstream_value_returns_none_when_ledger_missing(tmp_path: Path):
    p = ledger_path(tmp_path, "energy/never_ran")
    assert last_upstream_value(p, "S22", "2024") is None


def test_last_upstream_value_respects_facet_when_provided(tmp_path: Path):
    p = ledger_path(tmp_path, "energy/example")
    append(p, _observation(facet="coal", value_upstream=80.0))
    append(p, _observation(facet="hydro", value_upstream=20.0))
    assert last_upstream_value(p, "S22", "2024", facet="coal") == 80.0
    assert last_upstream_value(p, "S22", "2024", facet="hydro") == 20.0
    assert last_upstream_value(p, "S22", "2024", facet=None) is None


# ---------------------------------------------------------------------------
# banner.py
# ---------------------------------------------------------------------------


def _obs(status: str, sampled_at: str, run_id: str | None = None) -> ParityObservation:
    return ParityObservation(
        entity_id="S22",
        time="2024",
        value_ours=80.0,
        value_upstream=80.0,
        status=status,                                # type: ignore[arg-type]
        sampled_at=sampled_at,
        upstream_url="https://icedapi.niti.gov.in/v1/example",
        run_id=run_id,
    )


def test_summarise_empty_returns_zero_sample_shape():
    out = summarise([])
    assert out == {
        "sample_size": 0,
        "divergent_count": 0,
        "status_counts": {
            "match": 0, "near_match": 0, "diverge": 0,
            "revised_upstream": 0, "missing_upstream": 0, "missing_ours": 0,
        },
        "last_run_id": None,
        "last_sampled_at": None,
    }


def test_summarise_counts_divergent_as_diverge_plus_three_missing_buckets():
    observations = [
        _obs("match",            "2026-05-17T10:00:00Z", "r1"),
        _obs("match",            "2026-05-17T10:00:01Z", "r1"),
        _obs("near_match",       "2026-05-17T10:00:02Z", "r1"),
        _obs("diverge",          "2026-05-17T10:00:03Z", "r1"),
        _obs("revised_upstream", "2026-05-17T10:00:04Z", "r1"),
        _obs("missing_upstream", "2026-05-17T10:00:05Z", "r1"),
        _obs("missing_ours",     "2026-05-17T10:00:06Z", "r1"),
    ]
    out = summarise(observations)
    assert out["sample_size"] == 7
    # diverge + revised_upstream + missing_upstream + missing_ours = 4.
    assert out["divergent_count"] == 4
    assert out["status_counts"]["match"] == 2
    assert out["status_counts"]["near_match"] == 1
    # near_match is NOT divergent — the citizen banner treats it as a pass.
    assert out["last_run_id"] == "r1"
    assert out["last_sampled_at"] == "2026-05-17T10:00:06Z"


def test_summarise_tracks_last_run_by_sampled_at_max():
    observations = [
        _obs("match", "2026-05-17T09:00:00Z", "r0"),
        _obs("match", "2026-05-18T09:00:00Z", "r1"),
        _obs("match", "2026-05-17T18:00:00Z", "r0"),  # out of order, older
    ]
    out = summarise(observations)
    assert out["last_run_id"] == "r1"
    assert out["last_sampled_at"] == "2026-05-18T09:00:00Z"


# ---------------------------------------------------------------------------
# probe.py: UpstreamFetcher is structural — a plain function satisfies it.
# ---------------------------------------------------------------------------


def test_upstream_fetcher_protocol_accepts_plain_function():
    from iced_parity import UpstreamFetcher

    def fetcher(indicator_id: str, cell: Cell) -> tuple[float | None, str]:
        return 42.0, f"https://example/{indicator_id}/{cell.entity_id}"

    # Structural typing — no isinstance check available; assignment alone
    # proves the type matches as far as the typing system cares.
    f: UpstreamFetcher = fetcher
    value, url = f("energy/example", Cell("S22", "2024"))
    assert value == 42.0
    assert url == "https://example/energy/example/S22"


# ---------------------------------------------------------------------------
# Round-trip: ParityObservation -> JSONL dict -> JSON -> back via read_lines
# ---------------------------------------------------------------------------


def test_parity_observation_jsonl_roundtrip_via_ledger(tmp_path: Path):
    obs = ParityObservation(
        entity_id="S22",
        time="2024",
        value_ours=80.0,
        value_upstream=90.0,
        status="revised_upstream",
        sampled_at="2026-05-17T10:00:00Z",
        upstream_url="https://icedapi.niti.gov.in/v1/example",
        facet="coal",
        value_prior_upstream=80.0,
        delta=-10.0,
        delta_pct=pytest.approx(-11.111, rel=1e-3),
        tolerance_used=DEFAULT_REL_TOLERANCE,
        run_id="r1",
    )
    p = ledger_path(tmp_path, "energy/example")
    # delta_pct is a pytest.approx; serialise the real value here.
    payload = obs.to_jsonl_dict()
    payload["delta_pct"] = -11.111
    append(p, payload)
    [restored] = list(read_lines(p))
    assert restored["facet"] == "coal"
    assert restored["status"] == "revised_upstream"
    assert restored["value_prior_upstream"] == 80.0
    assert restored["run_id"] == "r1"
