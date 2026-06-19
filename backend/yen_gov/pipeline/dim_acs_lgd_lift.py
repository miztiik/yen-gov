"""Resolve ``ac_crosswalk.lgd_ac_id`` for canonical AC writes (Row A3).

:func:`load_lgd_lookup` returns the ``(state_code, eci_no) -> lgd_ac_id``
map over the covered subset, sourced from
``datasets/data/entities/ac_crosswalk.csv`` (the canonical home after the
parquet retirement in X1b). The live/backfill envelope builders
(:func:`pipeline.canonical_eci_backfill.build_slice_envelope`) call this so
EVERY future ``dim_acs`` write carries ``lgd_ac_id``. Without it the
writer's DELETE+INSERT UPSERT would null the column on the next re-run.

``lgd_ac_id`` is the canonical INTERNAL join key per ADR-0049; ``eci_no``
stays the citizen-facing display + URL label. The crosswalk covers only the
2008 delimitation cycle, so 1976 rows (and ACs with no LGD code yet, e.g.
U08/J&K, S03/Assam) keep ``lgd_ac_id = NULL``.

The one-shot ``relift_dim_acs`` emit (which rematerialised the retired
``dim_acs.parquet`` through the canonical writer) was removed in the
manifest-replace rip row; the parquet it targeted no longer exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import duckdb

#: The crosswalk binds only the post-delimitation cycle. A 1976 ``(state, eci)``
#: must never inherit a 2008 LGD code, hence the explicit guard on the join.
CROSSWALK_DELIM_YEAR = 2008


def load_lgd_lookup(datasets_root: Path) -> dict[tuple[str, int], int]:
    """Map ``(state_code, eci_no) -> lgd_ac_id`` over covered crosswalk rows.

    Only rows with a non-null ``lgd_ac_id`` appear; a missing key means the AC
    is not yet bound to an LGD code and the caller leaves ``lgd_ac_id`` NULL.
    Returns an empty map when the crosswalk CSV is absent.

    Reads ``datasets/data/entities/ac_crosswalk.csv`` via typed
    ``read_csv(columns=...)`` per the CSV column contract at
    ``datasets/data/_schema/columns.json``. The CSV does not carry the
    ``S01``-style ECI state code directly; it is derived in-SQL from the
    leading ``IN-([SU][0-9]{2})-`` segment of ``ac_id`` (every covered row
    in the on-disk corpus matches this pattern).
    """
    cx_path = datasets_root / "data" / "entities" / "ac_crosswalk.csv"
    if not cx_path.is_file():
        return {}
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            """
            SELECT regexp_extract(ac_id, '^IN-([SU][0-9]{2})-', 1) AS state_code,
                   eci_no,
                   lgd_ac_id
            FROM read_csv(
                ?,
                header = true,
                columns = {
                    'state_entity_id': 'VARCHAR',
                    'delim_year': 'INTEGER',
                    'eci_no': 'INTEGER',
                    'lgd_ac_id': 'INTEGER',
                    'ac_id': 'VARCHAR',
                    'ac_name': 'VARCHAR',
                    'match_method': 'VARCHAR',
                    'source_id': 'VARCHAR'
                },
                nullstr = '',
                auto_detect = false
            )
            WHERE lgd_ac_id IS NOT NULL
            """,
            [cx_path.as_posix()],
        ).fetchall()
    finally:
        con.close()
    return {(str(s), int(e)): int(lgd) for s, e, lgd in rows}


# Re-export for the envelope builders that populate lgd_ac_id on live writes.
__all__ = ["load_lgd_lookup", "CROSSWALK_DELIM_YEAR"]


# Type alias kept inline to avoid a runtime import where only annotations need it.
LgdLookup = Mapping[tuple[str, int], int]
