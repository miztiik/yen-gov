"""Pure parser for the data.gov.in Pincode Directory CSV.

Why a SEPARATE parser module (vs the existing ``parsers.py``)?
--------------------------------------------------------------
``parsers.py`` is shaped for **indicator** CSVs — state-time-value
fact rows that flow into a ``datasets/indicators/.../<id>.json``
artifact. The Pincode Directory is **reference data** (one row per
Post Office, no time axis, no fact value) and lands as a flat CSV
under ``datasets/reference/in/pincodes/``. Same source (data.gov.in
OGD), different shape — keeping it in its own module avoids
polluting ``IndicatorSpec`` / ``SHIPPED_SPECS`` with an artificial
"reference" leg.

This module is I/O-free. Network + filesystem live in the upcoming
``ingest_pincode.py`` (Phase A.1.b, ships after the operator
captcha-fetches the CSV and drops it under
``.runtime/raw/datagovin/pincode_directory.csv``); this file converts
already-loaded CSV bytes into canonical rows.

See:
- Resource on data.gov.in:
  https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month
- ``ResourceMeta`` for ``"reference/pincode_directory"`` in :mod:`.urls`
- Plan-doc § A.1 in ``TODO/20260524-boundary-coverage-expansion-plan.md``
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PincodeDirectoryShapeError(RuntimeError):
    """The CSV header didn't match the expected Pincode Directory shape, or
    no usable rows survived parsing. Either the operator dropped the wrong
    file, or data.gov.in re-published the resource with a different schema
    (re-run :mod:`tools.datagovin_recon`)."""


# ---------------------------------------------------------------------------
# Canonical row + parsed bundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PincodeRow:
    """One Post Office row from the Pincode Directory CSV.

    The five fields map 1:1 to the upstream CSV's columns. We keep the
    upstream vocabulary verbatim (``circlename``, ``regionname``,
    ``divisionname``, ``officename``, ``pincode``) — pincode is
    *reference* data; downstream consumers join on the upstream names
    rather than an internal rename.
    """

    circlename: str
    regionname: str
    divisionname: str
    officename: str
    pincode: str  # always a 6-digit string; leading-zero-safe


@dataclass(frozen=True)
class ParsedPincodeDirectory:
    rows: tuple[PincodeRow, ...]
    record_count: int  # records read from the CSV (header excluded)
    invalid_pincode_count: int  # records dropped because pincode wasn't 6 digits


# ---------------------------------------------------------------------------
# Decoding helpers
# ---------------------------------------------------------------------------


# Canonical (lower-no-space) header keys we require the CSV to carry.
_EXPECTED_HEADERS: tuple[str, ...] = (
    "circlename",
    "regionname",
    "divisionname",
    "officename",
    "pincode",
)


def _decode_csv(raw: bytes) -> str:
    """Decode CSV bytes, tolerating UTF-8-BOM and Latin-1 fallback.

    Mirrors :func:`yen_gov.sources.datagovin_ogd.parsers._decode_csv` —
    kept private here so this module stays self-contained (no
    cross-module coupling on a 5-line helper).
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise PincodeDirectoryShapeError("CSV bytes are not decodable")


def _norm_header(h: str) -> str:
    """Collapse whitespace + lowercase for tolerant header matching.

    Upstream cosmetic variants ("Circle Name" vs "CircleName" vs
    "circlename") all collapse to ``"circlename"``.
    """
    return "".join(str(h).split()).lower()


def _is_valid_pincode(p: str) -> bool:
    """Indian pincodes are exactly 6 ASCII digits.

    We don't enforce the leading-digit-range (1..8) here — defence
    APO/FPO pincodes use otherwise-unallocated prefixes and we'd rather
    keep them than silently drop the post office. The 6-digit length is
    the hard constraint.
    """
    return len(p) == 6 and p.isdigit()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_pincode_directory(raw: bytes) -> ParsedPincodeDirectory:
    """Parse one Pincode Directory CSV download into canonical rows.

    Raises:
        PincodeDirectoryShapeError: required columns missing, or no rows
            survived parsing (all rows had non-conforming pincodes).
    """
    text = _decode_csv(raw)
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    if not fieldnames:
        raise PincodeDirectoryShapeError("CSV has no header row")

    header_lookup = {_norm_header(h): h for h in fieldnames}
    actual: dict[str, str] = {}
    missing: list[str] = []
    for expected in _EXPECTED_HEADERS:
        original = header_lookup.get(expected)
        if original is None:
            missing.append(expected)
        else:
            actual[expected] = original
    if missing:
        raise PincodeDirectoryShapeError(
            f"required columns missing: {missing!r}. "
            f"Available headers (normalised): {sorted(header_lookup)!r}"
        )

    rows: list[PincodeRow] = []
    record_count = 0
    invalid_pincode_count = 0
    for rec in reader:
        record_count += 1
        # Strip whitespace per-cell; preserve internal whitespace.
        circle = (rec.get(actual["circlename"]) or "").strip()
        region = (rec.get(actual["regionname"]) or "").strip()
        division = (rec.get(actual["divisionname"]) or "").strip()
        office = (rec.get(actual["officename"]) or "").strip()
        pin_raw = (rec.get(actual["pincode"]) or "").strip()
        # Tolerate CSVs that exported pincode as int (no leading-zero
        # risk for India, but float-as-pincode shows up as "560001.0"
        # from some Excel-mediated exports — strip the trailing ".0").
        if pin_raw.endswith(".0") and pin_raw[:-2].isdigit():
            pin_raw = pin_raw[:-2]
        if not _is_valid_pincode(pin_raw):
            invalid_pincode_count += 1
            continue
        rows.append(
            PincodeRow(
                circlename=circle,
                regionname=region,
                divisionname=division,
                officename=office,
                pincode=pin_raw,
            )
        )

    if not rows:
        raise PincodeDirectoryShapeError(
            f"CSV had {record_count} records but none survived parsing "
            f"({invalid_pincode_count} had non-6-digit pincodes)"
        )

    return ParsedPincodeDirectory(
        rows=tuple(rows),
        record_count=record_count,
        invalid_pincode_count=invalid_pincode_count,
    )
