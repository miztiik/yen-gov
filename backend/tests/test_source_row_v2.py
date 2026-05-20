"""Tier-A tests for the v2.0 sources citation-ledger contract.

Per CLAUDE.md §15: tmp_path only, no mocks, no corpus walk. These tests
pin the citation-ledger semantics (ADR-0032 / P.0e) end-to-end:

1. The on-disk schema accepts the documented v2.0 example.
2. The on-disk schema rejects every removed v1.0 fetch-ledger field
   (``additionalProperties: false`` is the structural gate).
3. ``derive_source_id`` is deterministic over the citation triple.
4. ``derive_source_id`` handles an empty vintage cleanly.
5. ``render_citation`` composes a sensible default from the triple.
6. ``render_citation`` produces a vintage-less default when vintage is empty.
7. ``render_citation`` returns ``citation_full`` verbatim when provided.
8. ``verification_method_rank`` returns the documented integer hierarchy.
9. The 4-value verification_method enum is ordered as a quality ladder
   (live-fetch is the highest-trust label; editorial is the lowest).
10. The Pydantic SourceRow ↔ writer DDL column list stays in sync — the
    test imports both and walks them, so a future schema bump that adds
    a column without updating the DDL fires here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from yen_gov.canonical.citation import (
    CONFIDENCE_TIERS,
    LICENSES,
    VERIFICATION_METHODS,
    derive_source_id,
    render_citation,
    verification_method_rank,
)
from yen_gov.canonical.envelope import SourceRow
from yen_gov.canonical.writer import _SRC_DDL


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "source.schema.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _example_v2_row() -> dict:
    return {
        "source_id": "src-abc123def456",
        "producer": "Election Commission of India",
        "title": "Statistical Report Section 10 (Detailed Results) — S22 AcGenApr2021",
        "vintage": "AcGenApr2021",
        "license": "OGL-IN-1.0",
        "confidence_tier": "gold",
        "is_issuing_authority": True,
        "verification_method": "archived-snapshot",
        "url_main": "https://results.eci.gov.in/AcGenApr2021/S22/Section10.xlsx",
        "citation_full": None,
        "notes": None,
    }


def _v2_container(rows: list[dict]) -> dict:
    return {
        "$schema": "../schemas/source.schema.json",
        "$schema_version": "2.0",
        "sources": rows,
    }


# ---------------------------------------------------------------------------
# Schema-on-disk tests (validate the rewritten source.schema.json)
# ---------------------------------------------------------------------------


def test_schema_loads_and_validates_v2_example() -> None:
    """The shipped schema MUST accept a well-formed v2.0 row + envelope.

    This is the smoke test for the schema rewrite itself — if the file
    is malformed JSON, or the example diverges from the contract, this
    fails loudly before any other test attempts to construct rows.
    """
    schema = _load_schema()
    assert schema["x-version"] == "2.0"
    # The last changelog entry's version MUST match x-version (CLAUDE.md §11).
    assert schema["x-changelog"][-1]["version"] == "2.0"
    validator = Draft202012Validator(schema)
    container = _v2_container([_example_v2_row()])
    errors = sorted(validator.iter_errors(container), key=lambda e: list(e.path))
    assert errors == [], f"v2.0 example failed validation: {errors}"


def test_schema_rejects_v1_fields() -> None:
    """``additionalProperties: false`` MUST forbid every removed v1.0 field.

    The v1.0 → v2.0 pivot removed the fetch-ledger columns. The schema's
    structural gate is the only thing keeping a stray v1.0 emitter from
    sneaking a forbidden field back into a v2.0 row.
    """
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    forbidden_v1_fields = {
        "url": "https://example.gov.in/x",
        "content_hash": "deadbeef" * 8,
        "url_download": "https://example.gov.in/x",
        "date_accessed": "2026-05-20",
        "first_fetched_at": "2026-05-20T00:00:00Z",
        "last_seen_at": "2026-05-20T00:00:00Z",
    }
    for field_name, sample_value in forbidden_v1_fields.items():
        row = _example_v2_row()
        row[field_name] = sample_value
        container = _v2_container([row])
        errors = list(validator.iter_errors(container))
        assert errors, (
            f"v2.0 schema should REJECT v1.0 field {field_name!r}, "
            f"but validation passed for row {row!r}"
        )


# ---------------------------------------------------------------------------
# derive_source_id tests
# ---------------------------------------------------------------------------


def test_source_id_derivation_is_deterministic() -> None:
    """Same (producer, title, vintage) → same source_id, always.

    The whole point of derivation is that two ingest paths (e.g. live-fetch
    vs hand-imported) producing the same citation collapse to ONE row.
    """
    producer = "Election Commission of India"
    title = "Statistical Report Section 10 (Detailed Results) — S22 AcGenApr2021"
    vintage = "AcGenApr2021"
    first = derive_source_id(producer, title, vintage)
    second = derive_source_id(producer, title, vintage)
    assert first == second
    # MUST match the on-disk regex so writer rows are accepted.
    assert re.match(r"^src-[a-z0-9]{12}$", first), first
    # Sanity: a different vintage MUST produce a different id.
    other = derive_source_id(producer, title, "AcGenMay2026")
    assert other != first


def test_source_id_handles_empty_vintage() -> None:
    """A citation with no published vintage (rare — undated reports) must
    still derive a stable, regex-conformant source_id."""
    sid = derive_source_id("yen-gov", "Internal Hand-Authored Note", "")
    assert re.match(r"^src-[a-z0-9]{12}$", sid), sid
    # Determinism MUST hold even when vintage is empty.
    assert sid == derive_source_id("yen-gov", "Internal Hand-Authored Note", "")


# ---------------------------------------------------------------------------
# render_citation tests
# ---------------------------------------------------------------------------


def test_default_citation_render_with_vintage() -> None:
    """When citation_full is None, the renderer composes a citizen-readable
    default from the (producer, title, vintage) triple."""
    rendered = render_citation(
        producer="Election Commission of India",
        title="Statistical Report Section 10 (Detailed Results) — S22 AcGenApr2021",
        vintage="AcGenApr2021",
    )
    assert "Election Commission of India" in rendered
    assert "Statistical Report Section 10" in rendered
    assert "AcGenApr2021" in rendered


def test_default_citation_render_without_vintage() -> None:
    """An empty vintage MUST NOT crash the renderer or produce a dangling
    separator — citizens see a cleanly-truncated citation."""
    rendered = render_citation(
        producer="yen-gov",
        title="Internal Hand-Authored Note",
        vintage="",
    )
    assert "yen-gov" in rendered
    assert "Internal Hand-Authored Note" in rendered
    # No trailing parenthesis-with-empty-vintage, no double space, no
    # double comma. Exact format is up to the renderer; these are the
    # smell tests.
    assert "()" not in rendered
    assert ", ," not in rendered
    assert "  " not in rendered


def test_citation_full_override_wins() -> None:
    """When the adapter supplies citation_full, it is returned verbatim —
    publisher-fidelity beats template composition."""
    override = "Election Commission of India (2021). “Statistical Report on General Election to the Legislative Assembly of Tamil Nadu, 2021.” New Delhi."
    rendered = render_citation(
        producer="Election Commission of India",
        title="Statistical Report Section 10 (Detailed Results) — S22 AcGenApr2021",
        vintage="AcGenApr2021",
        citation_full=override,
    )
    assert rendered == override


# ---------------------------------------------------------------------------
# verification_method tests
# ---------------------------------------------------------------------------


def test_verification_method_rank() -> None:
    """Documented integer hierarchy: live-fetch > archived-snapshot >
    transcribed > editorial. Citizens (or downstream tooling) that want to
    pick the highest-confidence source for a fact use this rank."""
    assert verification_method_rank("live-fetch") == 4
    assert verification_method_rank("archived-snapshot") == 3
    assert verification_method_rank("transcribed") == 2
    assert verification_method_rank("editorial") == 1


def test_verification_method_enum_order_documents_hierarchy() -> None:
    """The VERIFICATION_METHODS tuple is the canonical order; the rank
    function MUST agree with it (rank = len - index, i.e. first element is
    highest trust). Pins the doc-to-code binding so a future shuffle of
    one fires the other in the same commit."""
    assert VERIFICATION_METHODS == (
        "live-fetch",
        "archived-snapshot",
        "transcribed",
        "editorial",
    )
    ranks = [verification_method_rank(m) for m in VERIFICATION_METHODS]
    assert ranks == sorted(ranks, reverse=True), (
        f"verification_method_rank disagrees with VERIFICATION_METHODS "
        f"hierarchy: ranks={ranks}"
    )


# ---------------------------------------------------------------------------
# Writer DDL ↔ Pydantic model parity
# ---------------------------------------------------------------------------


def test_writer_ddl_matches_schema_columns() -> None:
    """The writer's in-memory ``sources`` table DDL MUST list exactly the
    same columns (and in the same order) as the Pydantic ``SourceRow`` —
    otherwise the executemany tuple-positional INSERT silently misaligns.

    Catches the "add a column to the schema, forget to add it to the DDL
    or the INSERT tuple builder" class of bug. Runs against the real
    ``_SRC_DDL`` constant exported by ``canonical.writer``, no mocks.
    """
    # Extract the column NAMES (first whitespace-delimited token per line
    # inside the parens) from _SRC_DDL.
    ddl_columns: list[str] = []
    inside = False
    for raw_line in _SRC_DDL.splitlines():
        line = raw_line.strip()
        if line.startswith("CREATE TABLE"):
            inside = True
            continue
        if line.startswith(")"):
            inside = False
            continue
        if not inside or not line:
            continue
        # Strip trailing comma + type tokens; keep first identifier.
        col = line.split()[0].rstrip(",")
        ddl_columns.append(col)

    pydantic_columns = list(SourceRow.model_fields.keys())
    assert ddl_columns == pydantic_columns, (
        f"DDL and SourceRow column lists diverged:\n"
        f"  DDL:      {ddl_columns}\n"
        f"  Pydantic: {pydantic_columns}\n"
        "Both must be updated in the same commit (ADR-0032)."
    )

    # Belt-and-braces: feed the DDL to DuckDB and confirm an
    # executemany-positional INSERT with len(pydantic_columns) placeholders
    # accepts a row built from a real SourceRow's tuple shape.
    con = duckdb.connect(":memory:")
    con.execute(_SRC_DDL)
    row = SourceRow(
        source_id="src-test00000001",
        producer="yen-gov",
        title="Test",
        vintage="2026",
        license="internal",
        confidence_tier="gold",
        is_issuing_authority=False,
        verification_method="editorial",
    )
    tup = tuple(getattr(row, c) for c in pydantic_columns)
    placeholders = ", ".join(["?"] * len(pydantic_columns))
    con.execute(f"INSERT INTO sources VALUES ({placeholders})", tup)
    [(n,)] = con.execute("SELECT COUNT(*) FROM sources").fetchall()
    assert n == 1


# ---------------------------------------------------------------------------
# Catalogue sanity (kept narrow — these constants are the public surface
# the citation module exports for other modules to reuse).
# ---------------------------------------------------------------------------


def test_catalogue_constants_match_pydantic_literals() -> None:
    """The Literal enums on SourceRow MUST agree with the exported tuples
    so other modules (frontend codegen, validator, doc generators) can
    iterate either one and get the same answer."""
    # Pydantic Literal values come out of model_fields as `args` on the
    # underlying annotation; we project them via the field's metadata.
    license_literal = SourceRow.model_fields["license"].annotation
    confidence_literal = SourceRow.model_fields["confidence_tier"].annotation
    verification_literal = SourceRow.model_fields["verification_method"].annotation

    from typing import get_args

    assert set(get_args(license_literal)) == set(LICENSES)
    assert set(get_args(confidence_literal)) == set(CONFIDENCE_TIERS)
    assert set(get_args(verification_literal)) == set(VERIFICATION_METHODS)


def test_pydantic_rejects_invalid_source_id_pattern() -> None:
    """Defence-in-depth: even if a caller skips ``derive_source_id``, the
    Pydantic regex MUST reject a non-conformant source_id."""
    with pytest.raises(ValidationError):
        SourceRow(
            source_id="src-too-short",  # not 12 lowercase alnum
            producer="yen-gov",
            title="x",
            vintage="2026",
            license="internal",
            confidence_tier="gold",
            is_issuing_authority=False,
            verification_method="editorial",
        )
