"""Livestock adapter - lifts NDLM (Bharat Pashudhan / National Digital
Livestock Mission) meadow shards into BatchEnvelopes for the canonical
Parquet store.

First slice (this module): ``livestock_pashu_aadhaar`` fact-table emits
10 per-species facet-child indicators at DISTRICT granularity
(``district-pashu-aadhaar-count-<species>``). The parent indicator
``district-pashu-aadhaar-count`` is compute-on-read per Hans' D33.8
ruling.

User mandate 2026-05-25 (citizen-honest data shape): district
granularity is preserved; species granularity (facet axis) is preserved.
Gender granularity (a third axis on the raw NDLM responses) is retained
in ``.runtime/raw/ndlm/`` and may lift in a follow-up PR.

Source provenance: all 10 species indicators FK to
``src-7e5d4aac4995`` (ndlm_pashu_aadhaar) seeded by PR #276
(livestock_sources_seed.py). The writer's FK gate verifies closure
against ``datasets/data/entities/source.csv`` before any bytes touch
disk.

Hans+Max (data shape) + Gregor (contract) authorities apply per
CLAUDE.md §0a.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope

from .naip_iv import build_envelope as _build_naip_iv
from .owner_reg import build_envelope as _build_owner_reg
from .pashu_aadhaar import build_envelope as _build_pashu_aadhaar


#: Canonical write-order stems. Single source of truth for ``--table``
#: CLI validation (PR-A4).
KNOWN_TARGET_TABLE_STEMS: frozenset[str] = frozenset({
    "livestock_pashu_aadhaar",
    "livestock_owner_registration",
    "livestock_naip_iv",
})


def build_envelopes(
    repo_root: Path,
    *,
    only: set[str] | None = None,
) -> list[BatchEnvelope]:
    """Build all livestock envelopes in canonical write-order.

    First slice ships 3 envelopes (pashu_aadhaar, owner_registration,
    naip_iv). Follow-up PRs in the Path A sprint will add
    nadcp_vaccination and breeding (abip + rgm) envelopes here; each
    emits to its own ``livestock_*`` parquet and shares only the
    cross-family ``sources.parquet`` (already seeded by PR #276).

    ``only`` (PR-A4): when provided, restrict the returned envelope list
    to those whose ``target_table_stem`` is in the set. Unknown stems
    raise ``ValueError`` BEFORE any meadow JSON is read.
    """
    if only is not None:
        unknown = sorted(only - KNOWN_TARGET_TABLE_STEMS)
        if unknown:
            raise ValueError(
                f"unknown livestock table stem(s): {unknown!r}; "
                f"known: {sorted(KNOWN_TARGET_TABLE_STEMS)!r}"
            )
    builders = [
        ("livestock_pashu_aadhaar", _build_pashu_aadhaar),
        ("livestock_owner_registration", _build_owner_reg),
        ("livestock_naip_iv", _build_naip_iv),
    ]
    return [
        builder(repo_root)
        for stem, builder in builders
        if only is None or stem in only
    ]
