"""Adapter protocol + the in-memory adapter registry (Row 4, plan section 3).

The orchestrator drives every upstream source through ONE polymorphic seam:
a registry ``{adapter_slug -> Adapter}``. The orchestrator NEVER branches on
``adapter_slug`` (the critical Row-4 gate); it dispatches through this
protocol, so adding a source is adding a registry entry, never an
``if adapter_slug ==`` arm in the engine.

Protocol surface (Gregor + Fowler ruling, Row 4 persona debate)
---------------------------------------------------------------
The Row-4 Adapter is deliberately MINIMAL -- three members:

* ``adapter_slug`` -- the registry key.
* ``source_specs() -> tuple[SourceSpec, ...]`` -- the author-time
  :class:`~yen_gov.canonical.ingest.spec.SourceSpec` rows the adapter owns.
  The orchestrator derives BOTH the ``indicator_id -> [adapter_slug]`` index
  AND the registration FK-check inputs from these. We expose ``SourceSpec``
  (the Row-1 parent type), NOT a flat ``indicator_specs()``, because a single
  adapter can drive MORE THAN ONE source: ``rbi_handbook`` feeds the SRS
  vital-rates table (4 indicators) and the SRS abridged life tables (1
  indicator) -- two distinct ``(producer, title, vintage)`` citations. A flat
  indicator list would erase that provenance grouping, which both
  ``status`` (which source owns which years) and Row 5's per-source
  ``fetch()`` need.
* ``run_indicator(indicator_id, *, repo_root, config) -> AdapterRunResult`` --
  drive the adapter's EXISTING ingest for one indicator and report a typed
  outcome. ``rbi_handbook`` is wired AS-IS here (it keeps its own
  parse + emit path); ``run_pipeline`` extraction is Row 11, fetch + delta is
  Row 5, the enrich/publish honesty gates are Row 6. None of those leak into
  this protocol yet (YAGNI; start minimal, extend on the row that needs it).

Layer (CLAUDE.md section 4): ``canonical/ingest`` is a sibling to
``canonical/adapters`` with ONE ``engine -> adapters`` import arrow. This
module is the only place that arrow is drawn; the rbi import is function-local
so the module-load graph (and ``ingest --help``) stays free of openpyxl.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.ingest.fetch import CacheKey, FetchedUnit
from yen_gov.canonical.ingest.paths import to_repo_relative_posix
from yen_gov.canonical.ingest.spec import IndicatorSpec, SourceSpec

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping


class OrchestrateConfig(BaseModel):
    """Run-time knobs the orchestrator hands each adapter.

    Kept tiny on purpose (no ``pydantic-settings`` / ``config/sources.json`` /
    ``active_adapter`` -- those are explicit YAGNI in the plan). ``staging_dir``
    is the operator-staged-workbook directory the local pipeline reads from;
    automated ``fetch()`` (which makes ``staging_dir`` optional for fetchable
    sources) lands in Row 5. Frozen so an adapter cannot mutate the run config
    underneath the orchestrator.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    staging_dir: Path | None = None


class AdapterRunResult(BaseModel):
    """One indicator's outcome after an adapter drove its ingest.

    The typed value :meth:`Adapter.run_indicator` returns. It carries exactly
    what the orchestrator needs to log a faithful publish line and what the
    refactor-safety oracle compares (the emitted file + its row/entity/year
    summary). ``output_ref`` is a repo-relative POSIX string (routed through
    :func:`~yen_gov.canonical.ingest.paths.to_repo_relative_posix`) so a path
    never leaks its absolute, drive-qualified form into a log line or result
    (CLAUDE.md section 2).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_slug: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
    indicator_id: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60)
    output_ref: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    time_min: int = Field(ge=1850, le=2100)
    time_max: int = Field(ge=1850, le=2100)
    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")


class YearResult(BaseModel):
    """One year's outcome after a fetchable adapter enriched + published it.

    The typed value :meth:`FetchableAdapter.process_year` returns. The
    orchestrator aggregates these across the years it actually processed (the
    skipped years are NOT represented -- their absence is the point) to log a
    faithful publish line; the final :class:`AdapterRunResult` is read back off
    the emitted CSV so it reflects the full coverage, not just this run's slice.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator_id: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60)
    year: int = Field(ge=1850, le=2100)
    rows_written: int = Field(ge=0)
    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")


@runtime_checkable
class Adapter(Protocol):
    """The polymorphic surface the orchestrator drives.

    Any object exposing ``adapter_slug`` + :meth:`source_specs` +
    :meth:`run_indicator` is a valid adapter. ``@runtime_checkable`` lets the
    registry assert ``isinstance(obj, Adapter)`` at wiring time.
    """

    adapter_slug: str

    def source_specs(self) -> tuple[SourceSpec, ...]:
        """Return the author-time source specs this adapter owns."""
        ...

    def run_indicator(
        self, indicator_id: str, *, repo_root: Path, config: OrchestrateConfig
    ) -> AdapterRunResult:
        """Drive the adapter's existing ingest for ``indicator_id`` and report."""
        ...


