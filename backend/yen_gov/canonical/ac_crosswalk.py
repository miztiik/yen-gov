"""Assembly-constituency crosswalk: ``eci_no`` <-> ``lgd_ac_id`` binding.

Single home for the ``ac_crosswalk`` Canonical Data Model (one row per
``(state_code, eci_no)``, total over every SoT AC). The crosswalk binds
ECI's per-state ballot number (``eci_no`` - the citizen-facing display +
URL label) to the LGD Assembly Constituency code (``lgd_ac_id`` - the
canonical INTERNAL join key) per ADR-0049.

**Why a dedicated module** (Row A1 of
``TODO/20260530-eci-to-lgd-acid-migration-plan.md``):

* The crosswalk is the ONE seam every downstream cutover row (A3, B1-B3,
  C1) joins against. Co-locating the lookup + the bijection-and-completeness
  invariant here keeps the producer (``tools/migrate/build_ac_crosswalk.py``,
  Row A2) and the consumers (``dim_acs`` lift, frontend join) reading the
  same contract.
* ``assert_bijection`` is the single load-bearing safety net for the whole
  migration. It is introduced here (Row A1, fixture-tested), exercised
  against the real table in Row A2, and re-run every cutover phase. A
  silent crosswalk defect is the canonical undercount trap; this fails at
  the compile boundary with an actionable message rather than surfacing as
  a wrong citizen result months later.

This module is PURE: no I/O, no parquet, no DuckDB. Callers load rows
(from parquet, JSON fixtures, or hand-built dicts) and pass plain mappings
in. That keeps the invariant testable without touching disk.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

#: ``match_method`` value meaning "no LGD code resolved yet" (lgd_ac_id null).
UNMAPPED: str = "unmapped"

#: Allowed ``match_method`` values (mirrors ac-crosswalk.schema.json enum).
MATCH_METHODS: frozenset[str] = frozenset(
    {"lgd_direct", "name_reservation_join", UNMAPPED}
)


class CrosswalkError(ValueError):
    """Raised when the crosswalk violates its bijection/completeness contract.

    Always names the offending key(s) so the failure is actionable at the
    compile boundary rather than surfacing as a wrong result downstream.
    """


def _pk(row: Mapping[str, Any]) -> tuple[str, int]:
    """Return the ``(state_code, eci_no)`` primary key of a crosswalk row."""
    return (str(row["state_code"]), int(row["eci_no"]))


def lookup_lgd_ac_id(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, int], int | None]:
    """Map ``(state_code, eci_no) -> lgd_ac_id`` (None where unmapped).

    The forward direction every consumer needs: given the citizen-facing
    ``(state_code, eci_no)``, return the canonical internal join key. A
    value of ``None`` means the AC is not yet bound to an LGD code and the
    caller must fall back to ``ac_no``/``eci_no``.

    Raises:
        CrosswalkError: if two rows share the same ``(state_code, eci_no)``.
    """
    out: dict[tuple[str, int], int | None] = {}
    for row in rows:
        key = _pk(row)
        if key in out:
            raise CrosswalkError(
                f"duplicate crosswalk PK {key!r}: (state_code, eci_no) must "
                f"be unique (total over every SoT AC)"
            )
        raw = row.get("lgd_ac_id")
        out[key] = None if raw is None else int(raw)
    return out


def lookup_eci_no(
    rows: Iterable[Mapping[str, Any]],
) -> dict[int, tuple[str, int]]:
    """Map ``lgd_ac_id -> (state_code, eci_no)`` over the covered subset.

    The reverse direction (boundary feature keyed on lgd_ac_id -> citizen
    ballot number). Only covered rows (non-null ``lgd_ac_id``) appear.

    Raises:
        CrosswalkError: if two covered rows share the same ``lgd_ac_id``
            (the join key must be globally unique).
    """
    out: dict[int, tuple[str, int]] = {}
    for row in rows:
        raw = row.get("lgd_ac_id")
        if raw is None:
            continue
        lgd = int(raw)
        key = _pk(row)
        if lgd in out:
            raise CrosswalkError(
                f"duplicate lgd_ac_id {lgd!r} bound to both {out[lgd]!r} and "
                f"{key!r}: the LGD join key must be globally unique"
            )
        out[lgd] = key
    return out


def assert_bijection(
    rows: Sequence[Mapping[str, Any]],
    sot_acs: Iterable[tuple[str, int]] | None = None,
) -> None:
    """Assert the crosswalk's bijection-and-completeness contract.

    The single load-bearing safety net for the eci_no -> lgd_ac_id
    migration. Checks, in order:

    1. **PK uniqueness** - ``(state_code, eci_no)`` is unique.
    2. **match_method validity** - every row's ``match_method`` is a known
       enum value, and ``lgd_ac_id IS NULL`` iff ``match_method == 'unmapped'``.
    3. **lgd_ac_id global uniqueness** - no two covered rows share a code.
    4. **strict bijection on the covered subset** - the forward map
       ``(state_code, eci_no) -> lgd_ac_id`` and the reverse map
       ``lgd_ac_id -> (state_code, eci_no)`` are mutual inverses.
    5. **completeness** (only when ``sot_acs`` is given) - every SoT
       ``(state_code, eci_no)`` has exactly one crosswalk row and the
       crosswalk introduces no rows absent from the SoT (total, no extras).

    Args:
        rows: the crosswalk rows (parquet-loaded dicts or fixtures).
        sot_acs: optional ground-truth set of ``(state_code, eci_no)``
            pairs the crosswalk must cover exactly. When omitted, only
            internal consistency (checks 1-4) is asserted.

    Raises:
        CrosswalkError: on the first violation, naming the offending key.
    """
    rows = list(rows)

    # 1 + 2: PK uniqueness + match_method validity, in one pass.
    seen_pk: set[tuple[str, int]] = set()
    for row in rows:
        key = _pk(row)
        if key in seen_pk:
            raise CrosswalkError(
                f"duplicate crosswalk PK {key!r}: (state_code, eci_no) must "
                f"be unique"
            )
        seen_pk.add(key)

        method = row.get("match_method")
        if method not in MATCH_METHODS:
            raise CrosswalkError(
                f"row {key!r} has invalid match_method {method!r}; "
                f"expected one of {sorted(MATCH_METHODS)}"
            )
        is_null = row.get("lgd_ac_id") is None
        is_unmapped = method == UNMAPPED
        if is_null != is_unmapped:
            raise CrosswalkError(
                f"row {key!r} violates the null/unmapped invariant: "
                f"lgd_ac_id IS NULL ({is_null}) must equal "
                f"match_method == 'unmapped' ({is_unmapped})"
            )

    # 3 + 4: global uniqueness of lgd_ac_id + strict bijection. lookup_eci_no
    # raises on a duplicate code; the forward/reverse round-trip then proves
    # mutual inversion over the covered subset.
    forward = lookup_lgd_ac_id(rows)
    reverse = lookup_eci_no(rows)
    for key, lgd in forward.items():
        if lgd is None:
            continue
        back = reverse.get(lgd)
        if back != key:
            raise CrosswalkError(
                f"bijection broken at {key!r}: forward maps to lgd_ac_id "
                f"{lgd!r} but reverse maps that code to {back!r}"
            )

    # 5: completeness against the SoT ground truth (exact cover).
    if sot_acs is not None:
        sot_set = {(str(s), int(n)) for s, n in sot_acs}
        missing = sot_set - seen_pk
        if missing:
            raise CrosswalkError(
                f"crosswalk is missing {len(missing)} SoT AC(s): "
                f"{sorted(missing)[:10]}"
            )
        extra = seen_pk - sot_set
        if extra:
            raise CrosswalkError(
                f"crosswalk has {len(extra)} row(s) absent from the SoT: "
                f"{sorted(extra)[:10]}"
            )
