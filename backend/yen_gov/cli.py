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
    """Ingest the ECI 2024 Lok Sabha constituency-wise result into canonical Parquet."""
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
    """Ingest one historical Lok Sabha GE year from the TCPD panel into Parquet."""
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

