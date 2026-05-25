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

Hans honest-renderer doctrine applies to ALL Pashu Aadhaar indicators:
the count is animals issued a 12-digit Pashu Aadhaar TAG, NOT an
estimate of the actual livestock population. Coverage varies by state
(rollout in progress). Catalogue carries
``comparability="directional_only"`` + ``renderer_rules=["no_rank_table"]``
on every indicator in this lift; the renderer suppresses rank-table
views and labels the choropleth "illustrative, not a ranking".
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import SOURCE_IDS, SPECIES, load_meadow, parse_ndlm_period

# Meadow-path vintage segment - matches the source citation seeded in
# PR #276. The row-level ``time`` field carries the CY-vs-FY distinction.
MEADOW_VINTAGE = "2024-25"


def build_envelope(repo_root: Path) -> BatchEnvelope:
    rows: list[ObservationRow] = []

    source_id = SOURCE_IDS["ndlm_pashu_aadhaar"]

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

    return BatchEnvelope(
        target_family="livestock",
        target_table_stem="livestock_pashu_aadhaar",
        observation_rows=rows,
    )
