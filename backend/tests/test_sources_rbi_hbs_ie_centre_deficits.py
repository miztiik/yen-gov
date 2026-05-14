"""Adapter-level tests for ``yen_gov.sources.rbi_hbs_ie_centre_deficits``.

The parser is shared with ``rbi_appendix_deficits`` and is exercised
in :mod:`tests.test_sources_rbi_appendix_deficits`. Here we cover only
what is unique to this adapter: the shipped indicator set, the
cache-missing operator recipe, and the end-to-end write of four
schema-valid artifacts.

We build an in-memory workbook that mirrors HBS-IE Table 89's actual
shape (single sheet, row 1 blank-ish, row 2 title, row 3 unit, row 4
headers, row 5 column-index, rows 6+ year-data) so we can run the
adapter without depending on the gitignored cached XLSX.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from yen_gov.sources.rbi_hbs_ie_centre_deficits.ingest import (
    INDICATOR_META,
    RBIHBSIET89CacheMissing,
    SHIPPED_SPECS,
    ingest,
)


# Real Table 89 column labels (verified against
# T89_KeyDeficitIndicators_Centre_2025.xlsx via tools/rbi_hbs_ie_t89_inspect.py).
_HEADERS = (
    "Year",
    "Gross Fiscal Deficit",
    "Net Fiscal Deficit",
    "Gross Primary Deficit",
    "Net Primary Deficit",
    "Revenue Deficit",
    "Primary Revenue Deficit",
    "Drawdown of Cash Balances",
    "Net RBI Credit",
)


def _build_workbook(years: list[tuple[str, list[object]]]) -> bytes:
    """Build a T89-shaped workbook.

    ``years`` is ``[(year_label, [val_col2, val_col3, ...])]`` — one entry
    per fiscal year, each with 8 indicator values matching ``_HEADERS[1:]``.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "T_89"
    # Row 1 blank; row 2 title; row 3 unit; row 4 headers; row 5 column index.
    ws.append([None] * 10)
    ws.append([None, "TABLE 89 : KEY DEFICIT INDICATORS OF THE CENTRAL GOVERNMENT"])
    ws.append([None, "(₹ Crore)"])
    ws.append([None, *list(_HEADERS)])
    ws.append([None, *list(range(1, 10))])  # 1..9 column-index row
    for label, values in years:
        assert len(values) == 8, "expected 8 indicator values per year"
        ws.append([None, label, *values])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Shipped surface: 4 union_* indicators, distinct, in the catalogue.
# ---------------------------------------------------------------------------


def test_shipped_specs_cover_expected_union_indicator_set():
    expected = {
        "fiscal/union_gross_fiscal_deficit",
        "fiscal/union_revenue_deficit",
        "fiscal/union_primary_deficit",
        "fiscal/union_primary_revenue_deficit",
    }
    actual = {s.indicator_id for s in SHIPPED_SPECS}
    assert actual == expected


def test_shipped_specs_are_distinct():
    ids = [s.indicator_id for s in SHIPPED_SPECS]
    assert len(ids) == len(set(ids))


def test_every_spec_has_indicator_meta():
    for spec in SHIPPED_SPECS:
        assert spec.indicator_id in INDICATOR_META, (
            f"missing INDICATOR_META entry for {spec.indicator_id}"
        )


# ---------------------------------------------------------------------------
# Cache-missing surface: clear operator recipe.
# ---------------------------------------------------------------------------


