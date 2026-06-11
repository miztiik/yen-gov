"""Author the IndiaVotes party-catalogue snapshot CSV.

Run from the repo root:

    python -m tools.scrape_indiavotes_parties

Modes:

  - ``--listing-only``: scrape ``/parties`` only (top ~60 most-active
    parties; 1 request).
  - ``--probes-file PATH``: read newline-delimited publisher labels from
    PATH, slugify each, and probe ``/parties/<slug>/`` for the long-tail
    UNK labels. Skips labels whose slug we already saw via listing.
  - default: BOTH (recommended for the first run; subsequent runs are
    cache-hits).

The output snapshot CSV at
``datasets/ephemeral/indiavotes-parties/2026-06/registered.csv`` is the
input to ``backend/yen_gov/canonical/recon/adapters/indiavotes_parties.py``
(the PR adapter that promotes IndiaVotes from Q1 secondary-lane to a
NEW enrichment source for parties.csv aliases + mint-new rows per the
2026-06-11 user signoff "fix all UNK and rajasthan").

Politeness: see ``scrape.py``. 1.1 req/sec, 7-day cache, citizen UA.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

# Allow `python -m tools.scrape_indiavotes_parties` from repo root
# without setting PYTHONPATH.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from scrape import (  # noqa: E402  -- intentional after sys.path tweak
    CACHE_MAX_AGE_DAYS,
    DETAIL_URL_TEMPLATE,
    LISTING_URL,
    fetch_url,
    parse_detail,
    parse_listing,
    slugify,
)

REPO_ROOT = _HERE.parent.parent
DEFAULT_VINTAGE = "2026-06"

OUTPUT_DIR_TEMPLATE = "datasets/ephemeral/indiavotes-parties/{vintage}"
CACHE_DIR_NAME = "cache"
OUTPUT_CSV_NAME = "registered.csv"

OUTPUT_COLUMNS = (
    "party_abbreviation",
    "party_full_name",
    "slug",
    "iv_type",
    "ls_seats_won",
    "vs_seats_won",
    "contested",
    "active_period_from",
    "active_period_to",
    "iv_url",
    "source_lane",
    "notes",
)


def _output_paths(vintage: str) -> tuple[Path, Path, Path]:
    out_dir = REPO_ROOT / OUTPUT_DIR_TEMPLATE.format(vintage=vintage)
    cache_dir = out_dir / CACHE_DIR_NAME
    csv_path = out_dir / OUTPUT_CSV_NAME
    return out_dir, cache_dir, csv_path


def _write_snapshot(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        full = {k: (row.get(k) or "") for k in OUTPUT_COLUMNS}
        writer.writerow(full)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _read_labels(probes_file: Path) -> list[str]:
    """Read the operator's per-PR list of UNK publisher labels.

    One label per line; blank lines + ``#`` comment-lines skipped.
    Labels are taken VERBATIM (no trim of internal whitespace) since
    the IV slug builder applies aggressive normalisation downstream.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in probes_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def scrape_listing(*, vintage: str, force_refetch: bool = False) -> list[dict[str, str]]:
    """Fetch + parse /parties; return one row per top-60 party."""
    _out_dir, cache_dir, _csv = _output_paths(vintage)
    cache_path = cache_dir / "listing.html"
    cache_path, status = fetch_url(LISTING_URL, cache_path, force_refetch=force_refetch)
    if status != 200:
        sys.stderr.write(
            f"[scrape] LISTING fetch failed status={status} url={LISTING_URL}\n"
            f"[scrape] Probable IV outage / rate-limit. STOP and surface.\n"
        )
        return []
    parsed = parse_listing(cache_path)
    for row in parsed:
        row["iv_url"] = DETAIL_URL_TEMPLATE.format(slug=row["slug"])
        row["source_lane"] = "listing"
        row["notes"] = ""
    return parsed


