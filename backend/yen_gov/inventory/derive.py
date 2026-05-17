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


# ===================================================================== #
# derive_temporal_range — pure derivation of observed temporal range    #
# from rows[].time + rows[].period_label + indicator.time_grain.        #
#                                                                       #
# Consumers: completeness index emitter (operator surface) and the      #
# citizen indicator card caption (via a TS mirror in lib/indicators.ts  #
# whose rule is policed by a shared fixture under                       #
# datasets/_test/temporal-range-fixtures/).                             #
#                                                                       #
# Design notes:                                                         #
#   - Publisher-vocabulary preservation: rows[].time tokens are the     #
#     publisher's own form (`2015-04`, `2011`, `2026-05-14`). We do     #
#     NOT normalise; lexicographic min/max preserves chronological      #
#     order for every ISO-anchored shape we have today.                 #
#   - Fail-loud on mixed vocabularies inside ONE artifact (debate       #
#     consensus 2026-05-17): heterogeneous rows[].time is an adapter    #
#     bug, not a feature. Silent-omit would overload the null signal.   #
#   - gap_count_within_range is omitted for time_grain="date"           #
#     (snapshot dates have no meaningful cadence between samples).      #
# ===================================================================== #

import re

# Shape detectors. Order matters: more specific first.
_SHAPE_PATS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("date",       re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("year_month", re.compile(r"^\d{4}-\d{2}$")),
    ("year",       re.compile(r"^\d{4}$")),
    # NOTE: no "fy" shape ("FY YYYY-YY" as rows[].time). No production
    # artifact emits that token directly in rows[].time — fiscal-year
    # artifacts emit ISO-anchored YYYY-04 and carry the printable FY
    # label in rows[].period_label. Per Fowler review 2026-05-17; YAGNI
    # — if an adapter ever does emit FY-prefixed time tokens the
    # heterogeneous-vocabulary guard will fail loud rather than guess.
)


def _detect_shape(token: str) -> str:
    for name, pat in _SHAPE_PATS:
        if pat.match(token.strip()):
            return name
    return "other"


