"""Shared helpers for the livestock adapter modules.

Three concerns live here:

* ``SOURCE_IDS`` - the 5 NDLM source_id strings seeded by PR #276
  (livestock_sources_seed.py). Hand-typed verbatim; the writer's FK
  gate verifies closure against the citation ledger before any bytes
  touch disk.
* ``SPECIES`` - the 10-species enumeration (Hans-friendly slug, display
  name, NDLM speciesCd). One pashu_aadhaar facet-child indicator exists
  per slug; canonical observation rows reference the slug in the
  ``-{species}`` suffix.
* ``parse_ndlm_period(time)`` - decode a NDLM vintage string ("2024"
  for CY year, "2024-25" for FY) into the canonical observation triple
  ``(period_label, year, period_seq)`` the writer expects.

Loaders here are deliberately thin (json.loads + path resolution). The
catalogue (``datasets/taxonomy/indicators.json``) is the sole authority
for indicator metadata (attribution_geography, unit, etc.); adapters
read the meadow ``rows[]`` only and rely on the writer's FK gate +
catalogue FK closure for everything else.
"""

from __future__ import annotations

import json
from pathlib import Path


# 5 source_ids seeded by PR #276 (livestock_sources_seed.py).
# DO NOT re-derive these in the adapter - the citation ledger is the
# source of truth, and the writer's FK gate verifies each appears in
# ``datasets/taxonomy/sources.parquet`` before observation rows touch
# disk. If a future PR rotates the source triple
# (``producer | title | vintage``) for any of these, the hash will
# rotate and BOTH the citation seed + this constant must update together.
SOURCE_IDS: dict[str, str] = {
    "ndlm_owner_registration": "src-d98dc531ef7e",
    "ndlm_pashu_aadhaar":      "src-7e5d4aac4995",
    "ndlm_nadcp_vaccination":  "src-1d0c0fbf96e3",
    "ndlm_breeding_abip_rgm":  "src-fb1694ab6a11",
    "ndlm_naip_iv":            "src-93a2a72db482",
}


# (speciesCd, kebab-slug, display name, citizen-readable description noun).
# Derived from the full Pashu Aadhaar corpus walk (.runtime/raw/ndlm/);
# matches the species enumeration in tools/livestock_meadow_pashu_aadhaar.py
# verbatim. The 10 species are the closed set NDLM emits as of vintage
# 2024 / 2024-25; a future vintage that adds an 11th MUST extend this
# tuple AND the indicator catalogue in lockstep.
SPECIES: tuple[tuple[int, str, str, str], ...] = (
    (1,  "cattle",  "Cattle",  "cattle"),
    (2,  "buffalo", "Buffalo", "buffaloes"),
    (3,  "yak",     "Yak",     "yaks"),
    (4,  "mithun",  "Mithun",  "mithun"),
    (5,  "sheep",   "Sheep",   "sheep"),
    (6,  "goat",    "Goat",    "goats"),
    (7,  "pig",     "Pig",     "pigs"),
    (10, "horse",   "Horse",   "horses"),
    (11, "donkey",  "Donkey",  "donkeys"),
    (12, "mule",    "Mule",    "mules"),
)

SPECIES_SLUGS: tuple[str, ...] = tuple(s[1] for s in SPECIES)


def parse_ndlm_period(time: str) -> tuple[str, int, int]:
    """Decode a NDLM vintage string to the canonical observation triple.

    NDLM publishes two vintages per ingest:
        * ``"2024"``    - Calendar Year (Jan-Dec).
        * ``"2024-25"`` - Fiscal Year (Apr-Mar). The yen-gov convention
                           is YEAR-NEXT-YY where YEAR is the FY's start
                           calendar year (so FY 2024-25 begins April 2024).

    Returns:
        (period_label, year, period_seq) where:
        * ``period_label`` is the vintage string verbatim.
        * ``year`` is the integer YYYY (start year for FY).
        * ``period_seq`` is 1 for both grains (NDLM publishes a single
          annual snapshot per vintage; no intra-year period ordering
          is meaningful).

    Raises:
        ValueError on a malformed input - adapters MUST validate at
        the meadow boundary, not silently coerce.
    """
    if not time:
        raise ValueError(f"Empty NDLM period: {time!r}")
    if "-" in time:
        year_s, _ = time.split("-", 1)
        return time, int(year_s), 1
    return time, int(time), 1


def load_meadow(repo_root: Path, source: str, vintage: str, file: str) -> dict:
    """Load a livestock meadow shard from
    ``datasets/livestock/_meadow/<source>/<vintage>/<file>``.

    Meadow tier per ADR-0041: typed, schema-validated, deterministic,
    ``source_id``-bearing JSON parsed from upstream but pre-canonical.
    Backend-internal - frontend MUST NOT fetch these paths (Phase B
    allowlist routes citizen reads to canonical Parquet).

    Returns the raw parsed JSON; the adapter is responsible for
    transforming ``rows[]`` into ``ObservationRow``.

    Args:
        source: short producer identifier, snake_case (e.g. ``"ndlm"``).
        vintage: source's own period label, matches the ``vintage`` field
            of the citation-ledger row in
            ``datasets/taxonomy/sources.parquet``.
        file: descriptor with ``.json`` suffix (e.g.
            ``"district-pashu-aadhaar-count-cattle.json"``).
    """
    p = (
        repo_root
        / "datasets"
        / "livestock"
        / "_meadow"
        / source
        / vintage
        / file
    )
    return json.loads(p.read_text(encoding="utf-8"))
