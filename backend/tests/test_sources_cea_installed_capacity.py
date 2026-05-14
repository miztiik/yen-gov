"""Pure-parser tests for the CEA Installed Capacity adapter.

Synthetic in-memory workbooks model the IC sheet layout documented
in ``tools/cea_recon.py`` output for ``Website-1.xlsx`` (CEA monthly
Executive Summary, March 2026 release):

  rows 1-7: title + sub-titles + (As on DD.MM.YYYY) date stamp +
            multi-row column header (Region|State, Ownership, Fuel-mode tree)
  rows 8-31: regional roll-ups (skipped — we work from the per-state tables)
  rows 68-: per-region per-state blocks. Each state block is 4 rows:
              col B = state name, col C = "State"     | values
              col B = None,        col C = "Private"  | values
              col B = None,        col C = "Central"  | values
              col B = None,        col C = "Sub-Total"| aggregated values

No real CEA bytes touch the test suite.
"""
from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from yen_gov.sources.cea_installed_capacity.parsers import (
    SHIPPED_COLUMNS,
    _coerce,
    _normalise_state_label,
    parse_workbook,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_workbook(sheets: dict[str, list[list[object]]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Header band carrying the snapshot date — must appear in the first ~12 rows
# of the IC sheet for ``_detect_snapshot_period`` to find it.
_HEADER_BAND = [
    [None, "ALL INDIA INSTALLED CAPACITY"],
    [None, "(As on 31.03.2026)"],
    [None, "(UTILITIES)"],
    [None],
    [None, "Region", "Ownership/ Sector", "Mode wise breakup"],
    [None, None, None, "Thermal", None, None, None, None, "Nuclear", "Renewable"],
    [None, None, None, "Coal", "Lignite", "Gas", "Diesel", "Total", None,
     "Hydro", "RES*(MNRE)", "Total"],
]


def _state_block(
    name: str,
    *,
    coal: float = 0,
    lignite: float = 0,
    gas: float = 0,
    diesel: float = 0,
    thermal: float | None = None,
    nuclear: float = 0,
    hydro: float = 0,
    res: float = 0,
    renewable_total: float | None = None,
    grand_total: float | None = None,
) -> list[list[object]]:
    """Build a 4-row state block (State / Private / Central / Sub-Total).

    The "State" tier carries the full requested totals; the Private and
    Central tiers are zeroed. The Sub-Total tier echoes the State tier so
    the parser's "use Sub-Total" rule produces the requested values.
    """
    therm = thermal if thermal is not None else (coal + lignite + gas + diesel)
    rene = renewable_total if renewable_total is not None else (hydro + res)
    grand = grand_total if grand_total is not None else (therm + nuclear + rene)
    state_row = [None, name, "State", coal, lignite, gas, diesel, therm,
                 nuclear, hydro, res, rene, grand]
    zero_row_priv = [None, None, "Private", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    zero_row_cent = [None, None, "Central", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    sub_total = [None, None, "Sub-Total", coal, lignite, gas, diesel, therm,
                 nuclear, hydro, res, rene, grand]
    return [state_row, zero_row_priv, zero_row_cent, sub_total]


# ---------------------------------------------------------------------------
# coerce helpers
# ---------------------------------------------------------------------------


def test_coerce_passes_through_numbers() -> None:
    assert _coerce(123) == 123.0
    assert _coerce(45.6) == 45.6
    assert _coerce(0) == 0.0


def test_coerce_strips_commas() -> None:
    assert _coerce("1,234.5") == 1234.5


def test_coerce_returns_none_for_null_tokens() -> None:
    assert _coerce(None) is None
    assert _coerce("") is None
    assert _coerce("—") is None
    assert _coerce("N.A.") is None
    assert _coerce("..") is None


def test_coerce_returns_none_for_unparseable_text() -> None:
    assert _coerce("see note 1") is None


# ---------------------------------------------------------------------------
# state-name normalisation
# ---------------------------------------------------------------------------


def test_normalise_state_label_canonical() -> None:
    assert _normalise_state_label("Tamil Nadu") == "S22"
    assert _normalise_state_label("Maharashtra") == "S13"
    assert _normalise_state_label("Delhi") == "U05"
    assert _normalise_state_label("Lakshadweep") == "U04"


def test_normalise_state_label_handles_whitespace_and_case() -> None:
    assert _normalise_state_label("  TAMIL  NADU  ") == "S22"
    assert _normalise_state_label("Andaman & Nicobar") == "U01"
    assert _normalise_state_label("andaman and nicobar") == "U01"


def test_normalise_state_label_drops_org_pseudo_states() -> None:
    # NLC and DVC look like state rows in the workbook (col B has the name)
    # but they're central PSUs whose capacity is not state-attributable.
    assert _normalise_state_label("NLC") is None
    assert _normalise_state_label("DVC") is None
    assert _normalise_state_label("Central - Unallocated") is None


def test_normalise_state_label_drops_region_totals() -> None:
    # Region total rows like "Total (Northern Region)" must not be mapped
    # to a state code.
    assert _normalise_state_label("Total (Northern Region)") is None
    assert _normalise_state_label("ALL INDIA") is None


def test_normalise_state_label_handles_jk_ladakh_bundle() -> None:
    # CEA bundles J&K and Ladakh into one row; we attribute to U08.
    assert _normalise_state_label("Jammu & Kashmir and Ladakh") == "U08"
    assert _normalise_state_label("Jammu and Kashmir and Ladakh") == "U08"


# ---------------------------------------------------------------------------
# parse_workbook end-to-end
# ---------------------------------------------------------------------------


def test_parse_workbook_emits_one_row_per_state_per_indicator() -> None:
    body = (
        _state_block("Tamil Nadu", coal=8000, gas=1000, nuclear=2000,
                     hydro=2000, res=20000)
        + _state_block("Maharashtra", coal=15000, gas=3000, hydro=3000,
                       res=15000)
        + _state_block("Delhi", gas=2000, res=500)
    )
    wb_bytes = _build_workbook({"IC": _HEADER_BAND + body})

    parsed = parse_workbook(wb_bytes)

    assert parsed.snapshot_period == "2026-03"
    assert parsed.state_count == 3

    total_rows = parsed.rows_by_indicator["energy/installed_capacity_total_mw"]
    by_entity = {r.entity_id: r.value for r in total_rows}
    assert by_entity == {
        "S22": pytest.approx(8000 + 1000 + 2000 + 2000 + 20000),
        "S13": pytest.approx(15000 + 3000 + 3000 + 15000),
        "U05": pytest.approx(2000 + 500),
    }

    coal_by_entity = {
        r.entity_id: r.value
        for r in parsed.rows_by_indicator["energy/installed_capacity_coal_mw"]
    }
    # Zero values ARE emitted (0 MW coal in Delhi is real information),
    # only None / unparseable cells get dropped.
    assert coal_by_entity == {"S22": 8000.0, "S13": 15000.0, "U05": 0.0}


def test_parse_workbook_skips_org_pseudo_states() -> None:
    """NLC, DVC, Central-Unallocated rows must NOT produce indicator rows."""
    body = (
        _state_block("Tamil Nadu", coal=8000)
        + _state_block("NLC", coal=999)  # should be dropped — central PSU
        + _state_block("DVC", coal=888)  # should be dropped — central corp
    )
    wb_bytes = _build_workbook({"IC": _HEADER_BAND + body})

    parsed = parse_workbook(wb_bytes)

    coal_rows = parsed.rows_by_indicator["energy/installed_capacity_coal_mw"]
    entities = {r.entity_id for r in coal_rows}
    # Only Tamil Nadu should resolve. NLC and DVC don't map to ECI codes.
    assert entities == {"S22"}
    assert parsed.state_count == 1


def test_parse_workbook_uses_sub_total_not_state_tier() -> None:
    """The Sub-Total row carries State+Private+Central. Verify we use it."""
    # Hand-build a block where the State tier and Sub-Total tier disagree,
    # to prove the parser reads Sub-Total.
    state_row = [None, "Tamil Nadu", "State", 100, 0, 0, 0, 100,
                 0, 0, 0, 0, 100]
    priv_row = [None, None, "Private", 200, 0, 0, 0, 200, 0, 0, 0, 0, 200]
    cent_row = [None, None, "Central", 50, 0, 0, 0, 50, 0, 0, 0, 0, 50]
    sub_row = [None, None, "Sub-Total", 350, 0, 0, 0, 350, 0, 0, 0, 0, 350]
    wb_bytes = _build_workbook({"IC": _HEADER_BAND + [state_row, priv_row, cent_row, sub_row]})

    parsed = parse_workbook(wb_bytes)

    coal_rows = parsed.rows_by_indicator["energy/installed_capacity_coal_mw"]
    assert len(coal_rows) == 1
    assert coal_rows[0].entity_id == "S22"
    # Must be Sub-Total (350), not the State-tier 100.
    assert coal_rows[0].value == 350.0


def test_parse_workbook_detects_snapshot_period_from_as_on() -> None:
    """Snapshot period comes from the (As on DD.MM.YYYY) header cell."""
    custom_header = [
        [None, "ALL INDIA INSTALLED CAPACITY"],
        [None, "(As on 30.06.2025)"],
        [None],
        [None, "Region", "Ownership/ Sector", "Mode wise breakup"],
        [None, None, None, "Thermal", None, None, None, None, "Nuclear",
         "Renewable"],
        [None, None, None, "Coal", "Lignite", "Gas", "Diesel", "Total", None,
         "Hydro", "RES*(MNRE)", "Total"],
    ]
    body = _state_block("Tamil Nadu", coal=8000)
    wb_bytes = _build_workbook({"IC": custom_header + body})

    parsed = parse_workbook(wb_bytes)

    assert parsed.snapshot_period == "2025-06"


def test_parse_workbook_raises_when_ic_sheet_missing() -> None:
    wb_bytes = _build_workbook({"Summary": [[None, "stuff"]]})
    with pytest.raises(ValueError, match="missing 'IC' sheet"):
        parse_workbook(wb_bytes)


def test_parse_workbook_raises_when_snapshot_undetectable() -> None:
    """Without an (As on …) cell the adapter must fail loudly, not invent a date."""
    no_date_header = [
        [None, "ALL INDIA INSTALLED CAPACITY"],
        [None, "(some other annotation)"],
        [None],
        [None, "Region", "Ownership/ Sector", "Mode wise breakup"],
        [None, None, None, "Thermal", None, None, None, None, "Nuclear",
         "Renewable"],
        [None, None, None, "Coal", "Lignite", "Gas", "Diesel", "Total", None,
         "Hydro", "RES*(MNRE)", "Total"],
    ]
    wb_bytes = _build_workbook({"IC": no_date_header + _state_block("Tamil Nadu", coal=8000)})
    with pytest.raises(ValueError, match="snapshot date"):
        parse_workbook(wb_bytes)


def test_parse_workbook_resets_state_context_between_blocks() -> None:
    """Region-total rows between state blocks must not leak the previous state.

    Without context reset, the next "Sub-Total" cell (e.g. the region's
    Grand Total) would falsely re-attribute capacity to the last state.
    """
    body = (
        _state_block("Tamil Nadu", coal=8000)
        + [
            # Region total block — non-state label in col B, NO new state name
            # carries through. The Sub-Total of THIS block must NOT add another
            # row to Tamil Nadu's coal indicator.
            [None, "Total (Southern Region)", "State", 99999, 0, 0, 0, 99999,
             0, 0, 0, 0, 99999],
            [None, None, "Private", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [None, None, "Central", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [None, None, "Sub-Total", 99999, 0, 0, 0, 99999, 0, 0, 0, 0, 99999],
        ]
        + _state_block("Karnataka", coal=4000)
    )
    wb_bytes = _build_workbook({"IC": _HEADER_BAND + body})

    parsed = parse_workbook(wb_bytes)

    coal_rows = parsed.rows_by_indicator["energy/installed_capacity_coal_mw"]
    entities = sorted((r.entity_id, r.value) for r in coal_rows)
    # Only Tamil Nadu (8000) and Karnataka (4000) — the 99999 region-total
    # Sub-Total must have been dropped.
    assert entities == [("S10", 4000.0), ("S22", 8000.0)]


def test_shipped_columns_are_distinct() -> None:
    """No two FuelColumn entries should share an indicator id or column index."""
    ids = [c.indicator_id for c in SHIPPED_COLUMNS]
    assert len(ids) == len(set(ids))
    # Column indexes can repeat in principle (e.g. a derived rollup), but
    # for the current shipped set they shouldn't — sanity check.
    cols = [c.column_index for c in SHIPPED_COLUMNS]
    assert len(cols) == len(set(cols))


def test_shipped_columns_cover_expected_fuels() -> None:
    """Lock in the indicator ids that the topic catalogue and frontend depend on."""
    ids = {c.indicator_id for c in SHIPPED_COLUMNS}
    assert ids == {
        "energy/installed_capacity_total_mw",
        "energy/installed_capacity_thermal_mw",
        "energy/installed_capacity_coal_mw",
        "energy/installed_capacity_gas_mw",
        "energy/installed_capacity_nuclear_mw",
        "energy/installed_capacity_hydro_mw",
        "energy/installed_capacity_renewable_mw",
    }
