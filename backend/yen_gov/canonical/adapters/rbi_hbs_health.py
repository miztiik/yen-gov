"""RBI Handbook of Statistics - health-infrastructure cohort (Row 5 fetchable).

The Row-5 *second cold caller*. It exists to prove the automated-Fetch engine
end to end with MORE THAN ONE caller and the dedup gate, so it is shaped to the
Fetch + delta grain rather than reusing the multi-year-workbook
``rbi_handbook`` parser:

* **Per-year cache unit.** The cohort ships ONE file per year
  (``health-<year>.csv``), which the committed checkpoint calls "the natural
  cache unit of every single-series source" (ingest-state.schema.json). Each
  per-year file is the raw payload the delta engine hashes, so mutating one
  year re-opens exactly that year and a re-run with unchanged years skips every
  year (fetch.skipped, zero new bytes).
* **Two indicators, one cache unit.** Each ``health-<year>.csv`` carries BOTH
  ``government-hospitals`` and ``hospital-beds`` as columns, so
  :meth:`cache_units_for` returns the SAME ``CacheKey`` set for either
  indicator. The orchestrator's :class:`~yen_gov.canonical.ingest.fetch.FetchedCache`
  fetches each year once and both indicators slice it -- the dedup gate.
* **operator_staged by default.** Like the RBI Handbook, the upstream is a
  flaky-TLS government endpoint, so the cohort fetches via the ``operator_staged``
  fallback (a locally-staged file); the ``httpx`` 3-try path is exercised
  directly in ``test_ingest_fetch.py`` with a mock transport. No code here ever
  touches the live network (CLAUDE.md Holy Law #1/#2: Fetch is local-only).

Catalogue (taxonomy registration) ruling: the two indicators are NOT minted into
``concepts.json`` / ``indicators.json`` here -- that is a Hans+Max taxonomy
decision out of Row-5 scope. Tests inject the catalogue as a fixture (the Row-4
precedent: ``orchestrate(indicators=..., concepts=...)``); a real
``ingest run --indicator government-hospitals`` correctly fails the registration
FK until the taxonomy entry lands. This adapter is wired into ``default_registry``
because the registry docstring sanctions exactly this Row-5 extension ("append
the HBS cohort here -- always by adding an entry, never by teaching the
orchestrator a new slug").

Provenance follows Holy Law #9 + the ``rbi_handbook`` precedent: the issuing
authority (CBHI / National Health Profile) is the ``producer``; the RBI Handbook
is named in the ``title`` as the machine-readable access surface. ``source_id``
is DERIVED from the triple, never hand-written.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.ingest.fetch import CacheKey
from yen_gov.canonical.ingest.registry import (
    AdapterRunResult,
    OrchestrateConfig,
    YearResult,
    summarise_indicator_csv,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec, SourceSpec

if TYPE_CHECKING:  # pragma: no cover - typing only
    from yen_gov.canonical.ingest.fetch import FetchedUnit

__all__ = ["HEALTH_SPECS", "RbiHbsHealthAdapter"]

_ADAPTER_SLUG = "rbi-hbs-health"
_DATAPOINTS_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_DATAPOINTS_REL_DIR = "datasets/data/datapoints/geo"
_SOURCE_REL = "datasets/data/entities/source.csv"
_GEO_REL = "datasets/data/entities/geo.csv"

# Default coverage window the cohort fetches (one per-year file each).
_DEFAULT_YEARS: tuple[int, ...] = (2019, 2020, 2021, 2022)
# The spec_version this build emits; a bump re-opens all years (Row 5 delta).
_SPEC_VERSION = "v1"

# Issuing authority (NOT "RBI"; RBI is the access surface) -- one citation.
_PRODUCER = (
    "Central Bureau of Health Intelligence, Ministry of Health and Family "
    "Welfare, Government of India"
)
_TITLE = (
    "National Health Profile (via RBI Handbook of Statistics on Indian States)"
)
_VINTAGE = "2024-25"
_URL = "https://www.cbhidghs.nic.in/"
# The per-year endpoint an `auto` fetch would GET; only the would-be URL since
# the cohort is operator_staged. Kept as a template so a future flip to live
# fetch is a one-line change.
_FETCH_URL_TEMPLATE = "https://www.cbhidghs.nic.in/showfile.php?lid=health-{year}"

# Cell contents that mean "no observation" -> dropped (sparse-safe).
_NA_MARKERS: frozenset[str] = frozenset(
    {"", "-", "--", "n.a.", "na", "n.a", "nr", "...", ".."}
)


@dataclass(frozen=True)
class HealthIndicatorSpec:
    """One health-infrastructure indicator + the CSV column it reads."""

    indicator_id: str
    column: str  # the column name inside health-<year>.csv
    name: str
    concept_id: str
    unit: str
    unit_canonical: str
    normalisation: str
    topic: str
    entity_kinds: str


HEALTH_SPECS: tuple[HealthIndicatorSpec, ...] = (
    HealthIndicatorSpec(
        indicator_id="government-hospitals",
        column="government_hospitals",
        name="Government hospitals",
        concept_id="government-hospitals",
        unit="hospitals",
        unit_canonical="hospitals",
        normalisation="absolute",
        topic="health",
        entity_kinds="country state",
    ),
    HealthIndicatorSpec(
        indicator_id="hospital-beds",
        column="hospital_beds",
        name="Government hospital beds",
        concept_id="hospital-beds",
        unit="beds",
        unit_canonical="beds",
        normalisation="absolute",
        topic="health",
        entity_kinds="country state",
    ),
)


def _spec_by_indicator(indicator_id: str) -> HealthIndicatorSpec:
    for spec in HEALTH_SPECS:
        if spec.indicator_id == indicator_id:
            return spec
    raise KeyError(
        f"no rbi-hbs-health spec for indicator_id {indicator_id!r}; "
        f"known: {[s.indicator_id for s in HEALTH_SPECS]}"
    )


class RbiHbsHealthAdapter:
    """The 2nd cold caller: a fetchable RBI HBS health-infrastructure cohort.

    Satisfies both :class:`~yen_gov.canonical.ingest.registry.Adapter` (so the
    registry + status work) and
    :class:`~yen_gov.canonical.ingest.registry.FetchableAdapter` (so the
    orchestrator drives it through the Fetch + delta loop). ``years`` and
    ``spec_version`` are constructor args so a test can vary the coverage window
    and prove a ``spec_version`` bump re-opens every year.
    """

    adapter_slug = _ADAPTER_SLUG

    def __init__(
        self,
        *,
        years: tuple[int, ...] = _DEFAULT_YEARS,
        spec_version: str = _SPEC_VERSION,
    ) -> None:
        self._years = tuple(sorted(years))
        self._spec_version = spec_version
        #: Per-(indicator, year) process_year calls, for the dedup/bump tests.
        self.processed: list[tuple[str, int]] = []

    # --- Adapter (Row 4) surface ------------------------------------------- #

    def source_specs(self) -> tuple[SourceSpec, ...]:
        """One citation; both indicators are children (they share the file)."""
        return (
            SourceSpec(
                adapter_slug=self.adapter_slug,
                producer=_PRODUCER,
                title=_TITLE,
                vintage=_VINTAGE,
                url=_URL,
                indicators=tuple(
                    IndicatorSpec(
                        indicator_id=spec.indicator_id,
                        unit=spec.unit_canonical,
                        normalisation=spec.normalisation,  # type: ignore[arg-type]
                    )
                    for spec in HEALTH_SPECS
                ),
            ),
        )

    def run_indicator(
        self, indicator_id: str, *, repo_root: Path, config: OrchestrateConfig
    ) -> AdapterRunResult:
        """Drive ONE indicator across all years directly (no delta).

        The standalone / protocol-compatibility path: the orchestrator uses the
        delta-aware loop instead (skip/resume), but this keeps the adapter a
        valid :class:`Adapter` and independently runnable. Reuses
        :meth:`process_year` so the emit logic is single-sourced.
        """
        from yen_gov.canonical.ingest.fetch import fetch_unit

        _spec_by_indicator(indicator_id)  # KeyError if not owned
        cache_dir = repo_root / ".runtime" / "cache" / "ingest"
        for cache_key in self.cache_units_for(indicator_id):
            fetched = fetch_unit(
                cache_key,
                cache_dir=cache_dir,
                staging_dir=config.staging_dir,
            )
            self.process_year(
                indicator_id, fetched=fetched, repo_root=repo_root, config=config
            )
        return summarise_indicator_csv(
            repo_root, indicator_id, adapter_slug=self.adapter_slug
        )

    # --- FetchableAdapter (Row 5) surface ---------------------------------- #

    def spec_version(self, indicator_id: str) -> str:
        """The spec_version this build emits (a bump re-opens all years)."""
        _spec_by_indicator(indicator_id)
        return self._spec_version

    def cache_units_for(self, indicator_id: str) -> tuple[CacheKey, ...]:
        """Return one per-year cache unit per covered year.

        BOTH indicators return the SAME ``CacheKey`` set (the per-year file
        carries both columns), so the run-scoped cache fetches each year once.
        """
        _spec_by_indicator(indicator_id)
        return tuple(
            CacheKey(
                adapter_slug=self.adapter_slug,
                # Indicator-agnostic on purpose: shared across both indicators
                # so their keys are EQUAL and dedup collapses them.
                unit_id=f"{self.adapter_slug}:health:{year}",
                year=year,
                staging_filename=f"health-{year}.csv",
                url=_FETCH_URL_TEMPLATE.format(year=year),
                mode="operator_staged",
            )
            for year in self._years
        )

    def process_year(
        self,
        indicator_id: str,
        *,
        fetched: "FetchedUnit",
        repo_root: Path,
        config: OrchestrateConfig,
    ) -> YearResult:
        """Enrich + publish ONE year for ``indicator_id`` (UPSERT into its CSV).

        Slices the indicator's column out of the shared per-year payload,
        resolves each state label to its LGD entity id (geo.csv is the SOT --
        no hardcoded state map, Holy Law #6), and UPSERTs the year's rows into
        ``datapoints/geo/<indicator_id>.csv`` keyed by ``(entity_id, time)`` so
        re-emitting one year leaves the others intact. The ``source.csv``
        citation row is upserted too so the FK closes.
        """
        # Lazy import: the rbi_handbook package __init__ pulls openpyxl; keep it
        # out of the module-load + registry-build graph (--help stays light).
        from yen_gov.canonical.adapters.rbi_handbook.resolver import (
            build_state_resolver,
        )

        spec = _spec_by_indicator(indicator_id)
        year = fetched.cache_key.year
        resolver = build_state_resolver(repo_root / _GEO_REL)
        source_id = derive_source_id(_PRODUCER, _TITLE, _VINTAGE)

        reader = csv.DictReader(io.StringIO(fetched.raw_bytes.decode("utf-8")))
        if reader.fieldnames is None or spec.column not in reader.fieldnames:
            raise ValueError(
                f"{indicator_id}: column {spec.column!r} not found in "
                f"health-{year}.csv (header={reader.fieldnames})"
            )
        rows: list[dict[str, Any]] = []
        for raw in reader:
            cell = (raw.get(spec.column) or "").strip()
            if cell.lower() in _NA_MARKERS:
                continue
            label = raw.get("state")
            entity_id = resolver.resolve(label)
            if entity_id is None:
                raise ValueError(
                    f"{indicator_id}: unresolved state label {label!r} in "
                    f"health-{year}.csv (no geo.csv match; fail loud, never "
                    "silently drop a row)"
                )
            rows.append(
                {
                    "entity_id": entity_id,
                    "time": year,
                    "value": float(cell),
                    "source_id": source_id,
                }
            )

        contract = load_columns()
        out_path = repo_root / _DATAPOINTS_REL_DIR / f"{indicator_id}.csv"
        _upsert(
            path=out_path,
            file_class=_DATAPOINTS_FILE_CLASS,
            new_rows=rows,
            contract=contract,
        )
        _upsert(
            path=repo_root / _SOURCE_REL,
            file_class=_SOURCE_REL,
            new_rows=[
                {
                    "source_id": source_id,
                    "producer": _PRODUCER,
                    "title": _TITLE,
                    "vintage": _VINTAGE,
                    "url": _URL,
                }
            ],
            contract=contract,
        )

        self.processed.append((indicator_id, year))
        return YearResult(
            indicator_id=indicator_id,
            year=year,
            rows_written=len(rows),
            source_id=source_id,
        )


def _upsert(
    *,
    path: Path,
    file_class: str,
    new_rows: list[dict[str, Any]],
    contract: Any,
) -> Path:
    """Merge ``new_rows`` into the CSV at ``path`` by the file class's PK.

    Reads any existing file, overlays the new rows keyed by the file class's PK,
    and rewrites through the canonical writer (which sorts by PK and skip-writes
    when nothing changed, so an unchanged year leaves a clean ``git status``).
    """
    fc = contract.for_glob(file_class)
    names = [c.name for c in fc.columns]
    pk_names = [c.name for c in fc.pk_columns]

    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                row = {
                    name: (raw.get(name) if (raw.get(name) or "") != "" else None)
                    for name in names
                }
                merged[tuple(_pk(row[k]) for k in pk_names)] = row
    for row in new_rows:
        key = tuple(_pk(row.get(k)) for k in pk_names)
        merged[key] = {name: row.get(name) for name in names}

    return write_csv(
        path=path,
        file_class=file_class,
        rows=list(merged.values()),
        contract=contract,
    )


def _pk(value: Any) -> Any:
    """Stringify a PK value so int/str compare equal across read + write."""
    return str(value) if value is not None else None
