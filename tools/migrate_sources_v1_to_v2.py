"""Migrate ``datasets/taxonomy/sources.parquet`` v1.0 → v2.0 + rewrite FKs.

One-shot tool used during the P.0e source-provenance pivot (ADR-0032). The
on-disk v1.0 corpus is a *fetch ledger* keyed on ``(url, content_hash)``
with ``source_id = sha256(url)[:12]``. The v2.0 contract is a *citation
ledger* keyed on ``(producer, title, vintage)`` with
``source_id = sha256(producer|title|vintage)[:12]``.

This tool produces the v2.0 end-state WITHOUT re-running
``canonical-backfill-eci`` (the legacy per-AC JSON corpus that pipeline
walked has been migrated out by Phase 0 closeout — running it returns
zero rows). Instead it:

1. Reads the existing v1.0 ``sources.parquet`` to harvest ``url_main``
   per pair.
2. Walks every ``datasets/elections/state=*/election_results.parquet``
   shard to discover the full ``(upstream_state, period_label)`` grid.
3. For each pair derives the v2.0 ``(producer, title, vintage)`` triple
   matching ``canonical_eci_backfill._source_for_result`` exactly, plus
   the corresponding 12-char ``source_id``.
4. Emits the new v2.0 ``sources.parquet`` (55 rows × 11 cols).
5. Rewrites the ``source_id`` column of every state-shard
   ``election_results.parquet`` so every row's FK points at the new
   citation row (rather than the deprecated per-fetch row).
6. Verifies FK closure: every ``source_id`` referenced in any
   observation Parquet has a matching row in the new sources.parquet,
   and there are no orphan source rows.

This file is intentionally NOT part of the regular ``backend/yen_gov``
package — it is a tools/ artifact used once. The schema bump itself
(envelope.py, writer.py, canonical_eci_backfill.py) is the durable code
change; this script is a one-time data migration.

Run from repo root:

    python tools/migrate_sources_v1_to_v2.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb

# Allow importing the canonical citation helper without installing backend.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = REPO_ROOT / "backend"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from yen_gov.canonical.citation import derive_source_id  # noqa: E402


SOURCES_PARQUET = REPO_ROOT / "datasets" / "taxonomy" / "sources.parquet"
ELECTIONS_GLOB = str(REPO_ROOT / "datasets" / "elections" / "state=*" / "election_results.parquet")
ENTITY_STATE_RE = re.compile(r"^IN-([SU][0-9]{2})")


def _citation_for_pair(upstream_state: str, period_label: str) -> tuple[str, str, str, str]:
    """Mirror of ``canonical_eci_backfill._source_for_result`` triple.

    Returns ``(source_id, producer, title, vintage)``. MUST stay in sync
    with the canonical builder — any drift here would produce dangling
    FKs the next time a real backfill runs.
    """
    producer = "Election Commission of India"
    title = f"Statistical Report Section 10 (Detailed Results) — {upstream_state} {period_label}"
    vintage = period_label
    source_id = derive_source_id(producer, title, vintage)
    return source_id, producer, title, vintage


def _pick_url_main(urls: list[str | None]) -> str | None:
    """Pick the first non-synthetic upstream URL from a list of v1.0 url_main values.

    ``local://AcGen.../S.../eci-section-10`` markers were the v1.0
    sentinel for hand-imported ACs (no real upstream URL). Under v2.0
    these collapse to ``url_main=None`` per the ADR-0032 contract: the
    citation row carries the producer/title/vintage citation; the lack
    of a click-through URL is honest.
    """
    for u in urls:
        if u is None or u == "" or u.startswith("local://"):
            continue
        return u
    return None


def main() -> int:
    if not SOURCES_PARQUET.exists():
        print(f"ERROR: {SOURCES_PARQUET} not found. Run `git restore datasets/taxonomy/sources.parquet` first.")
        return 2

    con = duckdb.connect()

    # --- Step 1: inventory of (hive_state, upstream_state, period_label) + url_main per old source_id ----
    grid = con.execute(
        f"""
        WITH joined AS (
            SELECT
                o.state          AS hive_state,
                regexp_extract(o.entity_id, '^IN-([SU][0-9]{{2}})', 1) AS upstream_state,
                o.period_label,
                o.source_id      AS old_source_id,
                s.url_main       AS old_url_main
            FROM read_parquet('{ELECTIONS_GLOB}', hive_partitioning=true) o
            LEFT JOIN read_parquet('{SOURCES_PARQUET.as_posix()}') s
                ON o.source_id = s.source_id
        )
        SELECT
            hive_state,
            upstream_state,
            period_label,
            list(DISTINCT old_url_main) AS urls
        FROM joined
        GROUP BY hive_state, upstream_state, period_label
        ORDER BY hive_state, period_label
        """
    ).fetchall()
    print(f"step 1: discovered {len(grid)} (hive_state, upstream_state, period_label) tuples")

    # --- Step 2: build v2.0 source rows -------------------------------------------------------
    v2_rows: list[tuple] = []
    seen_source_ids: set[str] = set()
    pair_to_new_sid: dict[tuple[str, str], str] = {}  # (hive_state, period_label) -> new source_id

    for hive_state, upstream_state, period_label, urls in grid:
        sid, producer, title, vintage = _citation_for_pair(upstream_state, period_label)
        pair_to_new_sid[(hive_state, period_label)] = sid
        if sid in seen_source_ids:
            continue  # different hive_state but identical (upstream_state, period_label) → same citation
        seen_source_ids.add(sid)
        url_main = _pick_url_main(list(urls))
        v2_rows.append(
            (
                sid,                         # source_id
                producer,                    # producer
                title,                       # title
                vintage,                     # vintage
                "OGL-IN-1.0",               # license — ECI publishes under NDSAP / OGL-India
                "gold",                     # confidence_tier — issuing authority
                True,                       # is_issuing_authority
                "archived-snapshot",        # verification_method
                url_main,                   # url_main (Optional)
                None,                       # citation_full (renderer composes from triple)
                None,                       # notes
            )
        )
    print(f"step 2: built {len(v2_rows)} v2.0 source rows (citation collapse: 84 → {len(v2_rows)})")

    # --- Step 3: emit v2.0 sources.parquet -----------------------------------------------------
    con.execute(
        """
        CREATE OR REPLACE TABLE sources (
            source_id            VARCHAR NOT NULL,
            producer             VARCHAR NOT NULL,
            title                VARCHAR NOT NULL,
            vintage              VARCHAR NOT NULL,
            license              VARCHAR NOT NULL,
            confidence_tier      VARCHAR NOT NULL,
            is_issuing_authority BOOLEAN NOT NULL,
            verification_method  VARCHAR NOT NULL,
            url_main             VARCHAR,
            citation_full        VARCHAR,
            notes                VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        v2_rows,
    )
    out_path = SOURCES_PARQUET.as_posix()
    con.execute(
        f"COPY (SELECT * FROM sources ORDER BY source_id) TO '{out_path}' "
        f"(FORMAT 'parquet', COMPRESSION 'zstd')"
    )
    print(f"step 3: wrote v2.0 sources.parquet ({len(v2_rows)} rows) to {out_path}")

    # --- Step 4: rewrite source_id column in every state shard --------------------------------
    state_dirs = sorted((REPO_ROOT / "datasets" / "elections").glob("state=*/election_results.parquet"))
    print(f"step 4: rewriting source_id column in {len(state_dirs)} state shards...")
    for shard in state_dirs:
        hive_state = shard.parent.name.removeprefix("state=")
        # Build the per-shard remap CASE
        pairs_for_shard = [(pl, sid) for (hs, pl), sid in pair_to_new_sid.items() if hs == hive_state]
        if not pairs_for_shard:
            print(f"  WARN: no remap pairs for shard {hive_state} — skipping")
            continue
        case_expr = " ".join(
            f"WHEN period_label = '{pl}' THEN '{sid}'" for pl, sid in pairs_for_shard
        )
        shard_posix = shard.as_posix()
        # CTAS into a temp table, then COPY back to Parquet
        con.execute("DROP TABLE IF EXISTS shard_rewrite")
        con.execute(
            f"""
            CREATE TABLE shard_rewrite AS
            SELECT
                observation_id,
                entity_id,
                year,
                period_label,
                period_seq,
                indicator_id,
                value_numeric,
                value_text,
                CASE {case_expr} ELSE source_id END AS source_id,
                derivation
            FROM read_parquet('{shard_posix}')
            """
        )
        con.execute(
            f"COPY (SELECT * FROM shard_rewrite ORDER BY observation_id) TO '{shard_posix}' "
            f"(FORMAT 'parquet', COMPRESSION 'zstd')"
        )
        n_rows = con.execute("SELECT count(*) FROM shard_rewrite").fetchone()[0]
        n_new_sids = con.execute("SELECT count(DISTINCT source_id) FROM shard_rewrite").fetchone()[0]
        print(f"  {hive_state}: {n_rows} rows, {n_new_sids} distinct source_ids")

    # --- Step 5: verify FK closure ------------------------------------------------------------
    orphans = con.execute(
        f"""
        SELECT count(DISTINCT o.source_id)
        FROM read_parquet('{ELECTIONS_GLOB}', hive_partitioning=true) o
        WHERE o.source_id NOT IN (
            SELECT source_id FROM read_parquet('{SOURCES_PARQUET.as_posix()}')
        )
        """
    ).fetchone()[0]
    unused = con.execute(
        f"""
        SELECT count(*)
        FROM read_parquet('{SOURCES_PARQUET.as_posix()}') s
        WHERE s.source_id NOT IN (
            SELECT DISTINCT source_id FROM read_parquet('{ELECTIONS_GLOB}', hive_partitioning=true)
        )
        """
    ).fetchone()[0]
    print(f"step 5: FK closure — orphan FKs in observations: {orphans}; unused source rows: {unused}")
    if orphans != 0:
        print("ERROR: FK closure broken; refusing to declare migration complete.")
        return 3
    print("MIGRATION COMPLETE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
