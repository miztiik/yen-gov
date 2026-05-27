"""Capacity-pipeline envelope -- ``energy_capacity_pipeline.parquet``.

Layer 3 (Enrich) + Layer 4 (Emit) of the ICED plantPipelineInfo ingest,
per the four-layer doctrine
([docs/concepts/ingest-fetch-enrich-separation.md]) and ADR-0046
pre-flight gate (proposal + report under
``TODO/20260527-iced-plant-pipeline-ingest/``).

Reads the meadow snapshot persisted by
``yen_gov.sources.iced_power.fetch_pipeline.fetch_plant_pipeline_info``
(layer 1) at ``datasets/energy/_meadow/iced/2026-05-27/plant_pipeline_info.json``,
runs it through the pure parser
``yen_gov.sources.iced_power.parsers.parse_plant_pipeline_info`` (layer 2),
collapses the two publisher ``status`` facets ("Under Construction and
likely to be commissioned" + "Under Construction but on Hold") to one
TOTAL pipeline value per (entity=IN, calendar-year) cell via SUM, and
emits canonical observation rows under indicator_id
``under-construction-capacity-gw``.

Why SUM-collapse the status facet rather than emit per-status children:
the canonical ``ObservationRow`` PK is (entity_id, year, period_label,
indicator_id) and carries no facet column; encoding the 2-value status
axis as per-facet child indicators would mint two new ``indicator_id``
rows (``-likely-to-be-commissioned`` / ``-on-hold``) which scopes beyond
this PR's single-id proposal. The status breakdown is preserved verbatim
in the meadow JSON; a follow-up PR can promote it to facet children if
a citizen-surface needs the split.

Grain: ``country`` (single ``entity_id="IN"``). Calendar-year time axis
(``period_label = "YYYY"``, ``period_seq = 1``). Publisher 2022 gap is
preserved verbatim per CLAUDE.md publisher-vocabulary discipline.

source_id is looked up via the ``SOURCE_IDS`` registry in
``_shared.py``; the hash is derived from the citation triple
(``"NITI Aayog India Climate & Energy Dashboard"``, ``"Plant Pipeline
Info National API (...)"``, ``"2026-05-27"``) at seed time -- never
hand-typed in observation-stamping call sites.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope, ObservationRow

from ._shared import SOURCE_IDS, load_meadow


#: Vintage matches the upstream Last-Modified date the layer-1 fetcher
#: persisted into the meadow path (ADR-0041 ``_meadow/<source>/<vintage>``
#: grammar). Update only when a new snapshot is committed; the writer's
#: source_id FK gate ties this vintage to the citation-ledger row.
_MEADOW_VINTAGE = "2026-05-27"


def build_envelope(repo_root: Path) -> BatchEnvelope:
    """Build the single-stem ``energy_capacity_pipeline`` envelope.

    20 calendar-year cells x 2 status facets in the meadow -> 20 rows
    after status SUM-collapse (one TOTAL pipeline GW per year). The 2022
    publisher gap survives the collapse (cell is absent in meadow, absent
    here -- not zero-filled).
    """
    shard = load_meadow(
        repo_root, "energy", "iced", _MEADOW_VINTAGE, "plant_pipeline_info.json",
    )

    # Status SUM-collapse: aggregate over the 2 publisher status labels
    # to one value per (entity_id, calendar-year). Sorted for stable
    # observation_id assignment downstream.
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for r in shard["rows"]:
        totals[(r["entity_id"], r["time"])] += float(r["value"])

    src = SOURCE_IDS["iced_plant_pipeline"]
    rows: list[ObservationRow] = []
    for (entity_id, time_s), value in sorted(totals.items()):
        # time format is "YYYY" calendar-year (4-char) per the parser
        # contract (verified by test_plant_pipeline_info_emits_country_year_status_rows).
        year = int(time_s)
        rows.append(
            ObservationRow(
                entity_id=entity_id,
                year=year,
                period_label=time_s,
                period_seq=1,
                indicator_id="under-construction-capacity-gw",
                value_numeric=value,
                source_id=src,
                derivation="sum",
            )
        )

    return BatchEnvelope(
        target_family="energy",
        target_table_stem="energy_capacity_pipeline",
        observation_rows=rows,
    )
