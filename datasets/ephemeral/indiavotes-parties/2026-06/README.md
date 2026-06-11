# IndiaVotes party catalogue snapshot — 2026-06

**Last Updated**: 2026-06-11

This directory holds an operator-committed snapshot of the
[IndiaVotes](https://www.indiavotes.com/parties) party catalogue. It is
the input to the parity adapter
[`backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py`](../../../../backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py)
which proposes alias-add + mint-new actions against
[`datasets/data/entities/parties.csv`](../../../data/entities/parties.csv).

The snapshot was authored on **2026-06-11** to address the
electoral-data-quality campaign's residual UNK cohort — 23,639 candidacies
rows resolving to `parties.IN.UNK` across 2,372 distinct publisher
labels. User signoff promoted IndiaVotes from Q1 secondary-lane oracle
(per-event parity, PR-S-* cohort) to a NEW enrichment source for
parties.csv aliases + mint-new rows:

> 2026-06-11: "A - fix all UNK and rajasthan"

per CLAUDE.md section 10 scope-change-ledger SCL-02.

## Files in this directory

- [registered.csv](registered.csv) — the parsed CSV, COMMITTED to git.
  One row per distinct IndiaVotes party catalogue entry (listing rows +
  per-slug probes for the long-tail UNK labels).
- `cache/listing.html` — raw HTML of `/parties` (CACHED, gitignored per
  CLAUDE.md section 3 ephemeral tier).
- `cache/detail/<slug>.html` — raw HTML per per-slug detail probe
  (CACHED, gitignored).
- `probe-misses.txt` — newline-delimited list of `(label, http_status)`
  for the slugs that did NOT resolve to a detail page (useful for the
  curator's hand-mint follow-up).

## How the snapshot was authored

Two-pass scrape by [`tools/scrape_indiavotes_parties`](../../../../tools/scrape_indiavotes_parties/):

1. **Listing** — single `GET` against `https://www.indiavotes.com/parties`.
   Returns ~60 most-active parties (sorted by LS seats won), one per
   row in a 6-column HTML table:
   `Party | Type | LS seats won | VS seats won | Contested | Active`.
   Per-party hyperlink to `/parties/<slug>/`.

2. **Probes** — one `GET` per distinct top-200 UNK publisher label
   against `https://www.indiavotes.com/parties/<slug>/`. The slug is
   built by lowercasing the publisher label and collapsing non-
   alphanumerics to hyphens. Detail page exposes the canonical full
   name in `<h1>`; type / counts / active are NOT on the detail page.

The probes-file input was constructed from the candidacies corpus:

```pwsh
# At repo root, in the worktree:
$env:PYTHONPATH = "$pwd\backend"
& "..\yen-gov\.venv\Scripts\python.exe" -c @"
import csv, glob
from collections import Counter
labels = Counter()
for p in glob.glob('datasets/elections/**/candidacies.csv', recursive=True):
    with open(p, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            if (r.get('party_id') or '').strip() == 'parties.IN.UNK':
                lab = (r.get('party_short_raw') or '').strip()
                if lab:
                    labels[lab] += 1
print('\n'.join(lab for lab, _ in labels.most_common(200)))
"@ > probes.txt

python -m tools.scrape_indiavotes_parties --probes-file probes.txt
```

Politeness: 1.1 req/sec single-threaded, 7-day cache, citizen UA, no
cookies / referer headers. See
[`tools/scrape_indiavotes_parties/README.md`](../../../../tools/scrape_indiavotes_parties/README.md)
for the full operator runbook + the doctrinal "never CI" rationale.

## When to refresh

When IndiaVotes publishes a major new election cycle (e.g. post a
general election) OR when a new wave of long-tail publisher labels
emerges in the candidacies corpus that the 2026-06 snapshot did not
catch. The next refresh authors a NEW `<vintage>/` directory (e.g.
`2027-06/`) and the adapter's `INDIAVOTES_VINTAGE` constant moves
forward; the previous snapshot stays in place as audit trail.

## What the snapshot does NOT carry

- **No vote counts.** Listing's LS seats won / VS seats won / Contested
  columns are kept on the snapshot rows but NOT consumed by the
  parties.csv enrichment (those are per-event facts, not party-identity
  facts).
- **No state codes.** IndiaVotes detail pages list strongholds but do
  not publish ISO 3166-2 codes; the curator leaves `home_state_codes`
  empty on mint-new rows for ECI's next list refresh to fill (Q1 ECI
  authority on home_state_codes).
- **No symbols / colours / Wikipedia URLs.** Those Q1 facts remain
  Wikipedia-authoritative; the IV adapter's enrich leg does NOT touch
  `brand_colour` / `symbol_asset` / `wikipedia`.
- **No ECI registration codes.** IV publishes its own internal slugs;
  the canonical `eci_codes` column stays ECI-authoritative.

## See also

- [tools/scrape_indiavotes_parties/README.md](../../../../tools/scrape_indiavotes_parties/README.md) — operator runbook.
- [backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py](../../../../backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py) — parity adapter.
- [tools/recon_curate_indiavotes_parties/](../../../../tools/recon_curate_indiavotes_parties/) — curator that applies verdict.csv to parties.csv.
- [docs/concepts/party-identity.md](../../../../docs/concepts/party-identity.md) — the identity contract.
- [datasets/data/entities/source.csv](../../../data/entities/source.csv) — IndiaVotes citation row (`src-...`).
