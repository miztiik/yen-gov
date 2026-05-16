"""Pure derivation of an indicator's `collection_inventory` block.

The folded indicator model (schema v1.6, required in v2.0) stores
collection state inline. Most fields are *derived* on every emit from
the indicator's own `series_spec` + `rows[]` + `sources[]`; a small
set of fields (`frozen`, `refetch_requested`, `unavailable_periods`)
are *operator-set* and preserved across re-derivation.

This module is intentionally a single file with internal helpers
(`_collected_cells`, `_pending_periods`, `_derive_status`,
`_max_fetched_at`) rather than a 4-file mini-package. The algorithm
is small enough that splitting it just inflates import surface area.
See `TODO/20260517-folded-indicator-and-collection-inventory-handover.md`
§5.4 for the spec.

Determinism contract: given the same `indicator_dict` input, returns
a byte-stable structure. List ordering is sorted (period `key`,
geography code, source url) so JSON re-serialisation is identical
between runs. This is what lets the wiring in commit 8 re-derive on
every refresh without producing `git status` churn.
"""

from __future__ import annotations

from typing import Any

# Operator-set fields preserved verbatim from the existing
# `collection_inventory` block on the indicator file. Anything else
# present on the existing block is dropped (it is derived; the previous
# emit's derived value is irrelevant to this emit's derivation).
_OPERATOR_SET_FIELDS: tuple[str, ...] = ("frozen", "refetch_requested", "unavailable_periods")


def derive_collection_inventory(indicator_dict: dict[str, Any]) -> dict[str, Any]:
    """Derive a fresh `collection_inventory` block for an indicator.

    Parameters
    ----------
    indicator_dict:
        The parsed indicator JSON. Must carry `rows`, `sources`, and
        (for non-empty derivation) `series_spec`. The existing
        `collection_inventory` (if any) is read only for the
        operator-set fields listed in `_OPERATOR_SET_FIELDS`; the rest
        is re-derived.

    Returns
    -------
    A dict with the full set of `collection_inventory` keys defined in
    `indicator.schema.json` v1.6+. Safe to assign back to
    `indicator_dict["collection_inventory"]`.
    """
    series_spec = indicator_dict.get("series_spec") or {}
    rows = indicator_dict.get("rows") or []
    sources = indicator_dict.get("sources") or []
    prior = indicator_dict.get("collection_inventory") or {}

    expected_geographies = list(series_spec.get("expected_geographies") or [])
    expected_periods = list(series_spec.get("expected_periods") or [])

    collected = _collected_cells(rows)
    observed = _observed_periods(rows, expected_periods)

    unavailable_periods = list(prior.get("unavailable_periods") or [])
    pending = _pending_periods(
        expected_periods=expected_periods,
        expected_geographies=expected_geographies,
        collected=collected,
        unavailable=unavailable_periods,
    )

    status = _derive_status(
        collected_count=len(collected),
        pending_count=len(pending),
        unavailable_count=len(unavailable_periods),
    )

    return {
        "status": status,
        "frozen": bool(prior.get("frozen", False)),
        "last_collected_at": _max_fetched_at(sources),
        "refetch_requested": bool(prior.get("refetch_requested", False)),
        "pending_periods": pending,
        "observed_periods": observed,
        "unavailable_periods": unavailable_periods,
    }


# --------------------------------------------------------------------- #
# helpers                                                               #
# --------------------------------------------------------------------- #


def _collected_cells(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Return `{(entity_id, period_key)}` for every row whose value is not null.

    The period key is `rows[].time` (the stable equality token; the
    citizen-readable `period_label` is informational only).
    """
    cells: set[tuple[str, str]] = set()
    for row in rows:
        if row.get("value") is None:
            continue
        entity_id = row.get("entity_id")
        time = row.get("time")
        if entity_id is None or time is None:
            continue
        cells.add((str(entity_id), str(time)))
    return cells


def _observed_periods(rows: list[dict[str, Any]], expected_periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive observed period tokens from `rows[]`.

    Uses `expected_periods` as the source for `(label, frequency)` when
    a matching `key` exists (because the schema requires a citizen
    label and a frequency on every period token; `rows[].time` carries
    only the key). For rows whose `time` is not in `expected_periods`,
    falls back to `period_label`/`time` as the label and the empty
    frequency `"ad_hoc"`. Sorted by `key` for determinism.
    """
    by_key = {p["key"]: p for p in expected_periods if "key" in p}
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        time = row.get("time")
        if time is None:
            continue
        key = str(time)
        if key in seen:
            continue
        if key in by_key:
            seen[key] = {
                "key": key,
                "label": by_key[key]["label"],
                "frequency": by_key[key]["frequency"],
            }
        else:
            seen[key] = {
                "key": key,
                "label": str(row.get("period_label") or time),
                "frequency": "ad_hoc",
            }
    return [seen[k] for k in sorted(seen)]


def _pending_periods(
    *,
    expected_periods: list[dict[str, Any]],
    expected_geographies: list[str],
    collected: set[tuple[str, str]],
    unavailable: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute pending periods.

    A period is pending if ANY expected geography is missing a
    collected cell for that period, excluding cells listed in
    `unavailable_periods`. Emits one period token per pending period
    (not per missing cell) per the handover \u00a75.4 step 3. Output
    sorted by period `key`.

    If `expected_geographies` is empty (e.g. the indicator inlines
    `["IN"]` for a union-only series), the rule degenerates to: a
    period is pending iff no collected cell exists for it.
    """
    unavailable_keys = {
        u.get("period", {}).get("key"): set(u.get("geographies") or [])
        for u in unavailable
        if u.get("period")
    }

    pending: list[dict[str, Any]] = []
    for period in expected_periods:
        key = period.get("key")
        if key is None:
            continue
        if not expected_geographies:
            if not any(c[1] == key for c in collected):
                pending.append({"key": key, "label": period["label"], "frequency": period["frequency"]})
            continue
        unavailable_geos = unavailable_keys.get(key, set())
        expected_geo_set = set(expected_geographies) - unavailable_geos
        if not expected_geo_set:
            continue  # whole period excluded; not pending
        collected_geos_for_period = {c[0] for c in collected if c[1] == key}
        missing = expected_geo_set - collected_geos_for_period
        if missing:
            pending.append({"key": key, "label": period["label"], "frequency": period["frequency"]})
    pending.sort(key=lambda p: p["key"])
    return pending


def _derive_status(*, collected_count: int, pending_count: int, unavailable_count: int) -> str:
    """Status enum: complete | partial | empty.

    - `empty`: zero collected cells.
    - `complete`: no pending periods (either everything expected has
      been collected, or the remainder is explicitly marked
      unavailable).
    - `partial`: everything else.
    """
    if collected_count == 0:
        return "empty"
    if pending_count == 0:
        return "complete"
    return "partial"


def _max_fetched_at(sources: list[dict[str, Any]]) -> str | None:
    """Return max `fetched_at` across sources, or None when sources is empty.

    Strings compare lexicographically; ISO-8601 UTC timestamps with
    consistent precision are safe to max() that way, which is how the
    rest of the codebase already orders them.
    """
    stamps = [s.get("fetched_at") for s in sources if s.get("fetched_at")]
    if not stamps:
        return None
    return max(str(s) for s in stamps)
