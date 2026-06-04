"""B2a.8 entities/party.csv emitter.

Lift ``datasets/taxonomy/parties.json`` to
``datasets/data/entities/party.csv`` per the parent plan section 20.3 +
sub-plan B2a.8: ``party_id`` is the sole canonical key; ``eci_codes`` is a
descriptive multi-value attribute (pipe-delimited), not a join key.

Columns retained (per ``datasets/data/_schema/columns.json``):

- ``party_id``      (PK; lifted as-is from taxonomy)
- ``short``         (from ``short_name``)
- ``full``          (from ``full_name``)
- ``eci_codes``     (pipe-delimited; nullable when taxonomy list is empty)
- ``brand_colour``  (hex from the ``brand_colour`` block; nullable)
- ``symbol_asset``  (``asset_path`` from the ``election_symbol`` block;
                      nullable when the party has no sanitised symbol)
- ``wikipedia``     (``wikipedia_url``; nullable)

Dropped (no home in the new contract; lives in taxonomy until X1b):

- aliases, alliance_history, founded_year, dissolved_year, notes,
  predecessor_party_id, successor_party_id, recognition, state_scope,
  and the nested ``brand_colour`` / ``election_symbol`` sub-fields beyond
  the projected single column above.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/party.csv"


def _read_parties(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("parties")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: missing or non-list 'parties' key")
    return entries


def _join_eci_codes(codes: Any) -> str | None:
    if not codes:
        return None
    if not isinstance(codes, list):
        raise ValueError(f"eci_codes must be a list, got {type(codes).__name__}")
    parts = [str(c) for c in codes if c is not None and str(c) != ""]
    return "|".join(parts) if parts else None


def _brand_colour_hex(block: Any) -> str | None:
    if not block:
        return None
    if not isinstance(block, dict):
        raise ValueError(f"brand_colour must be an object, got {type(block).__name__}")
    hex_val = block.get("hex")
    return str(hex_val) if hex_val else None


def _symbol_asset(block: Any) -> str | None:
    if not block:
        return None
    if not isinstance(block, dict):
        raise ValueError(
            f"election_symbol must be an object, got {type(block).__name__}"
        )
    asset = block.get("asset_path")
    return str(asset) if asset else None


def emit(*, parties_json: Path, out_path: Path) -> Path:
    """Emit ``out_path`` from the taxonomy parties register; return the path.

    Raises:
        FileNotFoundError: ``parties_json`` is missing.
        ValueError: required field missing, ``__`` in any emitted ``party_id``
            (plan section 21.6), duplicate ``party_id``, or malformed nested
            block (``eci_codes`` / ``brand_colour`` / ``election_symbol``).
    """
    if not parties_json.exists():
        raise FileNotFoundError(parties_json)

    parties = _read_parties(parties_json)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in parties:
        party_id = entry.get("party_id")
        short = entry.get("short_name")
        full = entry.get("full_name")
        if not party_id or not isinstance(party_id, str):
            raise ValueError(f"party entry missing 'party_id': {entry!r}")
        if not short or not isinstance(short, str):
            raise ValueError(f"party {party_id} missing 'short_name'")
        if not full or not isinstance(full, str):
            raise ValueError(f"party {party_id} missing 'full_name'")
        if "__" in party_id:
            raise ValueError(
                f"party_id must not contain '__' (plan section 21.6): {party_id!r}"
            )
        if party_id in seen:
            raise ValueError(f"duplicate party_id: {party_id!r}")
        seen.add(party_id)

        wiki = entry.get("wikipedia_url")
        rows.append(
            {
                "party_id": party_id,
                "short": short,
                "full": full,
                "eci_codes": _join_eci_codes(entry.get("eci_codes")),
                "brand_colour": _brand_colour_hex(entry.get("brand_colour")),
                "symbol_asset": _symbol_asset(entry.get("election_symbol")),
                "wikipedia": str(wiki) if wiki else None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
