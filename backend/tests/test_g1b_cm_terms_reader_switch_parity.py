"""G.1.b reader-switch parity oracle (Holy Law #7 — real on-disk data).

After the G.1.b reader-switch (2026-05-22), the tenure seed sources office
IDENTITY from `entities.parquet WHERE entity_type='office_bearer'`. Since
G.1.c (2026-05-22) tenure facts come from the consolidated long-form
`datasets/taxonomy/office_holdings.json` emitted by
`office_holdings_seed.compile_to_parquet`.

This oracle binds the canonical Parquet outputs on disk to the contract:
1. Every dim_offices row's identity columns (office_id/entity_id/role/label)
   MUST equal the matching office_bearer entity in entities.parquet.
2. Every holdings row's office_id MUST resolve to an office_bearer entity.
3. The CM baseline must stay at 31 offices / 359 holdings, with the
    2026-05-25 President/VP slice adding 2 offices / 5 holdings.

Runs only when the canonical parquets exist on disk; skips cleanly when the
corpus is absent (per Holy Law #7 — real data, not fixtures). The earlier
``test_g1a_office_bearer_entity_parity.py`` checks the entity-lift; this file
checks the reader-switch direction (offices/holdings -> entities).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITIES_PARQUET = REPO_ROOT / "datasets" / "taxonomy" / "entities.parquet"
DIM_OFFICES_PARQUET = REPO_ROOT / "datasets" / "governments" / "dim_offices.parquet"
HOLDINGS_PARQUET = (
    REPO_ROOT / "datasets" / "governments" / "governments_office_holdings.parquet"
)


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(":memory:")


@pytest.mark.skipif(
    not (ENTITIES_PARQUET.is_file() and DIM_OFFICES_PARQUET.is_file()),
    reason="entities.parquet or dim_offices.parquet not on disk (Holy Law #7)",
)
def test_every_dim_office_identity_matches_office_bearer_entity() -> None:
    """Every dim_offices row's (office_id, entity_id, role, label) must
    equal the corresponding office_bearer row in entities.parquet.

    This is the G.1.b contract: after the reader-switch the seed reads
    these four columns FROM entities.parquet; any future drift between
    the two surfaces would silently produce wrong office labels in the
    citizen "Your government" card.
    """
    con = _con()
    try:
        mismatches = con.execute(
            f"""
            WITH ob AS (
                SELECT
                    entity_id AS office_id,
                    parent_entity_id AS state_entity_id,
                    entity_code AS role,
                    display_name AS label
                FROM read_parquet('{ENTITIES_PARQUET.as_posix()}')
                WHERE entity_type = 'office_bearer'
            ),
            offices AS (
                SELECT office_id, entity_id, role, label
                FROM read_parquet('{DIM_OFFICES_PARQUET.as_posix()}')
            )
            SELECT
                offices.office_id,
                offices.entity_id     AS office_state_entity_id,
                ob.state_entity_id    AS entity_state_entity_id,
                offices.role          AS office_role,
                ob.role               AS entity_role,
                offices.label         AS office_label,
                ob.label              AS entity_label
            FROM offices
            LEFT JOIN ob USING (office_id)
            WHERE
                ob.office_id IS NULL
                OR offices.entity_id != ob.state_entity_id
                OR offices.role      != ob.role
                OR offices.label     != ob.label
            """
        ).fetchall()
    finally:
        con.close()
    assert mismatches == [], (
        f"{len(mismatches)} dim_offices row(s) diverge from entities.parquet "
        f"office_bearer identity. First 3: {mismatches[:3]!r}"
    )


@pytest.mark.skipif(
    not (ENTITIES_PARQUET.is_file() and HOLDINGS_PARQUET.is_file()),
    reason="entities.parquet or holdings.parquet not on disk (Holy Law #7)",
)
def test_every_holding_office_id_resolves_to_office_bearer_entity() -> None:
    """Every governments_office_holdings.office_id must resolve to an
    office_bearer entity. Catches orphan tenures that would point at a
    deleted office row.
    """
    con = _con()
    try:
        orphans = con.execute(
            f"""
            WITH ob AS (
                SELECT entity_id AS office_id
                FROM read_parquet('{ENTITIES_PARQUET.as_posix()}')
                WHERE entity_type = 'office_bearer'
            )
            SELECT DISTINCT h.office_id
            FROM read_parquet('{HOLDINGS_PARQUET.as_posix()}') AS h
            LEFT JOIN ob USING (office_id)
            WHERE ob.office_id IS NULL
            """
        ).fetchall()
    finally:
        con.close()
    assert orphans == [], (
        f"{len(orphans)} holdings row(s) reference an office_id with no "
        f"office_bearer entity in entities.parquet: {orphans!r}"
    )


@pytest.mark.skipif(
    not (DIM_OFFICES_PARQUET.is_file() and HOLDINGS_PARQUET.is_file()),
    reason="governments parquets not on disk (Holy Law #7)",
)
def test_row_counts_preserve_cm_baseline_plus_national_slice() -> None:
    """Belt-and-suspenders: the old CM baseline remains stable while
    the official President/VP slice adds exactly two office identities
    and five tenure rows.
    """
    con = _con()
    try:
        (offices_count,) = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{DIM_OFFICES_PARQUET.as_posix()}')"
        ).fetchone()
        (cm_offices_count,) = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{DIM_OFFICES_PARQUET.as_posix()}')
            WHERE role = 'CM'
            """
        ).fetchone()
        (national_offices_count,) = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{DIM_OFFICES_PARQUET.as_posix()}')
            WHERE office_id IN ('IN-PRES', 'IN-VPRES')
            """
        ).fetchone()
        (holdings_count,) = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{HOLDINGS_PARQUET.as_posix()}')"
        ).fetchone()
        (cm_holdings_count,) = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{HOLDINGS_PARQUET.as_posix()}')
            WHERE RIGHT(office_id, 3) = '-CM'
            """
        ).fetchone()
        (national_holdings_count,) = con.execute(
            f"""
            SELECT COUNT(*)
            FROM read_parquet('{HOLDINGS_PARQUET.as_posix()}')
            WHERE office_id IN ('IN-PRES', 'IN-VPRES')
            """
        ).fetchone()
    finally:
        con.close()
    assert offices_count == 33, f"expected 33 dim_offices rows; got {offices_count}"
    assert cm_offices_count == 31
    assert national_offices_count == 2
    assert holdings_count == 364, (
        f"expected 364 governments_office_holdings rows; got {holdings_count}"
    )
    assert cm_holdings_count == 359
    assert national_holdings_count == 5
