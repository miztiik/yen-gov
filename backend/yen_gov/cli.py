"""yen-gov CLI."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import typer

from yen_gov.sources.eci.events import event_info_for
from yen_gov.sources.eci.statistical_report_detailed import (
    parse_detailed_results,
    to_constituency_results,
)
from yen_gov.coverage import (
    INVENTORY_REL,
    compute_coverage,
    render_markdown,
)
from yen_gov.validate import run as run_validate

# G9 (2026-06-08): top-N / collapse-others rule formalised in PR-K
# (2026-05-18) lives here as a presentation constant, not a config knob.
# config/processing.json + ProcessingConfig were retired - the only
# alive consumer was eci-statreport-emit-local below; the fetch.* block
# died with core/http.py in B4-pt2.4 (#828).
_TOP_N_DEFAULT = 5
_COLLAPSE_OTHERS_DEFAULT = True

app = typer.Typer(help="yen-gov pipeline CLI", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """yen-gov pipeline CLI."""


@app.command()
def validate(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Two-tier validation across schemas and data files (CLAUDE.md §11)."""
    failures = run_validate(root)

    if not failures:
        typer.echo("validate: OK (0 issues)")
        raise typer.Exit(0)

    by_tier: dict[str, int] = {"A": 0, "B": 0}
    for f in failures:
        by_tier[f.tier] = by_tier.get(f.tier, 0) + 1
        typer.echo(f"  [tier {f.tier}] {f.file}: {f.message}")
    typer.echo(f"\nvalidate: FAILED — Tier A: {by_tier.get('A', 0)}, Tier B: {by_tier.get('B', 0)}")
    raise typer.Exit(1)


