"""Pure predicates extracted from :mod:`yen_gov.validate` Tier-B checks.

This is the **single source of truth** for the per-row rules that both
(a) the pre-flight ingest gate (:mod:`yen_gov.preflight`) evaluates against
a proposed ingest and (b) the Tier-B validators in :mod:`yen_gov.validate`
evaluate against the actual repository state. The Tier-B functions in
``validate.py`` are thin wrappers that load the catalogue / sources tree
and call into these predicates; the parity test
``backend/tests/test_preflight_predicates.py::test_predicate_parity_with_tier_b``
asserts identical violations on the same synthetic fixture so the two
seams never drift.

DRY history: predicate bodies were inlined inside each ``tier_b_*``
function until ADR-0046 split them out so the pre-flight gate (which has
no repo to walk yet) could re-use them.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from yen_gov.canonical.citation import derive_source_id

# Public regex constants (re-used by tier_b wrappers in validate.py so the
# two sites cannot drift on the prefix list).
GRAIN_PREFIX_RE = re.compile(r"^(state|district|national)-")
SOURCE_ID_HEX_RE = re.compile(r'"src-[0-9a-f]{12}"')
SOURCE_IDS_ASSIGN_RE = re.compile(r"^SOURCE_IDS\s*=", re.MULTILINE)

MIN_JUSTIFICATION_LEN = 20


# --- 1. grain prefix ---------------------------------------------------

def grain_prefix_violation(indicator_id: str) -> str | None:
    """Return the offending grain prefix (e.g. ``"state-"``) or ``None``.

    Mirrors :func:`yen_gov.validate.tier_b_indicator_id_no_grain_prefix`
    per-row logic. ADR-0044 grain-over-entity: indicator_id is
    ``<measure>-<unit>-<facet>`` only; grain lives on each observation
    row's ``entity_kind`` column.
    """
    if not isinstance(indicator_id, str):
        return None
    m = GRAIN_PREFIX_RE.match(indicator_id)
    return m.group(0) if m else None


# --- 2. update_period_days --------------------------------------------

def update_period_days_violation(value: Any) -> str | None:
    """Return an error message or ``None`` if cadence is a positive int.

    Mirrors :func:`yen_gov.validate.tier_b_indicator_freshness_declared`
    per-row logic. Booleans are explicitly rejected because Python treats
    ``True`` / ``False`` as ``int`` subclasses but cadence-as-bool is
    never meaningful.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return (
            f"update_period_days must be a positive integer (got {value!r}); "
            f"declare the publisher refresh cadence in days (NDLM monthly=30, "
            f"RBI Handbook annual=365, Census decennial=3650)"
        )
    return None


# --- 3. justification --------------------------------------------------

def justification_violation(value: Any, *, min_len: int = MIN_JUSTIFICATION_LEN) -> str | None:
    """Return an error message or ``None`` if the string is long enough.

    Mirrors :func:`yen_gov.validate.tier_b_indicator_has_justification`
    per-row predicate (the cross-grain-twin filter is in the wrapper).
    """
    if not isinstance(value, str) or len(value.strip()) < min_len:
        return (
            f"meta.justification must be a non-empty string of >= {min_len} "
            f"characters naming the dimension that distinguishes this "
            f"indicator from the nearest existing concept"
        )
    return None


# --- 4. concept_id FK --------------------------------------------------

def concept_id_exists(concept_id: str, concepts: Iterable[dict]) -> bool:
    """Return True if ``concept_id`` resolves in the registry."""
    if not isinstance(concept_id, str) or not concept_id:
        return False
    for row in concepts:
        if isinstance(row, dict) and row.get("concept_id") == concept_id:
            return True
    return False


# --- 5. source_id derivation ------------------------------------------

def source_id_derivation_violation(
    *,
    producer: str,
    title: str,
    vintage: str,
    claimed: str | None,
) -> str | None:
    """Return an error message or ``None`` if ``claimed`` matches the derived id.

    ``claimed`` may be ``None`` (proposal lets the writer derive at lift
    time — the recommended path). Otherwise it MUST equal
    ``derive_source_id(producer, title, vintage)`` per ADR-0032.
    """
    derived = derive_source_id(producer, title, vintage)
    if claimed is None:
        return None
    if claimed != derived:
        return (
            f"source_id={claimed!r} does not match derive_source_id output "
            f"{derived!r} for producer={producer!r} title={title!r} "
            f"vintage={vintage!r}; per CLAUDE.md §12 source_id MUST be "
            f"built via backend.yen_gov.canonical.citation.derive_source_id"
        )
    return None


# --- 6. hand-typed source_id literals (text scan) ----------------------

def hand_typed_source_id_hits(text: str) -> list[tuple[str, int]]:
    """Return ``[(snippet, line_no)]`` for forbidden source_id literals in ``text``.

    Mirrors :func:`yen_gov.validate.tier_b_no_hand_typed_source_id`
    per-file scan logic. Two forbidden patterns:
    ``^SOURCE_IDS\\s*=`` (top-level hash-table assignment) and
    ``"src-<12hex>"`` (raw hex literal).
    """
    hits: list[tuple[str, int]] = []
    for m in SOURCE_IDS_ASSIGN_RE.finditer(text):
        line_no = text[: m.start()].count("\n") + 1
        hits.append(("SOURCE_IDS=", line_no))
    for m in SOURCE_ID_HEX_RE.finditer(text):
        line_no = text[: m.start()].count("\n") + 1
        hits.append((m.group(0), line_no))
    return hits


# --- 7. cross-grain twin clustering (used by justification wrapper) ----

def cross_grain_twin_concepts(rows: Iterable[dict]) -> set[str]:
    """Return set of concept_ids that span >= 2 distinct entity_kinds tuples.

    Pure helper extracted from
    :func:`yen_gov.validate.tier_b_indicator_has_justification`.
    """
    by_concept: dict[str, set[tuple[str, ...]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        concept_id = row.get("concept_id")
        entity_kinds = row.get("entity_kinds")
        if not isinstance(concept_id, str) or not concept_id:
            continue
        if not isinstance(entity_kinds, list):
            continue
        by_concept.setdefault(concept_id, set()).add(
            tuple(sorted(str(k) for k in entity_kinds))
        )
    return {c for c, eks in by_concept.items() if len(eks) >= 2}


# --- 8. concept proliferation clusters (used by per-concept wrapper) --

def concept_proliferation_clusters(
    rows: Iterable[dict],
) -> list[tuple[str, tuple[str, ...], list[str]]]:
    """Return ``[(concept_id, ekinds, [indicator_ids])]`` for clusters >= 2.

    Pure helper extracted from
    :func:`yen_gov.validate.tier_b_one_indicator_per_concept`.
    """
    groups: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        indicator_id = row.get("indicator_id")
        concept_id = row.get("concept_id")
        entity_kinds = row.get("entity_kinds")
        if not isinstance(indicator_id, str):
            continue
        if not isinstance(concept_id, str) or not concept_id:
            continue
        if not isinstance(entity_kinds, list):
            continue
        key = (concept_id, tuple(sorted(str(k) for k in entity_kinds)))
        groups.setdefault(key, []).append(indicator_id)
    return [
        (cid, eks, sorted(ids))
        for (cid, eks), ids in sorted(groups.items())
        if len(ids) >= 2
    ]
