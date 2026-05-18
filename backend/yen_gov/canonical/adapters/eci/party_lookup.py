"""Party lookup — resolves ECI party strings to canonical party_ids.

The ECI per-AC page carries the party's display string (``"Dravida Munnetra
Kazhagam"`` or ``"DMK"`` depending on layout). Some pages also surface the
ECI numeric party code via partywiseresult-<state>.htm.

This module:
  1. Loads ``datasets/taxonomy/parties.json`` once.
  2. Builds two reverse indexes: alias-string → party_id and eci_code → party_id.
  3. Resolves with a deterministic priority: ECI code (when supplied) wins
     over alias match; ``parties.IN.IND`` is the sentinel for independents;
     ``parties.IN.NOTA`` for NOTA rows.

Unresolved party strings raise ``UnknownPartyError`` — the adapter should
fail loud, never silently coerce to IND (that would inflate the IND bucket).
The fix is to extend ``parties.json`` with the new alias.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class UnknownPartyError(LookupError):
    """A party string was not resolvable to any party_id in the roster."""


@dataclass(frozen=True)
class PartyLookup:
    """Resolves ECI-side identifiers to canonical party_ids.

    Constructed via ``load_party_lookup(datasets_root)``. Pure in-memory map;
    safe to share across all batches in a backfill run.
    """

    by_alias: dict[str, str]      # lowercase alias -> party_id
    by_eci_code: dict[str, str]   # eci numeric string -> party_id

    def resolve(
        self,
        *,
        party_full: str | None = None,
        party_short: str | None = None,
        eci_code: str | None = None,
        is_independent: bool = False,
        is_nota: bool = False,
    ) -> str:
        """Return party_id, raising UnknownPartyError if unresolvable.

        Resolution order:
            1. NOTA flag -> parties.IN.NOTA.
            2. Independent flag -> parties.IN.IND.
            3. ECI numeric code (most reliable when present).
            4. party_short alias (case-insensitive).
            5. party_full alias (case-insensitive).
        """
        if is_nota:
            return "parties.IN.NOTA"
        if is_independent:
            return "parties.IN.IND"
        if eci_code and eci_code in self.by_eci_code:
            return self.by_eci_code[eci_code]
        for candidate in (party_short, party_full):
            if not candidate:
                continue
            key = candidate.strip().lower()
            if key in self.by_alias:
                return self.by_alias[key]
        raise UnknownPartyError(
            f"Cannot resolve party: short={party_short!r} full={party_full!r} "
            f"eci_code={eci_code!r}. Extend datasets/taxonomy/parties.json."
        )


def load_party_lookup(datasets_root: Path) -> PartyLookup:
    """Load ``datasets/taxonomy/parties.json`` into a PartyLookup.

    Builds both indexes in a single pass. Aliases include short_name + full_name
    + every entry in the explicit ``aliases`` list. The raw roster is stashed
    on the instance so ``registry()`` can emit dim_parties rows without a
    second read.
    """
    path = datasets_root / "taxonomy" / "parties.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    by_alias: dict[str, str] = {}
    by_eci: dict[str, str] = {}
    for row in raw["parties"]:
        pid = row["party_id"]
        for alias in (row["short_name"], row["full_name"], *row.get("aliases", [])):
            by_alias[alias.strip().lower()] = pid
        for code in row.get("eci_codes", []):
            by_eci[code] = pid
    lookup = PartyLookup(by_alias=by_alias, by_eci_code=by_eci)
    # Stash raw roster on the (frozen) dataclass via object.__setattr__ —
    # registry() needs it; we don't want to break the frozen-shared-safe
    # contract for the resolution path.
    object.__setattr__(lookup, "_roster", raw["parties"])
    return lookup


def party_dim_rows(lookup: PartyLookup, *, source_id: str) -> list[dict]:
    """Build dim_parties payload dicts from a loaded lookup.

    Returns plain dicts (not PartyDimRow) to avoid a circular import with
    canonical/envelope; the driver wraps these in PartyDimRow before envelope
    construction. ``source_id`` is the provenance row for the parties.json
    registry itself, NOT the per-AC contest sources.
    """
    roster: list[dict] = getattr(lookup, "_roster", [])
    out: list[dict] = []
    for row in roster:
        eci_codes = row.get("eci_codes") or []
        out.append({
            "party_id": row["party_id"],
            "eci_code": eci_codes[0] if eci_codes else None,
            "short_name": row["short_name"],
            "full_name": row["full_name"],
            "recognition": row.get("recognition"),
            "source_id": source_id,
        })
    return out


def party_alliance_dim_rows(lookup: PartyLookup, *, source_id: str) -> list[dict]:
    """Build dim_party_alliances payload dicts from a loaded lookup.

    Flattens each party's ``alliance_history[]`` into one row per
    (party_id, period_label) pair. Parties without an ``alliance_history``
    entry contribute zero rows (absence rather than nulls). An explicit
    ``{"period_label": ..., "alliance": null}`` history entry surfaces as
    a row with alliance=None — that is "non-aligned this event", distinct
    from "alliance was never declared".
    """
    roster: list[dict] = getattr(lookup, "_roster", [])
    out: list[dict] = []
    for row in roster:
        history = row.get("alliance_history") or []
        for entry in history:
            out.append({
                "party_id": row["party_id"],
                "short_name": row["short_name"],
                "period_label": entry["period_label"],
                "alliance": entry.get("alliance"),
                "source_id": source_id,
            })
    return out
