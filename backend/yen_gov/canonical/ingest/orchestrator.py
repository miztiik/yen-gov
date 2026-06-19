"""The thin ingest orchestrator + the ``status`` reader (Row 4, plan section 3).

``orchestrate`` is the engine: on a trigger it resolves an indicator (or an
adapter scope) to the adapter(s) that feed it, FK-checks the targeted specs
against the catalogue, runs the fail-loud preamble, and drives each adapter
POLYMORPHICALLY through the registry. It NEVER branches on ``adapter_slug``
(the critical Row-4 gate) -- dispatch is ``registry[slug].run_indicator(...)``.

What is here vs. deferred (so a later row does not re-derive it):

* **Derived index.** ``build_indicator_index`` turns the registry into an
  in-memory ``{indicator_id -> [adapter_slug]}`` map. It is NEVER committed
  (plan section 3); it is rebuilt every call from the registry, the single
  source of truth.
* **Preamble (not a stage).** "validate spec + list cache units + diff vs
  checkpoint -> work-list". Row 4 implements the spec-validation half (the
  ``catalogue_fk`` FK + concept-compatibility check on each TARGETED
  indicator) and produces a work-list = the resolved targets. The cache-unit
  listing and the checkpoint delta-diff are Row 5 (fetch + state own them), so
  the work-list here is "every target, no skipping". The seam is marked.
* **FK scope.** The plan FK-checks "each IndicatorSpec.indicator_id vs
  indicators.json at registration". We scope that to the run's TARGETS, not
  the whole registry: an unrelated indicator's run must not fail because some
  OTHER adapter carries an indicator the taxonomy has not registered yet. A
  bogus ``--indicator`` fails earlier still, at target resolution.

``compute_status`` is the read-only companion: per-indicator coverage, which
source owns which years (read straight off the emitted datapoints CSV's
``source_id`` column -- the honest on-disk truth), and the staleness cadence.
Row 6 enriches it with publish-seam provenance; Row 4 already shows the
per-source year spans its gate requires.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.ingest import state
from yen_gov.canonical.ingest.catalogue_fk import check_indicator_registration
from yen_gov.canonical.ingest.registry import (
    Adapter,
    AdapterRunResult,
    OrchestrateConfig,
    default_registry,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

    from yen_gov.core.logging import StructuredLogger

# Repo-relative homes the status reader queries (POSIX, CLAUDE.md section 2).
_DATAPOINTS_GEO_REL = "datasets/data/datapoints/geo"
_VARIABLES_REL = "datasets/data/variables.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"


class IngestError(Exception):
    """Base for orchestrator-level failures."""


class IngestUsageError(IngestError):
    """The run scope is unresolvable (no/unknown indicator or adapter)."""


class RegistryConsistencyError(IngestError):
    """An adapter's ``source_specs`` disagree with its registry key."""


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #


class OrchestrateResult(BaseModel):
    """The typed outcome of one ``orchestrate`` call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator: str | None = None
    adapter: str | None = None
    fanout_line: str = Field(min_length=1)
    results: tuple[AdapterRunResult, ...] = ()


class SourceCoverage(BaseModel):
    """One source's year span for an indicator (read off the datapoints CSV)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    producer: str | None = None
    title: str | None = None
    year_min: int
    year_max: int
    observation_count: int = Field(ge=0)


