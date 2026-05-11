"""yen-gov CLI."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from yen_gov.core.http import Fetcher
from yen_gov.core.io import write_artifact
from yen_gov.core.models import ProcessingConfig, SourceRef
from yen_gov.pipeline.compose import (
    compose_result_summary_from_section_10,
    eci_code_by_short_from_partywise,
    reconcile_winners_against_partywise,
)
from yen_gov.pipeline.reference import scrape_state_reference
from yen_gov.pipeline.run import parties_snapshot_from_partywise, run_state_slice
from yen_gov.sources.eci.categories import category_id_for
from yen_gov.sources.eci.events import event_id_for
from yen_gov.sources.eci.partywise import parse_partywise
from yen_gov.sources.eci.statistical_report import (
    download_documents,
    fetch_catalog,
)
from yen_gov.sources.eci.statistical_report_detailed import (
    parse_detailed_results,
    to_constituency_results,
)
from yen_gov.sources.eci.urls import partywise_state_url
from yen_gov.validate import run as run_validate

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


@app.command()
def run(
    event: str = typer.Argument(..., help="ECI event id, e.g. AcGenMay2026."),
    state: str = typer.Argument(..., help="ECI state code, e.g. S22."),
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False, dir_okay=True, exists=True,
    ),
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to processing.json. Defaults to <root>/config/processing.json.",
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output dir. Defaults to <root>/datasets/elections/<event>/<state>/.",
    ),
    sqlite: bool = typer.Option(
        True, "--sqlite/--no-sqlite",
        help="Also emit results.sqlite next to the JSON (docs/architecture/backend/emit-sqlite.md).",
    ),
) -> None:
    """Fetch + parse + compose + emit one (event, state) AC slice from results.eci.gov.in."""
    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)

    output_dir = output or (root / "datasets" / "elections" / event / state)
    schema_dir = root / "datasets" / "schemas"

    with Fetcher(
        source="eci",
        runtime_root=root,
        timeout_seconds=cfg.fetch.timeout_seconds,
        retry_attempts=cfg.fetch.retry_attempts,
        retry_backoff_seconds=cfg.fetch.retry_backoff_seconds or 1.0,
        user_agent=cfg.fetch.user_agent,
    ) as fetcher:
        result = run_state_slice(
            event_id=event, state_code=state,
            output_dir=output_dir, schema_dir=schema_dir, fetcher=fetcher,
            top_n=cfg.results.top_n_candidates,
            collapse_others=cfg.results.collapse_others,
        )

    typer.echo(
        f"run: OK — {len(result.constituencies)} ACs, "
        f"{len(result.parties.parties)} parties, "
        f"summary={result.paths.summary}"
    )

    if sqlite:
        from yen_gov.emit.sqlite import emit_state_sqlite
        sqlite_path = emit_state_sqlite(state_dir=output_dir)
        typer.echo(f"sqlite: OK — {sqlite_path}")


@app.command()
def reference(
    state: str = typer.Argument(..., help="ECI state code, e.g. S22."),
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False, dir_okay=True, exists=True,
    ),
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to processing.json. Defaults to <root>/config/processing.json.",
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output dir. Defaults to <root>/datasets/reference/in/states/<state>/.",
    ),
    user_agent: str = typer.Option(
        "yen-gov/0.1 (https://github.com/miztiik/yen-gov; election data pipeline) httpx",
        "--user-agent",
        help="HTTP User-Agent. Wikipedia requires a descriptive UA (docs/architecture/backend/sources-wikipedia.md).",
    ),
) -> None:
    """One-shot Wikipedia scrape: districts.json + constituencies.json for one state."""
    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)

    output_dir = output or (root / "datasets" / "reference" / "in" / "states" / state)
    schema_dir = root / "datasets" / "schemas"

    with Fetcher(
        source="wikipedia",
        runtime_root=root,
        timeout_seconds=cfg.fetch.timeout_seconds,
        retry_attempts=cfg.fetch.retry_attempts,
        retry_backoff_seconds=cfg.fetch.retry_backoff_seconds or 1.0,
        user_agent=user_agent,
    ) as fetcher:
        result = scrape_state_reference(
            state_code=state, output_dir=output_dir,
            schema_dir=schema_dir, fetcher=fetcher,
        )

    typer.echo(
        f"reference: OK — {len(result.districts.districts)} districts, "
        f"{len(result.constituencies.constituencies)} constituencies\n"
        f"  {result.paths.districts}\n  {result.paths.constituencies}"
    )


@app.command("eci-statreport")
def eci_statreport(
    state: str = typer.Argument(..., help="ECI state code, e.g. S22."),
    year: int = typer.Argument(..., help="Election year, e.g. 2026."),
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False, dir_okay=True, exists=True,
    ),
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to processing.json. Defaults to <root>/config/processing.json.",
    ),
    download: bool = typer.Option(
        False, "--download/--no-download",
        help="Download every listed XLSX (and PDF) into .runtime/raw/eci/. "
             "Without this flag, only the catalog is fetched and printed.",
    ),
    skip_pdf: bool = typer.Option(
        False, "--skip-pdf",
        help="Skip PDF zip downloads; XLSX-only.",
    ),
) -> None:
    """Phase B catalog + download for ECI Statistical Reports (cleartext API).

    Resolves the pinned category_id for (state, year), fetches the
    /api/election-result catalog, and optionally downloads every listed
    XLSX (and PDF). The on-disk artifacts under .runtime/raw/eci/ are debug
    only (ADR-0003); only the cleartext landing-page permalinks shown in the
    output are safe to persist in sources[].
    """
    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)

    cid = category_id_for(state, year)
    typer.echo(f"category_id: {cid}  (pinned in sources/eci/categories.py)")

    # www.eci.gov.in is fronted by Akamai; processing.json's default
    # `yen-gov/0.1` UA is blocked. Bare Mozilla/5.0 is the only UA that
    # works consistently for both /api/election-result and the
    # /all_files/election_report/ permalinks. Documented in
    # tools/eci_recon/recon.py and docs/architecture/backend/sources-eci.md.
    eci_user_agent = "Mozilla/5.0"

    with Fetcher(
        source="eci",
        runtime_root=root,
        timeout_seconds=cfg.fetch.timeout_seconds,
        retry_attempts=cfg.fetch.retry_attempts,
        retry_backoff_seconds=cfg.fetch.retry_backoff_seconds or 1.0,
        user_agent=eci_user_agent,
    ) as fetcher:
        catalog = fetch_catalog(cid, fetcher=fetcher)
        typer.echo(f"cat_name:   {catalog.cat_name}")
        typer.echo(f"index_name: {catalog.index_name}")
        typer.echo(f"documents:  {len(catalog.documents)}")
        for doc in catalog.documents:
            typer.echo(f"  [{doc.id:>4}] {doc.title}")
            typer.echo(f"        xlsx: {doc.xlsx_url}")
            typer.echo(f"        pdf:  {doc.pdf_zip_url}")

        if not download:
            typer.echo("\nrun with --download to fetch the listed files into .runtime/raw/eci/")
            return

        results = download_documents(
            catalog, fetcher=fetcher, include_pdf=not skip_pdf
        )
        typer.echo(f"\ndownloaded {len(results)} files into .runtime/raw/eci/")
        for fr in results:
            size_kb = len(fr.content) / 1024
            typer.echo(f"  {size_kb:>7.1f} KB  {fr.url}")


@app.command("eci-statreport-emit")
def eci_statreport_emit(
    state: str = typer.Argument(..., help="ECI state code, e.g. S22."),
    year: int = typer.Argument(..., help="Election year, e.g. 2026."),
    event: str = typer.Option(
        None, "--event",
        help="On-disk event id (groups artifacts under "
             "datasets/elections/<event>/<state>/). Defaults to the value "
             "registered for (state, year) in sources/eci/events.py — only "
             "the May-2026 cohort is registered today (N1 of "
             "TODO/ECI-MULTI-STATE-INGEST-PLAN.md).",
    ),
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root.",
        file_okay=False, dir_okay=True, exists=True,
    ),
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to processing.json. Defaults to <root>/config/processing.json.",
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output dir. Defaults to <root>/datasets/elections/<event>/<state>/.",
    ),
) -> None:
    """Phase B per-AC emit from ECI Statistical Report Section 10 (Detailed Results).

    Resolves the catalog for (state, year), fetches the Section 10 XLSX,
    parses it, and emits one ConstituencyResult JSON per AC under
    <output>/results/<eci_no>.json. The Section 10 permalink (with the
    fetch timestamp) is the single sources[] entry on each emitted file.
    """
    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)

    # Default --event from the (state, year) registry. Explicit --event
    # still overrides for ad-hoc runs / future events not yet in the
    # registry. Per N1 of TODO/ECI-MULTI-STATE-INGEST-PLAN.md.
    if event is None:
        try:
            event = event_id_for(state, year)
        except KeyError as exc:
            raise typer.BadParameter(str(exc), param_hint="--event") from exc
    typer.echo(f"event:       {event}")

    output_dir = output or (root / "datasets" / "elections" / event / state)
    schema_dir = root / "datasets" / "schemas"
    cr_schema = json.loads(
        (schema_dir / "result.constituency.schema.json").read_text(encoding="utf-8")
    )

    cid = category_id_for(state, year)
    typer.echo(f"category_id: {cid}")

    with Fetcher(
        source="eci",
        runtime_root=root,
        timeout_seconds=cfg.fetch.timeout_seconds,
        retry_attempts=cfg.fetch.retry_attempts,
        retry_backoff_seconds=cfg.fetch.retry_backoff_seconds or 1.0,
        user_agent="Mozilla/5.0",  # Akamai blocks the project default
    ) as fetcher:
        catalog = fetch_catalog(cid, fetcher=fetcher)
        # Section 10 — title starts with "10" (sometimes "10-" or "10 -").
        section_10 = next(
            (d for d in catalog.documents if d.title.lstrip().startswith("10")),
            None,
        )
        if section_10 is None:
            raise typer.Exit(
                f"no Section 10 (Detailed Results) document in catalog for "
                f"category_id={cid}; titles were: "
                f"{[d.title for d in catalog.documents]}"
            )
        typer.echo(f"section 10:  {section_10.title}")
        typer.echo(f"             {section_10.xlsx_url}")

        fetched = fetcher.fetch(section_10.xlsx_url)
        raw = parse_detailed_results(fetched.content)

        # Backfill numeric party_eci_code from the live-results partywise page.
        # Section 10 carries SHORT codes only; the live-results table is the
        # authoritative source for {short → numeric eci_code} mappings.
        partywise_url = partywise_state_url(event, state)
        partywise_fetched = fetcher.fetch(partywise_url)
        partywise_snapshot = parse_partywise(partywise_fetched.content)
        party_eci_codes = eci_code_by_short_from_partywise(partywise_snapshot)
        typer.echo(
            f"partywise:   {partywise_url} "
            f"({len(party_eci_codes)} short->code mappings)"
        )

    sources = [
        SourceRef(url=fetched.url, fetched_at=fetched.fetched_at),
        SourceRef(url=partywise_fetched.url, fetched_at=partywise_fetched.fetched_at),
    ]
    results = to_constituency_results(
        raw,
        election=event,
        state=state,
        top_n=cfg.results.top_n_candidates,
        collapse_others=cfg.results.collapse_others,
        sources=sources,
        party_eci_codes=party_eci_codes,
    )

    # Cross-check: per-AC winners aggregated by party_short must match the
    # partywise (seats_won + leading) numbers. Either source could be wrong;
    # what matters is they agree before we publish. Fails loud — no partial
    # writes if mismatched.
    reconcile_winners_against_partywise(
        partywise=partywise_snapshot, constituencies=results,
    )

    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    for cr in results:
        write_artifact(
            path=results_dir / f"{cr.eci_no}.json",
            schema_id=cr._schema_id,
            schema_version=cr._schema_version,
            payload=cr.body_payload(),
            sources=cr.sources_payload(),
            schema_for_validation=cr_schema,
        )

    summary = compose_result_summary_from_section_10(
        raw, election=event, state=state, sources=sources,
        party_eci_codes=party_eci_codes,
    )
    summary_schema = json.loads(
        (schema_dir / "result.summary.schema.json").read_text(encoding="utf-8")
    )
    summary_path = output_dir / "result.summary.json"
    write_artifact(
        path=summary_path,
        schema_id=summary._schema_id,
        schema_version=summary._schema_version,
        payload=summary.body_payload(),
        sources=summary.sources_payload(),
        schema_for_validation=summary_schema,
    )

    # Emit parties.json from the partywise snapshot — same shape as the
    # Phase A pipeline. Required by the SQLite emitter and downstream consumers
    # that need the canonical {eci_code, short, full} party roster.
    parties = parties_snapshot_from_partywise(
        partywise_snapshot,
        election=event,
        sources=[SourceRef(
            url=partywise_fetched.url,
            fetched_at=partywise_fetched.fetched_at,
        )],
    )
    parties_schema = json.loads(
        (schema_dir / "party.schema.json").read_text(encoding="utf-8")
    )
    parties_path = output_dir / "parties.json"
    write_artifact(
        path=parties_path,
        schema_id=parties._schema_id,
        schema_version=parties._schema_version,
        payload=parties.body_payload(),
        sources=parties.sources_payload(),
        schema_for_validation=parties_schema,
    )

    typer.echo(
        f"emit: OK \u2014 {len(results)} ACs into {results_dir}"
        + (
            f" (skipped {len(raw.sections) - len(results)} countermanded)"
            if len(results) < len(raw.sections) else ""
        )
    )
    typer.echo(
        f"summary: {summary_path} \u2014 "
        f"{len(summary.party_totals)} parties, "
        f"top: "
        + ", ".join(
            f"{p.party_short}={p.seats_won}" for p in summary.party_totals[:5]
        )
    )


@app.command("ingest-energy-power-plants")
def ingest_energy_power_plants(
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False, dir_okay=True, exists=True,
    ),
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to processing.json. Defaults to <root>/config/processing.json.",
    ),
) -> None:
    """Ingest india-geodata energy/power-plants → features + indicator artifacts.

    Phase B of TODO/SOCIO-ECONOMIC-EXPANSION.md. See
    docs/research/energy-power-plants.md for source rationale.
    """
    from yen_gov.sources.india_geodata import power_plants

    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)
    schema_dir = root / "datasets" / "schemas"

    with Fetcher(
        source="india_geodata",
        runtime_root=root,
        timeout_seconds=cfg.fetch.timeout_seconds,
        retry_attempts=cfg.fetch.retry_attempts,
        retry_backoff_seconds=cfg.fetch.retry_backoff_seconds or 1.0,
        user_agent=cfg.fetch.user_agent,
    ) as fetcher:
        paths = power_plants.ingest(
            fetcher=fetcher, repo_root=root, schema_dir=schema_dir,
        )

    typer.echo(
        "ingest-energy-power-plants: OK\n"
        f"  geojson:   {paths.geojson}\n"
        f"  sidecar:   {paths.sidecar}\n"
        f"  indicator: {paths.indicator}"
    )


@app.command("ingest-fiscal-rbi")
def ingest_fiscal_rbi(
    root: Path = typer.Option(
        Path.cwd(), "--root", "-r",
        help="Repo root (defaults to current directory).",
        file_okay=False, dir_okay=True, exists=True,
    ),
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to processing.json. Defaults to <root>/config/processing.json.",
    ),
) -> None:
    """Ingest RBI State Finances workbook → 8 fiscal indicator artifacts.

    See docs/architecture/backend/sources-rbi.md for the contract and
    backend/yen_gov/sources/rbi_xlsx/urls.py for source-resolution chain
    (pinned URL → RBI_STATE_FINANCES_URL env → local .runtime cache).
    """
    from yen_gov.sources.rbi_xlsx import ingest as rbi_ingest_mod

    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)
    schema_dir = root / "datasets" / "schemas"

    with Fetcher(
        source="rbi",
        runtime_root=root,
        timeout_seconds=cfg.fetch.timeout_seconds,
        retry_attempts=cfg.fetch.retry_attempts,
        retry_backoff_seconds=cfg.fetch.retry_backoff_seconds or 1.0,
        # RBI's CDN rejects non-browser UAs with an HTML error page (which
        # then fails XLSX parsing as ``BadZipFile``). Use a real Chrome UA
        # for this source only — the project's "yen-gov/0.1" UA is kept
        # for every other adapter so RBI is the documented exception.
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 yen-gov/0.1"
        ),
    ) as fetcher:
        result = rbi_ingest_mod.ingest(
            fetcher=fetcher, repo_root=root, schema_dir=schema_dir,
        )

    typer.echo("ingest-fiscal-rbi: OK")
    for r in result.indicators:
        typer.echo(f"  - {r.indicator_id}")
        typer.echo(f"    workbook_url:  {r.workbook_url}")
        typer.echo(f"    workbook_time: {r.workbook_fetched_at.isoformat()}")
        typer.echo(f"    sheet:         {r.sheet_name}  ({r.period_columns} period cols)")
        typer.echo(f"    rows written:  {r.row_count}")
        typer.echo(f"    artifact:      {r.artifact_path.relative_to(root).as_posix()}")