def test_missing_cache_raises_with_operator_recipe(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("RBI_HBS_IE_T89_PATH", raising=False)
    schema_dir = Path(__file__).resolve().parents[2] / "datasets" / "schemas"
    with pytest.raises(RBIHBSIET89CacheMissing) as excinfo:
        ingest(repo_root=tmp_path, schema_dir=schema_dir)
    msg = str(excinfo.value)
    # Recipe must mention the listing page and the cache-relative path.
    assert "rbi.org.in" in msg
    assert "Handbook+of+Statistics" in msg
    assert ".runtime/raw/rbi/hbs_ie" in msg
    assert "$RBI_HBS_IE_T89_PATH" in msg


def test_env_override_pointing_at_nonexistent_path_raises(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("RBI_HBS_IE_T89_PATH", str(tmp_path / "nope.xlsx"))
    schema_dir = Path(__file__).resolve().parents[2] / "datasets" / "schemas"
    with pytest.raises(RBIHBSIET89CacheMissing):
        ingest(repo_root=tmp_path, schema_dir=schema_dir)


# ---------------------------------------------------------------------------
# End-to-end: ingest writes four schema-valid artifacts under a tmp root.
# ---------------------------------------------------------------------------


def test_ingest_writes_four_schema_valid_artifacts(
    tmp_path: Path, monkeypatch
):
    # Two-year minimal workbook covering all 8 indicator columns.
    # Indicator column order (per _HEADERS[1:]):
    #   GFD, NetFD, GrossPD, NetPD, RD, PRD, Drawdown, NetRBI
    workbook_bytes = _build_workbook(
        [
            ("2022-23", [1737755, 1648648, 809238, 747983, 1069926, 141409, -1622, 1404]),
            ("2023-24", [1654643, 1520194, 590771, 494583, 765216, -298656, 794, -263721]),
        ]
    )
    cache_path = tmp_path / "cached.xlsx"
    cache_path.write_bytes(workbook_bytes)
    monkeypatch.setenv("RBI_HBS_IE_T89_PATH", str(cache_path))

    schema_dir = Path(__file__).resolve().parents[2] / "datasets" / "schemas"
    result = ingest(repo_root=tmp_path, schema_dir=schema_dir)

    assert len(result.indicators) == 4
    out_dir = tmp_path / "datasets" / "indicators" / "in" / "fiscal"
    expected_files = {
        "union_gross_fiscal_deficit.json",
        "union_revenue_deficit.json",
        "union_primary_deficit.json",
        "union_primary_revenue_deficit.json",
    }
    assert {p.name for p in out_dir.iterdir()} == expected_files

    # Spot-check shape and value mapping on the gross fiscal deficit
    # artifact: (a) Centre-actor framing, (b) the 1737755 value lands
    # under 2022-23, (c) it's a fiscal_year time-grain national series.
    gfd = json.loads(
        (out_dir / "union_gross_fiscal_deficit.json").read_text(encoding="utf-8")
    )
    assert gfd["indicator"]["id"] == "fiscal/union_gross_fiscal_deficit"
    assert gfd["indicator"]["entity_kind"] == "country"
    assert gfd["indicator"]["time_grain"] == "fiscal_year"
    assert gfd["indicator"]["implementing_authority"] == "centre"
    assert gfd["indicator"]["funding_split"]["centre_pct"] == 100
    assert gfd["indicator"]["funding_split"]["state_pct"] == 0
    assert gfd["coverage"]["spatial"] == "India (Union Government)"
    assert gfd["coverage"]["admin_level"] == "national"
    assert gfd["sources"][0]["url"].startswith("https://www.rbi.org.in/")
    rows_by_time = {r["time"]: r["value"] for r in gfd["rows"]}
    assert rows_by_time["2022-04"] == 1737755
    assert rows_by_time["2023-04"] == 1654643

    # Verify the Gross-Primary → union_primary_deficit mapping is correct
    # (this is the column-label-match design choice documented in ingest.py).
    pd = json.loads(
        (out_dir / "union_primary_deficit.json").read_text(encoding="utf-8")
    )
    pd_rows = {r["time"]: r["value"] for r in pd["rows"]}
    assert pd_rows["2022-04"] == 809238  # Gross Primary Deficit value, NOT Net (747983)
    assert pd_rows["2023-04"] == 590771


def test_ingest_value_signs_preserved(tmp_path: Path, monkeypatch):
    """Negative values (revenue surpluses) must round-trip as negatives."""
    workbook_bytes = _build_workbook(
        [
            # 2023-24 has a primary revenue surplus (-298656 in real data).
            ("2023-24", [1654643, 1520194, 590771, 494583, 765216, -298656, 794, -263721]),
        ]
    )
    cache_path = tmp_path / "cached.xlsx"
    cache_path.write_bytes(workbook_bytes)
    monkeypatch.setenv("RBI_HBS_IE_T89_PATH", str(cache_path))

    schema_dir = Path(__file__).resolve().parents[2] / "datasets" / "schemas"
    ingest(repo_root=tmp_path, schema_dir=schema_dir)

    prd = json.loads(
        (
            tmp_path
            / "datasets"
            / "indicators"
            / "in"
            / "fiscal"
            / "union_primary_revenue_deficit.json"
        ).read_text(encoding="utf-8")
    )
    assert prd["rows"][0]["value"] == -298656
