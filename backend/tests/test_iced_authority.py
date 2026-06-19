"""Row 10 - ICED authority map + FK-lockstep migration + Tier-B oracle.

Covers:
* the decision map (``corrected_triple`` / ``reattributed_authorities`` /
  ``is_product_producer`` / ``DECISIONS`` completeness);
* the FK-lockstep migration on a ``tmp_path`` fixture (source.csv structured
  rewrite + datapoint / variables.csv / indicators.json token-replace);
* the Tier-B oracle - every producer is an organisation, every source_id
  resolves, the indicator_id set is identical before/after, and every
  reattributed producer is cited in docs/research/iced-authority-tracing.md.

Per the CLAUDE.md anti-pattern no test walks the real datasets corpus; the
migration + FK assertions use an injected ``tmp_path`` root. The one real file
read is the committed tracing doc (a single doc, not the corpus).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.iced_authority_map import (
    DECISIONS,
    ICED_ORG_PRODUCER,
    ICED_PRODUCT_PRODUCER,
    VIA_ICED_SUFFIX,
    apply_correction,
    corrected_triple,
    is_product_producer,
    reattributed_authorities,
)
from yen_gov.validate import tier_b_source_producer_not_a_product

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACING_DOC = REPO_ROOT / "docs" / "research" / "iced-authority-tracing.md"

# Representative ASCII-only ICED endpoints whose (producer, title, vintage)
# reproduce real DECISIONS source_ids. 3 reattributed + 2 kept.
_REATTR = [
    ("Capacity Metatable API (state-wise installed capacity, by fuel)", "2024-25",
     "https://iced.niti.gov.in/energy/electricity/generation/capacity/state-wise",
     "Central Electricity Authority"),
    ("Rooftop Solar Capacity (MW) State-wise API (per-state cumulative rooftop solar installed capacity)",
     "2024-25", "https://icedapi.niti.gov.in/energy/renewable/solar/rooftop/state",
     "Ministry of New and Renewable Energy"),
    ("Coal Consumption (Domestic) State-wise API (per-state fiscal-year coal consumption, by grade)",
     "2024-25", "https://icedapi.niti.gov.in/energy/fuel-sources/coal/consumption-domestic-state",
     "Ministry of Coal"),
]
_KEEP = [
    ("Renewable Energy Potential - Solar (state-wise) API", "2025-26", "https://iced.niti.gov.in"),
    ("Transmission Substation List API", "2024-25", "https://iced.niti.gov.in"),
]


def _iced_source_row(title: str, vintage: str, url: str) -> dict[str, str]:
    return {
        "source_id": derive_source_id(ICED_PRODUCT_PRODUCER, title, vintage),
        "producer": ICED_PRODUCT_PRODUCER,
        "title": title,
        "vintage": vintage,
        "url": url,
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _build_fixture(root: Path) -> dict[str, str]:
    """Build a minimal canonical store under ``root``; return indicator->old_sid."""
    src_rows: list[dict] = []
    indicator_to_sid: dict[str, str] = {}

    # ICED rows + a per-source datapoint CSV.
    catalogue: list[tuple[str, dict, str]] = []  # (indicator_id, source_row, file_class_dir)
    for i, (title, vintage, url, _authority) in enumerate(_REATTR):
        row = _iced_source_row(title, vintage, url)
        ind = f"reattr-indicator-{i}-mw"
        catalogue.append((ind, row, "geo"))
    for i, (title, vintage, url) in enumerate(_KEEP):
        row = _iced_source_row(title, vintage, url)
        ind = f"kept-indicator-{i}-mw"
        catalogue.append((ind, row, "geo"))

    # A non-ICED row (must stay byte-identical) + its datapoint.
    non_iced = {
        "source_id": "src-noniced000001",
        "producer": "Central Electricity Authority",
        "title": "Daily generation report",
        "vintage": "2024",
        "url": "https://cea.nic.in/",
    }
    catalogue_non = ("noniced-indicator-mw", non_iced, "geo")

    for ind, row, _dir in catalogue:
        src_rows.append(row)
        indicator_to_sid[ind] = row["source_id"]
    src_rows.append(non_iced)
    indicator_to_sid[catalogue_non[0]] = non_iced["source_id"]

    _write_csv(
        root / "datasets" / "data" / "entities" / "source.csv",
        ["source_id", "producer", "title", "vintage", "url"],
        src_rows,
    )

    # datapoints (entity_id, time, value, source_id)
    for ind, row, dirname in [*catalogue, catalogue_non]:
        sid = row["source_id"]
        dp_rows = [
            {"entity_id": "IN-S01", "time": "2020", "value": "10.5", "source_id": sid},
            {"entity_id": "IN-S02", "time": "2021", "value": "20.5", "source_id": sid},
        ]
        _write_csv(
            root / "datasets" / "data" / "datapoints" / dirname / f"{ind}.csv",
            ["entity_id", "time", "value", "source_id"],
            dp_rows,
        )

    # variables.csv carries source_id per indicator (a second FK surface).
    var_rows = [
        {"indicator_id": ind, "name": ind, "source_id": sid}
        for ind, sid in indicator_to_sid.items()
    ]
    _write_csv(
        root / "datasets" / "data" / "variables.csv",
        ["indicator_id", "name", "source_id"],
        var_rows,
    )

    # indicators.json carries source_id (a JSON FK surface).
    indicators = {
        "$schema": "../schemas/indicator-catalogue.schema.json",
        "$schema_version": "3.0",
        "indicators": [
            {"indicator_id": ind, "source_id": sid}
            for ind, sid in indicator_to_sid.items()
        ],
    }
    taxo = root / "datasets" / "taxonomy" / "indicators.json"
    taxo.parent.mkdir(parents=True, exist_ok=True)
    taxo.write_text(json.dumps(indicators, indent=2) + "\n", encoding="utf-8")

    return indicator_to_sid


def _read_source_rows(root: Path) -> list[dict]:
    src = root / "datasets" / "data" / "entities" / "source.csv"
    with src.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _datapoint_payloads(root: Path) -> dict[str, list[tuple[str, str, str]]]:
    """Map datapoint filename -> the (entity_id, time, value) triples (no source_id)."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    dp = root / "datasets" / "data" / "datapoints"
    for f in sorted(dp.rglob("*.csv")):
        with f.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        out[f.name] = [(r["entity_id"], r["time"], r["value"]) for r in rows]
    return out


