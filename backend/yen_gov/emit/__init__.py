"""Derived artifact emitters.

The emit subpackage projects the in-memory ``RunResult`` produced by
``pipeline/run.py`` into secondary researcher-friendly artifact formats.
Today only ``csv_bundle.py`` survives — the per-state SQLite emitter
(``emit/sqlite.py``) retired in PR-R.3 (TODO row 1.8e) once Psephlab +
Compare switched to the canonical Parquet store
(``datasets/elections/election_results.parquet``) via DuckDB-WASM. The
emit subpackage does NOT fetch, parse, or compose; those are
``pipeline/``'s job. Emitters consume the in-memory primary API
(``emit_state_*_from_data``, PR-O.3a) and never import from ``pipeline/``.
"""
