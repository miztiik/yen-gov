"""tools/elections - one-shot election-corpus mash + audit scripts.

The scripts here are NOT part of the runtime pipeline. They exist to repair
the per-(state, year) candidacies + summary corpus when the LGD spine, the
parquet legacy, and the fixture trust anchor drift apart (the F1.1 Path A
backfill that produced this directory). Once the X1a reader flip lands and
the parity oracle stays green for 30 days, these can be archived (CLAUDE.md
section 3 - tools/ is for standalone dev/ops tooling, never imported by
backend/).
"""
