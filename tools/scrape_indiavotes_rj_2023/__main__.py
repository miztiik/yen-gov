"""IndiaVotes scraper for Rajasthan Vidhan Sabha 2023 — 200 ACs.

Reads:
- ``https://www.indiavotes.com/vidhan-sabha/rajasthan/2023`` (master; party tally + AC slug list).
- ``https://www.indiavotes.com/vidhan-sabha/rajasthan/2023/<ac-slug>/`` × 200 (per-AC; candidate rows).

Writes (under ``datasets/ephemeral/indiavotes-rj-ae2023/2023-11/``):
- ``master.html`` + ``master.json`` — raw HTML + extracted ``iv-page-context`` JSON.
- ``ac/<slug>.html`` + ``ac/<slug>.json`` — same, per-AC.
- ``results.csv`` — flat candidate-grain CSV (one row per (AC, candidate)).
- ``summary.csv`` — flat AC-grain CSV (one row per AC; winner + runnerup + margin).
- ``README.md`` — citation + scrape date + politeness compliance.

Politeness invariants (must hold; the IndiaVotes operator does not publish
a robots.txt that names this scraper but the citizen-audit etiquette is
identical to ``tools/elections_parity_indiavotes/scrape.py``):

- 1 req/sec strictly serialised single-threaded.
- Cache-first; re-runs incur zero network traffic.
- Citizen UA; no Cookie / Referer / yen-gov-tagged headers.
- ``--no-fetch`` skips network entirely (emit CSVs from existing cache).

This is a sibling tool to ``tools/elections_parity_indiavotes/`` not a
modification of it: the older scraper targets the legacy HTML-table layout
(``find_all('table')`` + party-in-parens extraction). IndiaVotes migrated
to Astro v5 in early 2026 and now ships the data inside
``<script type="application/json" id="iv-page-context">{...}</script>``.
The two scrapers coexist (the older one is still wired into the parity
CLI per ``tests/test_elections_parity_indiavotes.py``).

Usage:

    python tools/scrape_indiavotes_rj_2023/__main__.py [--force-refetch] [--no-fetch]

Total wall-clock for a cold scrape: ~3.5 min (201 pages * 1 sec/req +
latency). Warm scrape (cache hit on all 201 files): seconds.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Iterable

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "datasets" / "ephemeral" / "indiavotes-rj-ae2023" / "2023-11"

USER_AGENT = (
    "yen-gov-electoral-corpus/0.1 "
    "(one-shot citizen audit; contact via github.com/yen-gov/yen-gov)"
)
REQUEST_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 30.0

MASTER_URL = "https://www.indiavotes.com/vidhan-sabha/rajasthan/2023"
AC_URL_TEMPLATE = "https://www.indiavotes.com/vidhan-sabha/rajasthan/2023/{slug}/"

# Astro v5 ships the page data in a typed JSON script tag. The id is stable
# across the IndiaVotes pages I have probed (master + per-AC); regex is
# DOTALL-safe (no nested <script> tags inside an iv-page-context blob).
_CTX_RE = re.compile(
    r'<script\s+type="application/json"\s+id="iv-page-context">(.*?)</script>',
    re.DOTALL,
)
# Per-AC href shape: ``/vidhan-sabha/rajasthan/2023/<ac-slug>/``. The master
# page also carries non-AC anchors under ``/vidhan-sabha/`` (compare links,
# nav chrome) which this regex excludes by pinning rajasthan/2023/<slug>/.
_AC_HREF_RE = re.compile(r'href="(/vidhan-sabha/rajasthan/2023/[a-z0-9-]+/)"')


def _fetch(url: str, cache_path: Path, *, force: bool = False) -> str:
    """Fetch ``url`` into ``cache_path``; cache-first; 1 req/sec sleep on miss."""

    if cache_path.exists() and not force:
        return cache_path.read_text(encoding="utf-8")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    time.sleep(REQUEST_INTERVAL_SECONDS)
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, headers=headers) as client:
        response = client.get(url, follow_redirects=True)
        response.raise_for_status()
    cache_path.write_text(response.text, encoding="utf-8")
    return response.text


def _extract_ctx(html: str) -> dict:
    """Pull the ``iv-page-context`` JSON blob out of an IndiaVotes HTML page."""

    match = _CTX_RE.search(html)
    if match is None:
        raise ValueError("no iv-page-context script tag found")
    return json.loads(match.group(1))


def _extract_ac_slugs(master_html: str) -> list[str]:
    """Extract the per-AC slug list from the master page anchors (200 ACs)."""

    slugs: list[str] = []
    seen: set[str] = set()
    for href in _AC_HREF_RE.findall(master_html):
        parts = href.strip("/").split("/")
        # Defensive: only ``vidhan-sabha/rajasthan/2023/<slug>/`` (4 segments).
        if len(parts) != 4:
            continue
        slug = parts[3]
        if slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return slugs


def fetch_master(*, force: bool = False) -> dict:
    """Fetch + cache the state-year master page; emit ``master.json`` alongside."""

    cache = SNAPSHOT_DIR / "master.html"
    html = _fetch(MASTER_URL, cache, force=force)
    ctx = _extract_ctx(html)
    (SNAPSHOT_DIR / "master.json").write_text(
        json.dumps(ctx, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return ctx


def fetch_ac(slug: str, *, force: bool = False) -> dict:
    """Fetch + cache one per-AC page; emit ``ac/<slug>.json`` alongside."""

    cache = SNAPSHOT_DIR / "ac" / f"{slug}.html"
    html = _fetch(AC_URL_TEMPLATE.format(slug=slug), cache, force=force)
    ctx = _extract_ctx(html)
    (SNAPSHOT_DIR / "ac" / f"{slug}.json").write_text(
        json.dumps(ctx, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return ctx


def _emit_results_csv(slugs: Iterable[str]) -> int:
    """Flatten 200 per-AC JSON files into one candidate-grain CSV."""

    rows: list[dict[str, str | int | float]] = []
    for slug in slugs:
        ctx_path = SNAPSHOT_DIR / "ac" / f"{slug}.json"
        ac = json.loads(ctx_path.read_text(encoding="utf-8"))
        meta = ac["meta"]
        result = ac["result"]
        for cand in result.get("candidates", []):
            rows.append(
                {
                    "constituency_slug": meta["slug"],
                    "constituency_name": meta["name"]["en"],
                    "district": (meta.get("districts") or [""])[0],
                    "category": meta.get("category") or "",
                    "candidate_slug": cand.get("candidate_slug") or "",
                    "candidate_name": cand["name"]["en"],
                    "party_slug": cand.get("party_slug") or "",
                    "party_abbreviation": cand.get("party_abbreviation") or "",
                    "votes": int(cand.get("votes") or 0),
                    "vote_share_pct": round(float(cand.get("vote_share") or 0.0) * 100, 4),
                    "position": int(cand.get("position") or 0),
                    "won": int(bool(cand.get("won"))),
                }
            )
    rows.sort(key=lambda r: (str(r["constituency_slug"]), int(r["position"]), str(r["candidate_name"])))
    out = SNAPSHOT_DIR / "results.csv"
    fieldnames = list(rows[0].keys()) if rows else []
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _emit_summary_csv(slugs: Iterable[str]) -> int:
    """Flatten 200 per-AC JSON files into one AC-grain CSV (winner / runnerup / margin)."""

    rows: list[dict] = []
    for slug in slugs:
        ctx_path = SNAPSHOT_DIR / "ac" / f"{slug}.json"
        ac = json.loads(ctx_path.read_text(encoding="utf-8"))
        meta = ac["meta"]
        result = ac["result"]
        summary = result.get("summary", {})
        candidates = result.get("candidates", [])
        winner = next((c for c in candidates if c.get("won")), None)
        if winner is None and candidates:
            # IndiaVotes occasionally lacks a ``won`` flag for uncontested or
            # awaiting-declaration races; fall back to position-1.
            winner = next((c for c in candidates if c.get("position") == 1), None)
        runnerup = next((c for c in candidates if c.get("position") == 2), None)
        rows.append(
            {
                "constituency_slug": meta["slug"],
                "constituency_name": meta["name"]["en"],
                "district": (meta.get("districts") or [""])[0],
                "category": meta.get("category") or "",
                "voters_eligible": int(summary.get("voters_eligible") or 0),
                "votes_polled": int(summary.get("votes_polled") or 0),
                "turnout_pct": round(float(summary.get("turnout") or 0.0) * 100, 4),
                "nota_votes": int(summary.get("nota_votes") or 0),
                "winner_candidate": winner["name"]["en"] if winner else "",
                "winner_party_abbreviation": (
                    winner.get("party_abbreviation") if winner else ""
                ) or "",
                "winner_votes": int(winner.get("votes") or 0) if winner else 0,
                "runnerup_candidate": runnerup["name"]["en"] if runnerup else "",
                "runnerup_party_abbreviation": (
                    runnerup.get("party_abbreviation") if runnerup else ""
                ) or "",
                "runnerup_votes": int(runnerup.get("votes") or 0) if runnerup else 0,
                "margin_votes": int(summary.get("winning_margin") or 0),
                "margin_pct": round(float(summary.get("winning_margin_share") or 0.0) * 100, 4),
            }
        )
    rows.sort(key=lambda r: r["constituency_slug"])
    out = SNAPSHOT_DIR / "summary.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _emit_readme(slugs: list[str], *, n_results: int, n_summary: int) -> None:
    body = f"""# IndiaVotes snapshot - Rajasthan Vidhan Sabha 2023

