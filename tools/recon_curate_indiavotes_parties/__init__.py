"""Curator: apply IndiaVotes parties verdict.csv to parties.csv.

NEVER CI. Operator-run only. Reads
``datasets/ephemeral/party-parity/indiavotes-parties/2026-06/<sha>/verdict.csv``
and applies the operator-curatable enrichments to
``datasets/data/entities/parties.csv``. See
``backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py`` for
the Q1 fact-class scoping rationale (IV's role is restricted to
alias-add + mint-new; NOT enrich of full_name / recognition_scope /
home_state_codes / brand_colour - those Q1 cells belong to other
oracles).
"""