@runtime_checkable
class FetchableAdapter(Adapter, Protocol):
    """An :class:`Adapter` that supports automated Fetch + per-year delta (Row 5).

    The orchestrator runs the Fetch + checkpoint loop for an adapter IFF it
    ``isinstance(adapter, FetchableAdapter)`` -- a CAPABILITY check, never a
    branch on ``adapter_slug`` (the critical Row-4 gate stays intact). A
    non-fetchable adapter (e.g. ``rbi_handbook``) is driven by the Row-4
    ``run_indicator`` path unchanged, so its byte-identity oracle is untouched.

    The three added members are the minimum the delta loop needs:

    * :meth:`cache_units_for` -- the per-year cache unit(s) an indicator draws
      from (plural: an indicator may span >1 unit). Two indicators that share a
      unit return EQUAL :class:`~yen_gov.canonical.ingest.fetch.CacheKey`s so the
      run-scoped cache fetches it once.
    * :meth:`spec_version` -- the build's spec version; a bump re-opens all years.
    * :meth:`process_year` -- enrich + publish ONE year (an UPSERT, so a single
      re-emitted year leaves the others intact), reporting a :class:`YearResult`.
    """

    def cache_units_for(self, indicator_id: str) -> tuple[CacheKey, ...]:
        """Return the per-year cache unit(s) ``indicator_id`` draws from."""
        ...

    def spec_version(self, indicator_id: str) -> str:
        """Return the build's spec version (a bump re-opens all years)."""
        ...

    def process_year(
        self,
        indicator_id: str,
        *,
        fetched: FetchedUnit,
        repo_root: Path,
        config: OrchestrateConfig,
    ) -> YearResult:
        """Enrich + publish ONE year for ``indicator_id`` (UPSERT) and report."""
        ...


class IngestConfigError(Exception):
    """An adapter was asked to run without the configuration it needs."""


# --------------------------------------------------------------------------- #
# rbi_handbook adapter (wired AS-IS; Row 11 extracts run_pipeline, not here)
# --------------------------------------------------------------------------- #


class RbiHandbookAdapter:
    """Adapt the existing ``rbi_handbook`` package to the :class:`Adapter` seam.

    A THIN wrapper: ``source_specs`` maps the package's ``SHIPPED_SPECS``
    (``HbsTableSpec`` rows) onto the Row-1 :class:`SourceSpec` /
    :class:`IndicatorSpec` shape, grouped by the ``(producer, title, vintage,
    url)`` citation; ``run_indicator`` calls the package's existing ``ingest``
    for the one requested table and maps its ``IngestedTable`` to an
    :class:`AdapterRunResult`. No parsing, emitting, or catalogue logic is
    duplicated or changed -- that is the refactor-safety oracle's whole point.

    All ``rbi_handbook`` imports are function-local so building the registry
    (and ``ingest --help``) does not pull openpyxl; it loads only when an
    indicator is actually inspected or run.
    """

    adapter_slug = "rbi-handbook"

    def source_specs(self) -> tuple[SourceSpec, ...]:
        from yen_gov.canonical.adapters.rbi_handbook import SHIPPED_SPECS

        return _rbi_source_specs(SHIPPED_SPECS)

    def run_indicator(
        self, indicator_id: str, *, repo_root: Path, config: OrchestrateConfig
    ) -> AdapterRunResult:
        from yen_gov.canonical.adapters.rbi_handbook import (
            ingest as rbi_ingest,
            spec_by_indicator_id,
        )

        if config.staging_dir is None:
            raise IngestConfigError(
                f"adapter {self.adapter_slug!r} needs --staging-dir: the RBI "
                "Handbook tables are operator-staged XLSX (automated fetch is "
                "Row 5). Stage the workbook(s) and pass the directory."
            )
        hbs_spec = spec_by_indicator_id(indicator_id)  # KeyError if not owned
        result = rbi_ingest(
            repo_root=repo_root,
            staging_dir=config.staging_dir,
            specs=(hbs_spec,),
        )
        table = result.tables[0]
        return AdapterRunResult(
            adapter_slug=self.adapter_slug,
            indicator_id=table.indicator_id,
            output_ref=to_repo_relative_posix(table.output_path, repo_root=repo_root),
            row_count=table.row_count,
            entity_count=table.entity_count,
            time_min=table.time_min,
            time_max=table.time_max,
            source_id=table.source_id,
        )


