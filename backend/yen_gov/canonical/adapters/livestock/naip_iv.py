"""NAIP IV envelope - ``livestock_naip_iv.parquet``.

Lifts 1 meadow shard (per ADR-0041,
``datasets/livestock/_meadow/ndlm/2024-25/naip_iv_district.json``) into
``ObservationRow``s on 4 stand-alone metric_family indicators, then
auto-rolls up to state grain per ADR-0043.

**Four-metric publisher cells, four indicators (no parent)**:

NAIP IV (National Artificial Insemination Programme, phase IV) records
four operational outputs per district: insemination events, pregnancy
diagnoses, calves born (publisher splits by sex), and farmers
benefitted. These four are NOT summable - inseminations + pregnancies
+ calves + farmers is a category mistake. Phase 2.C therefore emits
4 stand-alone indicators (no parent, no compute-on-read total) at each
of the two grains (district SoT, state SUM rollup) = 8 catalogue rows.

**Sex collapse (Approach B, matches Phase 2.A)**:

The publisher splits ``calves_born`` into ``calves_born|m`` and
``calves_born|f`` cells; the other three metric families carry only
``<metric>|none``. This adapter SUMs the sex axis during Pass 1 so
``calves_born`` lifts as a single metric. Preserving sex would require
a new ``sex`` FacetAxis + 2 grandchild indicators
(``calves-born-male``, ``calves-born-female``); deferred to a follow-up
PR after Hans audits the citizen copy for sex-stratified output.

**State-grain rollup** (ADR-0043, mirrors pashu_aadhaar + owner_reg).
After the first-pass district lift, SUM district rows by
(state_prefix, metric_family, period_label, year, period_seq) and emit
4 NEW state-grain indicators carrying:

* ``entity_id`` = state-grain prefix (e.g. ``IN-S01``); trailing
  ``-D<n>`` stripped via the shared ``state_prefix`` helper.
* ``value_numeric`` = SUM of district values for that (state, metric,
  period).
* ``source_id`` = SAME as district rows (ADR-0032 citation ledger).
* ``derivation = "sum"`` (a second SUM atop the already-collapsed
  district rows; honest per ADR-0043).

**Zero-coverage states are absent, not zero**: 8 states/UTs (Kerala,
Punjab, Puducherry, Chandigarh, Delhi, Lakshadweep, A&N, D&NH+D&D)
report no NAIP IV districts in the publisher's response. The meadow
file has zero rows for those districts; the rollup therefore produces
no state-grain row. This is correct: NAIP IV is a select-district
programme, and a missing state is genuinely out-of-scope, not a
zero-result. Hans's known_caveats[] on the descriptor surface this
honesty cue in the citizen-facing About-this-data panel.

Hans honest-renderer doctrine:

* AI counts are EVENTS (repeat inseminations on the same dam are
  counted multiple times); NOT unique animals.
* Pregnancy diagnoses are EVENTS (a single dam may be diagnosed
  multiple times in the same vintage).
* Calves born are biological outputs; the publisher splits by sex but
  Phase 2.C collapses (see above).
* Farmers benefitted is a count of unique farmers reached, not
  inseminations performed.

The catalogue carries ``comparability="directional_only"`` +
``renderer_rules=["no_rank_table"]`` on every indicator in this lift;
the renderer suppresses rank-table views and labels the choropleth
"illustrative, not a ranking".
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

# 4 metric families the publisher emits. The composite facet on each
# meadow row is ``<metric_family>|<sex>``; this adapter SUMs sex
# (Approach B) so only the metric family axis survives.
METRIC_FAMILIES: tuple[str, ...] = (
    "inseminations",
    "pregnancy_diagnoses",
    "calves_born",
    "farmers_benefitted",
)

# Translate snake_case metric family -> kebab-case indicator_id suffix.
# Indicator IDs forbid underscores
# (pattern ``^[a-z][a-z0-9]*(-[a-z0-9]+)*$``); the meadow facet vocab
# is snake_case. The two namespaces must NOT collide.
METRIC_TO_SLUG: dict[str, str] = {
    "inseminations": "inseminations",
    "pregnancy_diagnoses": "pregnancy-diagnoses",
    "calves_born": "calves-born",
    "farmers_benefitted": "farmers-benefitted",
}


def _lift_snapshot(
    repo_root: Path, vintage: str, source_id: str
) -> list[ObservationRow]:
    """Lift one operator snapshot window's rows into observations.

    Loads ``naip_iv_district.json`` from the named snapshot dir, SUMs
    the sex axis (Approach B), then auto-rolls up to state grain per
    ADR-0043. All rows in the returned list FK to the same ``source_id``
    (one citation row per snapshot per ADR-0042; the publisher's
    ``{year:}`` query parameter rides each row's ``period_label``).
    """
    rows: list[ObservationRow] = []
    shard = load_meadow(
        repo_root,
        MEADOW_SOURCE,
        vintage,
        "naip_iv_district.json",
    )

    # First pass: collapse the sex axis via SUM, lifting one row per
    # (district, metric_family, vintage). Key on
    # (entity_id, metric_family, period_label, year, period_seq) so
    # calves_born|m + calves_born|f in the same district-vintage cell
    # fold into a single observation row. The other three metric
    # families only have ``|none`` so this is a no-op for them.
    cells: dict[
        tuple[str, str, str, int, int],  # (entity_id, metric_family, period_label, year, period_seq)
        float,
    ] = defaultdict(float)
    for r in shard["rows"]:
        # The facet column carries "<metric_family>|<sex>"; split and
        # discard the sex component (deferred to a follow-up PR).
        facet = r["facet"]
        metric_family, _sex = facet.split("|", 1)
        if metric_family not in METRIC_TO_SLUG:
            # Defensive - the four metric families are the closed set;
            # a row with an unknown family is a publisher schema
            # rotation that needs caller attention BEFORE the writer
            # FK gate would catch it on a phantom indicator_id.
            raise ValueError(
                f"Unknown NAIP IV metric_family {metric_family!r} in meadow "
                f"row {r!r}. Extend METRIC_FAMILIES + METRIC_TO_SLUG first."
            )
        period_label, year, period_seq = parse_ndlm_period(r["time"])
        key = (r["entity_id"], metric_family, period_label, year, period_seq)
        cells[key] += float(r["value"])

    for (entity_id, metric_family, period_label, year, period_seq), total in cells.items():
        slug = METRIC_TO_SLUG[metric_family]
        rows.append(
            ObservationRow(
                entity_id=entity_id,
                year=year,
                period_label=period_label,
                period_seq=period_seq,
                indicator_id=f"district-livestock-naip-iv-{slug}",
                value_numeric=total,
                source_id=source_id,
                derivation="sum",
            )
        )

    # Second pass: write-time auto-rollup per ADR-0043. SUM district
    # rows by (state_prefix, metric_family, period_label, year,
    # period_seq); emit one state-grain ObservationRow per group.
    # SAME source_id, SAME period anchors, derivation="sum" (a second
    # SUM atop the already-collapsed district rows; ADR-0043 permits
    # this).
    sums: dict[
        tuple[str, str, str, int, int],  # (state_prefix, metric_slug, period_label, year, period_seq)
        float,
    ] = defaultdict(float)
    for row in rows:
        # rows[] currently only contains district-grain district-* ids.
        # The metric slug is whatever follows the "naip-iv-" prefix.
        slug = row.indicator_id.split("naip-iv-", 1)[-1]
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
                indicator_id=f"state-livestock-naip-iv-{slug}",
                value_numeric=total,
                source_id=source_id,
                derivation="sum",
            )
        )

    return rows


def build_envelope(repo_root: Path) -> BatchEnvelope:
    """Build the NAIP IV envelope across all discovered meadow snapshots.

    Iterates every dir under ``datasets/livestock/_meadow/ndlm/`` and
    lifts one batch per snapshot. Each batch's observation rows FK to
    a vintage-specific ``source_id`` derived via ``source_id_for``
    (per ADR-0042: live-fetch endpoints get one citation row per
    operator snapshot window).

    Today there is one snapshot (``2024-25``); the FY 2010-11..2025-26
    range lifted in 2026-05 lives inside that snapshot's meadow file
    via row-level ``time`` field. A future re-snapshot is auto-picked
    up by this loop without code change.
    """
    all_rows: list[ObservationRow] = []
    for vintage in discover_meadow_snapshots(repo_root, MEADOW_SOURCE):
        source_id = source_id_for("ndlm_naip_iv", vintage)
        all_rows.extend(_lift_snapshot(repo_root, vintage, source_id))

    return BatchEnvelope(
        target_family="livestock",
        target_table_stem="livestock_naip_iv",
        observation_rows=all_rows,
    )