def _expected_period_count(
    *, min_time: str, max_time: str, shape: str, time_grain: str
) -> int | None:
    """Inclusive count of expected periods between min and max at `time_grain` cadence.

    Returns None when the cadence is undefined (snapshot dates) or when
    the shape/grain combination is not supported.
    """
    if min_time == max_time:
        return 1
    if shape == "year":
        return int(max_time) - int(min_time) + 1
    if shape == "year_month":
        miny, minm = int(min_time[:4]), int(min_time[5:7])
        maxy, maxm = int(max_time[:4]), int(max_time[5:7])
        total_months = (maxy * 12 + maxm) - (miny * 12 + minm) + 1
        if time_grain == "month":
            return total_months
        if time_grain == "fiscal_year":
            # FY tokens are emitted as YYYY-04 (April-anchored).
            # Stride = 12 months; count years inclusive.
            return (maxy - miny) + 1
        if time_grain == "quarter":
            # Stride = 3 months; expect aligned starts.
            if total_months % 3 != 0 and (total_months - 1) % 3 != 0:
                # Quarter cadence inferred but observed months don't align.
                # Fall through to None rather than guess.
                return None
            return ((total_months - 1) // 3) + 1
        # Unknown grain on YYYY-MM shape — caller decides.
        return None
    if shape == "date":
        return None
    return None


# Cadences for which the publisher has no defined inter-observation
# interval. For these, derive_temporal_range omits both
# `gap_count_within_range` and `observed_periods_within_range`: asserting
# them against an inferred-from-time_grain cadence would mislead the
# citizen into reading patchiness into a complete record (Census-on-year,
# UNFCCC BUR, ad-hoc NEP tables). Per ADR-0027.
_UNDEFINED_CADENCE: frozenset[str] = frozenset({"decennial", "ad_hoc"})


def derive_temporal_range(indicator_dict: dict[str, Any]) -> dict[str, Any] | None:
    """Derive observed temporal-range fields from an indicator artifact.

    Parameters
    ----------
    indicator_dict:
        The parsed indicator JSON. Reads ``rows[]`` (uses ``.time`` and
        ``.period_label``), ``indicator.time_grain`` (per-row stamp
        resolution), and ``indicator.cadence`` (publisher release
        cadence, optional — added in indicator schema v4.1 per
        ADR-0027).

    Returns
    -------
    A dict with the following keys, or ``None`` when ``rows == []``:

    - ``min_time`` / ``max_time``: lexicographic min/max of distinct
      ``rows[].time`` tokens. Same string vocabulary as the publisher.
    - ``min_period_label`` / ``max_period_label``: ``period_label`` of
      any row holding that ``time`` (falls back to the token itself).
    - ``observed_periods_within_range``: count of distinct ``time``
      tokens in the artifact. **Omitted** when ``indicator.cadence``
      is ``decennial`` or ``ad_hoc`` (those series have no defined
      cadence, so an observed count framed against a range is
      misleading).
    - ``gap_count_within_range``: ``expected - observed`` at the
      cadence implied by ``indicator.cadence`` (preferred) or
      ``indicator.time_grain`` (fallback). **Omitted** for
      ``decennial``/``ad_hoc`` cadence, for ``time_grain="date"``,
      and when the cadence cannot be inferred.
    - ``time_grain``: mirrored from ``indicator.time_grain``.
    - ``cadence``: mirrored from ``indicator.cadence`` when present
      (so the completeness index can filter by cadence without
      joining the artifact). Omitted when the field is absent.

    Raises
    ------
    ValueError
        When ``rows[].time`` tokens span more than one detected
        vocabulary shape. This indicates an adapter bug — silent omit
        would overload the meaning of "no range" (CLAUDE.md \u00a710).
    """
    rows = indicator_dict.get("rows") or []
    if not rows:
        return None

    ind = indicator_dict.get("indicator") or {}
    grain = str(ind.get("time_grain") or "")
    cadence_raw = ind.get("cadence")
    cadence = str(cadence_raw) if cadence_raw else ""
    ind_id = str(ind.get("id") or "<unknown>")

    times: list[str] = []
    label_for: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or "time" not in row:
            continue
        t = str(row["time"])
        times.append(t)
        if t not in label_for:
            label_for[t] = str(row.get("period_label") or t)

    if not times:
        return None

    distinct_times = sorted(set(times))
    shapes = {_detect_shape(t) for t in distinct_times}
    if len(shapes) > 1:
        raise ValueError(
            f"indicator {ind_id}: heterogeneous rows[].time vocabulary: "
            f"shapes={sorted(shapes)}, sample_tokens={distinct_times[:5]}"
        )
    (shape,) = shapes

    min_time = distinct_times[0]
    max_time = distinct_times[-1]

    out: dict[str, Any] = {
        "min_time": min_time,
        "max_time": max_time,
        "min_period_label": label_for[min_time],
        "max_period_label": label_for[max_time],
    }
    # Mirror time_grain ONLY when set on the indicator. Writing the
    # empty string would conflate "indicator has no grain" with "grain
    # is the empty string" and drift from the TS mirror, which already
    # omits the key on empty. Per Fowler review 2026-05-17.
    if grain:
        out["time_grain"] = grain
    if cadence:
        out["cadence"] = cadence

    # decennial / ad_hoc series have no defined inter-observation
    # interval; omit BOTH observed_periods_within_range and
    # gap_count_within_range so the consumer never frames their
    # complete-by-publisher record as patchy. Per ADR-0027.
    if cadence in _UNDEFINED_CADENCE:
        return out

    out["observed_periods_within_range"] = len(distinct_times)

    expected = _expected_period_count(
        min_time=min_time, max_time=max_time, shape=shape, time_grain=grain
    )
    # `date` grain has no meaningful cadence even on a single snapshot;
    # gap_count_within_range stays absent so the consumer knows not to
    # render a "gaps" pill.
    if expected is not None and grain != "date":
        # Gap count cannot be negative; if observed > expected the cadence
        # inference was wrong (e.g. month grain but artifact has irregular
        # monthly + weekly mix). Surface as ValueError so the operator
        # discovers the inconsistency at emit time, not on the page.
        gap = expected - len(distinct_times)
        if gap < 0:
            raise ValueError(
                f"indicator {ind_id}: observed periods ({len(distinct_times)}) "
                f"exceed expected ({expected}) at grain={grain!r}, shape={shape!r}; "
                f"check cadence assumptions"
            )
        out["gap_count_within_range"] = gap

    return out
