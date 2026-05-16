# Disclaimer & Attribution

**Last Updated**: 2026-05-10

> Single source of truth for the user-facing disclaimer that appears on the
> About page and is linked from every map and every data view in the app.
> If you change wording here, the [About page](../../frontend/src/routes/About.svelte)
> picks it up — keep the two in sync. The same wording is also referenced
> from [data-sources.md](../reference/data-sources.md) so contributors and
> readers see one consistent story.

## Intent

yen-gov is an open, volunteer-run **curator** of Indian data — not
an authoritative publisher. The disclaimer exists to make three things
unambiguous to anyone landing on the site:

1. We are **not** the Election Commission of India, the Survey of India, or
   any government body. We are not affiliated with, endorsed by, or speaking
   for any of them.
2. The data and maps shown here are **best-effort reproductions** built by
   pulling from public sources (ECI portals, CEO portals, MyNeta, Wikipedia,
   open boundary repositories) and stitching them together with code that
   lives in this repository for anyone to inspect. Errors, gaps, and
   stale rows are possible.
3. We welcome corrections via GitHub Issues / Pull Requests. We will fix
   what we can, but we make no guarantees of accuracy, completeness,
   timeliness, or fitness for any particular purpose.

The tone is friendly and direct, not legalese. The goal is **clarity**, not
liability armor.

## Canonical wording

The text below is what the About page renders. Treat it as the contract.

---

### About yen-gov

**yen-gov** is an open-source project that brings together publicly
available Indian civic data — starting with electoral results and
broadening over time to socio-economic, demographic, and welfare
indicators (census releases, NSO/MoSPI tables, scheme-level reporting,
and more). It pulls from official portals (Election Commission of India,
state Chief Electoral Officer offices, ministry statistical releases) and
well-known community sources (Wikipedia, MyNeta, open boundary
repositories), validates everything against schemas, and presents it in
one place — for free, with the source code and the source data both open.

Every dataset that ships in this site carries a `sources` list that names
the exact URL each row was pulled from and when it was fetched. Nothing on
this site is anonymous — you can trace any number on any chart back to its
origin.

### About the data

- We are **not the Election Commission of India** and we are **not a
  government source**. We are a community project that reads public data
  and re-presents it.
- We make a **best effort** to be accurate and to stay close to the
  official record. Where official sources publish numbers, we use those
  numbers. Where they don't, we say so.
- Civic data is messy. Names get spelled multiple ways, party
  affiliations change between filing and result, postal-vote breakdowns
  arrive late, ECI itself sometimes revises numbers post-declaration,
  and socio-economic series get re-based or revised between releases.
  We try to track these, but **errors and lag are possible.**
- Treat anything you see here as a starting point, not the final word.
  For anything that matters — legal, journalistic, academic, or
  operational — verify against the original source we link to.
- Found a mistake?
  [Open an issue or a pull request on GitHub](https://github.com/miztiik/yen-gov).
  Patches that come with a citation get merged fastest.

### About the maps

The maps you see on this site are drawn from openly licensed boundary
files contributed by the community — primarily the
[**HindustanTimesLabs/shapefiles**](https://github.com/HindustanTimesLabs/shapefiles)
and [**datameet**](https://github.com/datameet/maps) repositories — not
from the Survey of India.

That has consequences:

- **Boundaries are illustrative, not authoritative.** They are accurate
  enough to identify a constituency or district at a glance, but they are
  **not** survey-grade. Do not use them for any legal, surveying,
  navigational, or boundary-dispute purpose.
- **The depiction of international and internal borders** on these maps
  follows the boundary files we use; it does **not** represent the
  position of the Government of India, of yen-gov, or of any contributor.
  For the official depiction of India's borders, refer to maps published
  by the [Survey of India](https://www.surveyofindia.gov.in/).
- Boundaries can be **out of date.** Constituencies are redrawn during
  delimitation; districts are created, merged, and renamed by state
  governments. Whatever vintage the upstream file is, our map inherits.
- Coverage is **uneven** — we currently have AC-level boundaries for a
  handful of states and add more as upstream sources publish them.

If you spot a wrong boundary, the right place to fix it is usually
upstream (HindustanTimesLabs / datameet); once the upstream file is
corrected, our pipeline picks it up on the next refresh.

### About this project

yen-gov is built and maintained on a volunteer basis. There is no company
behind it, no advertising, no analytics, no user accounts, and no data
collected from you. The whole site is a static bundle served from GitHub
Pages — what you download in your browser is everything there is.

Source code, data files, and contribution guidelines:
[github.com/miztiik/yen-gov](https://github.com/miztiik/yen-gov).

### "As-is", in plain language

We provide this site **as-is, with no warranty.** We don't promise it's
correct, complete, or current. We don't accept responsibility for
decisions made on the basis of what you read here. If accuracy matters
for what you're doing, go to the original source we cite.

That said — if something looks wrong, please tell us. We want it to be
right.

---

## Where this is surfaced

| Surface | How it links |
| ------- | ------------ |
| App route `/about` | Renders the wording above. Anchors: `#data`, `#maps`, `#project`. |
| Every map (via `MapChoropleth.svelte`) | Small ⓘ badge in the corner → `#/about#maps`. One place updates them all. |
| Left rail footer | "About & disclaimer" link → `#/about`. |
| Home page | Subtle one-line note under the headline → `#/about`. |
| `docs/reference/data-sources.md` | "See also" link back here, so contributors hit the same wording. |

## Why a doc instead of a `LICENSE`-style file

Code license (MIT) and content license (CC-BY-4.0) live where licenses
live — in the repo root and in `datasets/` provenance. This document is
different: it's the **user-facing** explanation of what the site is and
isn't, and it's optimised for a reader who is not a lawyer and not a
contributor — just someone who landed on a chart and wants to know how
much to trust it. That reader doesn't open `LICENSE`; they click "About".

So: license files stay in the repo for the legal questions; this doc
backs the page that answers the human question.

## See also

- [`frontend/src/routes/About.svelte`](../../frontend/src/routes/About.svelte) — the rendered page.
- [`frontend/src/lib/maplibre/MapChoropleth.svelte`](../../frontend/src/lib/maplibre/MapChoropleth.svelte) — the ⓘ badge that points readers here from every map.
- [`docs/reference/data-sources.md`](../reference/data-sources.md) — full source catalogue these maps and tables draw from.
- [`docs/concepts/data-provenance.md`](data-provenance.md) — the per-file `sources[]` contract that backs every claim above.
