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
against ``datasets/schemas/election-events.schema.json`` (v1.0). The
JSON groups events nested under ``states.<S22>: [...]``; the Parquet
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
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

ELECTION_EVENTS_ROW_SCHEMA_VERSION = "1.0"


EventKind = Literal["assembly", "lok_sabha", "by_election"]
DataStatus = Literal["complete", "partial", "pending_upstream"]


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    kind: EventKind
    display: str = Field(min_length=1)
    polled_on: str = Field(min_length=10, max_length=10)
    term_end_estimated: str | None = None
    default: bool = False
    data_status: DataStatus
    notes: str | None = None


class _ElectionEventsFile(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    states: dict[str, list[_Event]]


def _rows(
    states: dict[str, list[_Event]],
) -> list[
    tuple[str, str, str, str, str, str | None, bool, str, str | None]
]:
    out: list[
        tuple[str, str, str, str, str, str | None, bool, str, str | None]
    ] = []
    for state_code, events in states.items():
        defaults_seen = 0
        for ev in events:
            if ev.default:
                defaults_seen += 1
            out.append(
                (
                    state_code,
                    ev.event_id,
                    ev.kind,
                    ev.display,
                    ev.polled_on,
                    ev.term_end_estimated,
                    ev.default,
                    ev.data_status,
                    ev.notes,
                )
            )
        # Defensive: catalogue schema says "at most one default per
        # state" — flag bad inputs cleanly here rather than letting the
        # consumer pick arbitrarily. Per Plan §0e.10.2-E this is a
        # citizen-facing field (drives /s/<state>/elections default
        # route resolution); a silent dupe would mis-route citizens to
        # whichever event sorted last.
        if defaults_seen > 1:
            raise ValueError(
                f"state {state_code!r} declares {defaults_seen} default "
                "events; at most one may set default: true"
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
                is_default BOOLEAN NOT NULL,
                data_status VARCHAR NOT NULL,
                notes VARCHAR
            )
            """
        )
        if rows:
            con.executemany(
                "INSERT INTO election_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
