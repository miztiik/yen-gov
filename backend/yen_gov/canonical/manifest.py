"""Emit ``datasets/manifest.json`` - the control-plane manifest the static
frontend reads at startup.

:func:`emit_manifest` is the SOLE producer of ``manifest.json``. It is a pure
stamp: NO DuckDB, NO Parquet scan, NO directory walk. Every canonical Parquet
table retired (CLAUDE.md X1a-fu2), so ``tables`` is ALWAYS empty and the
manifest carries only the version stamp plus the append-only ``deprecations``
ledger. This replaces the dead Parquet-scanning regen body that lived in
``canonical/writer.py`` (``_regenerate_manifest``); that scan + its DuckDB
table-describe helpers + ``write_batch`` are torn down wholesale in a later
rip row.

``generated_at`` is a wall-clock stamp - permitted here by the CLAUDE.md
section 11 control-plane carve-out (the manifest is read at startup by
``isCompatibleSchemaVersion`` in the frontend; it is NOT observation
provenance, so the ``datetime.now`` ban does not apply).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from yen_gov.core.schema_registry import schema_id, schema_version

log = logging.getLogger(__name__)

_MANIFEST_SCHEMA = "manifest.schema.json"

# ``manifest.json`` lives at ``datasets/manifest.json``; its schema lives at
# ``datasets/schemas/<file>``. ``schema_id`` returns the schema's own ``$id``
# (``./manifest.schema.json``, relative to ``datasets/schemas/``), so prefix
# the ``schemas/`` directory to get the manifest-relative reference. Derived
# from the registry rather than hand-typed so the ref tracks the schema file.
_SCHEMA_REF = f"./schemas/{Path(schema_id(_MANIFEST_SCHEMA)).name}"


# Append-only ledger of dataset path renames / relocations stamped into
# ``datasets/manifest.json`` under the ``deprecations`` array (introduced in
# ``manifest.schema.json`` v1.2). Surfaces the legacy URL so archived embeds,
# cached fetches, and downstream tooling can resolve the canonical successor
# programmatically (the frontend loader also emits a one-shot ``console.warn``
# when it sees a legacy marker).
#
# Each entry: ``old_path`` (POSIX relative under ``datasets/``), ``new_path``
# (the canonical successor), ``deprecated_at`` (ISO 8601 date). Add a row
# whenever a citizen-facing artifact moves; never delete a row (citizen URLs
# that linked to the old path keep resolving as long as the successor entry
# stays here). See ``datasets/CHANGELOG.md`` for the human-readable narrative.
#
# This ledger moved here from ``canonical/writer.py`` in the manifest-replace
# rip row so it survives the wholesale ``writer.py`` teardown.
_DEPRECATIONS: list[dict[str, str]] = [
    {
        "old_path": "elections/observations.parquet",
        "new_path": "elections/election_results.parquet",
        "deprecated_at": "2026-05-18",
    },
    {
        "old_path": "elections/dim_candidates.parquet",
        "new_path": "elections/dim_persons.parquet",
        "deprecated_at": "2026-05-23",
    },
    # X1b parquet-delete (2026-06-06, PR #814) - 9 reader-flipped parquets
    # whose deprecation rows previously lived only as hand-edits in
    # datasets/manifest.json and would have been clobbered by the next
    # manifest-regen run. Lifted into the source list during
    # X1a-fu2-C (2026-06-07) so the manifest is idempotent again.
    {
        "old_path": "elections/dim_parties.parquet",
        "new_path": "data/entities/parties.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "elections/dim_pcs.parquet",
        "new_path": "data/entities/electoral.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "elections/dim_persons.parquet",
        "new_path": "elections/assembly/candidacies.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "taxonomy/ac_crosswalk.parquet",
        "new_path": "data/entities/ac_crosswalk.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "taxonomy/persons.parquet",
        "new_path": "elections/assembly/candidacies.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "taxonomy/sources.parquet",
        "new_path": "data/entities/source.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "taxonomy/methodology_breaks.parquet",
        "new_path": "data/methodology_breaks.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "elections/dim_acs.parquet",
        "new_path": "data/entities/electoral.csv",
        "deprecated_at": "2026-06-06",
    },
    {
        "old_path": "elections/elections_candidacies.parquet",
        "new_path": "elections/assembly/candidacies.csv",
        "deprecated_at": "2026-06-06",
    },
    # X1a-fu2-C (2026-06-07) - dim_party_alliances parquet retired in the
    # same PR; CSV transcoded via canonical/party_alliances_csv.py.
    {
        "old_path": "elections/dim_party_alliances.parquet",
        "new_path": "data/entities/party_alliances.csv",
        "deprecated_at": "2026-06-07",
    },
    # X1a-fu2-D (2026-06-07) - elections/state=*/election_results.parquet
    # (36 shards, 1.79M rows) retired in a mechanical rip-and-replace. One
    # CSV per state under data/datapoints/electoral/<slug>_election_results.csv;
    # 9-column SELECT * mirroring the parquet contract (entity_id, year,
    # period_label, period_seq, indicator_id, value_numeric, value_text,
    # source_id, derivation). The 3 frontend readers (composition-bar
    # adapter, election-seats-trend, india-leading-parties) flipped to
    # inline read_csv with hand-built columns={...} clauses. old_path /
    # new_path below are the canonical-identity strings (the actual files
    # are per-state-slug); the schema's pattern rejects `*` in deprecation
    # paths so we cite the family-stem instead.
    {
        "old_path": "elections/election_results.parquet",
        "new_path": "data/datapoints/electoral/election_results.csv",
        "deprecated_at": "2026-06-07",
    },
    # G8 (2026-06-08) - datasets/reference/in/pincodes/pincode-directory.parquet
    # (165627 rows, 3.7 MB) retired as part of the mechanical
    # ``datasets/reference/`` reshape (plan-doc section 9 + section 21.2
    # "CSV everywhere, no parquet"). Transcoded in place via DuckDB
    # ``COPY (SELECT * FROM read_parquet(...)) TO ... (HEADER, DELIMITER ',')``;
    # post-move row count == pre-move row count (165627). The sole backend
    # reader (``ingest_pincode_polygons.py::_build_pincode_to_state_lookup``)
    # flipped to typed ``read_csv(columns={'pincode': 'VARCHAR', 'statename':
    # 'VARCHAR'}, ...)`` per plan-doc section 21.2 typed-read mandate. No
    # frontend reader exists (verified via grep). Writer rewrite (parquet
    # emit -> direct CSV emit + the 9 parquet-shaped tests in
    # test_ingest_pincode.py) deferred to a G8-followup PR to keep this
    # change mechanical.
    {
        "old_path": "reference/in/pincodes/pincode-directory.parquet",
        "new_path": "data/entities/pincode.csv",
        "deprecated_at": "2026-06-08",
    },
    # G8-finish (2026-06-08) - the six surviving members of the
    # ``datasets/reference/lgd/`` parsed-snapshot family relocate as part
    # of the FULL ``datasets/reference/`` tier retirement (plan-doc
    # section 9 ``reference/`` row + section 21.2 one-format CSV mandate).
    # The five CSV snapshot masters move into the canonical entities tier
    # at ``datasets/data/entities/lgd/``; the JSON parse-receipt becomes
    # operator state under ``datasets/_ops/``. Sole writer
    # (``tools/lgd/parse_lgd_export.py``) + the 3 backend canonical seeds
    # (``state_codes_csv.py``, ``electoral_csv_from_snapshot.py``,
    # ``electoral_district_membership_csv.py``) + 2 runners are repointed
    # in the same commit.
    {
        "old_path": "reference/lgd/states.csv",
        "new_path": "data/entities/lgd/states.csv",
        "deprecated_at": "2026-06-08",
    },
    {
        "old_path": "reference/lgd/districts.csv",
        "new_path": "data/entities/lgd/districts.csv",
        "deprecated_at": "2026-06-08",
    },
    {
        "old_path": "reference/lgd/subdistricts.csv",
        "new_path": "data/entities/lgd/subdistricts.csv",
        "deprecated_at": "2026-06-08",
    },
    {
        "old_path": "reference/lgd/constituencies.csv",
        "new_path": "data/entities/lgd/constituencies.csv",
        "deprecated_at": "2026-06-08",
    },
    {
        "old_path": "reference/lgd/constituency_district_membership.csv",
        "new_path": "data/entities/lgd/constituency_district_membership.csv",
        "deprecated_at": "2026-06-08",
    },
    {
        "old_path": "reference/lgd/parse-receipt.json",
        "new_path": "_ops/lgd-parse-receipt.json",
        "deprecated_at": "2026-06-08",
    },
]


def emit_manifest(datasets_root: Path, *, dry_run: bool = False) -> Path:
    """Write ``<datasets_root>/manifest.json`` (version stamp + deprecations).

    No scan: ``tables`` is always ``[]`` (every canonical Parquet table
    retired). The atomic write mirrors the old writer seam - build the payload
    to a sibling tempfile, then ``os.replace`` it onto ``manifest.json``.

    ``dry_run`` builds the payload, byte-compares it against the on-disk file,
    logs ``UNCHANGED|CHANGED|NEW``, and writes nothing. Returns the manifest
    path in both modes.
    """
    manifest = {
        "$schema": _SCHEMA_REF,
        "$schema_version": schema_version(_MANIFEST_SCHEMA),
        "manifest_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tables": [],
        "deprecations": _DEPRECATIONS,
    }

    manifest_path = datasets_root / "manifest.json"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=datasets_root,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(manifest, tmp, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)

    if not dry_run:
        os.replace(tmp_path, manifest_path)
        return manifest_path

    try:
        new_bytes = tmp_path.read_bytes()
        if manifest_path.is_file():
            old_bytes = manifest_path.read_bytes()
            status = "UNCHANGED" if old_bytes == new_bytes else "CHANGED"
            log.info(
                "dry-run: %s %s (%d bytes -> %d bytes)",
                status,
                manifest_path.as_posix(),
                len(old_bytes),
                len(new_bytes),
            )
        else:
            log.info(
                "dry-run: NEW %s (%d bytes)",
                manifest_path.as_posix(),
                len(new_bytes),
            )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    return manifest_path
