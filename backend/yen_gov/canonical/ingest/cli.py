"""The ``ingest`` CLI sub-app (Row 4, plan section 3).

Mounted in ``yen_gov.cli`` with a single ``app.add_typer(ingest_app,
name="ingest")`` line, so the entry point is ``python -m yen_gov ingest
<verb>``. Row 4 ships two verbs:

* ``run`` -- drive an indicator (primary) or an adapter scope into the
  canonical store. Prints the one-line fan-out echo BEFORE the work, then a
  per-indicator summary.
* ``status`` -- per-indicator coverage + which source owns which years +
  staleness cadence.

``clean`` is Row 12 (it adds a verb to THIS sub-app). ``--from/--to`` stage
windows are Row 5+. ``--resume`` (Row 5) continues from the committed
checkpoint. The flags here are the stable Row-4 grammar; later rows extend,
never rename.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from yen_gov.canonical.ingest.catalogue_fk import CatalogueError
from yen_gov.canonical.ingest.orchestrator import (
    IngestError,
    compute_status,
    orchestrate,
)
from yen_gov.canonical.ingest.registry import IngestConfigError, OrchestrateConfig
from yen_gov.core.logging import StructuredLogger, new_run_id

ingest_app = typer.Typer(
    help="Drive upstream sources into the canonical store (Fetch -> Enrich -> Publish).",
    no_args_is_help=True,
)


@ingest_app.command("run")
def run_command(
    indicator: Optional[str] = typer.Option(
        None,
        "--indicator",
        "-i",
        help="The indicator to ingest (primary work address).",
    ),
    adapter: Optional[str] = typer.Option(
        None,
        "--adapter",
        "-a",
        help="Restrict to this adapter (scope filter); alone, run all its indicators.",
    ),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to the current directory).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    staging_dir: Optional[Path] = typer.Option(
        None,
        "--staging-dir",
        "-s",
        help=(
            "Directory of operator-staged source files (e.g. RBI Handbook "
            "XLSX, or a fetchable cohort's flaky-TLS fallback). Required for "
            "operator-staged adapters."
        ),
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help=(
            "Continue from the last completed checkpoint year (completed years "
            "are skipped, remaining years processed). A plain run is already "
            "idempotent with the same effect; this is the explicit affordance."
        ),
    ),
) -> None:
    """Drive an indicator (or adapter scope) into the canonical CSV store.

    ``ingest run --indicator total-fertility-rate`` resolves the owning
    adapter under the hood; ``--adapter rbi-handbook`` filters the scope (and,
    given alone, runs every indicator that adapter owns).
    """
    if indicator is None and adapter is None:
        typer.echo(
            "ingest run: specify --indicator (primary) and/or --adapter "
            "(scope filter)",
            err=True,
        )
        raise typer.Exit(2)

    config = OrchestrateConfig(staging_dir=staging_dir)
    logger = StructuredLogger(run_id=new_run_id(), runtime_root=root, echo=False)
    try:
        result = orchestrate(
            indicator=indicator,
            adapter=adapter,
            repo_root=root,
            config=config,
            logger=logger,
            on_fanout=typer.echo,
            resume=resume,
        )
    except (CatalogueError, IngestError, IngestConfigError, KeyError) as exc:
        typer.echo(f"ingest run: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        logger.close()

    for res in result.results:
        typer.echo(
            f"  {res.indicator_id}: {res.row_count} rows, "
            f"{res.entity_count} entities, {res.time_min}-{res.time_max} "
            f"-> {res.output_ref}"
        )
    typer.echo(f"ingest run: OK ({len(result.results)} indicator(s))")


@ingest_app.command("status")
def status_command(
    indicator: str = typer.Option(
        ...,
        "--indicator",
        "-i",
        help="The indicator to report coverage + per-source year spans for.",
    ),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        "-r",
        help="Repo root (defaults to the current directory).",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
) -> None:
    """Show per-indicator coverage: which source owns which years + staleness."""
    report = compute_status(indicator=indicator, repo_root=root)

    owners = ", ".join(report.adapters) if report.adapters else "(none)"
    typer.echo(f"{report.indicator_id}: owned by [{owners}]")
    if report.update_period_days is not None:
        typer.echo(f"  refresh cadence: every {report.update_period_days} days")
    if report.last_checked is not None:
        typer.echo(f"  last checked:    {report.last_checked}")

    if not report.has_coverage:
        typer.echo("  coverage:        none yet (not ingested into the corpus)")
        return

    typer.echo("  coverage (per source):")
    for cov in report.coverage:
        who = cov.producer or cov.source_id
        typer.echo(
            f"    {cov.source_id} ({who}): {cov.year_min}-{cov.year_max} "
            f"({cov.observation_count} observations)"
        )


__all__ = ["ingest_app"]
