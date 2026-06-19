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
import enum
import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yen_gov.canonical.ingest import state
from yen_gov.canonical.ingest.catalogue_fk import check_indicator_registration
from yen_gov.canonical.ingest.divergence import DivergenceResolution, check_divergence
from yen_gov.canonical.ingest.enrich_gates import (
    EntityObservation,
    check_bifurcation,
    check_price_basis,
    check_publisher_bounded_universe,
)
from yen_gov.canonical.ingest.fetch import CacheKey, FetchedCache
from yen_gov.canonical.ingest.messages import (
    CanonicalBatch,
    CanonicalObservationRow,
    ReplacementSemantics,
)
from yen_gov.canonical.ingest.registry import (
    Adapter,
    AdapterRunResult,
    FetchableAdapter,
    OrchestrateConfig,
    default_registry,
    summarise_indicator_csv,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec, PriceBasis
from yen_gov.canonical.ingest.splice_guard import (
    MethodologyBreak,
    check_splice,
    find_seams,
    load_methodology_breaks,
)
from yen_gov.core.events import FetchSkipped, emit

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping, Sequence

    from yen_gov.core.logging import StructuredLogger

# Repo-relative homes the status reader queries (POSIX, CLAUDE.md section 2).
_DATAPOINTS_GEO_REL = "datasets/data/datapoints/geo"
_VARIABLES_REL = "datasets/data/variables.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"
_INDICATORS_REL = "datasets/taxonomy/indicators.json"


class IngestError(Exception):
    """Base for orchestrator-level failures."""


class IngestUsageError(IngestError):
    """The run scope is unresolvable (no/unknown indicator or adapter)."""


class RegistryConsistencyError(IngestError):
    """An adapter's ``source_specs`` disagree with its registry key."""


# --------------------------------------------------------------------------- #
# stage window (--from / --to)
# --------------------------------------------------------------------------- #


class Stage(str, enum.Enum):
    """The three pure-filter stages, in pipeline order (plan section 3).

    Spec-validate + checkpoint-diff is ``run``'s fail-loud PREAMBLE, NOT a
    stage, so it runs regardless of the window. ``fetch`` lands the raw payload
    in the claim-check cache; ``enrich`` + ``publish`` are the adapter's FUSED
    ``process_year`` (an indicator's slice is parsed, gated, and UPSERT-published
    as one atomic unit). The runtime cut-points are therefore before-fetch /
    after-fetch / after-publish -- naming all three keeps the CLI vocabulary
    faithful to the plan while the engine collapses enrich+publish.
    """

    fetch = "fetch"
    enrich = "enrich"
    publish = "publish"


_STAGE_ORDER: tuple[Stage, ...] = (Stage.fetch, Stage.enrich, Stage.publish)


class StageWindow(BaseModel):
    """The ``[from_stage, to_stage]`` slice of the pipeline a ``run`` executes.

    The default (``fetch`` -> ``publish``) is the full flow: behaviour is
    byte-identical to a windowless run. ``from_stage`` must not come after
    ``to_stage`` in :data:`_STAGE_ORDER` -- enforced here so a programmatic
    caller cannot invert it (the CLI translates the failure into a clean
    exit-2).

    Because ``enrich`` + ``publish`` are fused in the adapter's
    ``process_year``, the window collapses to two decisions:

    * :attr:`runs_fetch` -- include FETCH (land/refresh the claim-check cache)?
      True iff ``from_stage`` is ``fetch`` (the lowest stage).
    * :attr:`runs_process` -- extend past FETCH into the fused enrich+publish?
      True iff ``to_stage`` is not ``fetch``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_stage: Stage = Stage.fetch
    to_stage: Stage = Stage.publish

    @model_validator(mode="after")
    def _check_order(self) -> "StageWindow":
        if _STAGE_ORDER.index(self.from_stage) > _STAGE_ORDER.index(self.to_stage):
            raise ValueError(
                f"--from {self.from_stage.value} must not be after --to "
                f"{self.to_stage.value} (stage order: fetch -> enrich -> publish)"
            )
        return self

    @property
    def runs_fetch(self) -> bool:
        """The window includes FETCH (the lowest stage)."""
        return self.from_stage == Stage.fetch

    @property
    def runs_process(self) -> bool:
        """The window extends past FETCH into the fused enrich+publish."""
        return self.to_stage != Stage.fetch

    @property
    def is_full(self) -> bool:
        """The default full flow (fetch -> publish); equivalent to no window."""
        return self.from_stage == Stage.fetch and self.to_stage == Stage.publish


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
    seam_years: tuple[int, ...] = ()
    is_spliced: bool = False


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
    resume: bool = False,
    stage_window: "StageWindow | None" = None,
    indicators: Iterable[dict] | None = None,
    concepts: Iterable[dict] | None = None,
    indicators_path: Path | None = None,
    concepts_path: Path | None = None,
    methodology_breaks: Iterable["Mapping[str, object]"] | None = None,
    methodology_breaks_path: Path | None = None,
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
        resume: the explicit "continue from the last completed checkpoint year"
            affordance. A plain run is already idempotent (the skip predicate
            refuses to skip an incomplete year), so this only annotates the log;
            correctness is identical with or without it.
        stage_window: the ``[from_stage, to_stage]`` slice to execute (default
            ``None`` = the full ``fetch`` -> ``publish`` flow, byte-identical to
            today). ``--to fetch`` warms the claim-check cache and stops before
            enrich+publish (emitting no datapoints); ``--from enrich`` skips
            FETCH and re-enriches + publishes from the cache a prior fetch
            landed (FAILS LOUD if the cache is cold). The preamble + the
            ``--resume`` / delta-skip behaviour run regardless of the window. A
            non-default window against a NON-fetchable adapter is refused: its
            ``run_indicator`` fuses fetch+enrich+publish with no cache seam to
            stop at or resume from.
        indicators / concepts / indicators_path / concepts_path: catalogue
            overrides forwarded to ``catalogue_fk`` (tests inject fixtures so
            they never walk the real corpus; defaults read the taxonomy SOT).
        methodology_breaks / methodology_breaks_path: overrides for the
            ``methodology_breaks`` table the publish-seam SPLICE gate consults
            (Row 6). Loaded LAZILY -- only a driven indicator whose emitted
            series actually changes ``source_id`` mid-series touches them, so a
            single-source run never reads the breaks table.

    Returns:
        :class:`OrchestrateResult` with the fan-out line and one
        :class:`AdapterRunResult` per driven indicator.

    Raises:
        IngestUsageError: the scope is unresolvable.
        CatalogueFkError / ConceptCompatibilityError: a targeted indicator
            fails the registration FK or concept-compatibility check.
        SpliceBreakRowError: a driven indicator's emitted series splices
            sources mid-series with no covering ``methodology_breaks`` row (the
            PUBLISH-seam provenance gate refuses such a run).
    """
    registry = dict(registry) if registry is not None else default_registry()
    index = build_indicator_index(registry)
    targets = _resolve_targets(index, indicator=indicator, adapter=adapter)
    window = stage_window if stage_window is not None else StageWindow()

    # --- PREAMBLE (not a stage): validate the targeted specs against the
    # catalogue (the spec-validation half). The cache-unit listing + checkpoint
    # delta-diff (Row 5) run INSIDE the per-adapter Fetch loop below, for
    # adapters that declare the fetchable capability; a Row-4 adapter keeps the
    # "every target, no skipping" behaviour.
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
    fetched_cache: FetchedCache | None = None
    driven_fetchable: set[str] = set()
    for slug, ind_id in work_list:
        # CAPABILITY dispatch -- the engine branches on the fetchable PROTOCOL,
        # never on adapter_slug (the Row-4 gate). A fetchable adapter runs the
        # Fetch + delta loop once for ALL its targeted indicators (so a shared
        # cache unit is fetched once); a Row-4 adapter is driven as-is.
        adapter_obj = registry[slug]
        if isinstance(adapter_obj, FetchableAdapter):
            if slug in driven_fetchable:
                continue
            driven_fetchable.add(slug)
            if fetched_cache is None:
                fetched_cache = FetchedCache(
                    repo_root=repo_root,
                    staging_dir=config.staging_dir,
                    logger=logger,
                )
            adapter_indicators = [i for s, i in work_list if s == slug]
            for res in _drive_fetchable_adapter(
                adapter_obj,
                adapter_indicators,
                repo_root=repo_root,
                config=config,
                fetched_cache=fetched_cache,
                logger=logger,
                resume=resume,
                stage_window=window,
            ):
                _log_published(logger, res)
                results.append(res)
        else:
            if not window.is_full:
                raise IngestUsageError(
                    f"adapter {slug!r} is not fetchable: its run_indicator fuses "
                    f"fetch+enrich+publish with no claim-check cache seam, so a "
                    f"stage window (--from {window.from_stage.value} --to "
                    f"{window.to_stage.value}) cannot be applied. Re-run it with "
                    f"the full default window (omit --from/--to)."
                )
            result = adapter_obj.run_indicator(
                ind_id, repo_root=repo_root, config=config
            )
            _log_published(logger, result)
            results.append(result)

    # PUBLISH-seam provenance gate (Row 6): refuse a run that emitted an
    # unmarked splice. Read off the honest on-disk series of each driven
    # indicator; a single-source series short-circuits before any catalogue or
    # breaks read, so the as-is single-source adapters are unaffected.
    _verify_published_provenance(
        repo_root,
        results,
        logger=logger,
        indicators=indicators,
        indicators_path=indicators_path,
        breaks=methodology_breaks,
        breaks_path=methodology_breaks_path,
    )

    return OrchestrateResult(
        indicator=indicator,
        adapter=adapter,
        fanout_line=fanout_line,
        results=tuple(results),
    )


# --------------------------------------------------------------------------- #
# fetchable Fetch + per-year delta loop (Row 5)
# --------------------------------------------------------------------------- #


def _drive_fetchable_adapter(
    adapter: FetchableAdapter,
    indicators: list[str],
    *,
    repo_root: Path,
    config: OrchestrateConfig,
    fetched_cache: FetchedCache,
    logger: "StructuredLogger | None",
    resume: bool,
    stage_window: StageWindow,
) -> list[AdapterRunResult]:
    """Drive one fetchable adapter through the [from, to] stage window.

    Fetches each per-year cache unit once (shared across the adapter's targeted
    indicators via ``fetched_cache``), SKIPS a year whose raw payload hash is
    unchanged (emitting ``fetch.skipped``, ticking the staleness clock, writing
    zero new datapoint bytes), re-processes a changed or never-completed year,
    and re-opens EVERY year on a ``spec_version`` bump. The checkpoint is
    persisted in a ``finally`` so a mid-run failure leaves the completed years
    recorded -- a re-run (or ``--resume``) continues from the last completed
    year. Each per-year file backs every indicator that draws from it, so all
    of a year's indicators are sliced BEFORE the year is marked completed.

    The ``stage_window`` selects which stages run per year:

    * ``runs_fetch`` -> :meth:`FetchedCache.get_or_fetch` (network/staged read +
      land the claim-check); else :meth:`FetchedCache.get_cached` (read the
      claim-check a prior fetch landed, FAIL LOUD if cold).
    * ``runs_process`` -> the adapter's fused enrich+publish ``process_year`` +
      advance the checkpoint to ``completed``. A FETCH-only window
      (``--to fetch``) warms the cache and stops here, NOT marking the year
      completed (so a later ``--from enrich`` re-processes it) and emitting no
      datapoints (so the run reports zero published indicators).
    """
    slug = adapter.adapter_slug
    checkpoint = state.load(slug, repo_root)
    stored_spec = checkpoint.get("spec_version", "")
    spec_ver = adapter.spec_version(indicators[0])
    spec_bumped = bool(stored_spec) and stored_spec != spec_ver

    if logger is not None and resume:
        logger.info(
            "ingest.resume",
            f"resuming {slug} from its committed checkpoint",
            stage="fetch",
            adapter_slug=slug,
        )

    # {year -> (shared cache unit, indicators drawing from it)}: a per-year file
    # is fetched once and every indicator that draws from it is sliced before
    # the year is recorded, so two indicators sharing a unit fetch once.
    units_by_year: dict[int, tuple[CacheKey, list[str]]] = {}
    for indicator_id in indicators:
        for unit in adapter.cache_units_for(indicator_id):
            _, owners = units_by_year.setdefault(unit.year, (unit, []))
            owners.append(indicator_id)

    try:
        for year in sorted(units_by_year):
            unit, owners = units_by_year[year]
            # FETCH stage, or read the claim-check a prior fetch landed.
            if stage_window.runs_fetch:
                fetched = fetched_cache.get_or_fetch(unit)
            else:
                fetched = fetched_cache.get_cached(unit)
            if not spec_bumped and state.should_skip_year(
                checkpoint, year, fetched.raw_bytes
            ):
                if logger is not None:
                    emit(
                        logger,
                        FetchSkipped(year=year, reason="raw payload unchanged"),
                        repo_root=repo_root,
                        stage="fetch",
                    )
                checkpoint = state.touch_year(
                    checkpoint, year=year, last_checked=state.now_iso_z()
                )
                continue
            if not stage_window.runs_process:
                # FETCH-only window (--to fetch): the claim-check is warm; stop
                # before enrich+publish. The year is left NOT-completed so a
                # later --from enrich re-processes it from the cache.
                continue
            # ENRICH + PUBLISH (the adapter's fused process_year).
            for indicator_id in owners:
                adapter.process_year(
                    indicator_id,
                    fetched=fetched,
                    repo_root=repo_root,
                    config=config,
                )
            checkpoint = state.advance_year(
                checkpoint,
                year=year,
                raw_payload=fetched.raw_bytes,
                completed=True,
                last_checked=state.now_iso_z(),
            )
    finally:
        checkpoint["spec_version"] = spec_ver
        state.write(checkpoint, repo_root)

    if not stage_window.runs_process:
        # FETCH-only: nothing was published this run, so there is no emitted
        # datapoints CSV to summarise. The warm claim-check cache is the only
        # artifact; the run honestly reports zero published indicators.
        return []
    return [
        summarise_indicator_csv(repo_root, indicator_id, adapter_slug=slug)
        for indicator_id in indicators
    ]


def _log_published(
    logger: "StructuredLogger | None", result: AdapterRunResult
) -> None:
    """Emit the per-indicator ``ingest.published`` line (both dispatch paths)."""
    if logger is None:
        return
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


# --------------------------------------------------------------------------- #
# PUBLISH seam: honesty gates (Row 6)
# --------------------------------------------------------------------------- #
#
# Two wirings, both in this module so all publish-seam orchestration lives in
# one place:
#
# * ``apply_publish_gates`` is the PRE-WRITE composite a CanonicalBatch-producing
#   PUBLISH path calls: it runs the optional ENRICH gates checkable on a batch
#   (price-basis / bifurcation / bounded-universe), the DIVERGENCE gate (batch
#   vs what is on disk), then the SPLICE gate on the PROSPECTIVE merged series,
#   and returns the validated rows to write. The Row-6 oracle drives this
#   directly (refuse -> author break row -> publish one series, source_id intact;
#   and a >tolerance overlap disagreement fails loud).
# * ``_verify_published_provenance`` is the orchestrator's POST-EMIT guard for
#   the as-is adapters (which write their own CSV and never hand us a batch):
#   it reads each driven indicator's honest on-disk series and refuses a run
#   that emitted an unmarked splice. A single-source series short-circuits in
#   ``find_seams`` before any catalogue/breaks read, so the existing
#   single-source adapters (and their byte-identity oracle) are untouched.


class PublishDecision(BaseModel):
    """The validated outcome of :func:`apply_publish_gates` (rows ready to write)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator_id: str = Field(min_length=1)
    rows: tuple[CanonicalObservationRow, ...]
    seam_years: tuple[int, ...] = ()
    recorded_resolutions: tuple[DivergenceResolution, ...] = ()


def _read_geo_dicts(repo_root: Path, indicator_id: str) -> list[dict]:
    """Read an indicator's emitted geo datapoints as ``{entity_id,time,value,source_id}``.

    The honest on-disk provenance projection both publish-seam gates reason
    over. Absent file -> ``[]`` (nothing published yet, nothing to gate).
    """
    path = repo_root / _DATAPOINTS_GEO_REL / f"{indicator_id}.csv"
    if not path.is_file():
        return []
    out: list[dict] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            entity_id = (row.get("entity_id") or "").strip()
            raw_time = (row.get("time") or "").strip()
            if not entity_id or not raw_time:
                continue
            raw_value = (row.get("value") or "").strip()
            out.append(
                {
                    "entity_id": entity_id,
                    "time": int(raw_time),
                    "value": float(raw_value) if raw_value else None,
                    "source_id": (row.get("source_id") or "").strip(),
                }
            )
    return out


def _merge_rows(
    existing: "Iterable[CanonicalObservationRow]",
    batch_rows: "Iterable[CanonicalObservationRow]",
    semantics: ReplacementSemantics,
) -> list[CanonicalObservationRow]:
    """Compute the prospective on-disk rows after PUBLISH reconciles the batch.

    ``upsert`` matches on the geo PK ``(entity_id, time)`` -- a batch row
    replaces the incumbent for its cell, others are kept; ``replace_partition``
    discards the incumbent entirely. Sorted by ``(entity_id, time)`` for a
    deterministic seam scan (``write_csv`` re-sorts by PK on emit).
    """
    if semantics == ReplacementSemantics.replace_partition:
        merged = {(r.entity_id, r.time): r for r in batch_rows}
    else:
        merged = {(r.entity_id, r.time): r for r in existing}
        for r in batch_rows:
            merged[(r.entity_id, r.time)] = r
    return [merged[k] for k in sorted(merged)]


def _concept_price_basis(
    concept: "Mapping[str, object] | None",
) -> PriceBasis | None:
    """Parse a concept row's ``price_basis`` dict into a comparable model (or None)."""
    if concept is None:
        return None
    raw = concept.get("price_basis")
    if not raw:
        return None
    return PriceBasis(basis=raw["basis"], base_year=raw.get("base_year"))  # type: ignore[index]


def apply_publish_gates(
    batch: CanonicalBatch,
    *,
    repo_root: Path,
    existing_rows: "Iterable[CanonicalObservationRow] | None" = None,
    concept: "Mapping[str, object] | None" = None,
    methodology_break_ids: "Sequence[str] | None" = None,
    breaks: "Iterable[Mapping[str, object]] | None" = None,
    breaks_path: Path | None = None,
    divergence_resolutions: Iterable[DivergenceResolution] = (),
    incoming_price_basis: PriceBasis | None = None,
    entity_kinds: "Mapping[str, str] | None" = None,
    allowed_entities: "Sequence[str] | None" = None,
) -> PublishDecision:
    """Run the PUBLISH-seam honesty gates on a batch and return rows to write.

    Order: the batch-checkable ENRICH gates (price-basis when a basis is given;
    bifurcation when ``entity_kinds`` is given; bounded-universe when
    ``allowed_entities`` is given), then the DIVERGENCE gate (batch vs
    ``existing_rows`` -- read off disk when not supplied), then the SPLICE gate
    on the merged series. Returns a :class:`PublishDecision` whose ``rows`` are
    the validated, merged observation rows the caller writes via ``write_csv``.

    Raises the gate's typed error (``PriceBasisError`` / ``BifurcationError`` /
    ``PublisherBoundedUniverseError`` / ``DivergenceError`` /
    ``SpliceBreakRowError``) on the first violation.
    """
    if existing_rows is None:
        existing_models = [
            CanonicalObservationRow(**d) for d in _read_geo_dicts(repo_root, batch.indicator_id)
        ]
    else:
        existing_models = list(existing_rows)

    if incoming_price_basis is not None:
        check_price_basis(incoming_price_basis, _concept_price_basis(concept))
    if entity_kinds is not None:
        check_bifurcation(
            EntityObservation(
                entity_id=r.entity_id,
                time=r.time,
                entity_kind=entity_kinds.get(r.entity_id),
            )
            for r in batch.observation_rows
        )
    if allowed_entities is not None:
        check_publisher_bounded_universe(
            (r.entity_id for r in batch.observation_rows),
            allowed_entities=allowed_entities,
        )

    applied = check_divergence(
        batch.observation_rows,
        existing_models,
        concept=concept,
        resolutions=divergence_resolutions,
    )

    merged = _merge_rows(
        existing_models, batch.observation_rows, batch.replacement_semantics
    )
    breaks_map = load_methodology_breaks(breaks=breaks, breaks_path=breaks_path)
    seam_years = check_splice(
        merged,
        indicator_id=batch.indicator_id,
        methodology_break_ids=methodology_break_ids,
        breaks=breaks_map,
    )
    return PublishDecision(
        indicator_id=batch.indicator_id,
        rows=tuple(merged),
        seam_years=seam_years,
        recorded_resolutions=applied,
    )


def _load_indicator_rows(
    indicators: Iterable[dict] | None,
    indicators_path: Path | None,
    repo_root: Path,
) -> list[dict]:
    """Load the indicator catalogue rows (injected fixtures or the run's repo)."""
    if indicators is not None:
        return list(indicators)
    path = indicators_path or (repo_root / _INDICATORS_REL)
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("indicators", [])
    return rows if isinstance(rows, list) else []


def _indicator_break_ids(indicator_id: str, indicator_rows: list[dict]) -> list[str]:
    """Return an indicator's ``methodology_break_ids`` (or ``[]`` if undeclared)."""
    for row in indicator_rows:
        if row.get("indicator_id") == indicator_id:
            ids = row.get("methodology_break_ids") or []
            return [str(i) for i in ids] if isinstance(ids, list) else []
    return []


def _verify_published_provenance(
    repo_root: Path,
    results: list[AdapterRunResult],
    *,
    logger: "StructuredLogger | None",
    indicators: Iterable[dict] | None,
    indicators_path: Path | None,
    breaks: "Iterable[Mapping[str, object]] | None",
    breaks_path: Path | None,
) -> None:
    """Refuse a run whose emitted series splices sources without a break row.

    For each distinct driven indicator: read its on-disk series; if no entity's
    rows change ``source_id`` mid-series (the common single-source / disjoint
    case) skip without any catalogue or breaks read; otherwise resolve the
    indicator's ``methodology_break_ids`` + the breaks table and apply the
    SPLICE gate, which raises :class:`SpliceBreakRowError` on an uncovered seam.
    """
    seen: set[str] = set()
    breaks_map: "dict[str, MethodologyBreak] | None" = None
    indicator_rows: list[dict] | None = None
    for res in results:
        indicator_id = res.indicator_id
        if indicator_id in seen:
            continue
        seen.add(indicator_id)
        rows = _read_geo_dicts(repo_root, indicator_id)
        if len(rows) < 2 or not find_seams(rows):
            continue
        if breaks_map is None:
            breaks_map = load_methodology_breaks(breaks=breaks, breaks_path=breaks_path)
        if indicator_rows is None:
            indicator_rows = _load_indicator_rows(indicators, indicators_path, repo_root)
        check_splice(
            rows,
            indicator_id=indicator_id,
            methodology_break_ids=_indicator_break_ids(indicator_id, indicator_rows),
            breaks=breaks_map,
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
    last-checked stamp from the committed checkpoint when one exists. The
    ``seam_years`` (a mid-series ``source_id`` change in any entity) surface the
    splice provenance Row 6 enforces -- read-only here (it RAISES nowhere), so
    ``status`` can flag a spliced series without re-running PUBLISH.
    """
    registry = dict(registry) if registry is not None else default_registry()
    index = build_indicator_index(registry)
    adapters = tuple(sorted(index.get(indicator, [])))
    coverage = _read_coverage(repo_root, indicator)
    seams = find_seams(_read_geo_dicts(repo_root, indicator))
    seam_years = tuple(sorted({year for years in seams.values() for year in years}))
    return IndicatorStatus(
        indicator_id=indicator,
        adapters=adapters,
        coverage=coverage,
        update_period_days=_read_update_period(repo_root, indicator),
        last_checked=_read_last_checked(repo_root, adapters),
        has_coverage=bool(coverage),
        seam_years=seam_years,
        is_spliced=bool(seam_years),
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
    "PublishDecision",
    "RegistryConsistencyError",
    "SourceCoverage",
    "Stage",
    "StageWindow",
    "apply_publish_gates",
    "build_indicator_index",
    "compute_status",
    "orchestrate",
]
