"""Parquet -> long-format CSV reingest emitters (sub-plan B2b).

Each module here transcodes one family's surviving parquet artifacts into
``datasets/data/datapoints/<entity_kind>/<indicator_id>.csv`` (or the
elections per-election layout for B2b.5) per parent plan section 21.2 / 21.6.
Each family is gated by ``cross-format-parity`` in
``backend/tests/test_csv_parquet_parity.py`` (parent section 22.6).

B2b.5 elections scaffolding (sub-sub-plan B2b.5.1, PR #_pending_) lives in
``elections.py`` - it exposes the four FILE_CLASS constants + path-builder
helpers for the per-(state, year) and per-(year) emitters that land in
B2b.5.2 (assembly TN pilot), B2b.5.3 (assembly fan-out), and B2b.5.4
(parliament). No emit() here yet; the scaffolding is pure-functional contract
surface so the FILE_CLASS literals do not drift across emitter modules +
tests + drivers.
"""
