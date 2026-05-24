"""Compile ``datasets/taxonomy/election_events.json`` to a Parquet dim.

§8.3 Python-compiles-to-Parquet seam. Emits one row per
``(state_code, event_id)`` with all event metadata as wide columns —
the natural shape for joining elections observation rows back to their
event metadata (display label, polled_on date, data_status).

This is PURE REFERENCE — no winning_party_id, no seat counts, no
winner-aggregations. Per Plan §0e.10.2-E LOCKED: election_events
carries election metadata (when held, what kind, citizen label,
upstream completeness state), and nothing about WHO won. Winners come
from the elections fact tables (election_results.parquet) where they
belong. Lifting them into a reference table re-introduces the smear
the canonical pivot exists to remove.

Input contract: ``datasets/taxonomy/election_events.json`` validated
against ``datasets/schemas/election-events.schema.json`` (v1.1; the
``default`` boolean was removed in v1.1 because the per-state default
event is derived from ``max(polled_on)`` at read time rather than
hand-flagged — see PR #191 and the Q1+PR-2 cleanup PR). The JSON
groups events nested under ``states.<S22>: [...]``; the Parquet
denormalises that to one row per event with ``state_code`` as a
column so the table is queryable by either axis without unnesting a
map column.

Rejected designs (do NOT re-propose):
    1. Add ``winning_party_id`` and ``total_seats_won`` columns. Plan
       §0e.10.2-E explicitly REJECTED this. Election outcomes are
       observations, not reference. The fact-table pivot for elections
       (PR-O.1 / PR-R.1) is the consumer side; reference tables stay
       reference.
    2. Keep the nested ``states{<S>: [events]}`` shape via a MAP
       column. DuckDB-WASM MAP-lookup against a string key inside a
       WHERE clause forces a full scan; the wide denormalised shape
       hits the predicate index instead.
    3. Derive ``year`` from ``polled_on`` and key the table on
       (state, year). Multiple events can poll in the same calendar
       year (state assembly + state bye-election + national LS slice
       — see S04 Bihar 2024); event_id is the only unique key.
    4. Re-introduce ``is_default`` as a Parquet column derived from
       max(polled_on). The reader composes "which is default" at query
       time — materialising it in the dim duplicates the fact and
       makes every re-ingest a no-op write that nonetheless touches
       every cell. Reference tables stay reference; derivations stay
       derivations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

ELECTION_EVENTS_ROW_SCHEMA_VERSION = "1.1"


EventKind = Literal["assembly", "lok_sabha", "by_election"]
DataStatus = Literal["complete", "partial", "pending_upstream"]


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    kind: EventKind
    display: str = Field(min_length=1)
    polled_on: str = Field(min_length=10, max_length=10)
    term_end_estimated: str | None = None
    data_status: DataStatus
    notes: str | None = None


class _ElectionEventsFile(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    states: dict[str, list[_Event]]


def _rows(
    states: dict[str, list[_Event]],
) -> list[
    tuple[str, str, str, str, str, str | None, str, str | None]
]:
    out: list[
        tuple[str, str, str, str, str, str | None, str, str | None]
    ] = []
    for state_code, events in states.items():
        for ev in events:
            out.append(
                (
                    state_code,
                    ev.event_id,
                    ev.kind,
                    ev.display,
                    ev.polled_on,
                    ev.term_end_estimated,
                    ev.data_status,
                    ev.notes,
                )
            )
    out.sort(key=lambda row: (row[0], row[1]))
    return out


def compile_to_parquet(json_in: Path, parquet_out: Path) -> int:
    parquet_out = Path(parquet_out)
    payload = json.loads(Path(json_in).read_text(encoding="utf-8"))
    for k in ("$schema", "$schema_version", "$comment", "sources"):
        payload.pop(k, None)
    data = _ElectionEventsFile.model_validate(payload)
    rows = _rows(dict(data.states))

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE election_events (
                state_code VARCHAR NOT NULL,
                event_id VARCHAR NOT NULL,
                kind VARCHAR NOT NULL,
                display VARCHAR NOT NULL,
                polled_on DATE NOT NULL,
                term_end_estimated DATE,
                data_status VARCHAR NOT NULL,
                notes VARCHAR
            )
            """
        )
        if rows:
            con.executemany(
                "INSERT INTO election_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        con.execute(
            f"""
            COPY (
                SELECT * FROM election_events
                ORDER BY state_code, event_id
            ) TO '{parquet_out.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    return len(rows)