def _rbi_source_specs(shipped: tuple) -> tuple[SourceSpec, ...]:
    """Group ``rbi_handbook`` ``HbsTableSpec`` rows into Row-1 ``SourceSpec``s.

    One :class:`SourceSpec` per distinct ``(producer, title, vintage, url)``
    citation; each ``HbsTableSpec`` becomes a child :class:`IndicatorSpec`
    carrying the measurement tuple. ``price_basis`` / ``sampling_frame`` are
    ``None`` for this SRS vital-rates / life-expectancy cohort (physical-rate
    and duration concepts -- neither monetary nor a declared survey frame on
    the existing specs). Insertion order is preserved so the registry is
    deterministic.
    """
    groups: dict[tuple[str, str, str, str | None], list[IndicatorSpec]] = {}
    order: list[tuple[str, str, str, str | None]] = []
    for hbs in shipped:
        key = (
            hbs.source_producer,
            hbs.source_title,
            hbs.source_vintage,
            hbs.source_url,
        )
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(
            IndicatorSpec(
                indicator_id=hbs.indicator_id,
                # catalogue_fk compares spec.unit to concept.unit_canonical,
                # so the spec declares the CANONICAL unit.
                unit=hbs.unit_canonical,
                normalisation=hbs.normalisation,
                price_basis=None,
                sampling_frame=None,
            )
        )
    specs: list[SourceSpec] = []
    for key in order:
        producer, title, vintage, url = key
        specs.append(
            SourceSpec(
                adapter_slug=RbiHandbookAdapter.adapter_slug,
                producer=producer,
                title=title,
                vintage=vintage,
                url=url,
                indicators=tuple(groups[key]),
            )
        )
    return tuple(specs)


# --------------------------------------------------------------------------- #
# CSV summariser (shared by the fetchable run path + the orchestrator)
# --------------------------------------------------------------------------- #

_DATAPOINTS_GEO_REL = "datasets/data/datapoints/geo"


def summarise_indicator_csv(
    repo_root: Path,
    indicator_id: str,
    *,
    adapter_slug: str,
    geo_rel: str = _DATAPOINTS_GEO_REL,
) -> AdapterRunResult:
    """Read an indicator's emitted geo datapoints CSV into an AdapterRunResult.

    The honest on-disk summary: a fetchable run reports the FULL coverage (every
    year in the file), not just the years this run touched, so a run that
    skipped every year still reports the real span. ``source_id`` is taken from
    the file's ``source_id`` column (the recorded provenance), never re-derived.
    """
    path = repo_root / geo_rel / f"{indicator_id}.csv"
    if not path.is_file():
        raise IngestConfigError(
            f"no datapoints emitted for {indicator_id!r} at "
            f"{geo_rel}/{indicator_id}.csv"
        )
    times: list[int] = []
    entities: set[str] = set()
    source_id = ""
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            raw_time = (row.get("time") or "").strip()
            entity = (row.get("entity_id") or "").strip()
            sid = (row.get("source_id") or "").strip()
            if raw_time:
                times.append(int(raw_time))
            if entity:
                entities.add(entity)
            if sid and not source_id:
                source_id = sid
    if not times:
        raise IngestConfigError(
            f"datapoints file for {indicator_id!r} has no rows to summarise"
        )
    return AdapterRunResult(
        adapter_slug=adapter_slug,
        indicator_id=indicator_id,
        output_ref=to_repo_relative_posix(path, repo_root=repo_root),
        row_count=len(times),
        entity_count=len(entities),
        time_min=min(times),
        time_max=max(times),
        source_id=source_id,
    )


# --------------------------------------------------------------------------- #
# the default registry
# --------------------------------------------------------------------------- #


def default_registry() -> dict[str, Adapter]:
    """Return the wired adapter registry ``{adapter_slug -> Adapter}``.

    Row 4 wires ``rbi_handbook`` only; Rows 5 / 11 append the HBS cohort and
    the greenfield SDG adapter here -- always by adding an entry, never by
    teaching the orchestrator a new slug. Each adapter's ``adapter_slug``
    attribute is the key, asserted to match.
    """
    # Function-local import: the cohort pulls the canonical CSV layer; keep it
    # out of the module-load graph so importing the registry (and ``ingest
    # --help``) stays light, and so registry <-> cohort have no import cycle.
    from yen_gov.canonical.adapters.niti_sdg_index import NitiSdgIndexAdapter
    from yen_gov.canonical.adapters.rbi_hbs_health import RbiHbsHealthAdapter

    adapters: tuple[Adapter, ...] = (
        RbiHandbookAdapter(),
        RbiHbsHealthAdapter(),
        NitiSdgIndexAdapter(),
    )
    registry: dict[str, Adapter] = {}
    for adapter in adapters:
        slug = adapter.adapter_slug
        if slug in registry:
            raise ValueError(f"duplicate adapter_slug {slug!r} in the registry")
        registry[slug] = adapter
    return registry


__all__ = [
    "Adapter",
    "AdapterRunResult",
    "FetchableAdapter",
    "IngestConfigError",
    "OrchestrateConfig",
    "RbiHandbookAdapter",
    "YearResult",
    "default_registry",
    "summarise_indicator_csv",
]
