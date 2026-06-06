"""Compile consolidated office_holdings.json to dim_offices + office_holdings.

§8.3 Python-compiles-to-Parquet seam. Replaces ``cm_terms_seed.py`` as
the writer of:

- ``datasets/governments/dim_offices.parquet`` -- one row per office
    identity present in the authored holdings.
- ``datasets/governments/governments_office_holdings.parquet`` -- one
    row per office tenure or vacancy/regime interval.

Post-B3-pt2 (2026-06-06): the legacy side-effect of UPSERTing the
office citation rows into ``datasets/taxonomy/sources.parquet`` was
removed. X1b retired ``sources.parquet`` (PR #814); the citation ledger
is now ``datasets/data/entities/source.csv`` and the 31 Wikipedia "List
of Chief Ministers of <state>" rows + the per-office citation-group rows
referenced by ``office_holdings.json`` are seeded there once via the
B2a/source_csv path. The in-process FK gate inside ``compile_to_parquet``
(every holding row must resolve to either an ``office_citations`` URL
or a ``citation_groups`` entry) still catches a missing citation row
before any bytes hit disk; cross-format FK closure against source.csv
is enforced downstream by the B1 fk-validator gate.

G.1.c role (2026-05-22, consolidation): the 31 per-state cm_terms.json
files were retired in favour of one consolidated
``datasets/taxonomy/office_holdings.json`` per Hans + Max + Fowler
review. Office IDENTITY still reads from
``datasets/taxonomy/entities.parquet WHERE entity_type='office_bearer'``
(unchanged from G.1.b). Tenure facts now come from one file's
``holdings[]`` array; per-office url_main values come from the same
file's ``office_citations`` map. Parquet output is byte-identical to
the pre-G.1.c shape (verified by SHA256 dance in the G.1.c PR body).

Strangler-fig: PR 3 of 3 retiring the per-state cm_terms.json files.
G.1.a (PR #89) lifted office_bearer rows into entities.parquet;
G.1.b (PR #90) switched this seed's office-identity reader to those
rows; G.1.c (this PR) consolidates tenure JSON + deletes cm_terms_seed.py
+ retires datasets/schemas/state_government.schema.json. See
``TODO/20260522-g1-cm-terms-retirement-handover.md``.

Person identity model: unchanged from cm_terms_seed.py. Carries
``person_slug`` (deterministic lowercase hyphenated derivation from
``person_name``) plus a verbatim ``person_name`` text column. No
``dim_persons.parquet`` is created here -- full person identity (with
TCPD-style disambiguation across CM / candidate / MP / MLA appearances)
is the §0e.5 follow-up. President's Rule intervals carry
``person_slug IS NULL`` AND ``person_name IS NULL`` -- the office is
held by no person during such intervals, the schema must say so honestly.

v1.1 extension (2026-05-25): constitutional national offices use explicit
``citation_groups`` authored in office_holdings.json instead of the legacy
CM-only ``office_citations`` URL map. This keeps TCPD as seed/QA only;
citizen-facing provenance for President / Vice President rows comes from
official Government of India source groups.

Rejected designs (do NOT re-propose; full archive in
TODO/20260522-g1-cm-terms-retirement-handover.md §G.1.c):
    1. Keep per-state cm_terms.json + add a thin index layer. Doubles
       the operator's edit surface (32 files instead of 1). Loses
       Hans's "single git history for all CM provenance" win.
    2. Deterministic Wikipedia URL template
       ``f"https://en.wikipedia.org/wiki/List_of_chief_ministers_of_{state.replace(' ', '_')}"``.
       S19 Punjab requires a ``Punjab,_India`` disambiguation suffix;
       any template would mis-handle this and any future irregularly
       named office (e.g. UT-only offices with disambiguation). The
       ``office_citations`` map in office_holdings.json is the typed
       fix.
    3. Add a ``role`` column to office_holdings.json holdings[] rows.
       Role is encoded in office_id grammar (IN-S22-CM, IN-PM, ...);
       a separate column would let the two drift. Premature
       generalisation per Fowler review -- earned when 2nd concrete
       role lands.
    4. Emit one office_citations row per (office_id, citation_role)
       to anticipate per-role citation overrides. YAGNI -- today
       every office has exactly one citation (the Wikipedia list).
       When DCM / Gov / PM land, the per-role template + this map
       handles them. Schema-evolve later if needed.
    5. Have this seed OVERWRITE ``sources.parquet`` rather than upsert.
       Moot post-B3-pt2 (2026-06-06) -- this seed no longer writes
       to ``sources.parquet`` at all. The citation rows live in
       ``datasets/data/entities/source.csv`` seeded once via the
       B2a/source_csv path; the canonical singleton-ledger contract
       still requires accumulation (B2a uses CSV-row UPSERT keyed on
       source_id, not overwrite).
    6. Materialise one office row per regime (separate office_id for
       "elected-CM" vs "presidents_rule-Governor"). The OFFICE is the
       CM seat in both cases; the regime difference is captured on the
       holding row, not by inventing parallel offices. Unchanged from
       cm_terms_seed.py rejected #5.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.citation import derive_source_id

DIM_OFFICES_ROW_SCHEMA_VERSION = "1.0"
GOVERNMENTS_OFFICE_HOLDINGS_ROW_SCHEMA_VERSION = "1.1"

Regime = Literal["elected", "presidents_rule", "governors_rule", "interim"]
SelectionMethod = Literal[
    "legislature_confidence",
    "electoral_college",
    "appointed_by_president",
    "constitutional_succession",
]
TenureStatus = Literal["substantive", "acting", "additional_charge"]
License = Literal[
    "OGL-IN-1.0",
    "CC-BY-4.0",
    "CC0-1.0",
    "public-domain",
    "unknown-public",
    "internal",
]
ConfidenceTier = Literal["gold", "silver", "bronze"]
VerificationMethod = Literal[
    "live-fetch", "archived-snapshot", "transcribed", "editorial"
]


# ----------------------------------------------------------------------
# Input shapes
# ----------------------------------------------------------------------


class _OfficeCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url_main: str


class _CitationGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    producer: str
    title: str
    vintage: str
    license: License
    confidence_tier: ConfidenceTier
    is_issuing_authority: bool
    verification_method: VerificationMethod
    url_main: str | None = None
    citation_full: str | None = None
    notes: str | None = None


class _HoldingReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    note: str | None = None


class _OfficeHolding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    office_id: str = Field(pattern=r"^IN(-[A-Z0-9]+)+$")
    start_date: str  # ISO date
    end_date: str | None = None
    regime: Regime | None
    citation_group_id: str | None = None
    selection_method: SelectionMethod | None = None
    tenure_status: TenureStatus | None = None
    person_name: str | None = None
    party_eci_code: str | None = None
    alliance: str | None = None
    notes: str | None = None
    references: list[_HoldingReference] | None = None


class _OfficeHoldingsFile(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    office_citations: dict[str, _OfficeCitation]
    citation_groups: dict[str, _CitationGroup] = Field(default_factory=dict)
    holdings: list[_OfficeHolding]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify_person(name: str) -> str:
    """Lowercase, hyphenated identifier for a person.

    ``"M. Karunanidhi"`` -> ``"m-karunanidhi"``; ``"M.G. Ramachandran"``
    -> ``"m-g-ramachandran"``. Forward-compatible with a future
    ``dim_persons.parquet`` whose primary key uses the same convention.
    """
    return _SLUG_RE.sub("-", name.lower()).strip("-")


class _OfficeBearerIdentity(BaseModel):
    """Office-identity row read from ``entities.parquet``.

    Mirrors the four columns dim_offices needs from each office_bearer
    entity: office_id (= entity_id), entity_id of the parent entity
    (= parent_entity_id), role (= entity_code, e.g. ``CM``), and label
    (= display_name). The source_id citation comes from
    ``office_citations`` -- not from this row -- because that citation
    describes the historical-tenures upstream, not the existence of the
    office.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    office_id: str
    parent_entity_id: str
    role: str
    label: str