@app.command("check-overlap")
def check_overlap(
    noun: str = typer.Option(..., "--noun", help="Candidate concept noun (citizen-readable)."),
    unit: str = typer.Option(..., "--unit", help="Candidate unit canonical (e.g. kWh, count, pct)."),
    normalisation: str = typer.Option(
        ...,
        "--normalisation",
        help="One of: absolute, per_capita, per_area, share, ratio, index.",
    ),
    entity_kind: str = typer.Option(
        ...,
        "--entity-kind",
        help="One of: country, state, district, ac, party, candidate.",
    ),
    top_n: int = typer.Option(5, "--top-n", help="Max matches to display."),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Score a candidate concept against datasets/taxonomy/concepts.json.

    Per docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md
    §0quat guardrail #13: every new indicator_id MUST FK to a row in
    concepts.json. Run this BEFORE authoring any new ingest handover-doc.
    If any match scores >= 0.70 the action is UPSERT into the existing
    indicator or add a facet -- NOT mint a new id. Exits 1 in that case so
    the gate can be wired into a pre-PR hook.
    """
    from yen_gov.canonical.concept_registry import find_overlap

    matches = find_overlap(
        noun=noun,
        unit=unit,
        normalisation=normalisation,
        entity_kind=entity_kind,
        concepts_path=root / "datasets" / "taxonomy" / "concepts.json",
        top_n=top_n,
    )

    typer.echo(
        f"check-overlap: candidate noun={noun!r} unit={unit!r} "
        f"normalisation={normalisation!r} entity_kind={entity_kind!r}"
    )
    if not matches:
        typer.echo("  no concepts in registry; mint_new is acceptable.")
        raise typer.Exit(0)

    typer.echo(f"  top {len(matches)} matches:")
    typer.echo(f"  {'score':>6}  {'action':<10}  concept_id")
    for m in matches:
        typer.echo(
            f"  {m.match_score:>6.3f}  {m.recommended_action:<10}  {m.concept_id}"
        )

    blockers = [m for m in matches if m.recommended_action != "mint_new"]
    if blockers:
        top = blockers[0]
        typer.echo(
            f"\ncheck-overlap: FAILED -- {len(blockers)} match(es) score "
            f">= 0.70. Top recommendation: {top.recommended_action} into "
            f"{top.concept_id!r}. Per guardrail #13 do NOT mint a new id "
            f"when a concept match crosses the threshold; UPSERT or add a "
            f"facet on the existing indicator instead."
        )
        raise typer.Exit(1)

    typer.echo("\ncheck-overlap: OK -- no match crosses 0.70; mint_new is acceptable.")
    raise typer.Exit(0)


@app.command("pre-flight-ingest")
def pre_flight_ingest(
    proposal_file: Path = typer.Option(
        None,
        "--proposal-file",
        help=(
            "Path to a JSON file with the ingest proposal. Canonical input "
            "format; CLI flags below are sugar that hydrate an in-memory "
            "proposal -- the file always wins if both are supplied."
        ),
        file_okay=True,
        dir_okay=False,
    ),
    proposed_id: str = typer.Option(None, "--proposed-id"),
    family: str = typer.Option(None, "--family"),
    concept: str = typer.Option(None, "--concept"),
    unit: str = typer.Option(None, "--unit"),
    normalisation: str = typer.Option(None, "--normalisation"),
    entity_kind: str = typer.Option(None, "--entity-kind"),
    source_producer: str = typer.Option(None, "--source-producer"),
    source_title: str = typer.Option(None, "--source-title"),
    source_vintage: str = typer.Option(None, "--source-vintage"),
    update_period_days: int = typer.Option(None, "--update-period-days"),
    justification: str = typer.Option(None, "--justification"),
    report: Path = typer.Option(
        None,
        "--report",
        help="Write the JSON report to this path (in addition to stdout summary).",
        file_okay=True,
        dir_okay=False,
    ),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Pre-flight ingest gate (ADR-0046).

    Runs the six mechanical checks the human reviewer would otherwise have
    to apply by hand on every new-source ingest handover-doc:

    \b
      1. concept_overlap       - proposed concept vs concepts.json
      2. concept_fk            - proposal's concept_id resolves in registry
      3. grain_prefix          - proposed_id has no state-/district-/national- prefix
      4. update_period_days    - declared as positive integer
      5. justification         - non-empty string >= 20 chars
      6. source_id_derivation  - matches derive_source_id output

    Exit codes: 0 = pass (verdict mint_new / upsert / add_facet);
    1 = soft-warn (verdict + at least one warning); 2 = hard-fail
    (verdict = abort). No override flag per CLAUDE.md Holy Law #5.
    """
    from yen_gov.preflight import build_report, load_proposal

    cli_overrides = {
        "proposed_id": proposed_id,
        "family": family,
        "concept": concept,
        "unit": unit,
        "normalisation": normalisation,
        "entity_kind": entity_kind,
        "source_producer": source_producer,
        "source_title": source_title,
        "source_vintage": source_vintage,
        "update_period_days": update_period_days,
        "justification": justification,
    }

    try:
        proposal = load_proposal(
            proposal_file=proposal_file,
            cli_overrides=cli_overrides if proposal_file is None else None,
        )
    except ValueError as e:
        typer.echo(f"pre-flight-ingest: ERROR -- {e}", err=True)
        raise typer.Exit(2)

    report_obj = build_report(proposal, root=root)

    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps(report_obj.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    typer.echo(f"pre-flight-ingest: verdict={report_obj.verdict}")
    typer.echo(f"  recommended_action: {report_obj.recommended_action.kind}")
    if report_obj.recommended_action.target_indicator_id:
        typer.echo(
            f"  target_indicator_id: {report_obj.recommended_action.target_indicator_id}"
        )
    typer.echo(f"  rationale: {report_obj.recommended_action.rationale}")
    for c in report_obj.checks:
        typer.echo(f"  [{c.status:>4}] {c.name}: {c.evidence}")
    if report is not None:
        typer.echo(f"  report: {report.as_posix()}")

    raise typer.Exit(report_obj.exit_code)


@app.command("emit-taxonomy")
def emit_taxonomy(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory). Resolves to <root>/datasets/taxonomy/.",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Plan-only: compile each seed into a tempfile mirror of "
            "datasets/taxonomy/ + datasets/governments/, byte-compare to the "
            "real on-disk targets, log UNCHANGED|CHANGED per planned file, "
            "write nothing to disk. Manifest regen also runs as dry-run."
        ),
    ),
) -> None:
    """Compile hand-authored taxonomy parquet files (operator command).

    Regenerates the canonical hand-authored taxonomy parquets read by
    the static frontend via DuckDB-WASM:

    - **Entities, X1a-fu2-A (2026-06-07): RETIRED.**
      ``datasets/taxonomy/entities.parquet`` had its frontend readers
      flipped to ``datasets/data/entities/geo.csv`` (loadStates via
      DuckDB-WASM ``read_csv(columns=...)``) and to the hand-authored
      ``datasets/taxonomy/entities.json`` SoT (loadDistricts +
      loadAllDistrictEntities, which need ``legacy_id`` /
      ``parent_entity_id`` shapes that geo.csv does not carry). Step 5
      still drives the in-memory row-build through
      ``entities_seed.compile_to_parquet`` because step 6's office-bearer
      reader is a DuckDB SQL query against the parquet, but the file is
      written into a per-run tempdir; no parquet survives under
      ``datasets/taxonomy/``.
    - **Office holdings, B3-followup (2026-06-07): governments parquets
      RETIRED.** Step 6 now compiles ``datasets/taxonomy/office_holdings.json``
      to in-process row tuples (via ``office_holdings_seed`` in a tempdir
      parquet detour) and projects them to the canonical 3-CSV term-shape
      under ``datasets/data/`` via ``governments_term_shape.emit``:
      ``entities/office.csv`` + ``entities/holder.csv`` +
      ``datapoints/office_holdings.csv``. No parquet survives under
      ``datasets/governments/``.
    - **Indicators catalogue, X1a-fu2-B (2026-06-07): RETIRED.**
      ``datasets/taxonomy/indicators.parquet`` had ZERO live frontend
      readers; the parquet file was deleted in that PR and step 7 is gone.
      ``datasets/taxonomy/indicators.json`` remains the hand-authored
      catalogue SoT.

    Post-B3 (2026-06-06): the dead taxonomy seed steps for
    facet-axes / state_tiers / topics / indicator_topic_tags /
    election_events / methodology_breaks / sources / persons were
    removed because the matching parquets were retired in X1b (#814).
    The CSV replacements live under ``datasets/data/`` and are emitted
    by the canonical CSV writer / B2a seed emitters, not here.

    Post-B3-pt2 (2026-06-06): step 6 (office_holdings) no longer takes a
    ``sources.parquet`` argument; the Wikipedia "List of CMs" + per-
    citation-group source rows live in ``datasets/data/entities/source.csv``
    seeded once via B2a/source_csv, not per emit-taxonomy run.

    Post-B3-followup (2026-06-07): step 6 emits CSV only (no parquet
    survives under ``datasets/governments/``); the in-process tempdir
    parquet path is an implementation detour, not a citizen-visible
    artifact.
    """
    from yen_gov.canonical.alliance_membership_csv import (
        emit as _emit_alliance_membership_csv,
    )
    from yen_gov.canonical.entities_seed import (
        compile_to_parquet as _compile_entities,
    )
    from yen_gov.canonical.office_holdings_seed import (
        compile_to_parquet as _compile_office_holdings,
    )
    from yen_gov.canonical.party_alliances_csv import (
        emit as _emit_party_alliances_csv,
    )
    from yen_gov.canonical.reingest.governments_term_shape import (
        emit as _emit_governments_term_shape,
    )
    from yen_gov.canonical.writer import _regenerate_manifest

    real_taxonomy_dir = root / "datasets" / "taxonomy"
    real_taxonomy_dir.mkdir(parents=True, exist_ok=True)

    # PR-A2: dry-run mirrors taxonomy/ into a tempdir so every seed
    # compile runs end-to-end without touching the real on-disk
    # parquets. After the pipeline finishes we byte-compare each
    # generated tempfile against the real on-disk target and log an
    # UNCHANGED|CHANGED|NEW line per file.
    #
    # B3-followup (2026-06-07): governments/ is no longer in the
    # dry-run mirror because the parquets there retired - office
    # holdings now emit through a per-run tempdir detour to CSV under
    # datasets/data/ (step 6 below).
    if dry_run:
        import shutil as _shutil
        import tempfile as _tempfile

        _td = _tempfile.TemporaryDirectory(prefix="ygov_emit_dryrun_")
        try:
            td_root = Path(_td.name)
            taxonomy_dir = td_root / "taxonomy"
            _shutil.copytree(real_taxonomy_dir, taxonomy_dir, dirs_exist_ok=True)
            typer.echo("emit-taxonomy [dry-run]: mirroring taxonomy/ to tempdir")
        except BaseException:
            _td.cleanup()
            raise
    else:
        _td = None
        taxonomy_dir = real_taxonomy_dir

    try:
        prefix = "emit-taxonomy [dry-run]" if dry_run else "emit-taxonomy"

        # 5+6) entities + office_holdings -> 3-CSV term-shape
        # (post-X1a-fu2-A, 2026-06-07).
        #
        # ``datasets/taxonomy/entities.parquet`` RETIRED per X1a-fu2-A
        # sub-row A: the frontend reader-flipped to
        # ``datasets/data/entities/geo.csv`` via DuckDB-WASM
        # ``read_csv(columns=...)`` (loadStates) and to the hand-authored
        # ``datasets/taxonomy/entities.json`` SoT (loadDistricts, which
        # needs the Wikipedia 3-letter ``legacy_id`` column that geo.csv
        # does not carry). We still drive the in-memory row-build through
        # ``entities_seed.compile_to_parquet`` (because step 6's office
        # bearer reader is a DuckDB SQL query against the parquet) but
        # write it into a per-run tempdir; the tempdir lives through
        # step 6 so the office_holdings reader still resolves and is
        # cleaned up before this command exits. Same in-process tempdir
        # detour pattern as step 6 (B3-followup, 2026-06-07).
        #
        # Step 6: ``datasets/governments/{dim_offices,governments_office_holdings}.parquet``
        # pair RETIRED per umbrella plan O1 (no strangler-fig); CSV is
        # the survivor. We still drive the in-memory row-build through
        # ``office_holdings_seed.compile_to_parquet`` (because its
        # validation + citation logic is non-trivial and tested), but
        # we write the parquets into a per-run tempdir and immediately
        # project them onto the canonical 3-CSV shape under
        # ``datasets/data/`` via ``governments_term_shape.emit``.
        # The canonical entities/parties/geo CSVs under
        # ``datasets/data/`` must already exist (seeded by B2a).
        office_holdings_json = taxonomy_dir / "office_holdings.json"
        import tempfile as _tempfile_step5_6
        with _tempfile_step5_6.TemporaryDirectory(prefix="ygov_entities_") as _step5_tmp:
            _step5_tmp_dir = Path(_step5_tmp)
            entities_parquet = _step5_tmp_dir / "entities.parquet"
            rows = _compile_entities(
                taxonomy_dir / "entities.json",
                entities_parquet,
            )
            typer.echo(
                f"{prefix}: compiled {rows} entity rows "
                f"(via tempdir; no parquet survives under datasets/taxonomy/)"
            )
            with _tempfile_step5_6.TemporaryDirectory(prefix="ygov_office_holdings_") as _step6_tmp:
                _step6_tmp_dir = Path(_step6_tmp)
                office_count, holdings_count = _compile_office_holdings(
                    office_holdings_json,
                    entities_parquet,
                    _step6_tmp_dir / "dim_offices.parquet",
                    _step6_tmp_dir / "governments_office_holdings.parquet",
                )
                emitted = _emit_governments_term_shape(
                    parquet_dir=_step6_tmp_dir,
                    geo_entities_csv=root / "datasets" / "data" / "entities" / "geo.csv",
                    party_entities_csv=root / "datasets" / "data" / "entities" / "parties.csv",
                    out_data_dir=root / "datasets" / "data",
                )
        for file_class, path in emitted.items():
            typer.echo(
                f"{prefix}: wrote {path.relative_to(root).as_posix()} [{file_class}]"
            )
        typer.echo(
            f"{prefix}: compiled {office_count} offices + {holdings_count} holdings "
            f"(via tempdir; no parquet survives under datasets/governments/)"
        )

        # 7) indicators catalogue - RETIRED in X1a-fu2-B (2026-06-07).
        # `datasets/taxonomy/indicators.parquet` had ZERO live frontend
        # readers as of 2026-06-07 grep (the citizen path goes through
        # `frontend/src/lib/canonical/indicator-allowlist.ts` which carries
        # hand-authored IndicatorMeta inline). The parquet file was deleted
        # in this PR; `datasets/taxonomy/indicators.json` remains the
        # hand-authored SoT.

        # 8) party_alliances -> CSV transcode (X1a-fu2-C, 2026-06-07).
        # Projects ``datasets/elections/dim_party_alliances.parquet`` 1:1
        # to the canonical long-format CSV at
        # ``datasets/data/entities/party_alliances.csv`` so the frontend
        # state-overview view-model can read alliances via inline
        # ``read_csv(columns=...)``. The parquet is retired in the same
        # PR; once it is gone this step becomes a silent skip (the
        # committed CSV is then the source of truth). See
        # ``canonical/party_alliances_csv.py`` module docstring for the
        # full lifecycle + the writer-survival note (legacy ECI ingest
        # adapters still produce ``party_alliance_dim_rows`` envelopes
        # that the parquet writer in ``canonical/writer.py`` would
        # re-emit until B4 retires them).
        alliances_parquet = (
            root / "datasets" / "elections" / "dim_party_alliances.parquet"
        )
        alliances_csv = (
            root / "datasets" / "data" / "entities" / "party_alliances.csv"
        )
        emitted_alliances = _emit_party_alliances_csv(
            parquet_path=alliances_parquet,
            out_csv_path=alliances_csv,
        )
        if emitted_alliances is not None:
            typer.echo(
                f"{prefix}: wrote {emitted_alliances.relative_to(root).as_posix()} "
                "[datasets/data/entities/party_alliances.csv]"
            )
        else:
            typer.echo(
                f"{prefix}: skipped party_alliances.csv (parquet retired; "
                "committed CSV is authoritative)"
            )

        # 9) alliance_membership -> CSV emit (plan section 20.4).
        # Back-fills datasets/data/datapoints/alliance_membership.csv from
        # the per-CM-tenure alliance field on office_holdings.json (real
        # term boundaries) plus the per-event snapshot in
        # party_alliances.csv (term_start = event polled_on date; term_end
        # null since the snapshot does not record an end). PK is
        # (alliance_id, party_id, term_start); holdings-derived rows win
        # on collision because they carry explicit term_end values. Per
        # Holy Law #9 every row carries source_id FK to source.csv -
        # resolved by URL match against either the holding's
        # citation_group_id.url_main or the office_citations[office_id]
        # entry. The emitter surfaces unresolved party-ECI codes and
        # source URLs as diagnostics for operator follow-up; the offending
        # rows are SKIPPED, never silently dropped or guessed.
        alliance_membership_csv = (
            root / "datasets" / "data" / "datapoints" / "alliance_membership.csv"
        )
        am_result = _emit_alliance_membership_csv(
            office_holdings_json=office_holdings_json,
            party_alliances_csv=alliances_csv,
            parties_entities_csv=root
            / "datasets"
            / "data"
            / "entities"
            / "parties.csv",
            election_events_json=taxonomy_dir / "election_events.json",
            source_csv=root / "datasets" / "data" / "entities" / "source.csv",
            out_csv_path=alliance_membership_csv,
        )
        typer.echo(
            f"{prefix}: wrote {am_result.out_csv_path.relative_to(root).as_posix()} "
            f"[datasets/data/datapoints/alliance_membership.csv] "
            f"({am_result.rows_written} rows: "
            f"{am_result.from_holdings} from office_holdings.json, "
            f"{am_result.from_party_alliances} from party_alliances.csv)"
        )
        if am_result.unresolved_party_eci_codes:
            typer.echo(
                f"{prefix}: alliance_membership skipped holdings with unresolved "
                f"party ECI codes: {list(am_result.unresolved_party_eci_codes)}"
            )
        if am_result.unresolved_source_urls:
            typer.echo(
                f"{prefix}: alliance_membership skipped holdings with unresolved "
                f"source URLs (not in source.csv): "
                f"{list(am_result.unresolved_source_urls)}"
            )

        _regenerate_manifest(root / "datasets", dry_run=dry_run)

        if dry_run:
            # Byte-compare every file generated in the tempdir mirror against
            # its real counterpart and log a per-file UNCHANGED|CHANGED|NEW
            # summary. The manifest is regenerated against the real datasets/
            # tree (so it sees the real on-disk parquets, not the tempdir
            # copies), and ``_regenerate_manifest`` itself honours dry_run.
            for tmp_file in sorted(
                p for p in td_root.rglob("*") if p.is_file()
            ):
                rel = tmp_file.relative_to(td_root)
                real_file = root / "datasets" / rel
                _compare_dryrun_file(tmp_file, real_file)
    finally:
        if _td is not None:
            _td.cleanup()