**Scrape date**: 2026-06-11 (snapshot operator window).
**Vintage tag**: 2023-11 (Nov 2023 polling event; matches the source.csv vintage column).
**Source URLs**:
- Master: <{MASTER_URL}>
- Per-AC: <{AC_URL_TEMPLATE.format(slug='<slug>')}> x {len(slugs)}

**Politeness compliance**: 1 req/sec single-threaded; citizen UA
(`{USER_AGENT}`); no cookies / Referer / yen-gov-tagged headers; cache-first
(re-runs incur zero network traffic). Producer (citation grain):
IndiaVotes (compilation publisher; original data sourced from ECI).

## Why this snapshot exists

TCPD compilation cutoff is 2021 and the upstream thecont1 Nov 2023 cohort
is missing MP/CG/RJ/TG (only KA/ML/NL/TR present). The 200 Rajasthan ACs
therefore have no canonical source after the PR-S-MP-AE2023 PR collapsed
on precondition-fail (2026-06-10). This snapshot promotes IndiaVotes from
secondary parity-oracle source to primary ingest source for the Nov 2023
Rajasthan cohort.

User signoff (2026-06-11): "A - fix all UNK and rajasthan". Recorded as
Scope-change ledger row SCL-03 in the PR body per CLAUDE.md section 10.

