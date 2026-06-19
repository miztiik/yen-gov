"""Electoral observation + source CSV write seam (ingest rip-replace Row 8).

Replaces the retired ``BatchEnvelope`` -> ``write_batch`` path for the three
ECI election adapters (``eci_ls``, ``eci_ae_panel``,
``pipeline.canonical_eci_backfill``). Background: after X1a-fu2-D the parquet
writer's ``_emit_observations`` short-circuits ``family == "elections"`` and
returns 0, so the adapters computed observation facts but never wrote them to
disk; the per-state ``election_results.csv`` files were a one-time transcode.
This module wires the adapters' observation rows back to the canonical store.

Two write surfaces:

- :func:`write_electoral_results` transcodes observation rows 1:1 to the
  per-state long-format CSV
  ``datasets/data/datapoints/electoral/<state_slug>_election_results.csv``
  (file_class ``datasets/data/datapoints/electoral/*.csv``; the 9-column
  shape is exactly an observation row minus ``observation_id``). It UPSERTs on
  the logical key ``(entity_id, period_label, indicator_id)`` so re-running one
  event never drops the AC / other-event / other-grain rows already in a
  state's file. Mirrors the old ``write_batch`` UPSERT semantics.
- :func:`upsert_source_csv` additively appends citation rows to the 5-field
  ledger ``datasets/data/entities/source.csv`` (``source_id`` is derived by the
  adapter via ``canonical.citation.derive_source_id`` and never hand-authored).
  Mirrors the blessed append pattern in
  ``canonical.derived.event_summary._ensure_mart_source`` (preserves existing
  row order; only appends source_ids not already present).

Both inputs are duck-typed (the module deliberately does NOT import the
``envelope`` models, which Row 9 deletes): observation rows expose
``entity_id / year / period_label / period_seq / indicator_id / value_numeric /
value_text / source_id / derivation``; source rows expose ``source_id /
producer / title / vintage / url_main``.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.csv_columns import ColumnContract, load_columns
from yen_gov.canonical.csv_writer import write_csv

__all__ = [
    "ELECTORAL_FILE_CLASS",
    "ElectoralBatch",
    "observation_row_to_csv",
    "state_slug_for_entity_id",
    "upsert_source_csv",
    "write_electoral_results",
]

#: file_class glob into ``columns.json`` for the per-state election-results CSV.
ELECTORAL_FILE_CLASS = "datasets/data/datapoints/electoral/*.csv"

#: declared column order of the electoral datapoints file class (observation
#: row minus ``observation_id``). The logical UPSERT key is the composite PK
#: ``(entity_id, period_label, indicator_id)``.
_ELECTORAL_COLUMNS = (
    "entity_id",
    "year",
    "period_label",
    "period_seq",
    "indicator_id",
    "value_numeric",
    "value_text",
    "source_id",
    "derivation",
)
_LOGICAL_KEY = ("entity_id", "period_label", "indicator_id")

_SOURCE_CSV_REL = ("data", "entities", "source.csv")
_ELECTORAL_DIR_REL = ("data", "datapoints", "electoral")

# entity_id -> ECI st_code extraction. PC ids carry the state in segment four
# (``IN-PC-<delim>-<state>-<pc_no>[...]``); every other electoral id (AC seat,
# candidate, state/party rollup) carries it in segment two
# (``IN-<state>-...``). Mirrors writer.py::_STATE_PARTITION_SQL so the slug
# partition matches the existing on-disk per-state files exactly.
_PC_STATE_RE = re.compile(r"^IN-PC-\d+-([SU]\d{2})")
_GENERIC_STATE_RE = re.compile(r"^[A-Z]+-([A-Z0-9]+)")


@dataclass(frozen=True)
class ElectoralBatch:
    """Adapter -> CSV-write contract; the lightweight successor to
    ``BatchEnvelope`` for the three ECI election adapters.

    Only :attr:`observation_rows` and :attr:`source_rows` reach disk (via
    :func:`write_electoral_results` + :func:`upsert_source_csv`). The dim-row
    fields are retained so the adapters' builders + their existing tests keep
    the exact attribute surface the ``BatchEnvelope`` had; they are NOT
    written to disk (the dim parquets retired in X1b / X1a-fu2, and the legacy
    ``dim_party_alliances.parquet`` re-emit is dropped here - its data SoT is
    ``datasets/data/entities/party_alliances.csv``).
    """

    observation_rows: list[Any] = field(default_factory=list)
    source_rows: list[Any] = field(default_factory=list)
    pc_dim_rows: list[Any] = field(default_factory=list)
    ac_dim_rows: list[Any] = field(default_factory=list)
    person_dim_rows: list[Any] = field(default_factory=list)
    candidacy_rows: list[Any] = field(default_factory=list)
    party_dim_rows: list[Any] = field(default_factory=list)
    party_alliance_dim_rows: list[Any] = field(default_factory=list)


def state_slug_for_entity_id(entity_id: str) -> str:
    """Return the LGD-name state slug (e.g. ``tamil-nadu``) for an electoral
    ``entity_id``.

    Raises:
        ValueError: the entity_id does not start with a parseable ECI state
            segment, or the extracted st_code is not a known ECI code. The
            partition is fail-loud (never best-guess) per CLAUDE.md.
    """
    pc = _PC_STATE_RE.match(entity_id)
    if pc is not None:
        st_code = pc.group(1)
    elif entity_id == "IN":
        # Country-grain row (none today for elections); preserve the legacy
        # writer.py mapping IN -> "in" defensively.
        return "in"
    else:
        m = _GENERIC_STATE_RE.match(entity_id)
        if m is None:
            raise ValueError(
                f"cannot derive ECI state code from electoral entity_id {entity_id!r}"
            )
        st_code = m.group(1)
    try:
        return eci_to_lgd_slug(st_code)
    except KeyError as err:
        raise ValueError(
            f"electoral entity_id {entity_id!r} yielded unknown ECI st_code "
            f"{st_code!r}; cannot route to a per-state election_results.csv"
        ) from err


def observation_row_to_csv(row: Any) -> dict[str, Any]:
    """Project an observation row to the 9-column electoral CSV dict.

    ``observation_id`` is intentionally dropped - the per-state file class
    does not carry it (the logical key is the composite PK). value_numeric /
    value_text keep their ``None`` so ``write_csv`` emits an empty field.
    """
    return {
        "entity_id": row.entity_id,
        "year": row.year,
        "period_label": row.period_label,
        "period_seq": row.period_seq,
        "indicator_id": row.indicator_id,
        "value_numeric": row.value_numeric,
        "value_text": row.value_text,
        "source_id": row.source_id,
        "derivation": row.derivation,
    }


def write_electoral_results(
    *,
    datasets_root: Path,
    observation_rows: list[Any],
    contract: ColumnContract | None = None,
) -> dict[str, Path]:
    """UPSERT observation rows into the per-state election-results CSVs.

    Args:
        datasets_root: the ``datasets/`` directory (tests pass a tmp_path).
        observation_rows: observation rows the adapter built. Deduped on the
            logical key ``(entity_id, period_label, indicator_id)`` last-wins,
            mirroring the old ``write_batch`` envelope-internal dedupe.
        contract: optional pre-loaded ``ColumnContract`` (tests / repeated
            calls); loaded from ``columns.json`` when omitted.

    Returns:
        ``{state_slug: path}`` for every per-state CSV touched.

    Each state's existing CSV is read first and merged (new rows win on a
    logical-key collision) so pre-existing AC / other-event / other-grain rows
    are preserved (no-drop). Empty ``observation_rows`` is a no-op.
    """
    resolved = contract if contract is not None else load_columns()

    # Dedupe envelope-internal collisions last-wins (an observation_id is the
    # hash of the logical key, so this is what write_batch did under the hood).
    deduped: dict[tuple[str, str, str], Any] = {}
    for row in observation_rows:
        deduped[(row.entity_id, row.period_label, row.indicator_id)] = row

    by_slug: dict[str, list[Any]] = defaultdict(list)
    for row in deduped.values():
        by_slug[state_slug_for_entity_id(row.entity_id)].append(row)

    electoral_dir = datasets_root.joinpath(*_ELECTORAL_DIR_REL)
    written: dict[str, Path] = {}
    for slug, rows in by_slug.items():
        path = electoral_dir / f"{slug}_election_results.csv"
        merged = _read_existing_electoral(path)
        for row in rows:
            csv_row = observation_row_to_csv(row)
            merged[
                (csv_row["entity_id"], csv_row["period_label"], csv_row["indicator_id"])
            ] = csv_row
        write_csv(
            path=path,
            file_class=ELECTORAL_FILE_CLASS,
            rows=list(merged.values()),
            contract=resolved,
        )
        written[slug] = path
    return written


def _read_existing_electoral(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Read an existing per-state election-results CSV keyed by logical key.

    Values are raw-string dicts (empty field -> ``None``); ``write_csv`` coerces
    them back to the declared dtypes on write, so the round-trip is loss-free.
    """
    if not path.is_file():
        return {}
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            row = {col: (raw.get(col) if raw.get(col) != "" else None) for col in _ELECTORAL_COLUMNS}
            out[
                (raw["entity_id"], raw["period_label"], raw["indicator_id"])
            ] = row
    return out


