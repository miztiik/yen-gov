"""Compile per-state cm_terms.json files to dim_offices + office_holdings.

§8.3 Python-compiles-to-Parquet seam. Produces:

- ``datasets/governments/dim_offices.parquet`` — one row per
  (state, office) pair. Today only office=CM is materialised; the
  grammar (LOCKED §0e.10.2-A) generalises to DCM / GOV / PM / etc.
- ``datasets/governments/governments_office_holdings.parquet`` — one row
  per CM term (or President's Rule interval) across every state.
- Side effect: UPSERT 31 Wikipedia "List of Chief Ministers of …"
  citation rows into ``datasets/taxonomy/sources.parquet`` so every
  holdings row's ``source_id`` resolves to a real ledger entry.

T.0a-ii role: lift the 359 CM terms currently in 31 per-state
``datasets/governments/in/states/<S>/cm_terms.json`` files into the
canonical store. Citizen-visible UI (the "colour by government" overlay
on socio-economic indicator timelines) reads these two parquets via
DuckDB-WASM; the JSON sources stay on disk until T.0c removes them.

Person identity model: this MVP carries ``person_slug`` (deterministic
lowercase hyphenated derivation from ``cm_name``) plus a verbatim
``person_name`` text column. No ``dim_persons.parquet`` is created here
— full person identity (with TCPD-style disambiguation across CM /
candidate / MP / MLA appearances) is the §0e.5 follow-up. For now,
``person_slug`` is a forward-compatible JOIN key that downstream
``dim_persons`` work can adopt without re-keying this table. President's
Rule intervals carry ``person_slug IS NULL`` AND ``person_name IS NULL``
— the office is held by no person during such intervals, the schema
must say so honestly.

Rejected designs (do NOT re-propose):
    1. Mint ``person_id`` from a UUID or autoincrement integer. Loses
       referential transparency — re-running the seed would change
       every holding row's person_id. ``slugify(cm_name)`` is the
       cheapest deterministic identity per Plan §0e.5 MVP rules.
    2. Emit ``person_name = "President's Rule"`` instead of NULL for
       presidents_rule intervals. Conflates "no person holds the
       office" with "this person holds the office". NULL is the
       honest signal; the renderer composes the "President's Rule"
       caption from ``regime``, not from a synthetic person_name.
    3. Embed the source citation columns inline on each holdings row
       (producer/title/vintage). Re-creates the per-shard provenance
       smear CLAUDE.md §12 explicitly forbids — sources is a TABLE,
       not a per-row array. Holdings carry ``source_id`` only.
    4. Have this seed OVERWRITE ``sources.parquet`` rather than upsert.
       Would wipe the 55+ existing ECI envelope-derived source rows
       on every re-run. The canonical singleton-ledger contract
       requires accumulation, not replacement.
    5. Materialise one office row per regime (separate office_id for
       "elected-CM" vs "presidents_rule-Governor"). The OFFICE is the
       CM seat in both cases; the regime difference is captured on the
       holding row, not by inventing parallel offices.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.citation import derive_source_id

DIM_OFFICES_ROW_SCHEMA_VERSION = "1.0"
GOVERNMENTS_OFFICE_HOLDINGS_ROW_SCHEMA_VERSION = "1.0"

Regime = Literal["elected", "presidents_rule", "governors_rule", "interim"]


# ----------------------------------------------------------------------
# Input shapes
# ----------------------------------------------------------------------


class _SourceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    fetched_at: str
    name: str | None = None
    authority: str | None = None


class _TermReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    note: str | None = None


class _Term(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: str  # ISO date
    end: str | None = None
    regime: Regime
    party_code: str | None = None
    alliance: str | None = None
    cm_name: str | None = None
    notes: str | None = None
    references: list[_TermReference] | None = None


class _CmTermsFile(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    state: str = Field(pattern=r"^[SU]\d{2}$")
    sources: list[_SourceCitation]
    terms: list[_Term]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_WIKI_LIST_RE = re.compile(r"wikipedia\.org/wiki/List_of_(chief_ministers|.*ministers)", re.IGNORECASE)


def _slugify_person(name: str) -> str:
    """Lowercase, hyphenated identifier for a person.

    ``"M. Karunanidhi"`` -> ``"m-karunanidhi"``; ``"M.G. Ramachandran"``
    -> ``"m-g-ramachandran"``. Forward-compatible with a future
    ``dim_persons.parquet`` whose primary key uses the same convention.
    """
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def _pick_wiki_source(file: _CmTermsFile) -> _SourceCitation:
    """Return the Wikipedia 'List of Chief Ministers of <state>' source.

    Scans file-level ``sources[]`` for a Wikipedia list-of-CMs URL.
    Falls back to the first source if no match is found (defensive —
    every shipping cm_terms.json today does have a wiki list URL).
    """
    for s in file.sources:
        if _WIKI_LIST_RE.search(s.url):
            return s
    return file.sources[0]


def _load_state_display_names(entities_json: Path) -> dict[str, str]:
    """Return ``{state_code: display_name}`` from entities.json.

    Used to compose ``office.label`` and the Wikipedia source ``title``
    without hardcoding state names inside this module.
    """
    payload = json.loads(entities_json.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for row in payload["entities"]:
        if row["entity_type"] in {"state", "ut"}:
            # entity_id "IN-S22" -> state_code "S22"
            state_code = row["entity_id"].split("-")[1]
            out[state_code] = row["display_name"]
    return out


# ----------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------


def compile_to_parquet(
    cm_terms_files: Iterable[Path],
    entities_json: Path,
    sources_parquet: Path,
    dim_offices_out: Path,
    holdings_out: Path,
) -> tuple[int, int]:
    """Read all inputs, emit dim_offices + holdings, UPSERT sources.

    Args:
        cm_terms_files: paths to ``cm_terms.json`` files (one per state).
        entities_json: path to ``datasets/taxonomy/entities.json`` for
            state display-name lookup.
        sources_parquet: path to ``datasets/taxonomy/sources.parquet``;
            opened, augmented with 1 Wikipedia citation per state file,
            written back. Idempotent across re-runs.
        dim_offices_out: output path for ``dim_offices.parquet``.
        holdings_out: output path for
            ``governments_office_holdings.parquet``.

    Returns:
        ``(office_count, holdings_count)`` for orchestrator logging.
    """
    state_names = _load_state_display_names(Path(entities_json))

    office_rows: list[tuple] = []
    holding_rows: list[tuple] = []
    new_sources: dict[str, tuple] = {}  # source_id -> source row tuple

    for cm_path in cm_terms_files:
        cm_path = Path(cm_path)
        if not cm_path.is_file():
            continue
        raw = json.loads(cm_path.read_text(encoding="utf-8"))
        for k in ("$schema", "$schema_version", "$comment"):
            raw.pop(k, None)
        cm = _CmTermsFile.model_validate(raw)
        state_code = cm.state
        if state_code not in state_names:
            raise ValueError(
                f"{cm_path.as_posix()}: state {state_code!r} not in entities.json"
            )
        state_display = state_names[state_code]

        wiki = _pick_wiki_source(cm)
        producer = "Wikipedia"
        title = f"List of Chief Ministers of {state_display}"
        vintage = ""
        source_id = derive_source_id(producer, title, vintage)
        new_sources[source_id] = (
            source_id,
            producer,
            title,
            vintage,
            "CC-BY-4.0",
            "silver",
            False,  # is_issuing_authority
            "transcribed",
            wiki.url,
            None,  # citation_full
            None,  # notes
        )

        office_id = f"IN-{state_code}-CM"
        entity_id = f"IN-{state_code}"
        office_rows.append(
            (
                office_id,
                entity_id,
                "CM",
                f"Chief Minister of {state_display}",
                source_id,
            )
        )

        for term in cm.terms:
            person_slug = _slugify_person(term.cm_name) if term.cm_name else None
            holding_rows.append(
                (
                    office_id,
                    term.start,
                    term.end,
                    term.regime,
                    person_slug,
                    term.cm_name,
                    term.party_code,
                    term.alliance,
                    term.notes,
                    source_id,
                )
            )

    # Dedupe office_ids and assert per-state uniqueness
    seen_offices: set[str] = set()
    for row in office_rows:
        if row[0] in seen_offices:
            raise ValueError(f"duplicate office_id {row[0]!r}")
        seen_offices.add(row[0])

    office_rows.sort(key=lambda r: r[0])
    holding_rows.sort(key=lambda r: (r[0], r[1]))

    con = duckdb.connect(":memory:")
    try:
        # ----- dim_offices ---------------------------------------------
        con.execute(
            """
            CREATE TABLE dim_offices (
                office_id VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                label VARCHAR NOT NULL,
                source_id VARCHAR NOT NULL
            )
            """
        )
        con.executemany(
            "INSERT INTO dim_offices VALUES (?, ?, ?, ?, ?)",
            office_rows,
        )
        Path(dim_offices_out).parent.mkdir(parents=True, exist_ok=True)
        con.execute(
            f"""
            COPY (
                SELECT * FROM dim_offices ORDER BY office_id
            ) TO '{Path(dim_offices_out).as_posix()}' (FORMAT PARQUET)
            """
        )

        # ----- holdings ------------------------------------------------
        con.execute(
            """
            CREATE TABLE holdings (
                office_id VARCHAR NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                regime VARCHAR NOT NULL,
                person_slug VARCHAR,
                person_name VARCHAR,
                party_eci_code VARCHAR,
                alliance VARCHAR,
                notes VARCHAR,
                source_id VARCHAR NOT NULL
            )
            """
        )
        con.executemany(
            "INSERT INTO holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            holding_rows,
        )
        Path(holdings_out).parent.mkdir(parents=True, exist_ok=True)
        con.execute(
            f"""
            COPY (
                SELECT * FROM holdings ORDER BY office_id, start_date
            ) TO '{Path(holdings_out).as_posix()}' (FORMAT PARQUET)
            """
        )

        # ----- sources upsert ------------------------------------------
        # Read existing rows, drop any whose source_id we're about to
        # write (idempotency — re-running yields byte-identical output),
        # union with new rows, sort, write back.
        existing_path = Path(sources_parquet)
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        con.execute(
            """
            CREATE TABLE sources (
                source_id VARCHAR NOT NULL,
                producer VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                vintage VARCHAR NOT NULL,
                license VARCHAR NOT NULL,
                confidence_tier VARCHAR NOT NULL,
                is_issuing_authority BOOLEAN NOT NULL,
                verification_method VARCHAR NOT NULL,
                url_main VARCHAR,
                citation_full VARCHAR,
                notes VARCHAR
            )
            """
        )
        if existing_path.is_file():
            con.execute(
                f"INSERT INTO sources SELECT * FROM read_parquet('{existing_path.as_posix()}')"
            )
        # UPSERT — delete any rows with source_ids we're about to write,
        # then insert the new versions. Keeps re-runs byte-identical.
        if new_sources:
            sid_list = ",".join(f"'{sid}'" for sid in new_sources)
            con.execute(f"DELETE FROM sources WHERE source_id IN ({sid_list})")
            con.executemany(
                "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                list(new_sources.values()),
            )
        con.execute(
            f"""
            COPY (
                SELECT * FROM sources ORDER BY source_id
            ) TO '{existing_path.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()

    return len(office_rows), len(holding_rows)
