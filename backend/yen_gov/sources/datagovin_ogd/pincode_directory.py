"""Pure parser for the data.gov.in Pincode Directory CSV.

Why a SEPARATE parser module (vs the existing ``parsers.py``)?
--------------------------------------------------------------
``parsers.py`` is shaped for **indicator** CSVs — state-time-value
fact rows that flow into a ``datasets/indicators/.../<id>.json``
artifact. The Pincode Directory is **reference data** (one row per
Post Office, no time axis, no fact value) and lands as a flat CSV
at ``datasets/data/entities/pincode.csv`` (G8 2026-06-08: was
``datasets/reference/in/pincodes/pincode-directory.parquet``; the
reshape lifted reference entity data into ``data/entities/`` per
plan-doc section 9 + flipped Parquet -> CSV per section 21.2). Same
source (data.gov.in OGD), different shape — keeping it in its own
module avoids polluting ``IndicatorSpec`` / ``SHIPPED_SPECS`` with an
artificial "reference" leg.

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

    Five fields are REQUIRED (the original OGD portal-page schema):
    ``circlename``, ``regionname``, ``divisionname``, ``officename``,
    ``pincode``. The 2025 corpus carries six additional OPTIONAL
    columns the portal page didn't originally advertise:
    ``officetype`` (BO/SO/HO/GPO), ``delivery`` ("Delivery" /
    "Non-Delivery"), ``district``, ``statename`` (uppercase), plus
    point geometry (``latitude``, ``longitude``).

    Empty / missing / ``"NA"`` upstream values collapse to ``None``
    for the optional string fields and stay non-empty strings only
    when upstream actually published a value. lat/long parse as
    ``float`` when they sit inside the WGS84 envelope
    (lat ∈ [-90, 90], lon ∈ [-180, 180]) and ``None`` otherwise —
    out-of-envelope values bump :class:`ParsedPincodeDirectory`'s
    ``invalid_coordinate_count`` so an upstream-corruption spike is
    visible without losing the post office row itself.

    We keep the upstream vocabulary verbatim — pincode is *reference*
    data; downstream consumers join on the upstream names rather than
    an internal rename.
    """

    circlename: str
    regionname: str
    divisionname: str
    officename: str
    pincode: str  # always a 6-digit string; leading-zero-safe
    officetype: str | None = None
    delivery: str | None = None
    district: str | None = None
    statename: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class ParsedPincodeDirectory:
    rows: tuple[PincodeRow, ...]
    record_count: int  # records read from the CSV (header excluded)
    invalid_pincode_count: int  # records dropped because pincode wasn't 6 digits
    invalid_coordinate_count: int = 0  # rows kept but with lat/long out of WGS84 envelope


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

# Optional headers — populated when present; absent ones simply yield
# ``None`` on the corresponding :class:`PincodeRow` field. The 2025
# corpus ships all six; earlier corpora may not, and the parser stays
# back-compat so a future schema-shrinkage doesn't break the build.
_OPTIONAL_HEADERS: tuple[str, ...] = (
    "officetype",
    "delivery",
    "district",
    "statename",
    "latitude",
    "longitude",
)

# Upstream's sentinel for "this field has no value". The 2025 corpus
# uses bare ``NA`` (no quotes) for district/statename/lat/long on a
# handful of recently-renamed administrative units. Treat as missing
# rather than carrying the string ``"NA"`` into the canonical row.
_NA_SENTINELS: frozenset[str] = frozenset({"", "NA", "N/A", "na"})


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


def _opt_string(raw: str | None) -> str | None:
    """Per-cell coercion for the optional string fields.

    Collapses ``""`` / ``"NA"`` / ``"N/A"`` to ``None``; otherwise
    returns the input with surrounding whitespace stripped. The
    decision to drop "NA" at parse time (rather than carry it as a
    string) is deliberate: downstream readers that join on these
    fields should see ``None``-vs-value, not ``"NA"``-vs-value.
    """
    if raw is None:
        return None
    s = raw.strip()
    if s in _NA_SENTINELS:
        return None
    return s


def _parse_coord(
    raw: str | None,
    *,
    min_val: float,
    max_val: float,
) -> tuple[float | None, bool]:
    """Parse a lat / long cell, return ``(value_or_none, was_invalid)``.

    The second element distinguishes "upstream said NA/empty" (not
    invalid, just absent) from "upstream said a number but it was
    nonsense like 999 or 'foo'" (invalid — counted so a corruption
    spike is visible). Bounds: WGS84 (lat ∈ [-90, 90],
    lon ∈ [-180, 180]).
    """
    if raw is None:
        return (None, False)
    s = raw.strip()
    if s in _NA_SENTINELS:
        return (None, False)
    try:
        v = float(s)
    except ValueError:
        return (None, True)
    if v < min_val or v > max_val:
        return (None, True)
    return (v, False)


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

    # Optional headers — only populated when upstream actually ships them.
    optional_actual: dict[str, str] = {}
    for opt in _OPTIONAL_HEADERS:
        original = header_lookup.get(opt)
        if original is not None:
            optional_actual[opt] = original

    rows: list[PincodeRow] = []
    record_count = 0
    invalid_pincode_count = 0
    invalid_coordinate_count = 0
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

        # Optional fields — None when the column is absent OR upstream
        # said "" / "NA".
        officetype = (
            _opt_string(rec.get(optional_actual["officetype"]))
            if "officetype" in optional_actual
            else None
        )
        delivery = (
            _opt_string(rec.get(optional_actual["delivery"]))
            if "delivery" in optional_actual
            else None
        )
        district = (
            _opt_string(rec.get(optional_actual["district"]))
            if "district" in optional_actual
            else None
        )
        statename = (
            _opt_string(rec.get(optional_actual["statename"]))
            if "statename" in optional_actual
            else None
        )
        latitude: float | None = None
        longitude: float | None = None
        if "latitude" in optional_actual:
            latitude, lat_bad = _parse_coord(
                rec.get(optional_actual["latitude"]), min_val=-90.0, max_val=90.0,
            )
            if lat_bad:
                invalid_coordinate_count += 1
        if "longitude" in optional_actual:
            longitude, lon_bad = _parse_coord(
                rec.get(optional_actual["longitude"]), min_val=-180.0, max_val=180.0,
            )
            if lon_bad:
                invalid_coordinate_count += 1

        rows.append(
            PincodeRow(
                circlename=circle,
                regionname=region,
                divisionname=division,
                officename=office,
                pincode=pin_raw,
                officetype=officetype,
                delivery=delivery,
                district=district,
                statename=statename,
                latitude=latitude,
                longitude=longitude,
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
        invalid_coordinate_count=invalid_coordinate_count,
    )