# --------------------------------------------------------------------------
# Map unit tests
# --------------------------------------------------------------------------


def test_decisions_are_34_with_unique_source_ids():
    assert len(DECISIONS) == 34
    ids = [d.source_id for d in DECISIONS]
    assert len(set(ids)) == 34
    reattr = [d for d in DECISIONS if d.authority is not None]
    kept = [d for d in DECISIONS if d.authority is None]
    assert len(reattr) == 24
    assert len(kept) == 10
    # every decision cites in-repo evidence
    assert all(d.evidence.strip() for d in DECISIONS)


def test_corrected_triple_reattributes_passthrough():
    title, vintage, url, authority = _REATTR[0]  # Capacity Metatable -> CEA
    new_producer, new_title, new_vintage = corrected_triple(
        ICED_PRODUCT_PRODUCER, title, vintage
    )
    assert new_producer == authority
    assert new_title == title + VIA_ICED_SUFFIX
    assert new_vintage == vintage
    assert not is_product_producer(new_producer)


def test_corrected_triple_keeps_originated_as_org_label():
    title, vintage, _url = _KEEP[0]  # Solar potential -> keep
    new_producer, new_title, new_vintage = corrected_triple(
        ICED_PRODUCT_PRODUCER, title, vintage
    )
    assert new_producer == ICED_ORG_PRODUCER
    assert new_title == title  # title unchanged for kept rows
    assert new_vintage == vintage
    assert not is_product_producer(new_producer)


def test_corrected_triple_leaves_non_iced_untouched():
    out = corrected_triple("Central Electricity Authority", "Daily report", "2024")
    assert out == ("Central Electricity Authority", "Daily report", "2024")


def test_corrected_triple_unknown_iced_endpoint_raises():
    with pytest.raises(KeyError):
        corrected_triple(ICED_PRODUCT_PRODUCER, "A brand-new ICED endpoint", "2099-00")


def test_is_product_producer_flags_dashboard_not_org():
    assert is_product_producer(ICED_PRODUCT_PRODUCER)  # "...Dashboard"
    assert not is_product_producer(ICED_ORG_PRODUCER)  # "NITI Aayog ICED"
    assert not is_product_producer("Central Electricity Authority")
    assert not is_product_producer("Ministry of Statistics and Programme Implementation")


def test_reattributed_authorities_are_all_clean_organisations():
    auths = reattributed_authorities()
    assert auths  # non-empty
    assert all(not is_product_producer(a) for a in auths)
    # the 10 distinct authorities used by the 24 reattributed rows
    assert auths == {
        "Central Electricity Authority",
        "Central Pollution Control Board",
        "Ministry of Environment, Forest and Climate Change",
        "Ministry of Statistics and Programme Implementation",
        "Reserve Bank of India",
        "Ministry of Coal",
        "Petroleum Planning and Analysis Cell",
        "Ministry of Road Transport and Highways",
        "Power Finance Corporation",
        "Ministry of New and Renewable Energy",
    }


# --------------------------------------------------------------------------
# FK-lockstep migration on a tmp fixture
# --------------------------------------------------------------------------