def _compare_dryrun_file(tmp_file: Path, real_file: Path) -> None:
    """Byte-compare a tempdir-mirrored seed output against the real on-disk
    target and emit a single ``UNCHANGED|CHANGED|NEW`` line via ``typer.echo``.

    Used by ``emit-taxonomy --dry-run``. Read I/O only; never writes either
    side.
    """
    new_bytes = tmp_file.read_bytes()
    rel = real_file.name
    if not real_file.is_file():
        typer.echo(f"emit-taxonomy [dry-run]: NEW {real_file.as_posix()} ({len(new_bytes)} bytes)")
        return
    old_bytes = real_file.read_bytes()
    status = "UNCHANGED" if old_bytes == new_bytes else "CHANGED"
    typer.echo(
        f"emit-taxonomy [dry-run]: {status} {real_file.as_posix()} "
        f"({len(old_bytes)} -> {len(new_bytes)} bytes)"
    )


@app.command("derive-national-reference")
def derive_national_reference(
    indicator: str = typer.Option(
        ...,
        "--indicator",
        help="Canonical indicator id (file stem under datasets/data/datapoints/geo/).",
    ),
    population_indicator: str = typer.Option(
        "state-population-lakhs",
        "--population-indicator",
        help=(
            "Canonical indicator id used as the population denominator "
            "for the pop-weighted average (file stem under "
            "datasets/data/datapoints/geo/)."
        ),
    ),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Compute and write the national reference series for one indicator (G31a).

    Produces a sibling file
    ``datasets/data/datapoints/geo/<indicator>-national.csv`` carrying
    rows for two derived pseudo-entities -- ``IN-pop-weighted`` and
    ``IN-median`` -- one row per (entity_id, time) per the standard
    long-format 4-column shape. Idempotent: re-running overwrites the
    sibling file with the same deterministic output (writer skips the
    write when bytes match exactly).

    Inputs:
    - per-state observations:
      ``datasets/data/datapoints/geo/<indicator>.csv``
    - population denominator:
      ``datasets/data/datapoints/geo/<population_indicator>.csv``
      (defaults to ``state-population-lakhs``).
    - citation ledger: ``datasets/data/entities/source.csv`` -- the
      "yen-gov (derived)" row must already exist (B2a/source_csv seed)
      with the deterministic ``src-...`` id derived from the triple
      ``("yen-gov (derived)", "National reference line ...",
      "2026-06-09")``.

    Parent plan section 20.11 (Max + Hans verdict) authorises this
    derivation. The direction hard gate (``higher_is_better`` /
    ``lower_is_better`` only -- never ``neutral``) is enforced at the
    renderer-side seam, not here; this command computes whenever asked.
    """
    from yen_gov.canonical.citation import derive_source_id
    from yen_gov.canonical.csv_writer import write_csv
    from yen_gov.canonical.national_reference import compute_national_reference_rows

    datapoints_dir = root / "datasets" / "data" / "datapoints" / "geo"
    indicator_csv = datapoints_dir / f"{indicator}.csv"
    population_csv = datapoints_dir / f"{population_indicator}.csv"
    out_csv = datapoints_dir / f"{indicator}-national.csv"
    source_csv = root / "datasets" / "data" / "entities" / "source.csv"

    if not indicator_csv.exists():
        typer.echo(f"derive-national-reference: missing input {indicator_csv.as_posix()}", err=True)
        raise typer.Exit(2)
    if not population_csv.exists():
        typer.echo(
            f"derive-national-reference: missing population denominator "
            f"{population_csv.as_posix()}",
            err=True,
        )
        raise typer.Exit(2)
    if not source_csv.exists():
        typer.echo(
            f"derive-national-reference: missing citation ledger {source_csv.as_posix()}",
            err=True,
        )
        raise typer.Exit(2)

    # Derived-citation identity per parent plan section 20.11 + CLAUDE.md
    # section 12 + ADR-0042 (vintage = operator snapshot window). The
    # vintage is hard-coded (NOT datetime.now per CLAUDE.md section 10
    # anti-pattern) -- it pins the citation to the operator snapshot
    # window that this derivation rule was authored against.
    derived_source_id = derive_source_id(
        "yen-gov (derived)",
        "National reference line (pop-weighted average + median of states), "
        "computed from per-state values",
        "2026-06-09",
    )

    sources_text = source_csv.read_text(encoding="utf-8")
    if derived_source_id not in sources_text:
        typer.echo(
            f"derive-national-reference: citation row {derived_source_id!r} missing "
            f"from {source_csv.as_posix()}; add it before running this command.",
            err=True,
        )
        raise typer.Exit(2)

    state_rows = _read_long_csv(indicator_csv)
    population_rows = _read_long_csv(population_csv)
    # Filter the population to state-grain entities (drop IN itself and
    # any IN-* derived pseudo-entities); the compute function joins by
    # entity_id and we never want a country-grain population row to be
    # treated as a state-grain weight.
    population_rows = [r for r in population_rows if not str(r["entity_id"]).startswith("IN")]

    derived_rows = compute_national_reference_rows(
        state_rows, population_rows, derived_source_id
    )
    if not derived_rows:
        typer.echo(
            f"derive-national-reference: zero derived rows for indicator={indicator!r}; "
            f"writing empty file would still be a no-op.",
            err=True,
        )
        raise typer.Exit(1)

    write_csv(
        path=out_csv,
        file_class="datasets/data/datapoints/geo/*.csv",
        rows=derived_rows,
    )

    pw_count = sum(1 for r in derived_rows if r["entity_id"] == "IN-pop-weighted")
    median_count = sum(1 for r in derived_rows if r["entity_id"] == "IN-median")
    typer.echo(
        f"derive-national-reference: wrote {out_csv.relative_to(root).as_posix()} "
        f"({len(derived_rows)} rows: {pw_count} pop-weighted + {median_count} median; "
        f"input state rows: {len(state_rows)}; source_id: {derived_source_id})"
    )


@app.command("derive-party-pages")
def derive_party_pages(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Compute party-page derived marts from canonical electoral CSVs."""
    from yen_gov.canonical.derived.party_pages import refresh_party_page_marts

    root_resolved = root.resolve()
    result = refresh_party_page_marts(root_resolved)
    typer.echo(
        "derive-party-pages: wrote "
        f"{result.history_path.relative_to(root_resolved).as_posix()} "
        f"({result.history_rows} rows)"
    )
    typer.echo(
        "derive-party-pages: wrote "
        f"{result.strongholds_path.relative_to(root_resolved).as_posix()} "
        f"({result.stronghold_rows} rows)"
    )
    typer.echo(
        "derive-party-pages: wrote "
        f"{result.manifest_path.relative_to(root_resolved).as_posix()} "
        f"(input files: {result.input_file_count}; "
        f"party pages: {result.party_count}; "
        f"signature: {result.input_signature[:12]})"
    )


def _read_long_csv(path: Path) -> list[dict[str, object]]:
    """Read a 4-column long-format CSV (entity_id, time, value, source_id).

    Parses ``time`` as int and ``value`` as float (empty cell -> None).
    Used by ``derive-national-reference`` to materialise the per-state
    and population inputs before handing them to the pure compute
    function. Tier-B / B1.3 CsvValidator owns full contract checks; this
    helper is the minimum-viable read for the compute step.
    """
    import csv as _csv

    out: list[dict[str, object]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = _csv.DictReader(fh)
        for row in reader:
            value_raw = (row.get("value") or "").strip()
            value: float | None = float(value_raw) if value_raw else None
            out.append(
                {
                    "entity_id": row["entity_id"],
                    "time": int(row["time"]),
                    "value": value,
                    "source_id": row.get("source_id") or "",
                }
            )
    return out


def _refresh_party_pages_after_electoral_ingest(root: Path, prefix: str) -> None:
    """Refresh party-page marts after an electoral ingest command.

    The older elections writer path is still mid-rip: some commands write
    per-state electoral datapoint CSVs directly, while others still flow
    through the envelope writer. This shared post-step keeps CLI ingests from
    leaving `/parties/<slug>` read models stale; Tier-B validation catches any
    non-CLI path that edits the same inputs without running this refresh.
    """
    from yen_gov.canonical.derived.party_pages import refresh_party_page_marts

    result = refresh_party_page_marts(root)
    typer.echo(
        f"{prefix}: refreshed party-page marts "
        f"({result.history_rows} history rows, "
        f"{result.stronghold_rows} stronghold rows, "
        f"signature {result.input_signature[:12]})"
    )



@app.command("ingest-eci-ae-panel")
def ingest_eci_ae_panel(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
    input_csv: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="Panel CSV path.",
        exists=True,
        dir_okay=False,
    ),
    state: str = typer.Option(
        ...,
        "--state",
        help="ECI state code (for example S22).",
    ),
    min_year: int | None = typer.Option(
        None,
        "--min-year",
        help="Only include panel rows from this year onward.",
    ),
    max_year: int | None = typer.Option(
        None,
        "--max-year",
        help="Only include panel rows up to this year.",
    ),
    delim_id: list[str] | None = typer.Option(
        None,
        "--delim-id",
        help="Panel DelimID to include. Repeat for multiple values; approved statewise path uses 3 and 4.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print a read-only preflight report and do not write Parquet or inventory.",
    ),
    allow_unknown_parties: bool = typer.Option(
        False,
        "--allow-unknown-parties",
        help="Map unresolved parties to parties.IN.UNK while preserving party_short_raw and report counts.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-ingest even when datasets/elections/_inventory.json already records every event.",
    ),
) -> None:
    """Ingest a frozen ECI Assembly Election panel CSV into canonical Parquet."""
    from yen_gov.canonical.adapters.eci_ae_panel import PanelFilters, ingest_panel, inspect_panel

    filters = PanelFilters(
        min_year=min_year,
        max_year=max_year,
        delim_ids=frozenset(delim_id) if delim_id else None,
    )

    if dry_run:
        report = inspect_panel(
            datasets_root=root / "datasets",
            csv_path=input_csv,
            state_code=state,
            filters=filters,
        )
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
        return

    result = ingest_panel(
        repo_root=root,
        csv_path=input_csv,
        state_code=state,
        force=force,
        filters=filters,
        allow_unknown_parties=allow_unknown_parties,
    )
    if result.skipped:
        typer.echo(
            "ingest-eci-ae-panel: skipped; inventory already records "
            f"{len(result.events)} events for state={state}. Pass --force to re-ingest."
        )
        return
    assert result.write_result is not None
    typer.echo(
        "ingest-eci-ae-panel: wrote "
        f"{result.write_result.observation_rows_written} election observation rows, "
        f"{result.write_result.dim_rows_written.get('dim_persons', 0)} person rows, "
        f"{result.write_result.dim_rows_written.get('elections_candidacies', 0)} candidacy rows"
    )
    typer.echo(f"ingest-eci-ae-panel: events={','.join(result.events)}")
    typer.echo(f"ingest-eci-ae-panel: report={result.report_path.as_posix()}")
    _refresh_party_pages_after_electoral_ingest(root, "ingest-eci-ae-panel")


@app.command("ingest-eci-ls")
def ingest_eci_ls(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
    input_csv: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="ECI Report-33 constituency-wise detailed-result CSV.",
        exists=True,
        dir_okay=False,
    ),
    crosswalk_csv: Path = typer.Option(
        ...,
        "--crosswalk",
        "-c",
        help="ECI Report-34 AC→PC crosswalk CSV (supplies pc_no).",
        exists=True,
        dir_okay=False,
    ),
    allow_unknown_parties: bool = typer.Option(
        False,
        "--allow-unknown-parties",
        help="Map unresolved parties to parties.IN.UNK instead of failing fast.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-ingest even when datasets/elections/_inventory.json already records the event.",
    ),
) -> None:
    """Ingest the ECI 2024 Parliament constituency-wise result into canonical Parquet."""
    from yen_gov.canonical.adapters.eci_ls import ingest_ls

    result = ingest_ls(
        repo_root=root,
        csv_path=input_csv,
        crosswalk_path=crosswalk_csv,
        force=force,
        allow_unknown_parties=allow_unknown_parties,
    )
    if result.skipped:
        typer.echo(
            "ingest-eci-ls: skipped; inventory already records "
            f"event {result.event_id}. Pass --force to re-ingest."
        )
        return
    assert result.write_result is not None
    typer.echo(
        "ingest-eci-ls: wrote "
        f"{result.write_result.observation_rows_written} observation rows "
        "(total across rewritten state shards, including pre-existing AC rows), "
        f"{result.write_result.dim_rows_written.get('dim_pcs', 0)} dim_pcs rows "
        f"across {result.pc_count} PCs"
    )
    if result.unresolved_parties:
        typer.echo(
            f"ingest-eci-ls: {len(result.unresolved_parties)} unresolved party strings "
            "mapped to parties.IN.UNK"
        )
    typer.echo(f"ingest-eci-ls: event={result.event_id}")
    _refresh_party_pages_after_electoral_ingest(root, "ingest-eci-ls")


