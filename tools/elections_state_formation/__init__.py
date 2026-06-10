"""State-formation re-partition workflow (PR-W1b).

DRY-RUN by design. The operator-facing module is `repartition_dry_run.py`
which walks every per-state file under
``datasets/data/datapoints/electoral/`` and proposes which rows would
move under a historical-state re-partitioning. NO writes to the
electoral CSVs happen here; the proposal is emitted to
``datasets/_ops/state-formation-repartition-proposal.csv`` for user
sign-off per ESCALATE trigger #1 of
``TODO/20260609-election-experience-overhaul-plan.md``.

This tool lives under ``tools/`` per CLAUDE.md section 4 (tools are
standalone dev/ops) but DOES import
``yen_gov.canonical.historical_state_slug`` -- the established repo
pattern (see ``tools/boundaries/snapshot.py`` for the precedent). The
canonical helper is the contract surface; copying it here would
fork the slug logic at the first schema bump.
"""