def upsert_source_csv(*, datasets_root: Path, source_rows: list[Any]) -> Path:
    """Additively append citation rows to the 5-field ``source.csv`` ledger.

    Args:
        datasets_root: the ``datasets/`` directory.
        source_rows: source rows the adapter built (each exposes
            ``source_id / producer / title / vintage / url_main``). The
            ``source_id`` is already derived via ``derive_source_id`` upstream.

    Returns:
        The path to ``datasets/data/entities/source.csv``.

    Additive + idempotent: existing rows keep their order; a ``source_id``
    already present is left untouched (a citation row is identity-keyed on the
    ``(producer, title, vintage)`` hash, so a present id is by construction the
    same citation). Mirrors ``event_summary._ensure_mart_source``.

    Raises:
        FileNotFoundError: the committed ``source.csv`` ledger is missing -
            it is a seeded FK target, not created from scratch by an adapter.
    """
    path = datasets_root.joinpath(*_SOURCE_CSV_REL)
    if not path.is_file():
        raise FileNotFoundError(
            f"source.csv citation ledger not found at {path.as_posix()}; "
            "seed it before running an electoral ingest"
        )
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    present = {r.get("source_id") for r in all_rows}
    appended = False
    # Sort by source_id so a multi-source ingest appends deterministically.
    for sr in sorted(source_rows, key=lambda s: s.source_id):
        if sr.source_id in present:
            continue
        present.add(sr.source_id)
        new_row = {fn: "" for fn in fieldnames}
        new_row["source_id"] = sr.source_id
        if "producer" in fieldnames:
            new_row["producer"] = sr.producer
        if "title" in fieldnames:
            new_row["title"] = sr.title
        if "vintage" in fieldnames:
            new_row["vintage"] = sr.vintage
        if "url" in fieldnames:
            new_row["url"] = getattr(sr, "url_main", None) or ""
        all_rows.append(new_row)
        appended = True

    if appended:
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(all_rows)
    return path
