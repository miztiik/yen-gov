"""Derived artifact emitters.

The emit subpackage projects validated JSON under `datasets/elections/...` into
secondary artifact formats (SQLite today; possibly Parquet later). It does NOT
fetch, parse, or compose; those are `pipeline/`'s job. Per docs/architecture/backend/emit-sqlite.md the emitter
reads the JSON contract surface and never imports from `pipeline/`.
"""