## Files

- `master.html` + `master.json` - state-year landing page (party tally +
  total-seats + turnout, extracted from the Astro v5 `iv-page-context`
  script tag).
- `ac/<slug>.html` + `ac/<slug>.json` x {len(slugs)} - per-AC candidate
  tables + summary.
- `results.csv` - flat candidate-grain CSV ({n_results} rows; one per
  (AC, candidate); NOTA excluded because IndiaVotes records it on the
  summary `nota_votes` field, not as a candidate row).
- `summary.csv` - flat AC-grain CSV ({n_summary} rows; winner +
  runnerup + margin).

## Downstream consumer

`tools/elections_rj_ae2023_ingest/` maps these flat CSV rows to the
canonical `datasets/elections/assembly/state=rajasthan/election=2023/`
candidacies.csv + summary.csv (Holy Law #6, OWID one-format-per-tier).

Re-run with `--force-refetch` to bypass the cache and re-fetch every
page; the cache files are byte-stable across re-runs because the
IndiaVotes pages are SSR'd and the JSON blobs are deterministic.
"""
    (SNAPSHOT_DIR / "README.md").write_text(body, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scrape_indiavotes_rj_2023",
        description=(
            "One-shot IndiaVotes scrape for RJ Vidhan Sabha 2023 (200 ACs). "
            "NEVER CI. See README for politeness rationale."
        ),
    )
    parser.add_argument(
        "--force-refetch",
        action="store_true",
        help="Bypass the on-disk cache and re-fetch every page.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help=(
            "Skip network entirely; emit CSVs from existing cache only. "
            "Useful for ingest re-runs and offline debugging."
        ),
    )
    args = parser.parse_args(argv)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_DIR / "ac").mkdir(exist_ok=True)

    if not args.no_fetch:
        print(f"[scrape] fetching master: {MASTER_URL}", file=sys.stderr)
        master_ctx = fetch_master(force=args.force_refetch)
        print(
            f"[scrape] master totalSeats={master_ctx.get('totalSeats')}, "
            f"turnout={master_ctx.get('turnout')}, "
            f"partyTally rows={len(master_ctx.get('partyTally') or [])}",
            file=sys.stderr,
        )

    master_html = (SNAPSHOT_DIR / "master.html").read_text(encoding="utf-8")
    slugs = _extract_ac_slugs(master_html)
    print(f"[scrape] discovered {len(slugs)} AC slugs", file=sys.stderr)
    if len(slugs) != 200:
        print(
            f"[scrape] WARNING: AC count {len(slugs)} != expected 200; "
            "delimitation mismatch or master-page layout drift",
            file=sys.stderr,
        )

    if not args.no_fetch:
        for i, slug in enumerate(slugs, 1):
            if i == 1 or i % 25 == 0 or i == len(slugs):
                print(f"[scrape] {i}/{len(slugs)}: {slug}", file=sys.stderr)
            try:
                fetch_ac(slug, force=args.force_refetch)
            except Exception as exc:
                print(f"[scrape] FAILED {slug}: {type(exc).__name__}: {exc}", file=sys.stderr)
                return 2

    n_results = _emit_results_csv(slugs)
    n_summary = _emit_summary_csv(slugs)
    _emit_readme(slugs, n_results=n_results, n_summary=n_summary)
    print(
        f"[scrape] wrote results.csv ({n_results} rows) + "
        f"summary.csv ({n_summary} rows) + README.md",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
