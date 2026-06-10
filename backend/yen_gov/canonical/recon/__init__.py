"""Tier-C cross-source parity / reconciliation namespace.

Created by PR-2 of the 2026-06-10 electoral-data-quality + party-catalogue
plan (Wave 0 / Gregor section 5 + section 6 verdicts; CLAUDE.md section 0a
authority table — Gregor on integration topology).

This namespace hosts the cross-source publisher-string-to-canonical-id
parity machinery referenced by the new ``python -m yen_gov parity`` CLI:

  - ``shape_a.py`` — the canonical INTERMEDIATE schema every per-source
    adapter materialises (``ShapeARow`` + CSV read/write helpers). One row
    per (external publisher entity, source scope, source vintage).
  - ``aggregator.py`` — the EIP-style Compare-Aggregator that groups
    shape-A rows by proposed canonical ``party_id`` and emits
    ``VerdictRow`` records carrying the Fowler machine-decidable VERIFIED
    / DISPUTED / UNVERIFIED verdict (plan section 0.5 ESCALATE #2).
  - ``adapters/`` — the empty REGISTRY this PR ships. PR-W-1 / W-2 / W-3
    + each Stream X PR add one adapter module each
    (``recon/adapters/<source>.py`` exporting an ``ADAPTER`` instance) and
    register it in ``recon.adapters.REGISTRY[<source>] = ADAPTER``. No
    adapters land in this PR.

Tier-C contract (Wave 0 / Gregor section 6 verdict): this namespace is
NEVER walked by CI; the parity CLI is an OPERATOR-RUN tool only. Tier-A +
Tier-B keep the always-on safety net of FK closure (party_resolver +
candidacies / electoral CSV row-shape).

Verdict CSV commit policy (plan section 0.4 Q3 default; user-confirmed):

  - First run of any (source, vintage) is committed to
    ``datasets/ephemeral/party-parity/<source>/<vintage>/<sha>/verdict.csv``
    where ``<sha>`` is the PR's commit short-hash. The committed file is
    the operator-curatable ledger that future plan rows reference.
  - Re-runs of the SAME (source, vintage) write to a sibling ``<sha>``
    directory and are gitignored — ``datasets/ephemeral/`` is the
    ephemeral tier (CLAUDE.md section 3) and only the named first-run
    verdict.csv crosses the git boundary.

See also:

  - ``datasets/ephemeral/`` — ephemeral tier; not a contract surface.
  - ``backend/yen_gov/canonical/party_resolver.py`` — the central
    publisher-string-to-id resolver every adapter ALSO uses for the
    proposed_party_id field on each shape-A row.
  - ``backend/yen_gov/cli.py`` — the ``parity`` subcommand that dispatches
    the adapter and writes the verdict CSV.
"""

from __future__ import annotations
