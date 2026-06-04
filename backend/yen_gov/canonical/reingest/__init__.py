"""Parquet -> long-format CSV reingest emitters (sub-plan B2b).

Each module here transcodes one family's surviving parquet artifacts into
``datasets/data/datapoints/<entity_kind>/<indicator_id>.csv`` (or the
elections per-election layout for B2b.5) per parent plan section 21.2 / 21.6.
Each family is gated by ``cross-format-parity`` in
``backend/tests/test_csv_parquet_parity.py`` (parent section 22.6).
"""
