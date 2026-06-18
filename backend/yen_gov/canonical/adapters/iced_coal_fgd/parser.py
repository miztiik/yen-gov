"""ICED coal-plant FGD feed - decrypt, classify FGD + operating status, coerce.

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes a coal-plant
air-quality-impact inventory as an AES-encrypted JSON feed. Each ``data``
element is one generating UNIT (a plant has one or more units), shaped::

    {"plantName": "...", "unitName": "... Unit 1", "source": "coal",
     "capacity": 150, "commissioningDate": "2012-10-01T00:00:00.000Z",
     "commissioningStatus": "operational", "commissioningGroup": "operational",
     "developer": "...", "fgdDate": "...", "fgdStatus": "FGD installed",
     "fgdGroup": "FGD installed", "lat": 14.21, "lng": 80.09}

This module turns the raw envelope into typed :class:`CoalUnit` records and
two binary classifications that the FGD-share metric needs. It does NOT
geocode (that geospatial concern lives in :mod:`.geocode`) and it does NOT
aggregate (that lives in :mod:`.ingest`). It is a pure decrypt -> classify ->
coerce transform.

FGD classification (the numerator membership test)
--------------------------------------------------
FGD = flue-gas desulphurisation, a wet/dry SO2 scrubber bolted onto the flue.
The feed's ``fgdGroup`` field buckets each unit's retrofit progress. Exactly
ONE bucket asserts a physically-installed scrubber:

    "FGD installed"            -> HAS FGD (counted)

Every other observed bucket is NOT a confirmed flue-gas scrubber and is
treated as "no FGD" for this metric:

    "None"                              no scrubber, none planned-on-record
    "No FGD Planned"                    explicitly none
    "Bid Awarded" / "Under bidding"     procurement stage - not yet built
    "Feasibility Study under various stages"  pre-procurement
    "To be decommissioned"              exiting - not retrofitted
    "Stressed Asset"                    financially stalled - not retrofitted
    "Converted to Captive Power Plant"  ownership change - not a scrubber
    "CFBC Boilers" (Circulating Fluidized Bed Combustion)  a DIFFERENT
        SO2-control technology (in-furnace limestone), NOT a flue-gas
        scrubber - deliberately EXCLUDED so the metric measures FGD only.
    "Claims to be SO2 compliant"        an unverified operator claim, not a
        confirmed installed scrubber - EXCLUDED (conservative / honest).

The conservative single-bucket rule keeps the indicator honest: it reports
confirmed flue-gas-desulphurisation capacity, not aspiration. India's FGD
retrofit programme is years behind schedule, so a LOW share is the truthful
number, not a defect.

Operating-status classification (the share's denominator + numerator gate)
-------------------------------------------------------------------------
The honest metric is the share of the OPERATING fleet that is scrubbed. The
feed's ``commissioningGroup`` buckets each unit:

    "operational"           -> in the operating fleet (counted)
    "retired"                generating no longer
    "pipeline"               not yet generating (under construction / planned)
    "Temporarily Closed"     not currently generating
    "captive-power-plant"    a separate captive category, not grid coal fleet

Only ``commissioningGroup == "operational"`` units enter the share (both its
numerator and denominator).

No network: reads operator-staged response bytes only (parent plan section
21.4). Decryption is the shared CryptoJS-OpenSSL path in
``yen_gov.sources.iced_common.crypto`` (a plain-JSON body parses straight
through, so synthetic test fixtures need no AES).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yen_gov.sources.iced_common import load_iced_response

__all__ = [
    "CoalUnit",
    "CoalFgdShapeError",
    "ParseReport",
    "HAS_FGD_GROUPS",
    "OPERATIONAL_GROUP",
    "COAL_SOURCE",
    "parse_coal_units",
]

# The single ``fgdGroup`` bucket that asserts a physically-installed flue-gas
# desulphurisation scrubber. A frozenset (not a scalar) so a future feed that
# splits "FGD installed" into "FGD installed" + "FGD operational" can be
# admitted by one edit here, with the drift guard below catching a rename.
HAS_FGD_GROUPS: frozenset[str] = frozenset({"FGD installed"})

# The ``commissioningGroup`` bucket that means the unit is in the operating
# fleet. The share is computed over this fleet only.
OPERATIONAL_GROUP = "operational"

# Only coal units belong in a coal-FGD metric; a non-coal row would be a feed
# surprise (today the feed is 100% coal). Such rows are skipped + counted.
COAL_SOURCE = "coal"

# Coordinate / capacity cell contents that mean "no value".
_NA_MARKERS: frozenset[str] = frozenset(
    {"", "-", "--", "n.a.", "na", "n.a", "na.", "nr", "...", "null", "none"}
)


class CoalFgdShapeError(ValueError):
    """The staged ICED coal-FGD feed no longer matches its expected shape.

    Raised loud (never emit a wholesale-empty or all-zero series) when the
    envelope has no ``data`` list, a data element is not an object, the
    ``commissioningGroup`` vocabulary no longer contains an "operational"
    bucket, or the ``fgdGroup`` vocabulary no longer contains the
    "FGD installed" bucket. A silent vocabulary rename would turn the whole
    metric into a misleading 0% - a lie to the citizen.
    """


@dataclass(frozen=True)
class CoalUnit:
    """One coal generating unit, classified and coerced.

    ``lat`` / ``lng`` / ``capacity`` are ``None`` when the source cell was an
    N.A. marker; geocoding + aggregation skip such units and report them.
    """

    plant_name: str
    unit_name: str
    capacity_mw: float | None
    lat: float | None
    lng: float | None
    fgd_group: str
    commissioning_group: str
    has_fgd: bool
    operational: bool


@dataclass(frozen=True)
class ParseReport:
    """Counts the operator needs to trust (or distrust) the parsed feed."""

    total_units: int
    coal_units: int
    non_coal_skipped: int
    operational_units: int
    operational_fgd_units: int
    operational_missing_coords: tuple[CoalUnit, ...]
    operational_missing_capacity: tuple[CoalUnit, ...]
    fgd_groups_seen: tuple[str, ...]
    commissioning_groups_seen: tuple[str, ...]


def parse_coal_units(raw_bytes: bytes) -> tuple[list[CoalUnit], ParseReport]:
    """Decrypt the envelope and classify every coal unit.

    Args:
        raw_bytes: the operator-staged raw response body (AES envelope, or
            plain JSON for a synthetic fixture).

    Returns:
        ``(units, report)`` - ``units`` is every coal unit (classified +
        coerced, in feed order); ``report`` carries the counts a caller needs
        to surface and to fail-loud on.

    Raises:
        CoalFgdShapeError: the envelope has no ``data`` list, an element is
            not an object, or the feed no longer contains an "operational"
            commissioning bucket or an "FGD installed" fgd bucket (vocabulary
            drift - refuse to emit a misleading all-zero series).
    """
    envelope = load_iced_response(raw_bytes, decrypt=True)
    data = _extract_data(envelope)

    units: list[CoalUnit] = []
    fgd_groups_seen: set[str] = set()
    commissioning_groups_seen: set[str] = set()
    non_coal_skipped = 0

    for index, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise CoalFgdShapeError(
                f"coal-fgd: data[{index}] is not an object "
                f"({type(raw).__name__}); the feed shape changed."
            )
        source = str(raw.get("source", "")).strip().lower()
        if source != COAL_SOURCE:
            non_coal_skipped += 1
            continue

        fgd_group = str(raw.get("fgdGroup")).strip() if raw.get("fgdGroup") is not None else ""
        commissioning_group = (
            str(raw.get("commissioningGroup")).strip()
            if raw.get("commissioningGroup") is not None
            else ""
        )
        fgd_groups_seen.add(fgd_group)
        commissioning_groups_seen.add(commissioning_group)

        units.append(
            CoalUnit(
                plant_name=str(raw.get("plantName", "")).strip(),
                unit_name=str(raw.get("unitName", "")).strip(),
                capacity_mw=_coerce_number(raw.get("capacity"), index, "capacity"),
                lat=_coerce_number(raw.get("lat"), index, "lat"),
                lng=_coerce_number(raw.get("lng"), index, "lng"),
                fgd_group=fgd_group,
                commissioning_group=commissioning_group,
                has_fgd=fgd_group in HAS_FGD_GROUPS,
                operational=commissioning_group == OPERATIONAL_GROUP,
            )
        )

    if not units:
        raise CoalFgdShapeError(
            "coal-fgd: the feed contained no coal units; refusing to emit an "
            "empty series."
        )

    # Vocabulary-drift guards: the metric is meaningless if the "operational"
    # or "FGD installed" labels were renamed upstream. Fail loud rather than
    # silently emit an empty or all-zero series.
    if OPERATIONAL_GROUP not in commissioning_groups_seen:
        raise CoalFgdShapeError(
            f"coal-fgd: no unit has commissioningGroup {OPERATIONAL_GROUP!r}; "
            f"saw {sorted(commissioning_groups_seen)}. The publisher may have "
            f"renamed the operating-fleet bucket - re-check the feed before "
            f"ingesting."
        )
    if not (HAS_FGD_GROUPS & fgd_groups_seen):
        raise CoalFgdShapeError(
            f"coal-fgd: no unit has an FGD-installed fgdGroup "
            f"{sorted(HAS_FGD_GROUPS)}; saw {sorted(fgd_groups_seen)}. The "
            f"publisher may have renamed the FGD-installed bucket - refusing "
            f"to emit a misleading all-zero series."
        )

    operational = [u for u in units if u.operational]
    report = ParseReport(
        total_units=len(units) + non_coal_skipped,
        coal_units=len(units),
        non_coal_skipped=non_coal_skipped,
        operational_units=len(operational),
        operational_fgd_units=sum(1 for u in operational if u.has_fgd),
        operational_missing_coords=tuple(
            u for u in operational if u.lat is None or u.lng is None
        ),
        operational_missing_capacity=tuple(
            u for u in operational if u.capacity_mw is None
        ),
        fgd_groups_seen=tuple(sorted(fgd_groups_seen)),
        commissioning_groups_seen=tuple(sorted(commissioning_groups_seen)),
    )
    return units, report


def _extract_data(envelope: Any) -> list[Any]:
    """Pull the ``data`` list out of the decrypted envelope, fail-loud."""
    if isinstance(envelope, dict):
        data = envelope.get("data")
    elif isinstance(envelope, list):
        data = envelope
    else:
        data = None
    if not isinstance(data, list):
        raise CoalFgdShapeError(
            f"coal-fgd: decrypted response has no 'data' list "
            f"(got {type(envelope).__name__}); the endpoint format changed."
        )
    return data


def _coerce_number(value: Any, index: int, field: str) -> float | None:
    """Coerce a numeric cell to float, or None for an N.A. / empty cell.

    Raises on genuine garbage (a non-numeric, non-N.A. string) so a feed-shape
    change surfaces instead of being silently coerced to None.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise CoalFgdShapeError(
            f"coal-fgd: data[{index}] {field} is a boolean; expected a number."
        )
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in _NA_MARKERS:
            return None
        try:
            return float(text)
        except ValueError:
            # A non-numeric, non-N.A. coordinate/capacity string (e.g. a stray
            # label). Treat as missing rather than crash the whole feed - the
            # unit is reported as unplaced/uncapacitied downstream.
            return None
    raise CoalFgdShapeError(
        f"coal-fgd: data[{index}] {field} has unexpected type "
        f"{type(value).__name__}."
    )
