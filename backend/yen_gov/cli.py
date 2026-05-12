"""yen-gov CLI."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from yen_gov.core.http import Fetcher
from yen_gov.core.io import write_artifact
from yen_gov.core.models import PartyEntry, PartiesSnapshot, ProcessingConfig, SourceRef
from yen_gov.pipeline.compose import (
    compose_result_summary_from_section_10,
    eci_code_by_short_from_partywise,
    load_eci_party_registry,
    parties_snapshot_from_section3,
    reconcile_winners_against_partywise,
)
from yen_gov.pipeline.reference import scrape_state_reference
from yen_gov.pipeline.run import parties_snapshot_from_partywise, run_state_slice
from yen_gov.sources.eci.categories import category_id_for
from yen_gov.sources.eci.events import event_info_for
from yen_gov.sources.eci.partywise import parse_partywise
from yen_gov.sources.eci.section3 import parse_section3_parties
from yen_gov.sources.eci.statistical_report import (
    download_documents,
    fetch_catalog,
)
from yen_gov.sources.eci.static_catalog import (
    STATIC_CATALOG_BROWSER_HEADERS,
    has_static_catalog,
    resolve_catalog,
)
from yen_gov.sources.eci.statistical_report_detailed import (
    parse_detailed_results,
    to_constituency_results,
)
from yen_gov.coverage import (
    INVENTORY_REL,
    compute_coverage,
    render_markdown,
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
    ``datasets/reference/in/election-events.json`` against the on-disk
    artifacts under ``datasets/elections/`` and renders a citizen-readable
    inventory. Re-run after every ingest; the file is not hand-maintained.
    """
    report = compute_coverage(root)
    md = render_markdown(report)
    typer.echo(md, nl=False)
    if write:
        target = root / INVENTORY_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md, encoding="utf-8")
        typer.echo(f"\ncoverage: wrote {INVENTORY_REL}")


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
    csv_bundle: bool = typer.Option(
        True, "--csv/--no-csv",
        help="Also emit results.csv (long format, researcher-facing) next to the JSON "
             "(docs/architecture/backend/emit-csv.md).",
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

    if csv_bundle:
        from yen_gov.emit.csv_bundle import emit_state_csv
        csv_path = emit_state_csv(state_dir=output_dir)
        typer.echo(f"csv: OK — {csv_path}")


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
    state: str = typer.Argument(
        None,
        help="ECI state code, e.g. S22. Omit when using --category-id.",
    ),
    year: int = typer.Argument(
        None,
        help="Election year, e.g. 2026. Omit when using --category-id.",
    ),
    category_id_opt: int = typer.Option(
        None, "--category-id",
        help="Bypass the (state, year) pin lookup and fetch this category_id "
             "directly. Useful for recon on a freshly-published URL like "
             "https://www.eci.gov.in/statistical-report/ae/<year>/<id> before "
             "editing config/eci-pins.json. Mutually exclusive with state/year.",
    ),
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

    Two ways to identify the catalogue:
      - ``eci-statreport S22 2026``                    (pinned lookup)
      - ``eci-statreport --category-id 16``            (direct, no pin)

    The first resolves the pinned category_id for (state, year); use this
    once a state's pin is in config/eci-pins.json. The second is for recon:
    when ECI publishes a new URL like /statistical-report/ae/2025/16, the
    integer at the end IS the category_id and you can inspect it without
    touching the pin file. The on-disk artifacts under .runtime/raw/eci/
    are debug only (ADR-0003); only the cleartext landing-page permalinks
    shown in the output are safe to persist in sources[].
    """
    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)

    if category_id_opt is not None:
        if state is not None or year is not None:
            raise typer.BadParameter(
                "--category-id is mutually exclusive with state/year arguments",
                param_hint="--category-id",
            )
        cid = category_id_opt
        typer.echo(f"category_id: {cid}  (direct, bypassing pin lookup)")
    else:
        if state is None or year is None:
            raise typer.BadParameter(
                "provide either (state year) positional args OR --category-id",
                param_hint="state year",
            )
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
    try:
        info = event_info_for(state, year)
    except KeyError as exc:
        if event is None:
            raise typer.BadParameter(str(exc), param_hint="--event") from exc
        # Caller passed an explicit --event for an unregistered (state, year).
        # Assume no partywise; user takes responsibility.
        from yen_gov.sources.eci.events import EventInfo  # local import OK
        info = EventInfo(event_id=event, has_partywise=False)
    if event is None:
        event = info.event_id
    has_partywise = info.has_partywise
    typer.echo(f"event:       {event} (has_partywise={has_partywise})")

    output_dir = output or (root / "datasets" / "elections" / event / state)
    schema_dir = root / "datasets" / "schemas"
    cr_schema = json.loads(
        (schema_dir / "result.constituency.schema.json").read_text(encoding="utf-8")
    )

    # 2024+ cohorts go through /api/election-result?category_id=<pinned id>;
    # 2023 cohorts go through the static URL template registered in
    # sources/eci/static_catalog.py. The dispatcher picks; the rest of the
    # function reads the same CatalogResponse contract regardless.
    static_path = has_static_catalog(state, year)
    if static_path:
        typer.echo("catalog:     static (legacy /full-statistical-reports/ URL template)")
    else:
        typer.echo(f"category_id: {category_id_for(state, year)}")

    extra_headers = STATIC_CATALOG_BROWSER_HEADERS if static_path else None

    with Fetcher(
        source="eci",
        runtime_root=root,
        timeout_seconds=cfg.fetch.timeout_seconds,
        retry_attempts=cfg.fetch.retry_attempts,
        retry_backoff_seconds=cfg.fetch.retry_backoff_seconds or 1.0,
        user_agent="Mozilla/5.0",  # Akamai blocks the project default
        extra_headers=extra_headers,
    ) as fetcher:
        catalog = resolve_catalog(state, year, fetcher=fetcher)
        # Section 10 — title starts with "10" (sometimes "10-" or "10 -").
        section_10 = next(
            (d for d in catalog.documents if d.title.lstrip().startswith("10")),
            None,
        )
        if section_10 is None:
            raise typer.Exit(
                f"no Section 10 (Detailed Results) document in catalog for "
                f"({state!r}, {year}); titles were: "
                f"{[d.title for d in catalog.documents]}"
            )
        typer.echo(f"section 10:  {section_10.title}")
        typer.echo(f"             {section_10.xlsx_url}")

        fetched = fetcher.fetch(section_10.xlsx_url)
        raw = parse_detailed_results(fetched.content)

        partywise_snapshot = None
        partywise_fetched = None
        section_3_fetched = None
        section_3_parties: list = []
        if has_partywise:
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
        else:
            # Archived event without a live-results portal page. Section 3
            # (List of Political Parties Participated) gives short→full
            # names but no numeric eci_code. We backfill numeric codes from
            # the canonical party registry derived from every parties.json
            # already on disk (ECI numeric codes are stable across cohorts).
            # Per N6 of TODO/ECI-MULTI-STATE-INGEST-PLAN.md.
            registry = load_eci_party_registry(root / "datasets" / "elections")
            party_eci_codes = {}
            section_3 = next(
                (d for d in catalog.documents if d.title.lstrip().startswith("3")),
                None,
            )
            if section_3 is not None:
                typer.echo(f"section 3:   {section_3.title}")
                typer.echo(f"             {section_3.xlsx_url}")
                section_3_fetched = fetcher.fetch(section_3.xlsx_url)
                section_3_parties = parse_section3_parties(section_3_fetched.content)
                # Resolve {short → eci_code} against the registry and feed
                # the same dict into to_constituency_results /
                # compose_result_summary_from_section_10 so per-AC results
                # AND result.summary.json carry numeric codes too.
                party_eci_codes = {
                    p.short_name: registry[p.short_name].eci_code
                    for p in section_3_parties
                    if p.short_name in registry
                }
                typer.echo(
                    f"             ({len(section_3_parties)} parties; "
                    f"{len(party_eci_codes)} resolved via registry "
                    f"({len(registry)} known shorts), "
                    f"{len(section_3_parties) - len(party_eci_codes)} unresolved)"
                )
            else:
                typer.echo(
                    "section 3:   (not found in catalog — parties roster will be empty)"
                )

    sources = [SourceRef(url=fetched.url, fetched_at=fetched.fetched_at)]
    if partywise_fetched is not None:
        sources.append(SourceRef(
            url=partywise_fetched.url, fetched_at=partywise_fetched.fetched_at,
        ))
    elif section_3_fetched is not None:
        sources.append(SourceRef(
            url=section_3_fetched.url, fetched_at=section_3_fetched.fetched_at,
        ))
    results = to_constituency_results(
        raw,
        election=event,
        state=state,
        top_n=cfg.results.top_n_candidates,
        collapse_others=cfg.results.collapse_others,
        sources=sources,
        party_eci_codes=party_eci_codes,
    )

    if partywise_snapshot is not None:
        # Cross-check: per-AC winners aggregated by party_short must match
        # the partywise (seats_won + leading) numbers. Either source could
        # be wrong; what matters is they agree before we publish. Fails
        # loud — no partial writes if mismatched.
        reconcile_winners_against_partywise(
            partywise=partywise_snapshot, constituencies=results,
        )
    else:
        typer.echo(
            "reconcile:   SKIPPED (no partywise snapshot; trusting Section 10 only)"
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

    # parties.json: live cohorts use the partywise snapshot directly; archived
    # cohorts use Section 3 + the canonical eci_code registry built from every
    # parties.json already on disk. The schema requires numeric eci_code, so
    # any Section-3 party whose short isn't in the registry is dropped from
    # the artifact (and surfaced in the unresolved log line).
    parties_schema = json.loads(
        (schema_dir / "party.schema.json").read_text(encoding="utf-8")
    )
    parties_path = output_dir / "parties.json"
    parties_snapshot = None
    if partywise_snapshot is not None and partywise_fetched is not None:
        parties_snapshot = parties_snapshot_from_partywise(
            partywise_snapshot,
            election=event,
            sources=[SourceRef(
                url=partywise_fetched.url,
                fetched_at=partywise_fetched.fetched_at,
            )],
        )
    elif section_3_fetched is not None and section_3_parties:
        # Archived path. registry was loaded above in the else branch.
        registry = load_eci_party_registry(root / "datasets" / "elections")
        parties_snapshot, unresolved = parties_snapshot_from_section3(
            section_3_parties,
            election=event,
            section_3_source=SourceRef(
                url=section_3_fetched.url,
                fetched_at=section_3_fetched.fetched_at,
            ),
            registry=registry,
            fetched_at=section_3_fetched.fetched_at,
        )
        if parties_snapshot is None:
            typer.echo(
                "parties.json: SKIPPED (zero of "
                f"{len(section_3_parties)} Section-3 parties resolved against "
                f"registry; populate datasets/elections/<event>/<state>/parties.json "
                "for at least one cohort first)"
            )
        elif unresolved:
            typer.echo(
                f"parties.json: {len(parties_snapshot.parties)} parties "
                f"({len(unresolved)} dropped — short_names absent from registry: "
                f"{', '.join(sorted(unresolved)[:10])}"
                + ("…" if len(unresolved) > 10 else "")
                + ")"
            )

    if parties_snapshot is not None:
        write_artifact(
            path=parties_path,
            schema_id=parties_snapshot._schema_id,
            schema_version=parties_snapshot._schema_version,
            payload=parties_snapshot.body_payload(),
            sources=parties_snapshot.sources_payload(),
            schema_for_validation=parties_schema,
        )
    elif partywise_snapshot is None and section_3_fetched is None:
        typer.echo(
            "parties.json: SKIPPED (no partywise snapshot and no Section 3)"
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


# State-name token → ECI state code. Mirrors NAME_TO_ECI used by the
# (now-deleted) recon tool; used by eci-statreport-emit-local to
# auto-detect (state, year) from the drop-dir filename.
_LOCAL_NAME_TO_ECI: dict[str, str] = {
    "andhra_pradesh": "S01", "arunachal_pradesh": "S02", "assam": "S03",
    "bihar": "S04", "goa": "S05", "gujarat": "S06", "haryana": "S07",
    "himachal_pradesh": "S08", "karnataka": "S10", "kerala": "S11",
    "madhya_pradesh": "S12", "maharashtra": "S13", "manipur": "S14",
    "meghalaya": "S15", "mizoram": "S16", "nagaland": "S17",
    "odisha": "S18", "punjab": "S19", "rajasthan": "S20", "sikkim": "S21",
    "tamil_nadu": "S22", "tripura": "S23", "uttar_pradesh": "S24",
    "west_bengal": "S25", "chhattisgarh": "S26", "jharkhand": "S27",
    "uttarakhand": "S28", "telangana": "S29",
    "delhi": "U05", "puducherry": "U07", "jammu_kashmir": "U08",
}

# Filename pattern: ``YYYY_state_<name>_*.xlsx`` (the shape produced by
# old.eci.gov.in's Section 10 hand-download flow). See
# notes/eci-portal-recon-2026-05-11.md for sample filenames.
_LOCAL_FNAME_RE = re.compile(
    r"^(?P<year>\d{4})_state_(?P<state>[a-z][a-z_]*?)(?=_[A-Z0-9]|[-. ]|$)",
)


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
    config: Path = typer.Option(
        None, "--config", "-c",
        help="Path to processing.json. Defaults to <root>/config/processing.json.",
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

    # --- Load config (top_n / collapse_others) --------------------------------
    config_path = config or (root / "config" / "processing.json")
    config_doc = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("$schema", "$schema_version"):
        config_doc.pop(key, None)
    cfg = ProcessingConfig.model_validate(config_doc)

    # --- Parse + emit ---------------------------------------------------------
    schema_dir = root / "datasets" / "schemas"
    cr_schema = json.loads(
        (schema_dir / "result.constituency.schema.json").read_text(encoding="utf-8")
    )
    summary_schema = json.loads(
        (schema_dir / "result.summary.schema.json").read_text(encoding="utf-8")
    )

    raw = parse_detailed_results(file.read_bytes())
    typer.echo(f"parsed:      {len(raw.sections)} AC sections")

    # sources=[] per ADR-0002 (hand-authored / out-of-band ingest)
    results = to_constituency_results(
        raw,
        election=event,
        state=state,
        top_n=cfg.results.top_n_candidates,
        collapse_others=cfg.results.collapse_others,
        sources=[],
        party_eci_codes=None,
    )
    output_dir = root / "datasets" / "elections" / event / state
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
        raw, election=event, state=state, sources=[], party_eci_codes=None,
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

    # parties.json: hand-import path has no Section 3 (the operator only
    # downloaded the Section 10 XLSX). Fall back to the same registry-
    # resolve idea used by the archived /api/ path, but treat the *unique
    # set of party_shorts present in Section 10 candidates* as the "which
    # parties participated\" claim. Independents and NOTA are excluded.
    # See docs/architecture/backend/sources-eci.md §\"When parties.json
    # gets emitted (and when it doesn't)\" for the wider doctrine.
    parties_schema = json.loads(
        (schema_dir / "party.schema.json").read_text(encoding="utf-8")
    )
    parties_path = output_dir / "parties.json"
    section_10_shorts: list[str] = sorted({
        c.party_short
        for sec in raw.sections
        for c in sec.candidates
        if not c.is_nota and not c.is_independent
    })
    registry = load_eci_party_registry(root / "datasets" / "elections")
    resolved = [s for s in section_10_shorts if s in registry]
    unresolved = [s for s in section_10_shorts if s not in registry]
    if resolved:
        # Aggregated artifact per ADR-0002: sources is the union of every
        # registry source-URL that contributed a resolved short. The local-
        # emit path itself was hand-authored (no upstream URL of its own),
        # so the only sources cited are the live cohorts whose published
        # eci_code we are reusing.
        contributing_urls: set[str] = set()
        for s in resolved:
            contributing_urls.update(registry[s].source_urls)
        snapshot = PartiesSnapshot(
            sources=[
                SourceRef(url=url, fetched_at=registry[resolved[0]].source_urls and "2026-05-13T00:00:00Z")  # noqa: E501
                for url in sorted(contributing_urls)
            ],
            election=event,
            parties=[
                PartyEntry(
                    eci_code=registry[s].eci_code,
                    short_name=s,
                    full_name=registry[s].full_name,
                )
                for s in resolved
            ],
        )
        write_artifact(
            path=parties_path,
            schema_id=snapshot._schema_id,
            schema_version=snapshot._schema_version,
            payload=snapshot.body_payload(),
            sources=snapshot.sources_payload(),
            schema_for_validation=parties_schema,
        )
        typer.echo(
            f"parties.json: {len(resolved)} parties "
            + (f"({len(unresolved)} dropped \u2014 absent from registry: "
               f"{', '.join(unresolved[:10])}"
               + ("\u2026" if len(unresolved) > 10 else "")
               + ")" if unresolved else "")
        )
    else:
        typer.echo(
            f"parties.json: SKIPPED (zero of {len(section_10_shorts)} "
            "Section-10 party_shorts resolved against registry)"
        )

    skipped = len(raw.sections) - len(results)
    typer.echo(
        f"emit:        OK \u2014 {len(results)} ACs into {results_dir}"
        + (f" (skipped {skipped} countermanded)" if skipped else "")
    )
    typer.echo(f"summary:     {summary_path}")

    # SQLite + CSV bundles parity with the live emit path. Psephlab and
    # the per-AC winner overlay both load results.sqlite directly, so
    # skipping it here would render the historical events but blank the
    # winners-on-map and 404 every Psephlab route. Same rationale for
    # the CSV bundle (researcher-facing).
    from yen_gov.emit.sqlite import emit_state_sqlite
    from yen_gov.emit.csv_bundle import emit_state_csv
    sqlite_path = emit_state_sqlite(state_dir=output_dir)
    typer.echo(f"sqlite:      OK \u2014 {sqlite_path}")
    csv_path = emit_state_csv(state_dir=output_dir)
    typer.echo(f"csv:         OK \u2014 {csv_path}")

    if delete_source_on_success:
        file.unlink()
        typer.echo(f"cleaned:     removed source {file}")


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


