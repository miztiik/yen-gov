"""One-shot IndiaVotes scrape for Rajasthan Vidhan Sabha 2023.

Sister tool to ``tools/elections_parity_indiavotes/``. Targets the IndiaVotes
Astro v5 frontend (``<script id="iv-page-context">``) rather than the older
HTML-table layout the parity oracle scraper handles. Authored as part of the
RJ-AE-Nov-2023 ingest (user-named oracle 2026-06-11: "fix all UNK and
rajasthan") because TCPD compilation cutoff is 2021 and the upstream
thecont1 Nov 2023 cohort is missing MP/CG/RJ/TG.

Never CI. One-shot scrape. See ``tools/scrape_indiavotes_rj_2023/README.md``
for politeness rationale (1 req/sec; citizen UA; cache-first; no cookies).
"""