@app.command("ingest-ls-ge-tcpd")
def ingest_ls_ge_tcpd_cmd(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
    input_csv: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="TCPD All-States GE panel CSV (All_States_GE.csv).",
        exists=True,
        dir_okay=False,
    ),
    year: int = typer.Option(
        ...,
        "--year",
        "-y",
        help="General-election year to ingest (e.g. 2019).",
    ),
    allow_unknown_parties: bool = typer.Option(
        False,
        "--allow-unknown-parties",
        help="Map unresolved parties to parties.IN.UNK instead of failing fast.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-ingest even when datasets/elections/_inventory.json already records the event.",
    ),
) -> None:
    """Ingest one historical Parliament GE year from the TCPD panel into Parquet."""
    from yen_gov.canonical.adapters.eci_ls import EVENT_BY_GE_YEAR, ingest_ls_tcpd

    event = EVENT_BY_GE_YEAR.get(year)
    if event is None:
        known = ", ".join(str(y) for y in sorted(EVENT_BY_GE_YEAR))
        raise typer.BadParameter(
            f"no PC event registered for GE year {year} (known: {known})"
        )

    result = ingest_ls_tcpd(
        repo_root=root,
        csv_path=input_csv,
        year=year,
        event=event,
        force=force,
        allow_unknown_parties=allow_unknown_parties,
    )
    if result.skipped:
        typer.echo(
            "ingest-ls-ge-tcpd: skipped; inventory already records "
            f"event {result.event_id}. Pass --force to re-ingest."
        )
        return
    assert result.write_result is not None
    typer.echo(
        "ingest-ls-ge-tcpd: wrote "
        f"{result.write_result.observation_rows_written} observation rows "
        "(total across rewritten state shards, including pre-existing rows), "
        f"{result.write_result.dim_rows_written.get('dim_pcs', 0)} dim_pcs rows "
        f"across {result.pc_count} PCs"
    )
    if result.unresolved_parties:
        typer.echo(
            f"ingest-ls-ge-tcpd: {len(result.unresolved_parties)} unresolved party "
            "strings mapped to parties.IN.UNK"
        )
    typer.echo(f"ingest-ls-ge-tcpd: event={result.event_id}")
    _refresh_party_pages_after_electoral_ingest(root, "ingest-ls-ge-tcpd")



