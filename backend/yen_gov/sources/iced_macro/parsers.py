"""Pure parsers for the iced_macro adapter (national/state macro indicators
from the ICED economy-demography endpoint family).

Each parser is pure: takes the already-decrypted JSON dict and returns
a list of canonical indicator rows.
"""
from __future__ import annotations

from typing import Any

from yen_gov.sources.iced_common import (
    ENTITY_MAP,
    ICEDShapeError,
    coerce_numeric,
    fy_to_period,
)


def _data_list(decrypted: Any, endpoint_label: str) -> list[Any]:
    if not isinstance(decrypted, dict):
        raise ICEDShapeError(
            f"expected {endpoint_label} to return a dict, got {type(decrypted).__name__}"
        )
    data = decrypted.get("data")
    if not isinstance(data, list):
        raise ICEDShapeError(
            f"expected {endpoint_label} to carry a 'data' list, got {type(data).__name__}"
        )
    return data


def _dedup_sort(rows: dict[tuple[str, str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows.values(), key=lambda r: (r["entity_id"], r["time"], r.get("facet", "")))


# ---------------------------------------------------------------------------
# parse_gdp_trend  (split into national + state results)
# ---------------------------------------------------------------------------


class GDPParseResult:
    __slots__ = ("national", "state", "skipped_unmapped")

    def __init__(self, national, state, skipped_unmapped):
        self.national = national
        self.state = state
        self.skipped_unmapped = skipped_unmapped


def parse_gdp_trend(decrypted: Any) -> GDPParseResult:
    """Split GDP-trend rows into national-only and state-only series.

    Filters for ``priceType == "gross"`` (the headline number; the
    ``export`` and ``import`` price-type rows are different deflator
    bases not used in our top-line view). Facet is ``priceCategory``
    (``"current"`` vs ``"constant"``).
    """
    data = _data_list(decrypted, "GDP-trend")

    national: dict[tuple[str, str, str], dict[str, Any]] = {}
    state: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = 0

    for raw in data:
        if not isinstance(raw, dict):
            continue
        trend = (raw.get("trendType") or "").strip().lower()
        # National rows carry priceType ∈ {gross, export, import}; only
        # 'gross' is the GDP headline. State rows omit priceType entirely
        # (single series per state-year-category) so don't filter them out.
        if trend == "national":
            ptype = (raw.get("priceType") or "").lower()
            if ptype != "gross":
                continue
        category = (raw.get("priceCategory") or "").strip().lower()
        if category not in {"current", "constant"}:
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("price"))
        if value is None:
            continue

        if trend == "national":
            key = ("IN", period, category)
            national[key] = {
                "entity_id": "IN", "time": period, "value": value, "facet": category,
            }
        elif trend == "state":
            label = (raw.get("state") or "").strip()
            entity_id = ENTITY_MAP.get(label)
            if not entity_id:
                skipped += 1
                continue
            key = (entity_id, period, category)
            state[key] = {
                "entity_id": entity_id, "time": period, "value": value, "facet": category,
            }

    return GDPParseResult(
        national=_dedup_sort(national),
        state=_dedup_sort(state),
        skipped_unmapped=skipped,
    )


# ---------------------------------------------------------------------------
# parse_industrial_production
# ---------------------------------------------------------------------------


def parse_industrial_production(decrypted: Any) -> list[dict[str, Any]]:
    """National IIP, faceted by ICED's category labels (sectoral + use-based)."""
    data = _data_list(decrypted, "industrial-production")

    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in data:
        if not isinstance(raw, dict):
            continue
        category = (raw.get("category") or "").strip()
        if not category:
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("index"))
        if value is None:
            continue
        key = ("IN", period, category)
        rows[key] = {
            "entity_id": "IN", "time": period, "value": value, "facet": category,
        }
    return _dedup_sort(rows)


# ---------------------------------------------------------------------------
# parse_population_by_residence
# ---------------------------------------------------------------------------


