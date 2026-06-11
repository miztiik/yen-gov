# `datasets/ephemeral/thecont1-india-votes-data/` - snapshot README

**Last Updated**: 2026-06-11

Operator-dropped snapshots of the per-(year, state) Assembly CSVs from the
[thecont1/india-votes-data](https://github.com/thecont1/india-votes-data)
GitHub repository. Used by the
[backend/yen_gov/canonical/recon/adapters/thecont1_state.py](../../../backend/yen_gov/canonical/recon/adapters/thecont1_state.py)
Tier-C parity adapter (PR-S-TN-AE2026 of the 2026-06-10 electoral-data-
quality plan).

## Provenance

- **Producer**: thecont1 (community-maintained personal repo).
- **Upstream URL pattern**: `https://raw.githubusercontent.com/thecont1/india-votes-data/main/data/csv/<YEAR>Assembly-<STATE_ABBR>.csv`
  - `<YEAR>` is the 4-digit polling year (e.g. `2026`).
  - `<STATE_ABBR>` is the 2-letter ISO-3166 abbreviation (e.g. `TN`, `WB`, `KL`).
- **Local snapshot path** (re-named by operator at snapshot time):
  `datasets/ephemeral/thecont1-india-votes-data/<YEAR>/Assembly-<StateSlug>.csv`
  - `<StateSlug>` is the kebab-case yen-gov state slug (e.g. `Tamil-Nadu`,
    `West-Bengal`, `Kerala`). The re-name is so the per-state lookup table
    in `thecont1_state.py::_SNAPSHOT_NAME_BY_STATE_SLUG` matches the
    on-disk state-slug doctrine without divergence.
- **License**: the upstream repo carries no LICENSE file as of 2026-06-11.
  Treat as `unknown-public` per the
  [docs/concepts/data-provenance.md](../../../docs/concepts/data-provenance.md)
  enum until upstream publishes a license. Citation triple already in
  `datasets/data/entities/source.csv` (`thecont1` owner) - extend the row
  with a SPDX identifier when upstream clarifies.

## Re-snapshot policy

- Snapshots ARE committed (Q3 commit policy of the 2026-06-10 plan):
  per-state per-event CSVs are small (~300-500 KB) and the bytes-on-disk
  trail is the audit-trail. Operator drops a fresh file with
  `Invoke-WebRequest` (PowerShell) or `curl` (POSIX), commits with the
  PR that consumes the snapshot, and stamps the operator-snapshot
  window in the matching `source.csv` row's `vintage` column per
  ADR-0042.
- Re-snapshot is rare: only when the upstream publishes a corrected
  CSV for an already-snapshotted (year, state). Replace in-place; the
  citation row in `source.csv` gets a NEW `vintage` value (e.g.
  `2026-06-11` -> `2026-07-15`) and a NEW deterministic `source_id`
  per `derive_source_id(producer, title, vintage)` per the
  citation-ledger rule.
- The path is gitignored at the parent `datasets/ephemeral/.gitignore`
  level; commits force-add (`git add -f`) at land time. The
  per-(year, state) granularity keeps the trail recoverable when the
  upstream repo deletes / renames files.

## On-disk file format

CSV; column order verified 2026-06-11 against `2026Assembly-TN.csv`:

| Column            | Type   | Notes                                                                 |
|-------------------|--------|-----------------------------------------------------------------------|
| `election_year`   | int    | 4-digit year                                                          |
| `election_type`   | enum   | `"Assembly"` (this dir only carries AE snapshots)                     |
| `election_state`  | string | 2-letter ISO-3166 abbreviation (`"TN"`, `"WB"`, `"KL"`)               |
| `constituency`    | string | publisher constituency name (UPPER-CASE)                              |
| `constituency_no` | int    | 1-based ECI eci_no within the state                                   |
| `serial_no`       | int    | per-AC candidate ordinal (1 = first listed)                           |
| `candidate`       | string | publisher candidate name                                              |
| `party`           | string | publisher FULL party name (e.g. `"Dravida Munnetra Kazhagam"`)        |
| `evm_votes`       | int    | EVM-only vote count for this candidate                                |
| `postal_votes`    | int    | postal-ballot vote count for this candidate                           |

The adapter sums `evm_votes + postal_votes` to identify the winner per
AC (max-total-votes per `constituency_no` group). Tie-break: lower
`serial_no` (the upstream's published order).

## Cohort coverage as of 2026-06-11

Snapshots currently on disk:

- `2026/Assembly-Tamil-Nadu.csv` - PR-S-TN-AE2026 oracle. 4257 candidate
  rows across 234 ACs. Source URL:
  `https://raw.githubusercontent.com/thecont1/india-votes-data/main/data/csv/2026Assembly-TN.csv`
  (upstream file name uses `TN`; locally renamed to `Tamil-Nadu` per
  the lookup-table doctrine).
- `2024/Assembly-Maharashtra.csv` - PR-S-MH-AE2024 oracle. 4424 candidate
  rows across 288 ACs. Source URL:
  `https://raw.githubusercontent.com/thecont1/india-votes-data/main/data/csv/2024Assembly-MH.csv`
  (upstream file name uses `MH`; locally renamed to `Maharashtra` per
  the lookup-table doctrine). This snapshot is the ONLY oracle on disk
  for MH AcGenNov2024 - the yen-gov-side per-event `candidacies.csv` at
  `datasets/elections/assembly/state=maharashtra/election=2024/` does
  NOT exist (the canonical store's MH 2024 data lives only in
  long-format under `datasets/data/datapoints/electoral/
  maharashtra_election_results.csv`), so the parity sweep runs as
  1-oracle degenerate per the brief's stop condition #3. See
  PR-S-MH-AE2024 body for the Q7 SHS-Shinde / NCP-Ajit aggregate-seat
  oracle derived from long-format.

Future PR-S-* / PR-PC-* PRs in the 2026-06-10 plan will add:

- `2026/Assembly-West-Bengal.csv` (PR-S-WB-AE2026 cohort - upstream
  file `2026Assembly-WB.csv` exists per repo listing)
- `2023/Assembly-Karnataka.csv` (PR-S-KA-AE2023 cohort - upstream
  `2023Assembly-KA.csv` exists)

The upstream repo's PC compilation lives at a different path
(`data/csv/<YEAR>LokSabha.csv`) and is handled by a sibling adapter
(`recon/adapters/thecont1_pc.py` in a future PR-PC-* PR), NOT this
adapter.