@app.command()
def coverage(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
    write: bool = typer.Option(
        True,
        "--write/--no-write",
        help=f"Also write the rendered Markdown to <root>/{INVENTORY_REL}.",
    ),
) -> None:
    """Print + write the election data inventory (CLAUDE.md Holy Law #4).

    Reconciles the declared coverage in
    ``datasets/taxonomy/election_events.json`` against the on-disk
    artifacts under ``datasets/elections/`` and renders a citizen-readable
    inventory. Re-run after every ingest; the file is not hand-maintained.
    """
    report = compute_coverage(root)
    md = render_markdown(report)
    # The Temporal Richness meter uses U+25CF / U+25CB. On Windows the default
    # console code page (cp1252) cannot encode them, so a naive `typer.echo`
    # crashes when stdout is the terminal. Reconfigure to UTF-8 with a safe
    # fallback so the command works in PowerShell / cmd without operators
    # having to set $env:PYTHONIOENCODING manually.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    typer.echo(md, nl=False)
    if write:
        target = root / INVENTORY_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md, encoding="utf-8")
        typer.echo(f"\ncoverage: wrote {INVENTORY_REL}")


# `lift-energy` and `lift-livestock` CLI commands retired 2026-06-07
# (Phase C of TODO/20260607-energy-livestock-csv-migration-subplan.md).
# The canonical store for both families is now per-indicator CSV under
# `datasets/data/datapoints/geo/` (the FE reader was flipped in R2,
# commit 96275ab6). The parquet writer adapters under
# `backend/yen_gov/canonical/adapters/{energy,livestock}/` were deleted
# in the same commit; the corresponding parquet files retired in
# Phase D. No replacement CLI is shipped — the CSVs are the
# source-of-truth and are emitted directly by their upstream ingesters
# (see `datasets/data/datapoints/geo/<id>.csv` for the on-disk
# artifacts).


@app.command("eci-statreport-emit-local")
def eci_statreport_emit_local(
    file: Path = typer.Argument(
        ..., help="Path to a hand-downloaded Section 10 XLSX file.",
        exists=True, file_okay=True, dir_okay=False,
    ),
    state: str = typer.Option(
        None, "--state",
        help="ECI state code (e.g. S03). Auto-detected from filename "
             "'YYYY_state_<name>_*.xlsx' if omitted.",
    ),
    year: int = typer.Option(
        None, "--year",
        help="Election year. Auto-detected from filename if omitted.",
    ),
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root.",
        file_okay=False, dir_okay=True, exists=True,
    ),
    delete_source_on_success: bool = typer.Option(
        True, "--delete-source/--keep-source",
        help="Delete the source XLSX after successful emit. Drop-dir is "
             "ephemeral by convention (datasets/raw_ephemeral_datasets/).",
    ),
) -> None:
    """Phase B per-AC emit from a LOCAL Section 10 XLSX file (no network).

    Historical assembly elections (2016-2023) that predate the live-results
    portal are not retrievable through the regular ``eci-statreport-emit``
    path: there is no `/api/election-result` entry, no static catalog page,
    and most are served only as XLSX downloads behind old.eci.gov.in's
    finicky portal. The "ingest" for those is therefore a hand-download
    into ``datasets/raw_ephemeral_datasets/`` followed by this command.

    Because the bytes were obtained outside our Fetcher, this command emits
    artifacts with ``sources: []`` per ADR-0002 — the "empty list = hand-
    authored / out-of-band ingest" signal. Future re-ingest from a proper
    archive URL family can replace these in place.
    """
    # --- Resolve (state, year) ------------------------------------------------
    if state is None or year is None:
        m = _LOCAL_FNAME_RE.match(file.name)
        if m is None:
            raise typer.BadParameter(
                f"could not auto-detect state/year from filename {file.name!r}; "
                f"pass --state and --year explicitly. Expected pattern: "
                f"'YYYY_state_<name>_*.xlsx'.",
                param_hint="--state/--year",
            )
        if year is None:
            year = int(m.group("year"))
        if state is None:
            token = m.group("state").rstrip("_").lower()
            if token not in _LOCAL_NAME_TO_ECI:
                raise typer.BadParameter(
                    f"unknown state token {token!r} in filename {file.name!r}; "
                    f"pass --state explicitly.",
                    param_hint="--state",
                )
            state = _LOCAL_NAME_TO_ECI[token]

    # --- Resolve event (must be registered) -----------------------------------
    try:
        info = event_info_for(state, year)
    except KeyError as exc:
        raise typer.BadParameter(str(exc), param_hint="--state/--year") from exc
    event = info.event_id
    typer.echo(f"file:        {file.name}")
    typer.echo(f"state/year:  {state} / {year}")
    typer.echo(f"event:       {event} (has_partywise={info.has_partywise})")

    # --- Parse + emit ---------------------------------------------------------
    # Per O1 doctrine + B4-pt3 (no strangler-fig - git is the backup), the
    # legacy per-event JSON shards (results/<ac>.json, result.summary.json,
    # parties.json) are no longer emitted from this command. The
    # researcher-facing per-state CSV bundle survives as the only output.
    # G9 (2026-06-08): top_n / collapse_others now sourced from module
    # constants (config/processing.json + ProcessingConfig retired).
    raw = parse_detailed_results(file.read_bytes())
    typer.echo(f"parsed:      {len(raw.sections)} AC sections")

    # sources=[] per ADR-0002 (hand-authored / out-of-band ingest)
    results = to_constituency_results(
        raw,
        election=event,
        state=state,
        top_n=_TOP_N_DEFAULT,
        collapse_others=_COLLAPSE_OTHERS_DEFAULT,
        sources=[],
        party_eci_codes=None,
    )
    output_dir = root / "datasets" / "elections" / event / state
    output_dir.mkdir(parents=True, exist_ok=True)

    skipped = len(raw.sections) - len(results)
    typer.echo(
        f"emit:        OK \u2014 {len(results)} ACs"
        + (f" (skipped {skipped} countermanded)" if skipped else "")
    )

    # CSV bundle (researcher-facing) - the only artifact this command
    # writes since B4-pt3 retired the legacy folded-JSON emit chokepoint.
    from yen_gov.emit.csv_bundle import emit_state_csv_from_data
    constituency_dicts = [cr.body_payload() for cr in results]
    csv_path = emit_state_csv_from_data(
        constituencies=constituency_dicts,
        output_path=output_dir / "results.csv",
    )
    typer.echo(f"csv:         OK \u2014 {csv_path}")

    if delete_source_on_success:
        file.unlink()
        typer.echo(f"cleaned:     removed source {file}")


