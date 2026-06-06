"""Orchestrator for the RBI ingest of State Finances Statement workbooks.

Network + filesystem boundary. For each indicator spec passed in:
  1. Resolve a workbook URL via :mod:`.urls` (registry → env override
     → local cache fallback).
  2. Fetch the XLSX bytes.
  3. Run the pure parser (:mod:`.parsers`) for that single indicator.
  4. Write a ``datasets/indicators/in/<scope>/<leaf>.json`` artifact
     conforming to ``datasets/schemas/indicator.schema.json``, where
     ``<scope>`` is the first path segment of the indicator id
     (``fiscal``, ``health``, …). The orchestrator is therefore
     scope-agnostic — adding a non-fiscal indicator that lives in a
     Statement workbook of this shape only needs a new spec + meta +
     URL pin + CLI command, no parser/orchestrator edits.

See ``docs/architecture/backend/sources-rbi.md`` for the per-indicator
honesty fields each artifact materialises.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.core.http import Fetcher, FetchResult
from yen_gov.core.io import Source, write_artifact

from .parsers import (
    SHIPPED_SPECS,
    IndicatorSpec,
    ParsedIndicator,
    parse_workbook,
)
from .urls import LISTING_PAGE, RBI_AUTHORITY_URL, latest_url


RBI_SOURCE_NAME = "rbi"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RBISourceUnavailable(RuntimeError):
    """No usable workbook source for an indicator: registry empty, env
    unset, no local cache."""


# ---------------------------------------------------------------------------
# Per-indicator metadata (from sources-rbi.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorMeta:
    """Honesty fields for one indicator emitted from a Statement workbook.

    Originally fiscal-only; v1.5 schema added a Hans-governance layer
    that is opt-in per indicator. Existing fiscal entries do not set
    the new fields and therefore re-emit byte-identically (the payload
    builder only injects optional fields when they are set).
    """

    indicator_id: str
    title: str
    description: str
    direction: str            # higher_is_better | lower_is_better | neutral
    comparability: str
    attribution_geography: str
    icon: str
    funding_split_state_pct: int
    notes: str
    # Schema-driven rendering hints. Per the unit-not-in-id rule (see
    # docs/concepts/schema-is-the-design-system.md, section
    # "Indicator id encodes concept + normalisation, never the unit"):
    # the id is unit-agnostic; the unit lives in the indicator artifact.
    value_kind: str = "share"  # count | rate | share | currency | index | duration | raw
    unit: str = "%"
    series_breaks: tuple[dict[str, str], ...] = ()
    # v1.5 optional Hans-governance fields. Each is emitted only when
    # set, so existing fiscal entries (none set) re-emit unchanged.
    implementing_authority: str = "state"  # state | centre | joint | local_body | parastatal
    time_grain: str = "fiscal_year"
    chart_type: str | None = None  # choropleth | ranked | stacked-trend (None ⇒ schema default)
    denominator: Mapping[str, Any] | str | None = None
    revision_tier_by_period: tuple[Mapping[str, str], ...] = ()
    excludes: tuple[str, ...] = ()
    funding_split_source: str = "definition (own vs centrally-transferred)"


# Registry of shipped indicators' metadata. Currently one entry; new
# entries land alongside their spec in parsers.SHIPPED_SPECS and their
# URL pin in urls.KNOWN_URLS.
INDICATOR_META: dict[str, IndicatorMeta] = {
    "fiscal/outstanding_debt_pct_gsdp": IndicatorMeta(
        indicator_id="fiscal/outstanding_debt_pct_gsdp",
        title="Outstanding liabilities (% of GSDP)",
        description=(
            "Stock of state-government debt outstanding at the end of each "
            "fiscal year, expressed as a share of Gross State Domestic "
            "Product. Includes loans and public-account liabilities. "
            "Higher values mean a larger debt burden relative to the "
            "state's economic base. The FRBM Act 2003 imposed the first "
            "hard ceilings on state debt; pre-2003 series used different "
            "consolidation rules."
        ),
        direction="lower_is_better",
        comparability="comparable_across_states",
        attribution_geography="where_administered",
        icon="landmark",
        funding_split_state_pct=100,
        value_kind="share",
        unit="%",
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', Statement 20 "
            "(Total Outstanding Liabilities — As per cent of GSDP). The "
            "latest two periods are the State governments' Revised "
            "Estimates (RE) and Budget Estimates (BE); earlier periods are "
            "Accounts data. Telangana's series begins in 2014-15 (state "
            "formation) — pre-2014 cells are intentionally null."
        ),
    ),
    "fiscal/net_transfers_from_centre": IndicatorMeta(
        indicator_id="fiscal/net_transfers_from_centre",
        title="Net transfers from the Centre",
        description=(
            "Total devolution + grants flowing from the Central Government "
            "to each State / Union Territory in a fiscal year, net of "
            "items returned or adjusted (RBI's 'Net' column). Devolution "
            "is the state's share in central taxes (Finance Commission "
            "formula); grants include Finance Commission grants, "
            "centrally-sponsored scheme grants, and special-purpose "
            "transfers. This is the federal-transfer side of state "
            "fiscal capacity — a state's debt and deficit numbers are "
            "only honest read alongside how much the Centre is sending."
        ),
        direction="neutral",
        # ₹ Crore raw transfers are size-confounded: large states (UP, MH)
        # always lead. Honest comparability requires per-capita or
        # %-of-state-revenue normalisation, which arrives as sibling
        # indicators (per the unit-not-in-id rule, those are distinct ids).
        comparability="comparable_with_normalisation",
        attribution_geography="where_administered",
        icon="landmark",
        funding_split_state_pct=0,
        value_kind="currency",
        # The Indian convention: value column is in ₹ Crore (1 crore =
        # 10 million). The unit is metadata; the renderer's legend is
        # responsible for showing it. Per the unit-not-in-id rule.
        unit="INR (crore)",
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', "
            "Statement 17 (Devolution and Transfer of Resources from the "
            "Centre, Net column). Coverage is currently 3 fiscal years: "
            "2023-24 (Accounts), 2024-25 (Revised Estimates), "
            "2025-26 (Budget Estimates). Earlier years require scraping "
            "prior editions of the publication — tracked as a follow-up "
            "in the IA reset's ingest gate. Raw ₹ Crore values are not "
            "directly comparable across states of very different size; "
            "per-capita and %-of-state-revenue normalisations are "
            "planned as sibling indicators."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Canonical long-format CSV emission (B1.5.4)
# ---------------------------------------------------------------------------

# Per the sub-plan, all rbi_xlsx specs come from one publication
# (State Finances: A Study of Budgets); vintage per ADR-0042 is the
# publisher edition string. fk-validator stays dark on this hash until
# entities/source.csv lands (B2a), by design.
_CSV_SOURCE_PRODUCER = "Reserve Bank of India"
_CSV_SOURCE_TITLE = "State Finances: A Study of Budgets"
_CSV_SOURCE_VINTAGE = "2025-26"
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"

# Per-spec base variable_id (kebab-case `<measure>-<unit>-<facet>` per
# ADR-0044; no `__`, no grain prefix, per parent plan section 21.6 /
# 21.12). The pct-gsdp tail on outstanding_debt is the unit
# (share-of-GSDP), not a grain prefix; net_transfers carries an
# explicit inr-crore unit segment.
_INDICATOR_TO_BASE_VARIABLE_ID: dict[str, str] = {
    "fiscal/outstanding_debt_pct_gsdp": "outstanding-debt-pct-gsdp",
    "fiscal/net_transfers_from_centre": "net-transfers-from-centre-inr-crore",
}

# Parser-facet -> variable_id suffix. The writer does not yet support
# facet columns (csv_writer.py top-of-file note); per sub-plan point 7
# we split each facet-bearing series into per-facet variable_ids.
# Accounts data (facet=None) keeps the base id; RE and BE become
# explicit -revised-estimate / -budget-estimate variants.
_FACET_SUFFIX: dict[str | None, str] = {
    None: "",
    "RE": "-revised-estimate",
    "BE": "-budget-estimate",
}


def _slug_segment(text: str) -> str:
    """Kebab-case a free-text segment for use inside a variable_id.

    Mirrors the sibling rbi_appendix_deficits helper. Parent plan
    section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes.
    """
    out: list[str] = []
    prev_dash = True
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def _fy_start_year(time_str: str) -> int:
    """Lift the FY start year (int) from a parser period stamp.

    The parser emits ``YYYY-04`` (start of FY) for ``fy_span`` periods
    and ``YYYY-03`` (end of FY) for ``fy_end_year``. The canonical CSV
    file class declares ``time`` as integer; we lift the FY start year
    in both cases (for ``fy_end_year`` that is year-1, because the
    YYYY-03 stamp encodes end-of-FY which started in YYYY-1). This
    matches the sibling rbi_appendix_deficits helper's contract: the
    integer year column tracks the FY's start. Raises ``ValueError``
    on malformed input - fail fast at the boundary (CLAUDE.md
    anti-pattern: no silent coercion).
    """
    head, _, tail = time_str.partition("-")
    year = int(head)
    if tail == "03":
        return year - 1
    return year


def _variable_id_for(spec: IndicatorSpec, facet: str | None) -> str:
    """Compose the per-facet `variable_id` for one parser row."""
    base = _INDICATOR_TO_BASE_VARIABLE_ID[spec.indicator_id]
    suffix = _FACET_SUFFIX[facet]
    return f"{base}{suffix}"


def build_csv_variables(
    spec: IndicatorSpec,
    parsed: ParsedIndicator,
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build per-`variable_id` CSV row lists for one parsed indicator.

    Each row carries the four canonical columns declared on file class
    ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``. ``entity_id`` is the ECI state code lifted
    from the parser (parent plan section 22.4 #6: LGD/ECI key separation
    preserved; rbi_xlsx state rows key on ECI state codes). Null-valued
    rows (parser N.A. cells) are dropped. Rows sorted by
    (entity_id, time) per file-class contract.
    """
    by_variable: dict[str, list[dict[str, Any]]] = {}
    for r in parsed.rows:
        if r.value is None:
            continue
        variable_id = _variable_id_for(spec, r.facet)
        by_variable.setdefault(variable_id, []).append({
            "entity_id": r.entity_id,
            "time": _fy_start_year(r.time),
            "value": r.value,
            "source_id": source_id,
        })
    for variable_id, rows in by_variable.items():
        rows.sort(key=lambda row: (row["entity_id"], row["time"]))
    return by_variable


def emit_csv_variables(
    *, repo_root: Path, by_variable: dict[str, list[dict[str, Any]]]
) -> tuple[Path, ...]:
    """Write each `variable_id` to `datasets/data/datapoints/geo/<id>.csv`."""
    written: list[Path] = []
    out_dir = repo_root / _CSV_OUT_REL_DIR
    for variable_id, rows in sorted(by_variable.items()):
        path = write_csv(
            path=out_dir / f"{variable_id}.csv",
            file_class=_CSV_FILE_CLASS,
            rows=rows,
        )
        written.append(path)
    return tuple(written)

