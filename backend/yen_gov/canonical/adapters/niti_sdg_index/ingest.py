"""NITI Aayog SDG India Index - ingest orchestrator (greenfield, plan Row 11).

The THIRD single-series caller of the shared
:func:`~yen_gov.canonical.ingest.run_pipeline.run_pipeline` (after
``rbi_handbook`` + the ``rbi_hbs_health`` cohort). It is deliberately thin:
parse the operator-staged ``state,year,score`` CSV (``parser``), resolve every
label to its LGD ``entity_id`` via the shared ``geo.csv`` resolver, then hand
the long-format observations to ``run_pipeline`` for the full single-series
publish (datapoints + ``source.csv`` citation + ``variables.csv`` /
``concepts.csv`` catalogue rows).

Provenance doctrine (Holy Law #9): NITI Aayog ORIGINATES the SDG India Index
(it is NITI's own composite analytic, computed from a basket of official
indicators), so ``producer`` is the issuing authority ``"NITI Aayog"`` -- this
is NOT an ICED-style passthrough where the producer is a separate upstream.
``source_id`` is DERIVED from the (producer, title, vintage) triple by
``run_pipeline``, never hand-written.

Identity is the SOT: the indicator + concept are registered in
``datasets/taxonomy/{indicators,concepts}.json`` (the first ingest indicator to
be registered there), so an orchestrated ``ingest run --indicator
sdg-india-index-score`` passes the registration FK + concept-compatibility
check without any injected fixture.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.ingest.paths import to_repo_relative_posix
from yen_gov.canonical.ingest.registry import AdapterRunResult, OrchestrateConfig
from yen_gov.canonical.ingest.run_pipeline import Citation, run_pipeline
from yen_gov.canonical.ingest.spec import IndicatorSpec, SourceSpec

from .parser import SdgIndexSpec, parse_sdg_index_csv

__all__ = [
    "SHIPPED_SPEC",
    "IngestResult",
    "IngestedTable",
    "NitiSdgIndexAdapter",
    "ingest",
    "spec_by_indicator_id",
]

_ADAPTER_SLUG = "niti-sdg-index"
_GEO_REL = "datasets/data/entities/geo.csv"

#: The one shipped SDG India Index single-series spec. Adding a future edition
#: is a vintage bump (source_id re-derives, so the citation ledger tracks it);
#: a new SDG measure is one appended spec.
SHIPPED_SPEC = SdgIndexSpec(
    indicator_id="sdg-india-index-score",
    name="SDG India Index composite score",
    concept_id="sdg-india-index-score",
    concept_noun="SDG India Index score",
    concept_description=(
        "NITI Aayog SDG India Index composite score (0-100): a state/UT's "
        "distance to the 2030 SDG targets. A policy-dashboard index, not a "
        "direct outcome measure."
    ),
    unit="score",
    unit_canonical="score",
    normalisation="index",
    topic=None,
    entity_kinds="country state",
    update_period_days=365,
    source_producer="NITI Aayog",
    source_title="SDG India Index and Dashboard",
    source_vintage="2020-21",
    source_url="https://sdgindiaindex.niti.gov.in",
    staging_filename="sdg-india-index-2020-21.csv",
)


@dataclass(frozen=True)
class IngestedTable:
    """Per-indicator outcome reported to the CLI / tests."""

    indicator_id: str
    output_path: Path
    row_count: int
    entity_count: int
    time_min: int
    time_max: int
    source_id: str


@dataclass(frozen=True)
class IngestResult:
    """Aggregate outcome of one SDG India Index ingest run."""

    tables: tuple[IngestedTable, ...]

    @property
    def total_rows(self) -> int:
        return sum(t.row_count for t in self.tables)


def spec_by_indicator_id(indicator_id: str) -> SdgIndexSpec:
    """Return the shipped spec for ``indicator_id`` or raise ``KeyError``."""
    if indicator_id == SHIPPED_SPEC.indicator_id:
        return SHIPPED_SPEC
    raise KeyError(
        f"unknown SDG India Index indicator_id {indicator_id!r}; known: "
        f"['{SHIPPED_SPEC.indicator_id}']"
    )


def ingest(
    *,
    repo_root: Path,
    staging_dir: Path,
    spec: SdgIndexSpec | None = None,
) -> IngestResult:
    """Ingest the staged SDG India Index CSV into the canonical store.

    Args:
        repo_root: repo root; anchors the datapoint output dir, the catalogue
            CSVs, and the ``geo.csv`` resolver source.
        staging_dir: directory the operator dropped the SDG India Index CSV
            into (resolved by the spec's ``staging_filename``). Operator input;
            never a committed contract surface.
        spec: the spec to ingest; defaults to :data:`SHIPPED_SPEC`.

    Returns:
        :class:`IngestResult` summarising the emitted series.

    Raises:
        FileNotFoundError: ``geo.csv`` or the staged CSV is missing.
        SdgParseError: the staged CSV does not match the expected shape.
    """
    # Lazy import: keep openpyxl (pulled by the rbi_handbook package __init__)
    # out of this module's load + registry-build graph.
    from yen_gov.canonical.adapters.rbi_handbook.resolver import (
        build_state_resolver,
    )

    spec = spec if spec is not None else SHIPPED_SPEC
    resolver = build_state_resolver(repo_root / _GEO_REL)

    staged = staging_dir / spec.staging_filename
    if not staged.exists():
        raise FileNotFoundError(
            f"{spec.indicator_id}: staged SDG India Index CSV not found at "
            f"{staged.name} under the staging dir (no network ingest)."
        )
    observations = parse_sdg_index_csv(staged.read_bytes(), spec, resolver)

    outcome = run_pipeline(
        repo_root=repo_root,
        indicator_id=spec.indicator_id,
        observations=observations,
        citation=Citation(
            producer=spec.source_producer,
            title=spec.source_title,
            vintage=spec.source_vintage,
            url=spec.source_url,
        ),
        datapoints_mode="replace",
        variable_row_builder=_variable_row_builder(spec),
        concept_row=_concept_row(spec),
    )

    return IngestResult(
        tables=(
            IngestedTable(
                indicator_id=spec.indicator_id,
                output_path=outcome.output_path,
                row_count=outcome.row_count,
                entity_count=outcome.entity_count,
                time_min=outcome.time_min,
                time_max=outcome.time_max,
                source_id=outcome.source_id,
            ),
        )
    )


def _variable_row_builder(spec: SdgIndexSpec) -> Any:
    def build(source_id: str, time_min: int, time_max: int) -> dict[str, Any]:
        return {
            "indicator_id": spec.indicator_id,
            "name": spec.name,
            "concept_id": spec.concept_id,
            "unit": spec.unit,
            "derivation": None,
            "topic": spec.topic,
            "source_id": source_id,
            "update_period_days": spec.update_period_days,
            "time_min": time_min,
            "time_max": time_max,
            "entity_kinds": spec.entity_kinds,
        }

    return build


def _concept_row(spec: SdgIndexSpec) -> dict[str, Any]:
    return {
        "concept_id": spec.concept_id,
        "noun": spec.concept_noun,
        "unit_canonical": spec.unit_canonical,
        "normalisation": spec.normalisation,
        "entity_kinds": spec.entity_kinds,
        "description": spec.concept_description,
    }


class NitiSdgIndexAdapter:
    """Adapt the SDG India Index ingest to the orchestrator :class:`Adapter` seam.

    The third single-series caller of ``run_pipeline``, wired into
    ``default_registry`` so ``ingest run --indicator sdg-india-index-score``
    drives it polymorphically (the orchestrator never branches on
    ``adapter_slug``). The SDG India Index is operator-staged (the CSV is not on
    a live endpoint here), so it is a plain :class:`Adapter` -- the Row-5
    Fetch + delta loop is not needed.
    """

    adapter_slug = _ADAPTER_SLUG

    def source_specs(self) -> tuple[SourceSpec, ...]:
        return (
            SourceSpec(
                adapter_slug=self.adapter_slug,
                producer=SHIPPED_SPEC.source_producer,
                title=SHIPPED_SPEC.source_title,
                vintage=SHIPPED_SPEC.source_vintage,
                url=SHIPPED_SPEC.source_url,
                indicators=(
                    IndicatorSpec(
                        indicator_id=SHIPPED_SPEC.indicator_id,
                        unit=SHIPPED_SPEC.unit_canonical,
                        normalisation=SHIPPED_SPEC.normalisation,  # type: ignore[arg-type]
                    ),
                ),
            ),
        )

    def run_indicator(
        self, indicator_id: str, *, repo_root: Path, config: OrchestrateConfig
    ) -> AdapterRunResult:
        from yen_gov.canonical.ingest.registry import IngestConfigError

        spec = spec_by_indicator_id(indicator_id)  # KeyError if not owned
        if config.staging_dir is None:
            raise IngestConfigError(
                f"adapter {self.adapter_slug!r} needs --staging-dir: the SDG "
                "India Index CSV is operator-staged. Stage it and pass the dir."
            )
        result = ingest(
            repo_root=repo_root, staging_dir=config.staging_dir, spec=spec
        )
        table = result.tables[0]
        return AdapterRunResult(
            adapter_slug=self.adapter_slug,
            indicator_id=table.indicator_id,
            output_ref=to_repo_relative_posix(
                table.output_path, repo_root=repo_root
            ),
            row_count=table.row_count,
            entity_count=table.entity_count,
            time_min=table.time_min,
            time_max=table.time_max,
            source_id=table.source_id,
        )