@app.command("canonical-backfill-eci")
def canonical_backfill_eci(
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False, dir_okay=True, exists=True,
    ),
    event: list[str] = typer.Option(
        None, "--event",
        help="Restrict to one or more event_ids (e.g. AcGenMay2026). Repeat flag.",
    ),
    state: list[str] = typer.Option(
        None, "--state",
        help="Restrict to one or more ECI state codes (e.g. S22). Repeat flag.",
    ),
    corpus_root: Path = typer.Option(
        None, "--corpus-root",
        help=(
            "Override per-AC JSON corpus directory (containing "
            "<event>/<state>/results/*.json). Defaults to <root>/datasets/elections. "
            "Used to backfill from a restored snapshot under e.g. "
            "datasets/ephemeral/legacy-corpus/elections after the per-AC JSONs "
            "were removed from the canonical tree (commit 016c2352)."
        ),
        file_okay=False, dir_okay=True, exists=False,
    ),
) -> None:
    """Backfill datasets/elections/election_results.parquet from per-AC JSON corpus.

    Phase 1.1 step 5. Each (event, state) slice is one atomic UPSERT; a
    failure in one slice is recorded and the run continues. Progress is
    printed live per slice so long runs are observable.
    """
    from yen_gov.pipeline.canonical_eci_backfill import (
        SliceResult,
        backfill_elections,
    )

    def _print(s: SliceResult) -> None:
        if s.error:
            typer.echo(f"  [FAIL] {s.event_id}/{s.state_code}: {s.error}", err=True)
            return
        typer.echo(
            f"  [ok]   {s.event_id}/{s.state_code}: "
            f"{s.acs_processed:4d} ACs, {s.observation_rows_written:6d} obs, "
            f"{s.source_rows_written:3d} sources"
        )

    def _print_write_start(n_obs: int, n_sources: int) -> None:
        typer.echo(f"  [WRITE] event start: {n_obs} obs, {n_sources} sources ...")

    def _print_event_written(event_id: str, n_obs: int, n_sources: int, dt: float) -> None:
        typer.echo(
            f"  [WRITE] {event_id}: persisted {n_obs} obs, {n_sources} sources "
            f"in {dt:.2f}s"
        )

    res = backfill_elections(
        datasets_root=root / "datasets",
        events=event or None,
        states=state or None,
        on_slice=_print,
        on_write_start=_print_write_start,
        on_event_written=_print_event_written,
        corpus_root=corpus_root,
    )
    typer.echo("canonical-backfill-eci: done")
    typer.echo(f"  events processed:     {res.events_processed}")
    typer.echo(f"  states processed:     {res.states_processed}")
    typer.echo(f"  ACs processed:        {res.acs_processed}")
    typer.echo(f"  observation rows:     {res.observation_rows_written}")
    typer.echo(f"  source rows:          {res.source_rows_written}")
    if res.failed_slices:
        typer.echo(f"  FAILED slices ({len(res.failed_slices)}):", err=True)
        for s in res.failed_slices:
            typer.echo(f"    - {s.event_id}/{s.state_code}: {s.error}", err=True)
    if res.unresolved_parties:
        top = sorted(res.unresolved_parties.items(), key=lambda kv: -kv[1])[:20]
        total_misses = sum(res.unresolved_parties.values())
        typer.echo(
            f"  unresolved party_shorts: {len(res.unresolved_parties)} unique, "
            f"{total_misses} candidate rows -> parties.IN.UNK"
        )
        for short, n in top:
            typer.echo(f"    {short:24s} {n}")
    if res.failed_slices:
        raise typer.Exit(code=1)