def _load_office_bearer_identities(
    entities_parquet: Path,
) -> dict[str, _OfficeBearerIdentity]:
    """Return ``{office_id: _OfficeBearerIdentity}`` for all offices.

    Reads ``entity_type='office_bearer'`` rows from entities.parquet
    and keys them by ``entity_id`` (= office_id, e.g. ``IN-S22-CM``).
    Returns office_id as key (not state_code) because the long-form
    holdings carry office_id directly -- no state-code derivation needed.
    """
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"""
            SELECT entity_id, parent_entity_id, entity_code, display_name
            FROM read_parquet('{Path(entities_parquet).as_posix()}')
            WHERE entity_type = 'office_bearer'
            ORDER BY entity_id
            """
        ).fetchall()
    finally:
        con.close()
    out: dict[str, _OfficeBearerIdentity] = {}
    for entity_id, parent_entity_id, entity_code, display_name in rows:
        if parent_entity_id is None:
            raise ValueError(
                f"office_bearer {entity_id!r} has NULL parent_entity_id; expected IN-<state_code>"
            )
        if entity_id in out:
            raise ValueError(
                f"two office_bearer rows with entity_id={entity_id!r}"
            )
        out[entity_id] = _OfficeBearerIdentity(
            office_id=entity_id,
            parent_entity_id=parent_entity_id,
            role=entity_code,
            label=display_name,
        )
    return out


