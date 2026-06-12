"""Curator script: apply the TCPD-correlate verdict.csv to parties.csv.

Sibling of ``tools/correlate_unk_via_tcpd``. Reads the verdict.csv it emits
and applies:

  - ``action == alias-add``: append the publisher label as a new alias on
    the target parties.csv row (idempotent: skipped if already aliased).
  - ``action == mint-new``: append a new row to parties.csv with the TCPD
    mint payload (short / full / recognition_scope / home_state_codes /
    aliases / founded_year).
  - ``action == disputed``: NO mutation. The verdict row stays as a
    ledger entry for hand-curator review.

Idempotent: re-running the same verdict over an already-applied parties.csv
produces no changes. Skips collision-claimed aliases per the
``claimed_aliases`` policy from ``recon_curate_tcpd_parties._apply_enrich``.

Per CLAUDE.md section 10 (no auto-correct on publisher disagreement): this
tool only acts on the verdict rows the correlator already marked safe;
it does NOT make its own enrichment decisions. Disputed rows stay
disputed.

Does NOT mutate candidacies.csv directly. Run
``python -m tools.elections_party_id_repair --reresolve-unk --apply``
after this script to re-resolve the on-disk corpus through the
freshly-extended alias table.
"""
