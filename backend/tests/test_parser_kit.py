"""Unit tests for the shared ICED parser kit.

Three callers use this kit today (`iced_power`, `iced_socio`, and the
reference for `iced_state_wise`); these tests pin its public contract so
future fourth/fifth adapters can trust it without re-deriving edge cases.
"""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common import parser_kit


# ---------------------------------------------------------------------------
# fy_to_period
# ---------------------------------------------------------------------------


class TestFyToPeriod:
    def test_fy_label_to_fiscal_year(self) -> None:
        assert parser_kit.fy_to_period("2017-18") == "2017-04"

    def test_fy_label_to_year_grain_collapses_to_start_year(self) -> None:
        assert parser_kit.fy_to_period("2017-18", time_grain="year") == "2017"

    def test_bare_year_string_to_fiscal_year(self) -> None:
        assert parser_kit.fy_to_period("2017") == "2017-04"

    def test_bare_year_string_to_year_grain(self) -> None:
        assert parser_kit.fy_to_period("2017", time_grain="year") == "2017"

    def test_int_to_fiscal_year(self) -> None:
        assert parser_kit.fy_to_period(2017) == "2017-04"

    def test_int_to_year_grain(self) -> None:
        assert parser_kit.fy_to_period(2017, time_grain="year") == "2017"

    def test_whitespace_trimmed(self) -> None:
        assert parser_kit.fy_to_period("  2017-18  ") == "2017-04"

    @pytest.mark.parametrize("garbage", ["", "abcd", "2017-2018", "20-21", None, 2.5, [], {}])
    def test_unparseable_returns_none(self, garbage: object) -> None:
        assert parser_kit.fy_to_period(garbage) is None

    def test_bool_is_not_int(self) -> None:
        # bool ⊂ int in Python; the kit must reject it explicitly.
        assert parser_kit.fy_to_period(True) is None
        assert parser_kit.fy_to_period(False) is None


# ---------------------------------------------------------------------------
# row
# ---------------------------------------------------------------------------


class TestRow:
    def test_minimal_row(self) -> None:
        r = parser_kit.row(entity_id="S22", time="2017-04", value=42.0)
        assert r == {"entity_id": "S22", "time": "2017-04", "value": 42.0}

    def test_with_facet(self) -> None:
        r = parser_kit.row(entity_id="S22", time="2017-04", value=1.0, facet="solar")
        assert r == {
            "entity_id": "S22", "time": "2017-04", "value": 1.0, "facet": "solar",
        }

    def test_optional_fields_omitted_when_none(self) -> None:
        r = parser_kit.row(entity_id="S22", time="2017-04", value=1.0)
        assert "facet" not in r
        assert "vintage" not in r
        assert "period_label" not in r

    def test_value_none_preserved(self) -> None:
        # A None value is a legal "explicit gap" signal — schema permits it.
        r = parser_kit.row(entity_id="S22", time="2017-04", value=None)
        assert r["value"] is None

    def test_key_order_is_canonical(self) -> None:
        r = parser_kit.row(
            entity_id="S22", time="2017-04", value=1.0,
            facet="solar", vintage="actual", period_label="FY 2017-18",
        )
        assert list(r) == ["entity_id", "time", "value", "facet", "vintage", "period_label"]


# ---------------------------------------------------------------------------
# dedup_sort
# ---------------------------------------------------------------------------


class TestDedupSort:
    def test_last_write_wins_no_facet(self) -> None:
        rows = [
            {"entity_id": "S22", "time": "2017-04", "value": 1.0},
            {"entity_id": "S22", "time": "2017-04", "value": 9.0},  # later wins
        ]
        out = parser_kit.dedup_sort(rows)
        assert out == [{"entity_id": "S22", "time": "2017-04", "value": 9.0}]

    def test_last_write_wins_with_facet(self) -> None:
        rows = [
            {"entity_id": "S22", "time": "2017-04", "value": 1.0, "facet": "solar"},
            {"entity_id": "S22", "time": "2017-04", "value": 2.0, "facet": "wind"},
            {"entity_id": "S22", "time": "2017-04", "value": 9.0, "facet": "solar"},
        ]
        out = parser_kit.dedup_sort(rows)
        assert out == [
            {"entity_id": "S22", "time": "2017-04", "value": 9.0, "facet": "solar"},
            {"entity_id": "S22", "time": "2017-04", "value": 2.0, "facet": "wind"},
        ]

    def test_sorted_output(self) -> None:
        rows = [
            {"entity_id": "S22", "time": "2018-04", "value": 1.0, "facet": "wind"},
            {"entity_id": "S22", "time": "2018-04", "value": 1.0, "facet": "solar"},
            {"entity_id": "S01", "time": "2017-04", "value": 1.0},
        ]
        out = parser_kit.dedup_sort(rows)
        keys = [(r["entity_id"], r["time"], r.get("facet") or "") for r in out]
        assert keys == sorted(keys)

    def test_empty(self) -> None:
        assert parser_kit.dedup_sort([]) == []

    def test_facet_none_and_missing_treated_equivalently(self) -> None:
        rows = [
            {"entity_id": "S22", "time": "2017-04", "value": 1.0, "facet": None},
            {"entity_id": "S22", "time": "2017-04", "value": 9.0},  # no facet key
        ]
        out = parser_kit.dedup_sort(rows)
        # Same (entity, time, facet="") key → last one wins.
        assert len(out) == 1
        assert out[0]["value"] == 9.0


# ---------------------------------------------------------------------------
# unwrap_data
# ---------------------------------------------------------------------------


class TestUnwrapData:
    def test_envelope_unwrapped(self) -> None:
        assert parser_kit.unwrap_data({"status": "ok", "data": [1, 2, 3]}) == [1, 2, 3]

    def test_list_passthrough(self) -> None:
        assert parser_kit.unwrap_data([1, 2, 3]) == [1, 2, 3]

    def test_dict_without_data_key_passthrough(self) -> None:
        # ICED v1 endpoints sometimes ship payload directly under top-level keys
        # other than "data" — kit must NOT unwrap when "data" is absent.
        assert parser_kit.unwrap_data({"category": [], "seriesData": []}) == {
            "category": [], "seriesData": [],
        }

    def test_data_key_none_still_unwraps_to_none(self) -> None:
        # If the envelope literally carries data=None, that IS the payload.
        assert parser_kit.unwrap_data({"status": "ok", "data": None}) is None
