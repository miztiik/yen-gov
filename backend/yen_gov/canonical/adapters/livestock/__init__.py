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
against ``datasets/taxonomy/sources.parquet`` before any bytes touch
disk.

Hans+Max (data shape) + Gregor (contract) authorities apply per
CLAUDE.md §0a.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope

from .pashu_aadhaar import build_envelope as _build_pashu_aadhaar


def build_envelopes(repo_root: Path) -> list[BatchEnvelope]:
    """Build all livestock envelopes in canonical write-order.

    First slice ships 1 envelope (pashu_aadhaar). Follow-up PRs in the
    Path A sprint will add owner_registration, nadcp_vaccination, and
    naip_iv envelopes here; each emits to its own ``livestock_*``
    parquet and shares only the cross-family ``sources.parquet``
    (already seeded by PR #276).
    """
    return [
        _build_pashu_aadhaar(repo_root),
    ]
