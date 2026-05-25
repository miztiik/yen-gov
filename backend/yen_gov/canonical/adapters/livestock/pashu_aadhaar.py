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

from ._shared import SOURCE_IDS, SPECIES, load_meadow, parse_ndlm_period

# Meadow-path vintage segment - matches the source citation seeded in
# PR #276. The row-level ``time`` field carries the CY-vs-FY distinction.
MEADOW_VINTAGE = "2024-25"


def _state_prefix(district_entity_id: str) -> str:
    """Derive the state-grain entity_id from a district entity_id.

    Examples:
        ``IN-S01-D502`` -> ``IN-S01``
        ``IN-U08-D640`` -> ``IN-U08``

    Strips the trailing ``-D<n>`` segment via rsplit. Raises if the
    input doesn't match the district shape (defensive — meadow rows
    are pre-validated but the rollup contract is load-bearing per
    ADR-0043 and a silent miss here would undercount the state).
    """
    if "-D" not in district_entity_id:
        raise ValueError(
            f"Expected district entity_id of shape 'IN-S<n>-D<n>' or "
            f"'IN-U<n>-D<n>'; got {district_entity_id!r}"
        )
    prefix, _district_suffix = district_entity_id.rsplit("-D", 1)
    return prefix


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    source_id = SOURCE_IDS["ndlm_pashu_aadhaar"]

    # First pass: lift district-grain rows verbatim (one ObservationRow
    # per meadow row across all 10 species shards).
    for _sp_cd, sp_slug, _sp_display, _sp_noun in SPECIES:
        shard = load_meadow(
            repo_root,
            "ndlm",
            MEADOW_VINTAGE,
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
            _state_prefix(row.entity_id),
            species_slug,
            row.period_label,
            row.year,
            row.period_seq,
        )
        sums[key] += row.value_numeric

    for (state_prefix, species_slug, period_label, year, period_seq), total in sums.items():
        rows.append(
            ObservationRow(
                entity_id=state_prefix,
                year=year,
                period_label=period_label,
                period_seq=period_seq,
                indicator_id=f"state-pashu-aadhaar-count-{species_slug}",
                value_numeric=total,
                source_id=source_id,
                derivation="sum",
            )
        )

    return BatchEnvelope(
        target_family="livestock",
        target_table_stem="livestock_pashu_aadhaar",
        observation_rows=rows,
    )

