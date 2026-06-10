# Schemas

**Last Updated**: 2026-06-11

Reference index for schema contracts. Authoritative schema files live in `datasets/schemas/`; canonical CSV column contracts live in `datasets/data/_schema/`.

## See Also

- [docs/architecture/data/csv-column-contract.md](../architecture/data/csv-column-contract.md)
- [docs/architecture/data/schema-evolution.md](../architecture/data/schema-evolution.md)
- [docs/architecture/backend/validator.md](../architecture/backend/validator.md)
- [CLAUDE.md](../../CLAUDE.md)

## Schema Families

| Family | Location | Purpose |
| --- | --- | --- |
| JSON Schemas | `datasets/schemas/*.schema.json` | Hand-authored JSON artifact contracts, compatibility ledgers, manifest contracts, historical row-shape references. |
| Archived schemas | `datasets/schemas/archive/**` | Retained historical schemas used by schema-evolution compatibility checks. |
| CSV column contract | `datasets/data/_schema/columns.json` | File-class column names, dtypes, nullability, primary keys, and FK declarations for canonical CSV. |
| CSV column schema | `datasets/data/_schema/columns.schema.json` | JSON Schema for the CSV column contract itself. |
| Compatibility registry | `datasets/schema-compatibility.json` | Reader compatibility rules. |
| Schema evolution ledger | `datasets/schema-evolution.json` | Release history and value-change receipts. |

## Current Rules

- Every JSON Schema uses JSON Schema 2020-12 and carries `x-version` plus `x-changelog`.
- Version format is `<major>.<minor>` only.
- Minor bump = backwards-compatible addition. Major bump = breaking change.
- Writers emit current schema versions. Readers accept older versions only when `datasets/schema-compatibility.json` says they can.
- Canonical tabular data is CSV. Do not add new Parquet or JSON projections for citizen-facing tabular facts.
- CSV writes go through `backend/yen_gov/canonical/csv_writer.py`; CSV validation goes through `backend/yen_gov/canonical/csv_validator.py` and Tier-B checks.

## Common Commands

```powershell
$env:PYTHONPATH = "$pwd\backend"
python -m yen_gov validate --root .
python -m pytest -q backend/tests/test_csv_columns.py backend/tests/test_csv_writer.py backend/tests/test_csv_validator.py
```

## Updating This Index

Update this file when a schema family is added, retired, or moved. Do not list every schema row here by hand; the exact schema inventory is the filesystem under `datasets/schemas/`.
