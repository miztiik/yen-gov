# IndiaVotes party-catalogue scraper

**Last Updated**: 2026-06-11

One-shot operator scraper that authors the IndiaVotes party catalogue
snapshot under `datasets/ephemeral/indiavotes-parties/2026-06/registered.csv`.
NEVER CI. Sole consumer is
[`backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py`](../../backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py)
(the parity adapter that promotes IndiaVotes from Q1 secondary-lane to a
NEW enrichment source for `parties.csv` aliases + mint-new rows per
the 2026-06-11 user signoff "fix all UNK and rajasthan").

## When to run

When the operator wants to refresh the IndiaVotes catalogue snapshot. The
on-disk snapshot under `datasets/ephemeral/indiavotes-parties/<vintage>/`
IS committed (per CLAUDE.md section 3 ephemeral tier + Q3 audit trail);
re-running with a new `--vintage` arg authors a parallel snapshot
directory rather than overwriting the previous run.

## Two scrape modes

The IndiaVotes catalogue is reachable via two URL patterns:

- **Listing**: `https://www.indiavotes.com/parties` -- one HTML page with
  the top ~60 most-active parties (sorted by LS seats won), one row per
  party in a single table. Carries rich fields: party abbreviation +
  full name + type (national/state/independent/state-recognised) + LS
  seats won + VS seats won + total contested + active period
  (founded year -> last contested year).
- **Detail**: `https://www.indiavotes.com/parties/<slug>/` -- one HTML
  page per party. Keyed by the lowercase publisher abbreviation (e.g.
  `/parties/inc/`, `/parties/kjp/`). Carries only the canonical full
  name + stronghold list + per-state result tables; type / seat counts
  are NOT on the detail page.

The 2026-06 snapshot uses BOTH:

1. Scrape `/parties` listing -> 60 rich rows (national + top state parties).
2. For UNK publisher labels NOT covered by listing -> probe each slug
   against `/parties/<slug>/` to get the abbreviation + full name. Type
   / counts / active period are blank for probe-only rows (the curator's
   recognition_scope is left empty for those; ECI's next list refresh is
   the authoritative fill per Q1 fact-class table).

## Politeness

- **1.1 requests per second**, single-threaded. Implemented in
  [scrape.py](scrape.py) (`REQUEST_INTERVAL_SECONDS = 1.1`).
- **Cache-first**: pages cached under
  `datasets/ephemeral/indiavotes-parties/<vintage>/cache/`; re-runs
  within 7 days are zero network traffic. The cache subdirectory is
  ephemeral; only the parsed CSV at `registered.csv` is committed.
- **Citizen User-Agent**. No `Cookie` / `Referer` / yen-gov-tagged
  headers. IndiaVotes is treated as a goodwill provider.
- **No scraping at scale**. Listing is 1 request; probes are capped by
  the operator-supplied `--probes-file` (the 2026-06 run used the
  top-200 UNK labels: 200 requests over ~4 min).
- **No CI**. Adding this to a workflow is a Holy Law #5 violation
  (band-aid in the wrong layer).

## Usage

From the repo root:

```pwsh
# 1) Author a probes-file with the top-N UNK publisher labels.
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
"@ > tmp_probes.txt

# 2) Run the scraper.
python -m tools.scrape_indiavotes_parties --probes-file tmp_probes.txt
```

The scraper writes:

- `datasets/ephemeral/indiavotes-parties/2026-06/registered.csv` --
  the parsed CSV (COMMITTED to git per Q3 audit policy).
- `datasets/ephemeral/indiavotes-parties/2026-06/cache/listing.html` --
  the raw /parties HTML (CACHED, ephemeral).
- `datasets/ephemeral/indiavotes-parties/2026-06/cache/detail/<slug>.html` --
  the raw detail HTML per probed slug (CACHED, ephemeral).
- `datasets/ephemeral/indiavotes-parties/2026-06/probe-misses.txt` --
  one line per `(label, status)` for the slugs that did not resolve
  (for curator follow-up).

## When IndiaVotes is unreachable

If the live probe fails (network down, 4xx/5xx, rate-limit), the CLI
emits an error to stderr and returns the row set it managed to parse
so far. STOP at this point and surface the error; the scraper is NOT
designed to retry indefinitely (IV's rate-limiter would only get more
upset). The 7-day cache means re-running after a transient failure is
cheap if you got even half the rows through.

## See also

- [docs/concepts/party-identity.md](../../docs/concepts/party-identity.md) - the identity contract IV is enriching.
- [backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py](../../backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py) - the parity adapter that consumes the snapshot.
- [tools/recon_curate_indiavotes_parties/](../recon_curate_indiavotes_parties/) - the curator that applies the verdict.csv to `parties.csv`.
- [tools/elections_parity_indiavotes/scrape.py](../elections_parity_indiavotes/scrape.py) - the sibling per-state scraper this one borrows its politeness contract from.
