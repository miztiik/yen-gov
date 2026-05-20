"""Regression guard for PR-R.3 (TODO ``1.8e``).

The legacy per-state ``datasets/elections/<event>/<state>/results.sqlite``
artifact + the ``backend/yen_gov/emit/sqlite.py`` emitter + the
``frontend/src/lib/sql.ts`` sql.js loader + ``frontend/src/lib/psephlab/actuals.ts``
all retired in PR-R.3 (commit ``a4505501``). Psephlab + Compare now read
the canonical store (``datasets/elections/election_results.parquet``) via
DuckDB-WASM — see [`docs/architecture/data/canonical-store.md`](../../docs/architecture/data/canonical-store.md).

This test scans the backend as source text (no AST parse needed — the
goal is to catch the symbol re-appearing in any form, including a
revived import or a comment hinting the emitter is coming back). It
asserts CODE invariants only; the matching on-disk-corpus check
("zero ``.sqlite`` under ``datasets/elections/``") is data-quality
conformance and lives in ``python -m yen_gov validate --root .`` per
CLAUDE.md §10 + §11 Tier B.

Re-introducing any of the guarded symbols would silently fork the
contract surface back to per-state SQLite shards and violate
CLAUDE.md Holy Law #10 ("Emit JSON projections of canonical data
for the citizen frontend" — same anti-pattern applies to SQLite).
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
EMIT_DIR = BACKEND_ROOT / "yen_gov" / "emit"
PIPELINE_DIR = BACKEND_ROOT / "yen_gov" / "pipeline"


def test_sqlite_emitter_module_does_not_exist() -> None:
    """``backend/yen_gov/emit/sqlite.py`` MUST stay deleted. The
    canonical Parquet store (``election_results.parquet``) is the only
    shipped query artifact; per-state SQLite shards re-fork the contract
    surface."""
    candidate = EMIT_DIR / "sqlite.py"
    assert not candidate.exists(), (
        f"{candidate.relative_to(REPO_ROOT).as_posix()} reappeared. "
        "PR-R.3 deleted this emitter; the canonical Parquet store is the "
        "only shipped query artifact for elections data. Re-introducing "
        "a per-state SQLite emitter forks the contract surface and "
        "violates TODO row 1.8e + CLAUDE.md Holy Law #10."
    )


def test_pipeline_modules_do_not_import_sqlite3() -> None:
    """No ``pipeline/*.py`` module may import ``sqlite3``. The live-fetch
    flow writes ONLY to the canonical Parquet store via
    ``yen_gov.canonical.writer.write_batch`` (PR-O.3b-main); an sqlite3
    import signals a per-state SQLite emit path is being revived."""
    offenders: list[str] = []
    for py in PIPELINE_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "import sqlite3" in text or "from sqlite3" in text:
            offenders.append(py.relative_to(REPO_ROOT).as_posix())
    assert not offenders, (
        f"Pipeline modules imported sqlite3: {offenders}. The live-fetch "
        "pipeline writes only to the canonical Parquet store via "
        "write_batch (PR-O.3b-main, PR-R.3). Reintroducing sqlite3 here "
        "violates TODO row 1.8e."
    )


def test_emit_subpackage_does_not_reference_sqlite_module() -> None:
    """No ``emit/*.py`` module may import or reference the deleted
    ``yen_gov.emit.sqlite`` module. ``csv_bundle.py`` is the only
    surviving secondary emitter."""
    offenders: list[tuple[str, str]] = []
    needle_imports = (
        "from yen_gov.emit.sqlite",
        "from .sqlite import",
        "import yen_gov.emit.sqlite",
        "emit_state_sqlite",
        "write_state_sqlite",
    )
    for py in EMIT_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for needle in needle_imports:
            if needle in text:
                offenders.append((py.relative_to(REPO_ROOT).as_posix(), needle))
    assert not offenders, (
        f"emit/ modules referenced the deleted sqlite emitter: {offenders}. "
        "PR-R.3 retired ``yen_gov.emit.sqlite`` along with the 41 per-state "
        "``results.sqlite`` shards. Re-importing the module signals it is "
        "about to come back; violates TODO row 1.8e."
    )