class IndicatorStatus(BaseModel):
    """``status --indicator X``: coverage + which source owns which years."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator_id: str = Field(min_length=1)
    adapters: tuple[str, ...] = ()
    coverage: tuple[SourceCoverage, ...] = ()
    update_period_days: int | None = None
    last_checked: str | None = None
    has_coverage: bool = False


# --------------------------------------------------------------------------- #
# derived index + target resolution
# --------------------------------------------------------------------------- #


def build_indicator_index(registry: "Mapping[str, Adapter]") -> dict[str, list[str]]:
    """Build the derived ``{indicator_id -> [adapter_slug]}`` index (in-memory).

    Never committed (plan section 3); rebuilt from the registry each call.
    Asserts every ``SourceSpec.adapter_slug`` matches its registry key so a
    mis-wired adapter fails loud at index time rather than dispatching wrong.
    """
    index: dict[str, list[str]] = {}
    for slug, adapter in registry.items():
        for source_spec in adapter.source_specs():
            if source_spec.adapter_slug != slug:
                raise RegistryConsistencyError(
                    f"adapter registered under {slug!r} declares a source_spec "
                    f"with adapter_slug {source_spec.adapter_slug!r}"
                )
            for ind in source_spec.indicators:
                owners = index.setdefault(ind.indicator_id, [])
                if slug not in owners:
                    owners.append(slug)
    return index


def _resolve_targets(
    index: "Mapping[str, list[str]]",
    *,
    indicator: str | None,
    adapter: str | None,
) -> list[tuple[str, str]]:
    """Resolve ``(--indicator, --adapter)`` to a sorted ``[(slug, id)]`` work set.

    ``--indicator X`` is primary; ``--adapter Y`` is a scope filter. With only
    ``--adapter`` every indicator the adapter owns is targeted. Order is
    deterministic (sorted) so two equivalent invocations produce identical
    fan-out and results.
    """
    if indicator is None and adapter is None:
        raise IngestUsageError(
            "specify --indicator (primary) and/or --adapter (scope filter)"
        )

    known_adapters = {slug for owners in index.values() for slug in owners}
    if adapter is not None and adapter not in known_adapters:
        raise IngestUsageError(
            f"unknown adapter {adapter!r}; known: {sorted(known_adapters)}"
        )

    if indicator is not None:
        owners = index.get(indicator)
        if not owners:
            raise IngestUsageError(
                f"no registered adapter owns indicator {indicator!r}; "
                f"known indicators: {sorted(index)}"
            )
        targets = [
            (slug, indicator)
            for slug in sorted(owners)
            if adapter is None or slug == adapter
        ]
        if not targets:  # adapter filter excluded every owner
            raise IngestUsageError(
                f"adapter {adapter!r} does not own indicator {indicator!r}; "
                f"owners: {sorted(owners)}"
            )
        return targets

    # adapter-only scope: every indicator the adapter owns
    owned = sorted(ind for ind, owners in index.items() if adapter in owners)
    return [(adapter, ind) for ind in owned]


def _indicator_spec(
    registry: "Mapping[str, Adapter]", adapter_slug: str, indicator_id: str
) -> IndicatorSpec:
    """Return the :class:`IndicatorSpec` an adapter declares for an indicator."""
    for source_spec in registry[adapter_slug].source_specs():
        for ind in source_spec.indicators:
            if ind.indicator_id == indicator_id:
                return ind
    raise IngestUsageError(
        f"adapter {adapter_slug!r} declares no spec for indicator {indicator_id!r}"
    )


# --------------------------------------------------------------------------- #
# fan-out echo
# --------------------------------------------------------------------------- #


def _coverage_span(repo_root: Path, indicator_id: str) -> tuple[int, int] | None:
    """Return the (min, max) year already on disk for an indicator, or None.

    Read off the emitted ``geo/<id>.csv`` so the pre-work fan-out echo can name
    the existing coverage. A fresh run (no prior file) has no span; the echo
    degrades to the bare adapter slug rather than inventing years.
    """
    times = _datapoint_times(repo_root, indicator_id)
    if not times:
        return None
    return (min(times), max(times))


def _fanout_line(
    repo_root: Path,
    *,
    indicator: str | None,
    adapter: str | None,
    targets: list[tuple[str, str]],
) -> str:
    """Build the one-line fan-out echo printed before any work.

    Indicator-centric when an indicator is named
    (``<indicator> <- [<adapter> 2016-2018]: running 1 adapter``);
    adapter-centric for an adapter-only scope
    (``<adapter> -> [<id-a>, <id-b>]: running 2 indicators``). The year span is
    the existing on-disk coverage (Row 5's fetch will widen this to the
    about-to-be-fetched span); absent when nothing is on disk yet.
    """
    if indicator is not None:
        slugs: list[str] = []
        for slug, _ in targets:
            if slug not in slugs:
                slugs.append(slug)
        span = _coverage_span(repo_root, indicator)
        bracket = ", ".join(
            f"{slug} {span[0]}-{span[1]}" if span else slug for slug in slugs
        )
        n = len(slugs)
        return f"{indicator} <- [{bracket}]: running {n} adapter{_s(n)}"

    inds = [ind for _, ind in targets]
    n = len(inds)
    return f"{adapter} -> [{', '.join(inds)}]: running {n} indicator{_s(n)}"


def _s(n: int) -> str:
    return "" if n == 1 else "s"


# --------------------------------------------------------------------------- #
# orchestrate
# --------------------------------------------------------------------------- #


def orchestrate(
    *,
    indicator: str | None = None,
    adapter: str | None = None,
    repo_root: Path,
    config: OrchestrateConfig,
    registry: "Mapping[str, Adapter] | None" = None,
    logger: "StructuredLogger | None" = None,
    on_fanout: Callable[[str], None] | None = None,
    indicators: Iterable[dict] | None = None,
    concepts: Iterable[dict] | None = None,
    indicators_path: Path | None = None,
    concepts_path: Path | None = None,
) -> OrchestrateResult:
    """Drive the requested indicator (or adapter scope) into the canonical store.

    Args:
        indicator: the primary work address; resolved to its owning adapter(s)
            via the derived index.
        adapter: a scope filter (restrict to this adapter) and, when no
            ``indicator`` is given, the unit of work (all its indicators).
        repo_root: repo root anchoring the catalogue + emitted datapoints.
        config: per-run knobs handed to each adapter (e.g. ``staging_dir``).
        registry: the adapter registry; defaults to :func:`default_registry`.
        logger: optional stage-tagged logger; the fan-out + per-indicator
            publish lines are written to it when present.
        on_fanout: optional sink called with the fan-out line BEFORE any work
            (the CLI passes ``typer.echo`` so the echo precedes the output).
        indicators / concepts / indicators_path / concepts_path: catalogue
            overrides forwarded to ``catalogue_fk`` (tests inject fixtures so
            they never walk the real corpus; defaults read the taxonomy SOT).

    Returns:
        :class:`OrchestrateResult` with the fan-out line and one
        :class:`AdapterRunResult` per driven indicator.

    Raises:
        IngestUsageError: the scope is unresolvable.
        CatalogueFkError / ConceptCompatibilityError: a targeted indicator
            fails the registration FK or concept-compatibility check.
    """
    registry = dict(registry) if registry is not None else default_registry()
    index = build_indicator_index(registry)
    targets = _resolve_targets(index, indicator=indicator, adapter=adapter)

    # --- PREAMBLE (not a stage): validate the targeted specs against the
    # catalogue (the spec-validation half). Cache-unit listing + checkpoint
    # delta-diff are Row 5; the Row-4 work-list is "every target, no skipping".
    for slug, ind_id in targets:
        spec = _indicator_spec(registry, slug, ind_id)
        check_indicator_registration(
            spec,
            indicators=indicators,
            concepts=concepts,
            indicators_path=indicators_path,
            concepts_path=concepts_path,
        )
    work_list = list(targets)

    fanout_line = _fanout_line(
        repo_root, indicator=indicator, adapter=adapter, targets=work_list
    )
    if on_fanout is not None:
        on_fanout(fanout_line)
    if logger is not None:
        logger.info("ingest.fanout", fanout_line)

    results: list[AdapterRunResult] = []
    for slug, ind_id in work_list:
        # POLYMORPHIC dispatch -- the engine never knows which adapter this is.
        adapter_obj = registry[slug]
        result = adapter_obj.run_indicator(
            ind_id, repo_root=repo_root, config=config
        )
        if logger is not None:
            logger.info(
                "ingest.published",
                f"published {result.indicator_id} "
                f"({result.row_count} rows) -> {result.output_ref}",
                stage="publish",
                indicator_id=result.indicator_id,
                adapter_slug=result.adapter_slug,
                rows=result.row_count,
                entities=result.entity_count,
                year_min=result.time_min,
                year_max=result.time_max,
                output=result.output_ref,
                source_id=result.source_id,
            )
        results.append(result)

    return OrchestrateResult(
        indicator=indicator,
        adapter=adapter,
        fanout_line=fanout_line,
        results=tuple(results),
    )


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


def compute_status(
    *,
    indicator: str,
    repo_root: Path,
    registry: "Mapping[str, Adapter] | None" = None,
) -> IndicatorStatus:
    """Report coverage + per-source year spans + staleness for one indicator.

    The owning adapter(s) come from the derived index; the per-source year
    spans are read straight off the emitted ``geo/<id>.csv`` (its ``source_id``
    column is the honest record of which source supplied which observation);
    the cadence (``update_period_days``) comes from ``variables.csv`` and the
    last-checked stamp from the committed checkpoint when one exists.
    """
    registry = dict(registry) if registry is not None else default_registry()
    index = build_indicator_index(registry)
    adapters = tuple(sorted(index.get(indicator, [])))
    coverage = _read_coverage(repo_root, indicator)
    return IndicatorStatus(
        indicator_id=indicator,
        adapters=adapters,
        coverage=coverage,
        update_period_days=_read_update_period(repo_root, indicator),
        last_checked=_read_last_checked(repo_root, adapters),
        has_coverage=bool(coverage),
    )


def _datapoint_times(repo_root: Path, indicator_id: str) -> list[int]:
    """Return every integer ``time`` in the indicator's datapoints CSV (or [])."""
    path = repo_root / _DATAPOINTS_GEO_REL / f"{indicator_id}.csv"
    if not path.is_file():
        return []
    times: list[int] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("time") or "").strip()
            if raw:
                times.append(int(raw))
    return times


