"""Emit the UNK ledger: a worklist for the next correlation pass.

See ``__main__.py`` for the full doctrine + the schema. The short version:

After PR-Q2 (#957) and PR-Q8 ran the TCPD per-party catalogue correlator
and the apply tool flipped 7,442 UNK rows to real party_ids, the residual
~840 candidacy rows still carrying ``party_id == parties.IN.UNK`` are
publisher-side debt - TCPD often recognises the same label under a real
``Party_Name`` but our correlator could not bind it (placeholder-only
TCPD rows, state-year collisions, labels TCPD genuinely does not
catalogue, etc.).

This tool walks the post-rebind candidacies.csv corpus, groups remaining
UNK rows by ``(body, state_slug, year, event_id, publisher_label)``,
joins TCPD's per-party catalogue for context (when the label appears
anywhere in ``Party_Name`` / abbreviations), tags the skip_reason from
the most recent correlator skipped.csv, and writes
``datasets/_ops/unk-ledger-2026-06-12.csv`` - the worklist the next ECI
statreport / Wikipedia pass can chew through.

Run from the repo root:

    python -m tools.emit_unk_ledger

The output is byte-deterministic given the same inputs (sorted by
``(body, state_slug, year, publisher_label)``).
"""
