"""Wikidata source adapters.

Wikidata is the fallback source for party-organisation metadata that ECI does
not publish in machine-readable form: who the current President/Chairperson
of each registered party is, who the General Secretary is, and the start +
end dates of each term.

Per PR-7 of TODO/20260613-party-deferred-followups-plan.md (Max 2a / 2d / 2e
verdicts): wikidata is consumed offline via a pinned SPARQL JSON snapshot at
datasets/ephemeral/wikidata-party-leadership-<YYYY-MM-DD>.json. The snapshot
is operator-pasted from query.wikidata.org once per refresh cycle; we never
fetch live (Holy Law #1 - static-first; no production backend). The pinned
SPARQL query shape is documented in party_leadership.py module docstring.

PR-7 (this PR) lays the ingester scaffolding only. PR-9 will pin the first
real SPARQL snapshot and emit the first batch of parties_leadership.csv rows.
"""
