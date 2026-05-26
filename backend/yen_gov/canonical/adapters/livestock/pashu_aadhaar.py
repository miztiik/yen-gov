"""Pashu Aadhaar envelope - ``livestock_pashu_aadhaar.parquet``.

Lifts 10 meadow shards (per ADR-0041,
``datasets/livestock/_meadow/ndlm/2024-25/``):

    district-pashu-aadhaar-count-<species>.json   x 10 species

into ``ObservationRow``s on 10 facet-child indicators (one per species).
Each shard carries rows for BOTH NDLM raw vintages (CY 2024 + FY 2024-25);
the row's ``time`` field is the raw vintage selector and is decoded by
``parse_ndlm_period`` into ``(period_label, year, period_seq)``.

The meadow-path vintage segment ``2024-25`` matches the only NDLM source
citation seeded in PR #276 (``src-7e5d4aac4995`` with vintage="2024-25");
per ADR-0041 nn4 + ADR-0042 the meadow-path vintage MUST equal an
existing citation row's vintage.

The parent indicator ``district-pashu-aadhaar-count`` is compute-on-read
per Hans' D33.8 ruling (the parent's value is the sum of the 10 atomic
species children; no observation rows on disk for the parent).

District-level granularity is preserved (user mandate 2026-05-25:
"do not lose the district level data ... even more, granddad is also
if you can retain it, it is important"). Species facet is the second
granularity axis. A third axis (gender: male/female) is retained in
the raw NDLM responses (``.runtime/raw/ndlm/``) and may lift to a
``-male`` / ``-female`` grandchild family in a follow-up PR; the meadow
generator script (``tools/livestock_meadow_pashu_aadhaar.py``) is
prepared to extend without re-downloading raw data.

**State-grain rollup rows** (per ADR-0043, 2026-05-25). After lifting
all district rows, this adapter SUMs district rows by
``(state_prefix, species, period_label)`` and emits 10 NEW state-grain
indicators (``state-pashu-aadhaar-count-<species>``) carrying:

* ``entity_id`` = state-grain prefix (e.g. ``IN-S01`` from
  ``IN-S01-D502``); the trailing ``-D<n>`` is stripped.
* ``value_numeric`` = SUM of district values for that (state, species,
  period).
* ``source_id`` = SAME source as the district rows (ADR-0032 citation
  ledger semantics — rollup is the same producer's data summed, not a
  new fetch event).
* ``derivation = "sum"`` (already legal per ``observation.schema.json``
  v1.1 lines 76-92).
* ``period_label`` / ``year`` / ``period_seq`` inherited verbatim from
  the district rows.

The state-grain PARENT (``state-pashu-aadhaar-count``) is also
compute-on-read; no observation rows emitted (mirrors the district
parent's shape exactly per Hans D33.8).

Hans honest-renderer doctrine applies to ALL Pashu Aadhaar indicators
(district + state grains alike): the count is animals issued a 12-digit
Pashu Aadhaar TAG, NOT an estimate of the actual livestock population.
Coverage varies by state (rollout in progress). Catalogue carries
``comparability="directional_only"`` + ``renderer_rules=["no_rank_table"]``
on every indicator in this lift; the renderer suppresses rank-table
views and labels the choropleth "illustrative, not a ranking".
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import (
    SPECIES,
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


def _lift_snapshot(
    repo_root: Path, vintage: str, source_id: str
) -> list[ObservationRow]:
    """Lift one operator snapshot window's 10 species shards.

    Reads the 10 ``district-pashu-aadhaar-count-<species>.json`` files
    under ``_meadow/ndlm/<vintage>/`` and emits district + state-grain
    rows for each. All rows FK to the same ``source_id`` (one citation
    row per snapshot per ADR-0042).
    """
    rows: list[ObservationRow] = []

    # First pass: lift district-grain rows verbatim (one ObservationRow
    # per meadow row across all 10 species shards).
    for _sp_cd, sp_slug, _sp_display, _sp_noun in SPECIES:
        shard = load_meadow(
            repo_root,
            MEADOW_SOURCE,
            vintage,
            f"district-pashu-aadhaar-count-{sp_slug}.json",
        )
        indicator_id = f"district-pashu-aadhaar-count-{sp_slug}"
        for r in shard["rows"]:
            period_label, year, period_seq = parse_ndlm_period(r["time"])
            rows.append(
                ObservationRow(
                    entity_id=r["entity_id"],
                    year=year,
                    period_label=period_label,
                    period_seq=period_seq,
                    indicator_id=indicator_id,
                    value_numeric=float(r["value"]),
                    source_id=source_id,
                    derivation="raw",
                )
            )

    # Second pass: write-time auto-rollup per ADR-0043. SUM district
    # rows by (state_prefix, species, period_label, year, period_seq);
    # emit one state-grain ObservationRow per group. SAME source_id,
    # SAME period anchors, derivation="sum".
    #
    # Inline (~25 lines incl. dict shaping) per Fowler's "rule of three"
    # verdict on ADR-0043: extract to backend/yen_gov/canonical/rollup.py
    # only after the SECOND district family lands and the duplication
    # is visible. Premature abstraction would lock in a shape (group_by
    # axes, NaN handling, source_id inheritance, period alignment) the
    # second consumer may not fit.
    sums: dict[
        tuple[str, str, str, int, int],  # (state_prefix, species, period_label, year, period_seq)
        float,
    ] = defaultdict(float)
    for row in rows:
        # rows[] currently only contains district-grain district-* ids.
        # Every species slug is the trailing kebab segment.
        species_slug = row.indicator_id.rsplit("-", 1)[-1]
        key = (
            state_prefix(row.entity_id),
            species_slug,
            row.period_label,
            row.year,
            row.period_seq,
        )
        sums[key] += row.value_numeric

    for (state_id, species_slug, period_label, year, period_seq), total in sums.items():
        rows.append(
            ObservationRow(
                entity_id=state_id,
                year=year,
                period_label=period_label,
                period_seq=period_seq,
                indicator_id=f"state-pashu-aadhaar-count-{species_slug}",
                value_numeric=total,
                source_id=source_id,
                derivation="sum",
            )
        )

    return rows


def build_envelope(repo_root: Path) -> BatchEnvelope:
    """Build the Pashu Aadhaar envelope across all snapshots.

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
        source_id = source_id_for("ndlm_pashu_aadhaar", vintage)
        all_rows.extend(_lift_snapshot(repo_root, vintage, source_id))

    return BatchEnvelope(
        target_family="livestock",
        target_table_stem="livestock_pashu_aadhaar",
        observation_rows=all_rows,
    )

