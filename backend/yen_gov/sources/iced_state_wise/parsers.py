"""Pure parsers for the ICED state-wise deep-dive API.

Responsibilities:

* ``extract_rows`` — given a single decrypted FY response and an
  indicator spec, walk the parallel ``states`` / indicator-key arrays
  and emit canonical ``ParsedRow`` objects (entity_id, time, value).

The shared crypto + entity helpers used to live here; they have been
promoted to :mod:`yen_gov.sources.iced_common` so that every ICED
adapter (state-wise-deep-dive, agriculture-ghg, plant registry, …)
uses one canonical implementation. We re-export the public names below
for back-compat with any existing import sites.

No I/O. No pydantic. ``ingest`` lives one layer up.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from yen_gov.sources.iced_common import (
    ENTITY_MAP,
    ICEDShapeError,
    PASSPHRASE,
    coerce_numeric as _coerce_numeric_shared,
    decrypt_cryptojs_openssl,
    decrypt_response,
)
from yen_gov.sources.iced_common.crypto import _evp_bytes_to_key  # back-compat for tests
from yen_gov.sources.iced_common.entities import fy_to_period as _fy_to_period_shared


__all__ = (
    "PASSPHRASE",
    "ICEDShapeError",
    "decrypt_cryptojs_openssl",
    "decrypt_response",
    "coerce_numeric",
    "ParsedRow",
    "ParsedYear",
    "IndicatorSpec",
    "ENTITY_MAP",
    "extract_rows",
)


# ---------------------------------------------------------------------------
# Indicator extraction
# ---------------------------------------------------------------------------


def _fy_to_period(fy_label: str) -> str:
    """Back-compat wrapper around :func:`iced_common.entities.fy_to_period`.

    Preserves this module's historical exception type (``ICEDShapeError``)
    while delegating the actual parsing to the shared helper.
    """
    try:
        return _fy_to_period_shared(fy_label)
    except ValueError as exc:
        raise ICEDShapeError(str(exc)) from exc


def coerce_numeric(raw: Any) -> float | None:
    """Re-export of :func:`iced_common.entities.coerce_numeric`."""
    return _coerce_numeric_shared(raw)


@dataclass(frozen=True)
class ParsedRow:
    entity_id: str
    time: str
    value: float


@dataclass(frozen=True)
class IndicatorSpec:
    """Locate one indicator column in the decrypted response.

    Args:
        indicator_id: stable namespaced id (e.g. ``energy/state_generation_mu``).
        api_key: exact key in the API ``data`` dict whose value is a list
            parallel to ``states``. For composite ones (Installed Capacity
            with Allocated Shares is a dict {data, expand}) we also accept
            ``api_key_subkey``.
        api_key_subkey: optional sub-field name inside the value if it is
            a dict (e.g. ``"data"``).
    """

    indicator_id: str
    api_key: str
    api_key_subkey: str | None = None


# ENTITY_MAP is imported from iced_common (see top of file).


@dataclass(frozen=True)
class ParsedYear:
    """All rows extracted for one FY × one indicator spec."""

    indicator_id: str
    fy_label: str            # "2024-25"
    rows: tuple[ParsedRow, ...] = field(default_factory=tuple)


def extract_rows(
    *,
    spec: IndicatorSpec,
    fy_label: str,
    decrypted: dict[str, Any],
) -> ParsedYear:
    """Pull one indicator's per-state values out of one decrypted FY response."""
    payload = decrypted.get("data", decrypted)
    if not isinstance(payload, dict):
        raise ICEDShapeError("decrypted response has no top-level dict 'data'")

    states = payload.get("states")
    if not isinstance(states, list) or not states:
        raise ICEDShapeError(f"decrypted FY={fy_label!r} has no 'states' list")

    cell = payload.get(spec.api_key)
    if cell is None:
        raise ICEDShapeError(
            f"FY={fy_label!r} indicator key {spec.api_key!r} missing from response. "
            f"Available top-level keys: {sorted(payload.keys())[:20]}"
        )
    if spec.api_key_subkey is not None:
        if not isinstance(cell, dict) or spec.api_key_subkey not in cell:
            raise ICEDShapeError(
                f"FY={fy_label!r} indicator {spec.api_key!r} expected sub-dict "
                f"with key {spec.api_key_subkey!r}; got {type(cell).__name__}"
            )
        values = cell[spec.api_key_subkey]
    else:
        values = cell

    if not isinstance(values, list):
        raise ICEDShapeError(
            f"FY={fy_label!r} indicator {spec.api_key!r} value is not a list"
        )
    if len(values) != len(states):
        raise ICEDShapeError(
            f"FY={fy_label!r} indicator {spec.api_key!r}: values len={len(values)} "
            f"!= states len={len(states)}"
        )

    period = _fy_to_period(fy_label)
    rows: list[ParsedRow] = []
    for state_name, raw_value in zip(states, values, strict=True):
        entity_id = ENTITY_MAP.get(state_name)
        if entity_id is None:
            # Skip unknown sentinels like "Multiple States" / "Location TBD"
            # rather than failing — those aren't mappable to any geometry.
            continue
        v = coerce_numeric(raw_value)
        if v is None:
            continue
        rows.append(ParsedRow(entity_id=entity_id, time=period, value=v))

    return ParsedYear(
        indicator_id=spec.indicator_id, fy_label=fy_label, rows=tuple(rows)
    )