def test_apply_correction_fk_lockstep(tmp_path):
    indicator_to_old = _build_fixture(tmp_path)

    before_payloads = _datapoint_payloads(tmp_path)
    before_indicator_ids = set(indicator_to_old)
    before_var_indicators = {
        r["indicator_id"]
        for r in csv.DictReader(
            (tmp_path / "datasets" / "data" / "variables.csv").open(encoding="utf-8", newline="")
        )
    }

    result = apply_correction(tmp_path)

    # 5 ICED rows migrated (3 reattributed + 2 kept); non-ICED untouched.
    assert len(result.id_remap) == 5
    assert len(result.reattributed) == 3
    assert len(result.kept) == 2
    assert result.changed

    src_rows = _read_source_rows(tmp_path)
    by_id = {r["source_id"]: r for r in src_rows}

    # producer-not-a-product holds for every row after migration.
    assert all(not is_product_producer(r["producer"]) for r in src_rows)
    assert not any(r["producer"] == ICED_PRODUCT_PRODUCER for r in src_rows)

    # non-ICED row is byte-stable (id + producer unchanged).
    assert "src-noniced000001" in by_id
    assert by_id["src-noniced000001"]["producer"] == "Central Electricity Authority"

    # every new source_id is the deterministic hash of its corrected triple.
    for old_id, new_id in result.id_remap.items():
        row = by_id[new_id]
        assert derive_source_id(row["producer"], row["title"], row["vintage"]) == new_id

    # indicator_id set identical before/after (only the FK column moved).
    after_payloads = _datapoint_payloads(tmp_path)
    assert set(after_payloads) == set(before_payloads)
    assert after_payloads == before_payloads  # entity_id/time/value untouched
    after_var_indicators = {
        r["indicator_id"]
        for r in csv.DictReader(
            (tmp_path / "datasets" / "data" / "variables.csv").open(encoding="utf-8", newline="")
        )
    }
    assert after_var_indicators == before_var_indicators
    assert before_indicator_ids == after_var_indicators

    # ZERO dangling source_id across datapoints + variables.csv + indicators.json.
    known_ids = set(by_id)
    for f in (tmp_path / "datasets" / "data" / "datapoints").rglob("*.csv"):
        for r in csv.DictReader(f.open(encoding="utf-8", newline="")):
            assert r["source_id"] in known_ids
    for r in csv.DictReader(
        (tmp_path / "datasets" / "data" / "variables.csv").open(encoding="utf-8", newline="")
    ):
        assert r["source_id"] in known_ids
    taxo = json.loads(
        (tmp_path / "datasets" / "taxonomy" / "indicators.json").read_text(encoding="utf-8")
    )
    for ind in taxo["indicators"]:
        assert ind["source_id"] in known_ids

    # The Tier-B guard is clean on the migrated corpus.
    assert tier_b_source_producer_not_a_product(tmp_path) == []


def test_apply_correction_is_idempotent(tmp_path):
    _build_fixture(tmp_path)
    first = apply_correction(tmp_path)
    assert first.changed
    second = apply_correction(tmp_path)
    assert not second.changed
    assert second.id_remap == {}
    assert tier_b_source_producer_not_a_product(tmp_path) == []


# --------------------------------------------------------------------------
# Tier-B guard: catches the pre-D2 (dashboard producer) + dangling FK states
# --------------------------------------------------------------------------


def test_tier_b_flags_pre_migration_product_producer(tmp_path):
    _build_fixture(tmp_path)
    failures = tier_b_source_producer_not_a_product(tmp_path)
    # the 5 ICED rows carry the dashboard product producer pre-migration.
    product = [f for f in failures if "product/dashboard" in f.message]
    assert len(product) == 5
    assert all(f.tier == "B" for f in failures)


def test_tier_b_flags_dangling_source_id(tmp_path):
    _build_fixture(tmp_path)
    apply_correction(tmp_path)  # clean, migrated state
    # Corrupt one datapoint row to reference a source_id absent from source.csv.
    dp = next((tmp_path / "datasets" / "data" / "datapoints").rglob("*.csv"))
    rows = list(csv.DictReader(dp.open(encoding="utf-8", newline="")))
    rows[0]["source_id"] = "src-dangling00001"
    _write_csv(dp, ["entity_id", "time", "value", "source_id"], rows)
    failures = tier_b_source_producer_not_a_product(tmp_path)
    assert any("dangling FK" in f.message for f in failures)
    assert any("src-dangling00001" in f.message for f in failures)


# --------------------------------------------------------------------------
# Oracle: every reattributed producer is cited in the tracing doc
# --------------------------------------------------------------------------


def test_every_reattributed_producer_cited_in_tracing_doc():
    assert TRACING_DOC.is_file(), f"missing tracing doc {TRACING_DOC}"
    doc = TRACING_DOC.read_text(encoding="utf-8")
    for authority in sorted(reattributed_authorities()):
        assert authority in doc, f"reattributed producer not cited in tracing doc: {authority!r}"
    # the kept-label is documented too
    assert ICED_ORG_PRODUCER in doc
