"""Pure parser for data.gov.in OGD CSV downloads.

Why CSV (not the JSON API)?
---------------------------
The OGD JSON API requires an api-key. The documented public/sample
key caps records at ~10 per request and rate-limits aggressively
(429 after a handful of pages). Production ingest via the API would
need a registered key per https://api.data.gov.in/signup which
involves a phone-number SMS round-trip we cannot automate.

Conversely, every OGD resource page exposes a direct **CSV download**
behind a one-time captcha-gated form. An operator solves the captcha
once, drops the file under ``.runtime/raw/datagovin/<leaf>.csv``, and
every subsequent ingest re-runs from that cached file. The artifact's
``sources[]`` cites the resource page URL (the canonical attribution),
not the API.

This module is I/O-free. Network + filesystem live in ``ingest.py``;
this file converts already-loaded CSV bytes into canonical rows.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Iterable

# Reuse RBI's state-name normalisation: same canonical state names,
# perfect-superset lookup table.
from yen_gov.sources.rbi_xlsx.parsers import normalise_state_label


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DataGovInCsvShapeError(RuntimeError):
    """The CSV header didn't match the indicator spec, or there were no rows.
    Either the operator dropped the wrong file, or data.gov.in re-published
    the resource with a different schema (re-run recon)."""


# ---------------------------------------------------------------------------
# Indicator spec + parsed rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorSpec:
    """Declarative recipe for one CSV → indicator extraction.

    Fields:
        indicator_id: canonical id (e.g. ``fiscal/centre_transfers_gross``).
        state_column: header text of the column carrying the state name.
        time_column: header text of the column carrying the fiscal year
            label (e.g. "Financial Year"; values look like ``"2016-17"``).
        value_columns: tuple of header texts whose numeric values are
            **summed** to produce ``value``. For centre transfers we sum
            "Share in Central Taxes" + "Grants-in-Aid".
        period_kind: ``fy_span`` (start-of-FY, for flow values) or
            ``fy_end_year`` (end-of-FY, for stock values).
    """

    indicator_id: str
    state_column: str
    time_column: str
    value_columns: tuple[str, ...]
    period_kind: str  # "fy_span" | "fy_end_year"


SHIPPED_SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        indicator_id="fiscal/centre_transfers_gross",
        state_column="States",
        time_column="Financial Year",
        # Devolution (Col. 4) + Grants-in-Aid (Col. 5).
        value_columns=(
            "Revenue Receipts - Share In Central Taxes - Col. (4)",
            "Revenue Receipts - Grants-In-Aid - Col. (5)",
        ),
        period_kind="fy_span",
    ),
)


@dataclass(frozen=True)
class ParsedRow:
    entity_id: str
    time: str
    value: float


@dataclass(frozen=True)
class ParsedIndicator:
    rows: tuple[ParsedRow, ...]
    unmatched_states: tuple[str, ...]
    record_count: int


# ---------------------------------------------------------------------------
# Period normalisation
# ---------------------------------------------------------------------------


def _fy_to_period(fy: str, kind: str) -> str | None:
    """Convert ``"2016-17"`` to a canonical period string.

    ``fy_span``     → start-of-FY (``2016-04``). Flow values.
    ``fy_end_year`` → end-of-FY  (``2017-04``). Stock values.
    """
    if not fy or "-" not in fy:
        return None
    parts = fy.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or not parts[0].isdigit():
        return None
    start_year = int(parts[0])
    if kind == "fy_span":
        return f"{start_year:04d}-04"
    if kind == "fy_end_year":
        return f"{start_year + 1:04d}-04"
    raise ValueError(f"unknown period_kind: {kind!r}")


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------


def _decode_csv(raw: bytes) -> str:
    """Decode CSV bytes, tolerating UTF-8-BOM and Latin-1 fallback."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DataGovInCsvShapeError("CSV bytes are not decodable")


def _norm_header(h: str) -> str:
    """Collapse whitespace + lowercase for tolerant header matching."""
    return " ".join(str(h).split()).lower()


def parse_csv(raw: bytes, spec: IndicatorSpec) -> ParsedIndicator:
    """Parse one OGD CSV download into canonical rows.

    Raises:
        DataGovInCsvShapeError: required columns missing or no rows survived.
    """
    text = _decode_csv(raw)
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    if not fieldnames:
        raise DataGovInCsvShapeError("CSV has no header row")

    header_lookup = {_norm_header(h): h for h in fieldnames}
    state_col = header_lookup.get(_norm_header(spec.state_column))
    time_col = header_lookup.get(_norm_header(spec.time_column))
    value_cols: list[str] = []
    for vc in spec.value_columns:
        actual = header_lookup.get(_norm_header(vc))
        if actual is None:
            raise DataGovInCsvShapeError(
                f"value column not found in CSV: {vc!r}. "
                f"Available headers: {fieldnames}"
            )
        value_cols.append(actual)
    if state_col is None or time_col is None:
        raise DataGovInCsvShapeError(
            f"required columns missing. state_col={state_col!r} "
            f"time_col={time_col!r}. Available headers: {fieldnames}"
        )

    rows: list[ParsedRow] = []
    unmatched: list[str] = []
    record_count = 0
    for rec in reader:
        record_count += 1
        row = _parse_record(rec, state_col, time_col, value_cols, spec.period_kind)
        if row is None:
            raw_label = rec.get(state_col)
            if raw_label and isinstance(raw_label, str):
                unmatched.append(raw_label)
            continue
        rows.append(row)

    if not rows:
        raise DataGovInCsvShapeError(
            f"CSV had {record_count} records but none survived parsing"
        )

    return ParsedIndicator(
        rows=tuple(rows),
        unmatched_states=tuple(sorted(set(unmatched))),
        record_count=record_count,
    )


def _parse_record(
    rec: dict[str, str | None],
    state_col: str,
    time_col: str,
    value_cols: Iterable[str],
    period_kind: str,
) -> ParsedRow | None:
    raw_state = rec.get(state_col)
    raw_fy = rec.get(time_col)
    if not isinstance(raw_state, str) or not isinstance(raw_fy, str):
        return None
    eci = normalise_state_label(raw_state)
    if eci is None:
        return None
    time = _fy_to_period(raw_fy.strip(), period_kind)
    if time is None:
        return None

    total = 0.0
    saw_value = False
    for vc in value_cols:
        v = rec.get(vc)
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            continue
        try:
            total += float(str(v).replace(",", "").strip())
            saw_value = True
        except (TypeError, ValueError):
            continue
    if not saw_value:
        return None
    return ParsedRow(entity_id=eci, time=time, value=round(total, 4))
