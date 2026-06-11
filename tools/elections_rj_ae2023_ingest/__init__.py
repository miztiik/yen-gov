"""Canonical ingest of the IndiaVotes RJ 2023 snapshot into the elections corpus.

Reads ``datasets/ephemeral/indiavotes-rj-ae2023/2023-11/results.csv`` +
``summary.csv`` and emits the two canonical CSVs:

- ``datasets/elections/assembly/state=rajasthan/election=2023/candidacies.csv``
- ``datasets/elections/assembly/state=rajasthan/election=2023/summary.csv``

Also upserts the IndiaVotes citation-ledger row into
``datasets/data/entities/source.csv`` (one row per (producer, title, vintage)
triple; idempotent on re-run).

Authored as part of the RJ-AE-Nov-2023 ingest (user-named oracle 2026-06-11:
"fix all UNK and rajasthan"). Companion tool to
``tools/scrape_indiavotes_rj_2023/`` and pipeline-equivalent to the TCPD
backfill writers (``backend/yen_gov/canonical/reingest/assembly_results.py``)
without going through the TCPD ``All_States_AE.csv`` shape - IndiaVotes ships
the data in a different vocabulary (party_abbreviation, vote_share as ratio,
``won`` flag) so the mapping lives here, not in the shared assembly_results
writer.
"""
