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

from yen_gov.canonical.citation import derive_source_id, lookup_source_id
from yen_gov.canonical.livestock_sources_seed import (
    LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE,
    LIVESTOCK_SOURCE_ID_BY_NICKNAME,
)


# 5 source_ids materialised from livestock_sources_seed.py at the
# default operator snapshot window. Kept as a back-compat alias for
# callers that pre-date the multi-vintage architecture (2026-05-26);
# new code uses ``source_id_for(nickname, vintage)`` so the source_id
# rotates per snapshot window without a hand-typed constant table.
# The writer's FK gate verifies closure against
# ``datasets/taxonomy/sources.parquet`` before any bytes touch disk.
SOURCE_IDS: dict[str, str] = dict(LIVESTOCK_SOURCE_ID_BY_NICKNAME)


def source_id_for(
    nickname: str,
    vintage: str,
    *,
    sources_path: Path | None = None,
) -> str:
    """Derive the source_id for one (livestock endpoint, vintage) pair.

    Adapters call this once per discovered meadow snapshot dir to FK
    observation rows to the correct citation row. The (producer, title)
    pair comes from ``livestock_sources_seed.py``'s
    ``LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE`` map (the IDENTITY half of
    the citation triple); vintage is the per-snapshot parameter.

    When ``sources_path`` is provided AND the parquet exists (PR-A6),
    the source_id is looked up from the citation ledger via
    :func:`lookup_source_id` so the FK is verified at adapter time
    rather than only at the writer's gate. When omitted, or when the
    ledger is absent (test fixtures with synthetic repo roots), falls
    back to :func:`derive_source_id` -- the writer's FK gate remains
    the structural backstop.

    Per ADR-0042 (vintage = operator snapshot window for live-fetch
    sources without a publisher edition tag), vintage MUST match an
    existing citation row in ``datasets/taxonomy/sources.parquet`` or
    the writer's FK gate will reject the batch.

    Per ADR-0041 nn4, vintage MUST also match the meadow dir name the
    rows were loaded from (strict equality, enforced Tier-B). The
    caller therefore always passes the meadow dir name as vintage;
    NEVER a different label.

    Raises:
        ValueError if nickname is not one of the 5 seeded livestock
        nicknames (defensive: a typo here would emit observation rows
        with a phantom source_id that the FK gate catches later but
        with a less useful error message).
        LookupError if ``sources_path`` is provided but the triple has
        no matching row in the citation ledger.
    """
    if nickname not in LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE:
        valid = sorted(LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE)
        raise ValueError(
            f"Unknown livestock source nickname {nickname!r}; "
            f"valid nicknames: {valid}"
        )
    producer, title = LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE[nickname]
    if sources_path is not None and sources_path.exists():
        return lookup_source_id(
            producer, title, vintage, sources_path=sources_path
        )
    return derive_source_id(producer, title, vintage)


def discover_meadow_snapshots(
    repo_root: Path, source: str = "ndlm"
) -> tuple[str, ...]:
    """Discover all operator snapshot window dirs under the family meadow.

    Returns the sorted list of dir names found under
    ``datasets/livestock/_meadow/<source>/`` -- each represents one
    operator snapshot window per ADR-0042. Adapters iterate this list
    and emit one batch of observation rows per snapshot, FK'd via
    ``source_id_for(nickname, snapshot)`` to the matching citation row.

    Today this returns ``("2024-25",)`` -- one snapshot window pulled
    in the May 2026 operator session. A future re-snapshot (e.g. next
    FY) lands a new dir like ``"2025-26"`` and is auto-picked up by
    every adapter without code edits.

    Raises:
        ValueError if no snapshot dirs are present (empty family --
        adapters should not be invoked at all in this state; emit-time
        fail-loud is honest).
    """
    base = repo_root / "datasets" / "livestock" / "_meadow" / source
    snapshots = tuple(
        sorted(p.name for p in base.iterdir() if p.is_dir())
    ) if base.is_dir() else ()
    if not snapshots:
        raise ValueError(
            f"No meadow snapshot dirs found under {base}. The livestock "
            f"adapters cannot emit observation rows; run the meadow lift "
            f"tools (tools/livestock_meadow_*.py) first."
        )
    return snapshots


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


def state_prefix(district_entity_id: str) -> str:
    """Derive the state-grain entity_id from a district entity_id.

    Examples:
        ``IN-S01-D502`` -> ``IN-S01``
        ``IN-U08-D640`` -> ``IN-U08``

    Strips the trailing ``-D<n>`` segment via rsplit. Raises
    ``ValueError`` if the input doesn't match the district shape -
    meadow rows are pre-validated but the ADR-0043 rollup contract is
    load-bearing and a silent miss here would undercount the state.

    Extracted to ``_shared`` per Fowler rule-of-three: pashu_aadhaar
    (PR #281), owner_reg (PR #303), and naip_iv (this PR) all need the
    same shape. Future livestock adapters wire here; future
    cross-family adapters with the same district pattern may eventually
    promote this to ``yen_gov.canonical.rollup``.
    """
    if "-D" not in district_entity_id:
        raise ValueError(
            f"Expected district entity_id of shape 'IN-S<n>-D<n>' or "
            f"'IN-U<n>-D<n>'; got {district_entity_id!r}"
        )
    prefix, _district_suffix = district_entity_id.rsplit("-D", 1)
    return prefix