def parse_population_by_residence(decrypted: Any) -> tuple[list[dict[str, Any]], int]:
    """Census population per state, faceted by Rural/Urban."""
    data = _data_list(decrypted, "demographyActual")

    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = 0
    for raw in data:
        if not isinstance(raw, dict):
            continue
        category = (raw.get("category") or "").strip()
        if category not in {"Rural", "Urban"}:
            continue
        # Time is calendar census year (1961, 1971, ..., 2011)
        year = raw.get("year")
        try:
            time_str = str(int(year))
        except (TypeError, ValueError):
            continue
        value = coerce_numeric(raw.get("population"))
        if value is None:
            continue
        label = (raw.get("state") or "").strip()
        if label.lower() == "all india":
            entity_id = "IN"
        else:
            entity_id = ENTITY_MAP.get(label)
        if not entity_id:
            skipped += 1
            continue
        key = (entity_id, time_str, category)
        rows[key] = {
            "entity_id": entity_id, "time": time_str, "value": value,
            "facet": category, "vintage": "actual",
        }
    return _dedup_sort(rows), skipped


# ---------------------------------------------------------------------------
# parse_gva_trend  (national, constant-price by industry)
# ---------------------------------------------------------------------------


def parse_gva_trend_national_constant(decrypted: Any) -> list[dict[str, Any]]:
    """National GVA at constant 2011-12 prices, faceted by industry.

    The state series (14k rows) crosses industries with sector groups
    (Primary/Secondary/Tertiary) and a separate per-state aggregate row
    — too dense for one artifact. We ship only the national constant-
    price series here (10 industries × 14 fiscal years).
    """
    data = _data_list(decrypted, "gva-trend")

    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in data:
        if not isinstance(raw, dict):
            continue
        if (raw.get("trendType") or "").strip().lower() != "national":
            continue
        if (raw.get("priceType") or "").strip().lower() != "constant":
            continue
        industry = (raw.get("industryItem") or "").strip()
        if not industry:
            continue
        try:
            period = fy_to_period(str(raw.get("year") or ""))
        except ValueError:
            continue
        value = coerce_numeric(raw.get("price"))
        if value is None:
            continue
        key = ("IN", period, industry)
        rows[key] = {
            "entity_id": "IN", "time": period, "value": value, "facet": industry,
        }
    return _dedup_sort(rows)


# ---------------------------------------------------------------------------
# parse_balance_trendline  (national external-sector balances)
# ---------------------------------------------------------------------------


def _normalise_bop_year(raw_year: str) -> tuple[str, str | None] | None:
    """Return (period, vintage) for a BoP year string, or None to skip.

    Upstream year shapes:
        "2010-11"                        → ("2010-04", None)
        "2021-22 "                       → ("2021-04", None)            (trailing space)
        "2023-24 (Preliminary)"          → ("2023-04", "preliminary")
        "2024-25  (Apr-Sep) (Preliminary)" → None  (partial-year — skip)
    """
    if not isinstance(raw_year, str):
        return None
    cleaned = raw_year.strip()
    if "(Apr-" in cleaned or "(Jul-" in cleaned or "(Oct-" in cleaned or "(Jan-" in cleaned:
        return None
    vintage: str | None = None
    if "(Preliminary)" in cleaned:
        vintage = "preliminary"
        cleaned = cleaned.replace("(Preliminary)", "").strip()
    try:
        period = fy_to_period(cleaned)
    except ValueError:
        return None
    return period, vintage


def parse_balance_trendline(decrypted: Any) -> list[dict[str, Any]]:
    """India's external-balance items (Trade Balance, Current Account, etc).

    All values are national (no state breakdown). Vintage marks the
    Preliminary full-year rows so the renderer can flag them; partial-
    year (Apr-Sep) rows are dropped to keep the series annual-comparable.
    """
    data = _data_list(decrypted, "balance-trendline")

    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in data:
        if not isinstance(raw, dict):
            continue
        item = (raw.get("item") or "").strip()
        if not item:
            continue
        normalised = _normalise_bop_year(str(raw.get("year") or ""))
        if normalised is None:
            continue
        period, vintage = normalised
        value = coerce_numeric(raw.get("price"))
        if value is None:
            continue
        key = ("IN", period, item)
        row: dict[str, Any] = {
            "entity_id": "IN", "time": period, "value": value, "facet": item,
        }
        if vintage:
            row["vintage"] = vintage
        rows[key] = row
    return _dedup_sort(rows)