@app.command("parity")
def parity(
    source: str = typer.Option(
        ...,
        "--source",
        help=(
            "Source adapter id registered in recon.adapters.REGISTRY "
            "(e.g. tcpd-parties | eci-registered | wikipedia-parties | "
            "indiavotes-state | bhukyavenkatamahesh-pc | thecont1-state). "
            "PR-2 ships ZERO adapters; PR-W-1 + W-2 + W-3 + Stream X PRs "
            "register theirs."
        ),
    ),
    vintage: str = typer.Option(
        ...,
        "--vintage",
        help=(
            "Upstream snapshot pin per ADR-0042: YYYY, YYYY-MM, or "
            "YYYY-MM-DD. Operator snapshot window of the upstream "
            "observation; NOT wall-clock-now (CLAUDE.md section 10)."
        ),
    ),
    state: str | None = typer.Option(
        None,
        "--state",
        help="Optional state slug for state-scoped sources (e.g. 'tamil-nadu').",
    ),
    event: str | None = typer.Option(
        None,
        "--event",
        help="Optional ECI event id for event-scoped sources (e.g. 'AcGenMay2026').",
    ),
    kind: str | None = typer.Option(
        None,
        "--kind",
        help="Optional election kind for kind-scoped sources (assembly | parliament).",
    ),
    report: Path = typer.Option(
        ...,
        "--report",
        help=(
            "Output verdict CSV path. Convention per plan section 0.4 Q3: "
            "datasets/ephemeral/party-parity/<source>/<vintage>/<sha>/verdict.csv "
            "for the first run of a (source, vintage); subsequent re-runs "
            "are gitignored."
        ),
        file_okay=True,
        dir_okay=False,
    ),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Tier-C cross-source party parity (Wave 0 / Gregor section 6 verdict).

    Runs the named source adapter (registered under
    backend/yen_gov/canonical/recon/adapters/) to produce shape-A rows,
    runs the Compare-Aggregator against the canonical parties roster
    (datasets/data/entities/parties.csv), and writes a verdict CSV to
    --report.

    \b
    Tier-C contract per Wave 0 / Gregor section 6:
      - NEVER runs in CI; operator-run only.
      - Tier-A + Tier-B keep the always-on FK closure safety net.

    PR-2 ships the dispatch infrastructure ONLY; the adapter registry is
    empty. Calling --source <not-registered> exits non-zero with a
    `no adapter registered for source ...` message.
    """
    from yen_gov.canonical.recon.adapters import REGISTRY
    from yen_gov.canonical.recon.aggregator import compare, write_verdict_csv

    adapter = REGISTRY.get(source)
    if adapter is None:
        available = sorted(REGISTRY.keys())
        available_str = ", ".join(available) if available else "(none registered)"
        typer.echo(
            f"parity: no adapter registered for source {source!r}; "
            f"available: {available_str}",
            err=True,
        )
        raise typer.Exit(code=2)

    shape_a_rows = list(
        adapter(
            root=root,
            vintage=vintage,
            state=state,
            event=event,
            kind=kind,
        )
    )

    canonical_parties = _load_canonical_parties_for_parity(root)

    verdicts = compare(shape_a_rows, canonical_parties)
    n_written = write_verdict_csv(verdicts, report)

    # Per-verdict roll-up for the operator (mirrors check-overlap +
    # pre-flight-ingest summary lines).
    by_verdict: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for v in verdicts:
        by_verdict[v.verdict] = by_verdict.get(v.verdict, 0) + 1
        by_action[v.action] = by_action.get(v.action, 0) + 1

    typer.echo(
        f"parity: wrote {n_written} verdict row(s) to {report.as_posix()}"
    )
    typer.echo(
        f"  shape-A rows in:  {len(shape_a_rows)} (from source {source!r}, vintage {vintage!r})"
    )
    typer.echo(
        f"  verdicts:         "
        + ", ".join(f"{k}={by_verdict.get(k, 0)}" for k in ("VERIFIED", "DISPUTED", "UNVERIFIED"))
    )
    if by_action:
        typer.echo(
            f"  actions:          "
            + ", ".join(f"{k}={v}" for k, v in sorted(by_action.items()))
        )

    raise typer.Exit(0)


def _load_canonical_parties_for_parity(root: Path) -> dict[str, dict[str, str]]:
    """Project datasets/data/entities/parties.csv to a party_id -> row dict.

    Used by the ``parity`` command to determine whether a shape-A row's
    proposed_party_id already exists in the canonical roster (drives the
    ``current_party_id`` column on the verdict CSV and the mint-new vs
    conflict precedence on the action column).

    Kept local to cli.py (not in recon.aggregator) so the aggregator stays
    a pure function over its inputs and remains trivially unit-testable
    without disk.
    """
    import csv as _csv

    parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
    out: dict[str, dict[str, str]] = {}
    with parties_csv.open(encoding="utf-8", newline="") as fh:
        reader = _csv.DictReader(fh)
        for row in reader:
            pid = (row.get("party_id") or "").strip()
            if not pid:
                continue
            out[pid] = dict(row)
    return out


@app.command("parity-event")
def parity_event(
    source: str = typer.Option(
        ...,
        "--source",
        help=(
            "Comma-separated source adapter ids registered in "
            "recon.adapters.EVENT_REGISTRY (e.g. "
            "'yen-gov-elections,thecont1-state,tcpd-state'). The "
            "yen-gov-elections source is the canonical on-disk side; "
            "external sources oracle against it. The first run of any "
            "(state, event) is the first-run audit; subsequent runs "
            "go to sibling <sha>/ dirs and are gitignored."
        ),
    ),
    state: str = typer.Option(
        ...,
        "--state",
        help=(
            "State slug (e.g. 'tamil-nadu', 'west-bengal'). Same slug "
            "the on-disk datasets/elections/<kind>/state=<slug>/ "
            "partition uses."
        ),
    ),
    event: str = typer.Option(
        ...,
        "--event",
        help=(
            "ECI event id (e.g. 'AcGenMay2026'). Registered in "
            "backend/yen_gov/sources/eci/events.py."
        ),
    ),
    kind: str = typer.Option(
        ...,
        "--kind",
        help=(
            "Election kind: 'assembly' or 'parliament'. Determines the "
            "elections/<kind>/ partition root."
        ),
    ),
    vintage: str = typer.Option(
        "",
        "--vintage",
        help=(
            "Optional ADR-0042 snapshot pin. Most event adapters infer "
            "vintage from the event id; TCPD's per-state adapter pins "
            "to the compilation edition (TCPD_VINTAGE constant) and "
            "rejects mismatched values."
        ),
    ),
    report: Path = typer.Option(
        ...,
        "--report",
        help=(
            "Output verdict CSV path. Convention per plan section 0.4 "
            "Q3: datasets/ephemeral/party-parity/state=<slug>/<event>/"
            "<sha>/verdict.csv for the first run of a (state, event); "
            "subsequent re-runs are gitignored."
        ),
        file_okay=True,
        dir_okay=False,
    ),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Tier-C per-constituency cross-source parity (PR-S-* / PR-PC-*).

    Runs the named EVENT_REGISTRY adapters for the (state, event, kind)
    triple, runs the per-constituency Compare-Aggregator across their
    Shape-B outputs (recon/shape_b.py + recon/event_aggregator.py), and
    writes a per-AC verdict CSV to --report.

    \b
    Verdict semantics (Hans section 10 + Fowler machine-decidable):
      - VERIFIED:   n_oracles_present >= 2 AND all agree on
                    (winner_party_id, winner_candidate_name).
      - DISPUTED:   n_oracles_present >= 2 AND at least one disagrees.
      - UNVERIFIED: n_oracles_present < 2.

    \b
    Per Holy Law #9: ECI authority wins on winner_party_id
    disagreements; the aggregator surfaces the raw disagreement
    DISPUTED and the operator dispositions via curator_note +
    curator_source_id in a follow-up.

    Sources that genuinely cannot oracle the requested (state, event)
    (e.g. tcpd-state vs a post-2021 event - TCPD's compilation cutoff
    is 2021) return ZERO rows; the CLI logs the empty count and
    continues. The verdict still ships; a 2-of-2 agreement (yen-gov +
    one external) still counts as VERIFIED.

    Sibling of the per-party-roster ``parity`` subcommand. Two
    registries, two subcommands; share the recon namespace but verdict
    at different grains.
    """
    from yen_gov.canonical.recon.adapters import EVENT_REGISTRY
    from yen_gov.canonical.recon.event_aggregator import (
        compare_event,
        write_event_verdict_csv,
    )

    source_ids = [s.strip() for s in source.split(",") if s.strip()]
    if not source_ids:
        typer.echo(
            "parity-event: --source must be a non-empty comma-separated "
            "list (e.g. 'yen-gov-elections,thecont1-state').",
            err=True,
        )
        raise typer.Exit(code=2)

    # Validate every named source is registered BEFORE running any
    # adapter - fail-loud at the boundary per CLAUDE.md section 10
    # rather than partial-result on a typo.
    missing = [s for s in source_ids if s not in EVENT_REGISTRY]
    if missing:
        available = sorted(EVENT_REGISTRY.keys())
        available_str = ", ".join(available) if available else "(none registered)"
        typer.echo(
            f"parity-event: no event adapter registered for "
            f"{missing!r}; available: {available_str}",
            err=True,
        )
        raise typer.Exit(code=2)

    # Run each adapter, count empty-oracle outcomes for the operator
    # summary.
    all_rows: list = []  # ConstituencyParityRow
    per_source_counts: dict[str, int] = {}
    for source_id in source_ids:
        adapter = EVENT_REGISTRY[source_id]
        rows = list(
            adapter(
                root=root,
                vintage=vintage,
                state=state,
                event=event,
                kind=kind,
            )
        )
        per_source_counts[source_id] = len(rows)
        all_rows.extend(rows)

    # Load party_alliances.csv for the alliance surfacing column.
    alliances = _load_party_alliances_for_parity_event(root)

    verdicts = compare_event(all_rows, party_alliances=alliances)
    n_written = write_event_verdict_csv(verdicts, report)

    # Per-verdict roll-up for the operator summary.
    by_verdict: dict[str, int] = {}
    for v in verdicts:
        by_verdict[v.verdict] = by_verdict.get(v.verdict, 0) + 1

    typer.echo(
        f"parity-event: wrote {n_written} verdict row(s) to "
        f"{report.as_posix()}"
    )
    typer.echo(
        f"  state={state!r} event={event!r} kind={kind!r}"
    )
    typer.echo("  per-source row counts:")
    for s_id in source_ids:
        n_rows = per_source_counts[s_id]
        flag = " (EMPTY ORACLE)" if n_rows == 0 else ""
        typer.echo(f"    {s_id}: {n_rows}{flag}")
    typer.echo(
        "  verdicts:         "
        + ", ".join(
            f"{k}={by_verdict.get(k, 0)}"
            for k in ("VERIFIED", "DISPUTED", "UNVERIFIED")
        )
    )

    raise typer.Exit(0)


def _load_party_alliances_for_parity_event(
    root: Path,
) -> dict[tuple[str, str], str]:
    """Project party_alliances.csv to ``(party_id, event_id) -> alliance``.

    Used by the ``parity-event`` command to surface the alliance label
    on the verdict CSV's ``party_id_alliance`` column. When the file is
    absent or the row lacks an alliance value, the verdict's column is
    empty - the "alliance not yet curated for this event" badge signal
    per Q6.

    v2.0 schema (2026-06-12, plan TODO/20260612-alliance-phase-1-structural-fix-plan.md):
    column renamed period_label -> event_id; state column added but the
    parity-event verdict key remains (party_id, event_id) -- callers
    that care about per-state disambiguation can extend the key shape
    in a follow-up.
    """
    import csv as _csv

    alliances_csv = (
        root
        / "datasets"
        / "data"
        / "entities"
        / "party_alliances.csv"
    )
    out: dict[tuple[str, str], str] = {}
    if not alliances_csv.exists():
        return out
    with alliances_csv.open(encoding="utf-8", newline="") as fh:
        reader = _csv.DictReader(fh)
        for row in reader:
            pid = (row.get("party_id") or "").strip()
            event_id = (row.get("event_id") or "").strip()
            alliance = (row.get("alliance") or "").strip()
            if pid and event_id and alliance:
                out[(pid, event_id)] = alliance
    return out


@app.command("parity-pc")
def parity_pc(
    sources: str = typer.Option(
        ...,
        "--sources",
        help=(
            "Comma-separated source adapter ids registered in "
            "recon.adapters.REGISTRY for per-constituency parity "
            "(e.g. 'bhukyavenkatamahesh-pc,tcpd-pc'). The yen-gov "
            "canonical oracle ('yen-gov-canonical-pc') is auto-"
            "appended unless --no-include-canonical is passed."
        ),
    ),
    vintage: str = typer.Option(
        ...,
        "--vintage",
        help=(
            "Upstream snapshot pin per ADR-0042 (CLAUDE.md section "
            "12). Each adapter validates the vintage against its "
            "publisher edition pin and exits non-zero on mismatch."
        ),
    ),
    event: str = typer.Option(
        ...,
        "--event",
        help=(
            "ECI event id (e.g. 'LsGenJun2024'). The adapter parses "
            "the year from the trailing 4 digits to navigate to the "
            "datasets/elections/<kind>/election=<year>/summary.csv."
        ),
    ),
    kind: str = typer.Option(
        "parliament",
        "--kind",
        help=(
            "Election kind ('parliament' | 'assembly'). Drives the "
            "summary.csv path navigation for the yen-gov-canonical-pc "
            "oracle. For LS-2024 use 'parliament' (default)."
        ),
    ),
    state: str | None = typer.Option(
        None,
        "--state",
        help=(
            "Optional state slug filter (e.g. 'tamil-nadu'). Default "
            "(None) runs national parity across all states. The "
            "PR-PC-LS2024 brief documents this as 'handle missing "
            "--state for national event'."
        ),
    ),
    report: Path = typer.Option(
        ...,
        "--report",
        help=(
            "Output verdict CSV path. Convention per plan section "
            "0.4 Q3: datasets/ephemeral/party-parity/<kind>/<event>/"
            "<sha>/verdict.csv for the first run of a (kind, event)."
        ),
        file_okay=True,
        dir_okay=False,
    ),
    include_canonical: bool = typer.Option(
        True,
        "--include-canonical/--no-include-canonical",
        help=(
            "Auto-append 'yen-gov-canonical-pc' to the sources list. "
            "Default true: yen-gov canonical is the ECI-derived "
            "oracle that ALWAYS rides along per Holy Law #9 "
            "(issuing authority wins)."
        ),
    ),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Tier-C per-constituency parity (PR-PC-LS2024 of the 2026-06-10 plan).

    For each parliamentary constituency in the named event:
      1. Each adapter in --sources is run; the adapter projects its
         publisher's per-PC winner into a per-constituency shape-A
         row carrying (state_code, constituency_no, winner_party_id,
         winner_candidate, winner_votes).
      2. The yen-gov canonical oracle (auto-appended by default) is
         run alongside, reading summary.csv as the ECI-derived
         baseline (Holy Law #9: issuing authority always wins).
      3. The per-PC Compare-Aggregator (recon/pc_aggregator.py)
         groups by (state_code, constituency_no) and emits one
         verdict.csv row per PC with the Fowler machine-decidable
         rule (plan section 0.5 ESCALATE #2):

           VERIFIED   iff n_oracles_agreeing == n_oracles_present
                      AND n_oracles_present >= 2.
           UNVERIFIED iff n_oracles_present < 2.
           DISPUTED   otherwise.

      4. The verdict.csv is written to --report. The CLI exits 0
         even when DISPUTED rows are present; the operator inspects
         the report + applies curator decisions per CLAUDE.md
         section 10 (auto-correct BANNED).

    Subcommand is ADDITIVE per the PR-PC-LS2024 brief's CLI
    extension policy ("minimal-touch additive seam"): does NOT
    modify the existing per-party `parity` subcommand. PR-W-1 / W-2 /
    W-3 + future per-party adapters keep using `parity`; this
    subcommand handles per-constituency parity exclusively.
    """
    from yen_gov.canonical.recon.adapters import REGISTRY
    from yen_gov.canonical.recon.pc_aggregator import (
        compare_per_pc,
        write_pc_verdict_csv,
    )

    source_ids = [s.strip() for s in sources.split(",") if s.strip()]
    if include_canonical and "yen-gov-canonical-pc" not in source_ids:
        source_ids.append("yen-gov-canonical-pc")
    if not source_ids:
        typer.echo(
            "parity-pc: --sources must name at least one adapter",
            err=True,
        )
        raise typer.Exit(code=2)

    # Validate every named source is registered BEFORE running any
    # adapter - fail-loud at the boundary per CLAUDE.md section 10
    # rather than partial-result on a typo.
    missing = [s for s in source_ids if s not in REGISTRY]
    if missing:
        available = sorted(REGISTRY.keys())
        available_str = ", ".join(available) if available else "(none registered)"
        typer.echo(
            f"parity-pc: no adapter registered for {missing!r}; "
            f"available: {available_str}",
            err=True,
        )
        raise typer.Exit(code=2)

    # Run each adapter; count empty-oracle outcomes for the operator
    # summary. Empty is NOT an error (the tcpd-pc adapter returns
    # empty for years beyond its 2019 cutoff per the PR-PC-LS2024
    # brief's stop-condition fallback).
    all_rows: list[object] = []  # ShapeARow at runtime
    per_source_counts: dict[str, int] = {}
    for source_id in source_ids:
        adapter = REGISTRY[source_id]
        rows = list(
            adapter(
                root=root,
                vintage=vintage,
                state=state,
                event=event,
                kind=kind,
            )
        )
        per_source_counts[source_id] = len(rows)
        all_rows.extend(rows)

    canonical_parties = _load_canonical_parties_for_parity(root)
    verdicts = compare_per_pc(all_rows, canonical_parties)  # type: ignore[arg-type]
    n_written = write_pc_verdict_csv(verdicts, report)

    by_verdict: dict[str, int] = {}
    for v in verdicts:
        by_verdict[v.verdict] = by_verdict.get(v.verdict, 0) + 1

    typer.echo(
        f"parity-pc: wrote {n_written} verdict row(s) to "
        f"{report.as_posix()}"
    )
    typer.echo(
        f"  event={event!r} kind={kind!r} state={state!r}"
    )
    typer.echo("  per-source row counts:")
    for s_id in source_ids:
        n_rows = per_source_counts[s_id]
        flag = " (EMPTY ORACLE)" if n_rows == 0 else ""
        typer.echo(f"    {s_id}: {n_rows}{flag}")
    typer.echo(
        "  verdicts:         "
        + ", ".join(
            f"{k}={by_verdict.get(k, 0)}"
            for k in ("VERIFIED", "DISPUTED", "UNVERIFIED")
        )
    )

    raise typer.Exit(0)



@app.command("ingest-mh-ae2024-thecont1")
def ingest_mh_ae2024_cmd(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
) -> None:
    """Ingest Maharashtra Assembly Election 2024 from the thecont1 snapshot.

    Reads ``datasets/ephemeral/thecont1-india-votes-data/2024/Assembly-Maharashtra.csv``
    and emits canonical per-event CSVs:

      - ``datasets/elections/assembly/state=maharashtra/election=2024/candidacies.csv``
      - ``datasets/elections/assembly/state=maharashtra/election=2024/summary.csv``

    Also:
      - Appends the thecont1 citation row to ``datasets/data/entities/source.csv``
        if missing.
      - Flips ``datasets/taxonomy/election_events.json`` S13 ``assembly-2024``
        ``data_status`` from ``pending_upstream`` to ``complete``.
    """
    from yen_gov.canonical.adapters.thecont1_mh_ae2024 import ingest_mh_ae2024

    cand_n, sum_n, unk_winners, missing_acs = ingest_mh_ae2024(root)
    typer.echo("ingest-mh-ae2024-thecont1: OK")
    typer.echo(f"  candidacies.csv:        {cand_n} rows")
    typer.echo(f"  summary.csv:            {sum_n} rows")
    typer.echo(f"  unresolved winners:     {unk_winners} ACs with parties.IN.UNK")
    typer.echo(f"  missing ACs (gap):      {missing_acs} eci_nos not in electoral.csv")
    typer.echo("  election_events.json:   S13 assembly-2024 -> complete")

@app.command("ingest-eci-ae-form10")
def ingest_eci_ae_form10_cmd(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False,
        dir_okay=True,
        exists=True,
    ),
    report_csv: Path | None = typer.Option(
        None,
        "--report-csv",
        help="Optional path to write a per-event yearwise ingest report CSV.",
    ),
) -> None:
    """Ingest all 13 ECI Form-10 Detailed Results xlsx workbooks for the 2023-2025 cohort.

    Reads ``datasets/ephemeral/<state>_*Detailed_Results*.xlsx`` and emits canonical
    per-event CSVs into ``datasets/elections/assembly/state=<slug>/election=<year>/``.

    Also:
      - Appends ECI source citation rows to ``datasets/data/entities/source.csv``.
      - Flips ``datasets/taxonomy/election_events.json`` data_status to ``complete``
        for every successfully-ingested event.
    """
    from yen_gov.canonical.adapters.eci_form10_ae import ingest_all

    results, flipped = ingest_all(root)
    typer.echo("ingest-eci-ae-form10: results")
    typer.echo(f"  {'STATE':<25} {'YEAR':<5} {'EVENT_ID':<16} {'STATUS':<6} {'CAND':<6} {'AC':<4} {'UNK':<4} {'GAP':<4} REASON")
    for r in results:
        typer.echo(
            f"  {r.state_slug:<25} {r.election_year:<5} {r.event_id:<16} "
            f"{r.status:<6} {r.n_candidacies:<6} {r.n_summary:<4} "
            f"{r.n_unresolved_winners:<4} {r.n_missing_acs:<4} {r.reason}"
        )
    typer.echo(f"election_events.json: {flipped} entries flipped to 'complete'")

    if report_csv is not None:
        import csv as csv_mod
        fields = [
            "state_slug", "election_year", "event_id", "file_name", "status",
            "n_candidacies", "n_summary", "n_unresolved_winners",
            "n_missing_acs", "expected_acs", "reason",
        ]
        with report_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv_mod.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow({
                    "state_slug": r.state_slug,
                    "election_year": r.election_year,
                    "event_id": r.event_id,
                    "file_name": r.file_name,
                    "status": r.status,
                    "n_candidacies": r.n_candidacies,
                    "n_summary": r.n_summary,
                    "n_unresolved_winners": r.n_unresolved_winners,
                    "n_missing_acs": r.n_missing_acs,
                    "expected_acs": r.expected_acs,
                    "reason": r.reason,
                })
        typer.echo(f"report written to {report_csv}")