"""One-shot operator scraper for the IndiaVotes party catalogue.

NEVER CI. The output is a committed snapshot CSV at
``datasets/ephemeral/indiavotes-parties/2026-06/registered.csv`` consumed
by ``backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py``
(the PR adapter that promotes IndiaVotes from Q1 secondary-lane fact-class
table to a NEW enrichment source for parties.csv aliases + mint-new rows
per the 2026-06-11 user signoff). See ``README.md`` in this directory
for the operator runbook.
"""
