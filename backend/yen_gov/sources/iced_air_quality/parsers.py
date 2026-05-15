"""Pure parser for ICED's ``/climate-environment/environment/air-quality/fgd``.

Aggregates the 602 plant-unit rows the endpoint returns into one
state-level indicator: the share (in %) of each state's coal thermal
capacity (MW) that has actually installed flue-gas desulphurisation.

Why this is the first air-quality indicator we ship (governance):

  In December 2015 the MoEF&CC notified mandatory SO2 emission limits
  for coal- and lignite-fired thermal power plants, requiring FGD
  installation. The original 2017 deadline has been pushed repeatedly
  (2022, 2024, 2026, now 2027 for many categories). Tracking which
  states are actually compliant is a clean, citizen-readable governance
  metric: numerator and denominator are both observed quantities (MW),
  the policy is named (the 2015 notification), and there is no monitor-
  density argument to navigate (every plant in the tracker is a known,
  visible asset). Compare with the NAMP-based PM2.5 series, where state
  rankings are not honest because the monitor network is uneven and
  urban-biased.

Provenance (Hans 2026-05-15):

  ICED is a *re-publisher* — the underlying tracker is maintained by
  CEA (Central Electricity Authority) and tied to the MoEF&CC
  notification. Artifacts from this parser MUST list both the ICED API
  URL we fetched and the upstream policy URL in their ``sources``
  array. Listing only the ICED URL implies NITI Aayog as the publisher,
  which is incorrect.

This module is *pure*. No I/O, no decryption — it consumes the already-
decrypted ``{status, data: {fgdGroups, data, graphData}}`` dict that the
client returns and emits :class:`ParsedRow` objects. The fetch+decrypt
side is in :mod:`yen_gov.sources.iced_air_quality.ingest`; the network
boundary is :class:`IcedClient` in :mod:`yen_gov.sources.iced_common`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from yen_gov.sources.iced_common import ENTITY_MAP, ICEDShapeError


# The status string ICED writes for plant-units that have actually
# installed FGD. All other status values fall into the denominator but
# not the numerator. Pinned here (not inlined in the loop) so a future
# spelling change at the source fails loudly in test rather than
# silently zeroing every state's share.
FGD_INSTALLED_STATUS: str = "FGD installed"


@dataclass(frozen=True)
class ParsedRow:
    """One state-level row of the FGD indicator."""

    entity_id: str         # ECI state code (e.g. "S22")
    state_name: str        # ICED's spelling, kept for diagnostics
    capacity_total_mw: float
    capacity_installed_mw: float
    units_total: int
    units_installed: int

    @property
    def installed_share_pct(self) -> float:
        if self.capacity_total_mw <= 0:
            return 0.0
        return self.capacity_installed_mw / self.capacity_total_mw * 100.0


def extract_state_rows(decrypted: dict[str, Any]) -> list[ParsedRow]:
    """Aggregate the 602-plant-unit list into one row per state.

    The decrypted response shape (recon 2026-05-15) is::

        {"status": "success", "data": {
            "fgdGroups": [{"name": str, "value": float}, ...],   # capacity by group
            "data":      [<plant-unit row>, ...],                # 602 rows
            "graphData": null
        }}

    Each plant-unit row has::

        {developer, plantName, state, unitNo, capacity, fgdStatus,
         fgdGroup, fgdDate}

    State names are ICED-spelled; we look them up in
    :data:`yen_gov.sources.iced_common.ENTITY_MAP`. An unknown spelling
    raises :class:`ICEDShapeError` rather than silently dropping the
    rows — better to fail at ingest than to under-report a state.
    """
    if not isinstance(decrypted, dict):
        raise ICEDShapeError(f"FGD response is not a dict: {type(decrypted).__name__}")
    if "data" not in decrypted:
        raise ICEDShapeError(f"FGD response missing 'data': keys={list(decrypted)}")
    inner = decrypted["data"]
    if not isinstance(inner, dict) or "data" not in inner:
        raise ICEDShapeError(
            f"FGD response.data missing nested 'data' list: {type(inner).__name__}"
        )
    plant_rows = inner["data"]
    if not isinstance(plant_rows, list):
        raise ICEDShapeError(
            f"FGD plant rows is not a list: {type(plant_rows).__name__}"
        )

    # Aggregate per ICED state spelling (we'll resolve to entity_id below).
    accum: dict[str, dict[str, float]] = {}
    unknown_states: set[str] = set()
    for row in plant_rows:
        if not isinstance(row, dict):
            continue
        state = row.get("state")
        if not isinstance(state, str) or not state.strip():
            continue
        state = state.strip()
        if state not in ENTITY_MAP:
            unknown_states.add(state)
            continue
        cap = _coerce_mw(row.get("capacity"))
        if cap is None:
            # Capacity missing → this unit cannot contribute to either
            # side of the ratio. Skip it (don't pretend it's zero).
            continue
        bucket = accum.setdefault(
            state,
            {"cap_total": 0.0, "cap_inst": 0.0, "n_total": 0, "n_inst": 0},
        )
        bucket["cap_total"] += cap
        bucket["n_total"] += 1
        if row.get("fgdStatus") == FGD_INSTALLED_STATUS:
            bucket["cap_inst"] += cap
            bucket["n_inst"] += 1

    if unknown_states:
        # Hard-fail: a new state spelling means our aggregate is silently
        # incomplete. Preferable to surface this in CI than to ship a
        # 16-state map when the source has 17.
        raise ICEDShapeError(
            "FGD response contains state spellings not in ENTITY_MAP — "
            f"add them as aliases in iced_common.entities: {sorted(unknown_states)}"
        )

    rows = [
        ParsedRow(
            entity_id=ENTITY_MAP[state],
            state_name=state,
            capacity_total_mw=b["cap_total"],
            capacity_installed_mw=b["cap_inst"],
            units_total=int(b["n_total"]),
            units_installed=int(b["n_inst"]),
        )
        for state, b in accum.items()
    ]
    rows.sort(key=lambda r: r.entity_id)
    return rows


def _coerce_mw(raw: Any) -> float | None:
    """ICED ships ``capacity`` as a number, but defend against str/None."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None  # True/False is never a capacity
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        text = raw.strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def emit_indicator_rows(parsed: Iterable[ParsedRow]) -> list[dict[str, Any]]:
    """Convert :class:`ParsedRow` objects to indicator-schema row dicts.

    The artifact has one row per state; ``time`` is set by the ingest
    layer (snapshot date) so the parser stays time-agnostic and trivial
    to test.
    """
    return [
        {
            "entity_id": r.entity_id,
            # value: 0..100 share of state thermal capacity with FGD installed.
            # Rounded to 0.01 to keep diffable artifacts stable.
            "value": round(r.installed_share_pct, 2),
        }
        for r in parsed
    ]