def _read_coverage(repo_root: Path, indicator_id: str) -> tuple[SourceCoverage, ...]:
    """Group the indicator's datapoints by ``source_id`` into year spans."""
    path = repo_root / _DATAPOINTS_GEO_REL / f"{indicator_id}.csv"
    if not path.is_file():
        return ()
    spans: dict[str, list[int]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            raw_time = (row.get("time") or "").strip()
            source_id = (row.get("source_id") or "").strip()
            if not raw_time or not source_id:
                continue
            spans.setdefault(source_id, []).append(int(raw_time))
    if not spans:
        return ()
    producers = _read_source_index(repo_root)
    coverage = []
    for source_id in sorted(spans):
        years = spans[source_id]
        producer, title = producers.get(source_id, (None, None))
        coverage.append(
            SourceCoverage(
                source_id=source_id,
                producer=producer,
                title=title,
                year_min=min(years),
                year_max=max(years),
                observation_count=len(years),
            )
        )
    return tuple(coverage)


def _read_source_index(repo_root: Path) -> dict[str, tuple[str | None, str | None]]:
    """Map ``source_id -> (producer, title)`` from ``entities/source.csv``."""
    path = repo_root / _SOURCE_REL
    if not path.is_file():
        return {}
    out: dict[str, tuple[str | None, str | None]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = (row.get("source_id") or "").strip()
            if sid:
                out[sid] = (row.get("producer"), row.get("title"))
    return out


def _read_update_period(repo_root: Path, indicator_id: str) -> int | None:
    """Return the indicator's ``update_period_days`` from ``variables.csv``."""
    path = repo_root / _VARIABLES_REL
    if not path.is_file():
        return None
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("indicator_id") or "").strip() == indicator_id:
                raw = (row.get("update_period_days") or "").strip()
                return int(raw) if raw else None
    return None


def _read_last_checked(repo_root: Path, adapters: tuple[str, ...]) -> str | None:
    """Return the latest ``last_checked`` across the owning adapters' checkpoints.

    The committed year-checkpoint (Row 2) records a per-year ``last_checked``;
    the freshest one is the indicator's last-touched stamp. Absent until Row 5
    writes checkpoints, in which case there is nothing to report yet.
    """
    stamps: list[str] = []
    for adapter_slug in adapters:
        checkpoint = state.load(adapter_slug, repo_root)
        for entry in checkpoint.get("years", []):
            if isinstance(entry, dict):
                stamp = entry.get("last_checked")
                if isinstance(stamp, str) and stamp:
                    stamps.append(stamp)
    return max(stamps) if stamps else None


__all__ = [
    "IndicatorStatus",
    "IngestError",
    "IngestUsageError",
    "OrchestrateResult",
    "RegistryConsistencyError",
    "SourceCoverage",
    "build_indicator_index",
    "compute_status",
    "orchestrate",
]