def _state_display_from_label(label: str, role: str = "CM") -> str:
    """Recover the state display name from a CM office label.

    ``"Chief Minister of Tamil Nadu"`` -> ``"Tamil Nadu"``. Used to
    compose the Wikipedia source ``title`` ("List of Chief Ministers of
    <state>") without hardcoding state names inside this module. Mirrors
    the inverse of the entity_label format set in entities.json by
    G.1.a; if the label format ever changes, this helper changes with
    it (single source of truth).
    """
    prefix = "Chief Minister of " if role == "CM" else f"{role} of "
    if not label.startswith(prefix):
        raise ValueError(
            f"office label {label!r} does not start with expected prefix {prefix!r}"
        )
    return label[len(prefix):]


# ----------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------


def compile_to_parquet(
    office_holdings_json: Path,
    entities_parquet: Path,
    dim_offices_out: Path,
    holdings_out: Path,
) -> tuple[int, int]:
    """Read the consolidated holdings file, emit dim_offices + holdings.

    Args:
        office_holdings_json: path to ``datasets/taxonomy/office_holdings.json``.
            Provides tenure rows in ``holdings[]`` + per-office url_main
            in ``office_citations[]``.
        entities_parquet: path to ``datasets/taxonomy/entities.parquet``;
            office IDENTITY (the 31 dim_offices rows for CM today) is
            read from ``WHERE entity_type='office_bearer' AND
            entity_code='CM'``. Unchanged from G.1.b.
        dim_offices_out: output path for ``dim_offices.parquet``.
        holdings_out: output path for
            ``governments_office_holdings.parquet``.

    Returns:
        ``(office_count, holdings_count)`` for orchestrator logging.

    Post-B3-pt2 (2026-06-06): the ``sources_parquet`` arg was removed.
    The Wikipedia "List of Chief Ministers of <state>" citation rows
    (31 today) and the per-office ``citation_groups`` rows live in
    ``datasets/data/entities/source.csv`` seeded once via the
    B2a/source_csv path; this seed no longer UPSERTs them. The
    in-process FK gate inside this function (every holdings row must
    resolve to either an ``office_citations`` URL or a
    ``citation_groups`` entry) still catches a missing citation row
    before any bytes hit disk; cross-format FK closure against
    source.csv is enforced downstream by the B1 fk-validator gate.
    """
    office_identities = _load_office_bearer_identities(Path(entities_parquet))

    raw = json.loads(Path(office_holdings_json).read_text(encoding="utf-8"))
    for k in ("$schema", "$schema_version", "$comment"):
        raw.pop(k, None)
    file = _OfficeHoldingsFile.model_validate(raw)

    # Per-office legacy citation rows -- one source_id per CM office_id
    # present in office_citations. New non-CM rows use citation_groups
    # instead. The source rows themselves live in source.csv (B2a era);
    # this loop only derives the deterministic source_id for FK closure.
    # The ``citation.url_main`` field is validated for non-emptiness by
    # the Pydantic ``_OfficeCitation`` model at load time; this seeder
    # no longer reads it because the source.csv row carries the URL.
    office_source_ids: dict[str, str] = {}  # office_id -> source_id

    for office_id, _citation in sorted(file.office_citations.items()):
        identity = office_identities.get(office_id)
        if identity is None:
            raise ValueError(
                f"office_citations has {office_id!r} but entities.parquet has "
                f"no office_bearer entity with entity_id={office_id!r}. Did "
                f"G.1.a lift this state's office?"
            )
        state_display = _state_display_from_label(identity.label, role=identity.role)
        producer = "Wikipedia"
        if identity.role == "CM":
            title = f"List of Chief Ministers of {state_display}"
        else:
            raise ValueError(
                f"office {office_id!r} role={identity.role!r}: no citation "
                f"template in legacy office_citations. Use citation_groups "
                f"for non-CM office holdings."
            )
        vintage = "operator-snapshot-2026-05"  # Wikipedia pages have no publisher vintage; per ADR-0042 use operator-snapshot anchor
        office_source_ids[office_id] = derive_source_id(producer, title, vintage)

    citation_group_source_ids: dict[str, str] = {}
    for group_id, group in sorted(file.citation_groups.items()):
        citation_group_source_ids[group_id] = derive_source_id(
            group.producer, group.title, group.vintage
        )

    # Holdings rows -- look up source_id by office_id.
    holding_rows: list[tuple] = []
    office_dim_source_ids: dict[str, str] = {}
    for holding in file.holdings:
        identity = office_identities.get(holding.office_id)
        if identity is None:
            raise ValueError(
                f"holdings row office_id={holding.office_id!r} has no "
                f"office_bearer row in entities.parquet"
            )
        if holding.citation_group_id is not None:
            source_id = citation_group_source_ids.get(holding.citation_group_id)
            if source_id is None:
                raise ValueError(
                    f"holdings row office_id={holding.office_id!r} references "
                    f"citation_group_id={holding.citation_group_id!r}, but "
                    f"citation_groups has no such key"
                )
        else:
            source_id = office_source_ids.get(holding.office_id)
        if source_id is None:
            raise ValueError(
                f"holdings row office_id={holding.office_id!r} has no entry in "
                f"office_citations and no citation_group_id; non-legacy office "
                f"holdings must cite an explicit official citation group."
            )
        office_dim_source_ids.setdefault(identity.office_id, source_id)
        person_slug = _slugify_person(holding.person_name) if holding.person_name else None
        holding_rows.append(
            (
                holding.office_id,
                holding.start_date,
                holding.end_date,
                holding.regime,
                holding.selection_method,
                holding.tenure_status,
                person_slug,
                holding.person_name,
                holding.party_eci_code,
                holding.alliance,
                holding.notes,
                source_id,
            )
        )

    # Dedupe office_ids and assert per-state uniqueness
    office_rows: list[tuple] = []
    for office_id, source_id in sorted(office_dim_source_ids.items()):
        identity = office_identities[office_id]
        office_rows.append(
            (
                identity.office_id,
                identity.parent_entity_id,
                identity.role,
                identity.label,
                source_id,
            )
        )

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
                regime VARCHAR,
                selection_method VARCHAR,
                tenure_status VARCHAR,
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
            "INSERT INTO holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
    finally:
        con.close()

    return len(office_rows), len(holding_rows)
