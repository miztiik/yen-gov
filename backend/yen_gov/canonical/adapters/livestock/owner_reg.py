"""Owner Registration envelope - ``livestock_owner_registration.parquet``.

Lifts 1 meadow shard (per ADR-0041,
``datasets/livestock/_meadow/ndlm/2024-25/owner_reg_land_holding_district.json``)
into ``ObservationRow``s on 6 facet-child indicators (one per
land-holding bracket), then auto-rolls up to state grain per ADR-0043.

**Two-axis publisher cell, one-axis lift (Approach B)**:

The NDLM Owner Registration meadow row carries TWO facet axes -
``landholding`` (6 brackets) AND ``gender`` (male/female). Each meadow
row is one (district, landholding, gender, year) cell. This adapter
collapses the ``gender`` axis at write time via SUM, lifting at
(district, landholding, year) granularity only. The 6 resulting
facet-child indicators carry ``derivation="sum"`` to honestly tag the
within-cell collapse.

Why defer gender: the pashu_aadhaar precedent established the
convention - publisher gender splits are preserved in the meadow but
not lifted to canonical indicator children in the first slice
(``-male`` / ``-female`` grandchild family is a future PR if Hans flags
sufficient citizen value). Owner Registration follows the same rhythm
to keep PR sequencing predictable.

**State-grain rollup** (ADR-0043, mirrors pashu_aadhaar). After the
first-pass district lift, SUM district rows by (state_prefix,
landholding, period_label, year, period_seq) and emit 6 NEW state-grain
indicators carrying:

* ``entity_id`` = state-grain prefix (e.g. ``IN-S01``); trailing
  ``-D<n>`` stripped.
* ``value_numeric`` = SUM of district values for that (state,
  landholding, period).
* ``source_id`` = SAME as district rows (ADR-0032 citation ledger).
* ``derivation = "sum"`` (a second SUM over the already-collapsed
  district rows; honest per ADR-0043).

The parents (``district-livestock-owner-reg-count`` /
``state-livestock-owner-reg-count``) are compute-on-read; no
observation rows emitted (mirrors pashu_aadhaar's parent shape).

Hans honest-renderer doctrine: "Owner Registration count" is the count
of livestock owners who have completed Bharat Pashudhan registration,
NOT the actual count of livestock-owning households in the district.
Coverage varies by state (rollout in progress; landholding self-declared
without verification; gender split publisher-emitted but not lifted in
this PR). The catalogue carries ``comparability="directional_only"`` +
``renderer_rules=["no_rank_table"]`` on every indicator in this lift;
the renderer suppresses rank-table views and labels the choropleth
"illustrative, not a ranking".

The first consumer of ``yen_gov.canonical.lgd.load_district_lookup`` is
NOT this adapter - the meadow row carries ``entity_id`` already
resolved (the meadow generator did the LGD->entity_id translation).
This adapter reads the resolved ``entity_id`` verbatim. The LGD module
is consumed by future meadow generator tools.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import (
    discover_meadow_snapshots,
    load_meadow,
    parse_ndlm_period,
    source_id_for,
    state_prefix,
)

# Meadow source identifier (matches the dir layout
# datasets/livestock/_meadow/<source>/<snapshot>/). The vintage
# segment is discovered at run time via ``discover_meadow_snapshots``;
# no hardcoded vintage literal lives in this module.
MEADOW_SOURCE = "ndlm"

# 6 land-holding brackets the publisher emits. Snake_case literal here
# matches the FacetAxisValue value_id pattern (underscores allowed);
# the kebab translation for indicator_id suffixes is via
# LANDHOLDING_TO_SLUG below. The closed set is mirrored in
# ``backend/yen_gov/canonical/facet_axes_seed.py`` (axis_id="landholding");
# a future vintage that adds a 7th bracket MUST extend BOTH the seed
# AND this tuple in lockstep.
LANDHOLDING_BRACKETS: tuple[str, ...] = (
    "landless_marginal",
    "small",
    "semi_medium",
    "medium",
    "large",
    "not_specified",
)

# Translate snake_case landholding value_id -> kebab-case indicator_id
# suffix. Indicator IDs forbid underscores
# (pattern ``^[a-z][a-z0-9]*(-[a-z0-9]+)*$``); FacetAxisValue value_ids
# allow underscores. The two namespaces must NOT collide.
LANDHOLDING_TO_SLUG: dict[str, str] = {
    "landless_marginal": "landless-marginal",
    "small": "small",
    "semi_medium": "semi-medium",
    "medium": "medium",
    "large": "large",
    "not_specified": "not-specified",
}


def _lift_snapshot(
    repo_root: Path, vintage: str, source_id: str
) -> list[ObservationRow]:
    """Lift one operator snapshot window's rows into observations.

    Loads ``owner_reg_land_holding_district.json`` from the named
    snapshot dir, SUMs the gender axis (Approach B), then auto-rolls
    up to state grain per ADR-0043. All rows in the returned list FK
    to the same ``source_id`` (one citation row per snapshot per
    ADR-0042).
    """
    rows: list[ObservationRow] = []
    shard = load_meadow(
        repo_root,
        MEADOW_SOURCE,
        vintage,
        "owner_reg_land_holding_district.json",
    )

    # First pass: collapse the gender axis via SUM, lifting one row per
    # (district, landholding, vintage). Key on
    # (entity_id, landholding, period_label, year, period_seq) so male+
    # female counts in the same district-landholding-vintage cell fold
    # into a single observation row.
    cells: dict[
        tuple[str, str, str, int, int],  # (entity_id, landholding, period_label, year, period_seq)
        float,
    ] = defaultdict(float)
    for r in shard["rows"]:
        # The facet column carries "<landholding>|<gender>"; split and
        # discard the gender component (deferred to a follow-up PR).
        facet = r["facet"]
        landholding, _gender = facet.split("|", 1)
        if landholding not in LANDHOLDING_TO_SLUG:
            # Defensive - the FacetAxis seed is the closed set; a row
            # with an unknown bracket is a publisher schema rotation
            # that needs caller attention BEFORE the writer FK gate
            # would catch it on a phantom indicator_id.
            raise ValueError(
                f"Unknown landholding bracket {landholding!r} in meadow "
                f"row {r!r}. Extend LANDHOLDING_BRACKETS + "
                f"facet_axes_seed.py axis_id='landholding' first."
            )
        period_label, year, period_seq = parse_ndlm_period(r["time"])
        key = (r["entity_id"], landholding, period_label, year, period_seq)
        cells[key] += float(r["value"])

    for (entity_id, landholding, period_label, year, period_seq), total in cells.items():
        slug = LANDHOLDING_TO_SLUG[landholding]
        rows.append(
            ObservationRow(
                entity_id=entity_id,
                year=year,
                period_label=period_label,
                period_seq=period_seq,
                indicator_id=f"livestock-owner-reg-count-{slug}",
                value_numeric=total,
                source_id=source_id,
                derivation="sum",
            )
        )

    # Second pass: write-time auto-rollup per ADR-0043. SUM district
    # rows by (state_prefix, landholding, period_label, year, period_seq);
    # emit one state-grain ObservationRow per group. SAME source_id,
    # SAME period anchors, derivation="sum" (a second SUM atop the
    # already-collapsed district rows; ADR-0043 permits this).
    sums: dict[
        tuple[str, str, str, int, int],  # (state_prefix, landholding_slug, period_label, year, period_seq)
        float,
    ] = defaultdict(float)
    for row in rows:
        # rows[] currently only contains district-grain district-* ids.
        # The landholding-slug is whatever follows the "count-" prefix.
        slug = row.indicator_id.split("count-", 1)[-1]
        key = (
            state_prefix(row.entity_id),
            slug,
            row.period_label,
            row.year,
            row.period_seq,
        )
        sums[key] += row.value_numeric

    for (state_id, slug, period_label, year, period_seq), total in sums.items():
        rows.append(
            ObservationRow(
                entity_id=state_id,
                year=year,
                period_label=period_label,
                period_seq=period_seq,
                indicator_id=f"livestock-owner-reg-count-{slug}",
                value_numeric=total,
                source_id=source_id,
                derivation="sum",
            )
        )

    return rows


def build_envelope(repo_root: Path) -> BatchEnvelope:
    """Build the Owner Registration envelope across all snapshots.

    Iterates every dir under ``datasets/livestock/_meadow/ndlm/`` and
    lifts one batch per snapshot. Each batch's observation rows FK to
    a vintage-specific ``source_id`` derived via ``source_id_for``
    (per ADR-0042: live-fetch endpoints get one citation row per
    operator snapshot window). The FY 2010-11..2025-26 range lifted
    in 2026-05 lives inside the single ``2024-25`` snapshot's meadow
    file via row-level ``time`` field; a future re-snapshot is
    auto-picked up by this loop without code change.
    """
    all_rows: list[ObservationRow] = []
    for vintage in discover_meadow_snapshots(repo_root, MEADOW_SOURCE):
        source_id = source_id_for("ndlm_owner_registration", vintage)
        all_rows.extend(_lift_snapshot(repo_root, vintage, source_id))

    return BatchEnvelope(
        target_family="livestock",
        target_table_stem="livestock_owner_registration",
        observation_rows=all_rows,
    )