def scrape_probes(
    labels: list[str],
    *,
    vintage: str,
    known_slugs: set[str],
    force_refetch: bool = False,
) -> tuple[list[dict[str, str]], list[tuple[str, int]]]:
    """Probe ``/parties/<slug>/`` for each unique label-slug.

    Returns ``(detail_rows, miss_log)``.
    ``detail_rows`` is one row per slug that resolved 200 + parsed a
    full name. ``miss_log`` is the list of ``(label, status_code)``
    pairs for the slugs that did NOT resolve (useful for the curator's
    hand-mint follow-up).
    """
    _out_dir, cache_dir, _csv = _output_paths(vintage)
    detail_rows: list[dict[str, str]] = []
    miss_log: list[tuple[str, int]] = []
    seen_slugs: set[str] = set(known_slugs)
    for label in labels:
        slug = slugify(label)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        url = DETAIL_URL_TEMPLATE.format(slug=slug)
        cache_path = cache_dir / "detail" / f"{slug}.html"
        cache_path, status = fetch_url(url, cache_path, force_refetch=force_refetch)
        if status != 200:
            miss_log.append((label, status))
            continue
        parsed = parse_detail(cache_path, slug)
        if parsed is None:
            miss_log.append((label, -1))
            continue
        parsed["iv_url"] = url
        parsed["source_lane"] = "probe"
        parsed["notes"] = f"probe-from-label={label!r}"
        detail_rows.append(parsed)
    return detail_rows, miss_log


def merge_rows(
    listing_rows: list[dict[str, str]],
    detail_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge listing + detail rows. Listing wins on per-slug collision.

    The listing rows carry richer fields (iv_type / contested / active);
    the detail rows carry only the abbrev / full / slug triple. When a
    detail-row slug also appears in the listing, drop the detail row.
    """
    by_slug: dict[str, dict[str, str]] = {}
    for row in listing_rows:
        by_slug[row["slug"]] = row
    for row in detail_rows:
        if row["slug"] in by_slug:
            continue
        by_slug[row["slug"]] = row
    return sorted(by_slug.values(), key=lambda r: r["slug"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--vintage",
        default=DEFAULT_VINTAGE,
        help=f"Operator snapshot window (ADR-0042). Default: {DEFAULT_VINTAGE!r}.",
    )
    ap.add_argument(
        "--probes-file",
        type=Path,
        default=None,
        help=(
            "Path to a newline-delimited list of UNK publisher labels to "
            "probe directly. Default: only scrape /parties listing."
        ),
    )
    ap.add_argument(
        "--listing-only",
        action="store_true",
        help="Skip probes; scrape /parties listing only (1 request).",
    )
    ap.add_argument(
        "--force-refetch",
        action="store_true",
        help=f"Bypass the {CACHE_MAX_AGE_DAYS}-day cache and re-fetch every URL.",
    )
    args = ap.parse_args(argv)

    out_dir, cache_dir, csv_path = _output_paths(args.vintage)
    print(
        f"[scrape] vintage={args.vintage!r}\n"
        f"[scrape]   cache_dir = {cache_dir.relative_to(REPO_ROOT).as_posix()}\n"
        f"[scrape]   csv_path  = {csv_path.relative_to(REPO_ROOT).as_posix()}"
    )

    listing_rows = scrape_listing(vintage=args.vintage, force_refetch=args.force_refetch)
    print(f"[scrape] listing: {len(listing_rows)} rows")
    known_slugs = {row["slug"] for row in listing_rows}

    detail_rows: list[dict[str, str]] = []
    miss_log: list[tuple[str, int]] = []
    if not args.listing_only and args.probes_file is not None:
        if not args.probes_file.exists():
            print(f"[scrape] probes-file not found: {args.probes_file}", file=sys.stderr)
            return 2
        labels = _read_labels(args.probes_file)
        print(f"[scrape] probes: {len(labels)} unique labels from {args.probes_file.as_posix()}")
        detail_rows, miss_log = scrape_probes(
            labels,
            vintage=args.vintage,
            known_slugs=known_slugs,
            force_refetch=args.force_refetch,
        )
        print(f"[scrape] probes hits: {len(detail_rows)} (misses: {len(miss_log)})")

    merged = merge_rows(listing_rows, detail_rows)
    _write_snapshot(csv_path, merged)
    print(f"[scrape] wrote {len(merged)} rows -> {csv_path.relative_to(REPO_ROOT).as_posix()}")

    # Per-recognition tally for the operator-readable summary.
    by_type: Counter[str] = Counter()
    for row in merged:
        by_type[row.get("iv_type") or "(probe-only)"] += 1
    print("[scrape] by iv_type:")
    for k, v in by_type.most_common():
        print(f"  {v:4}  {k!r}")
    if miss_log:
        miss_path = out_dir / "probe-misses.txt"
        miss_path.write_text(
            "\n".join(f"{lab}\t{status}" for lab, status in miss_log),
            encoding="utf-8",
        )
        print(f"[scrape] probe-misses log -> {miss_path.relative_to(REPO_ROOT).as_posix()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
