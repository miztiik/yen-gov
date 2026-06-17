"""Stage ICED (NITI Aayog) energy API feeds into a local dir.

Operator-facing helper. The canonical ingest pipeline never touches the
network (the ICED network fetcher was deleted in the 2026-06 rip; the
ingest CLIs read operator-staged local files only). This tool is the
*separate* staging step the operator runs by hand: it GETs each ICED feed
and saves the raw response under ``.runtime/raw/iced/`` with the filename
the matching backend ingest expects. The backend imports nothing from here
and reaches no network.

What it does NOT do: it does not decrypt. ICED serves several feeds as an
AES envelope (a JSON string literal ``"U2FsdGVkX1...=="``). This tool saves
that raw blob verbatim; the backend decrypts at parse time via
``backend/yen_gov/sources/iced_common/crypto.py`` (the tools/ layer rule
forbids importing it here, and the cipher must live in exactly one place).
So an encrypted feed is staged as ciphertext and is NOT directly readable
until a backend adapter decrypts it. The feed table below marks which are
encrypted and whether a backend ingest exists yet.

The feed list mirrors the receipt in
``docs/architecture/data/energy-coverage.md`` section 4. CEA installed
capacity is intentionally absent: it is a manual XLSX download from the CEA
listing page, not an API.

Standalone: argparse + stdlib urllib only. No backend imports (tools/ rule).

Examples::

    # See what would be staged, fetch nothing:
    python tools/iced_stage.py --list
    python tools/iced_stage.py --dry-run

    # Stage every feed:
    python tools/iced_stage.py

    # Stage one feed, re-fetch even if cached:
    python tools/iced_stage.py --only solar_potential --force
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# ICED hosts (verbatim from the dashboard bundle; see
# backend/yen_gov/sources/iced_common/endpoints.py).
HOST_BASE = "https://icedapi.niti.gov.in"
HOST_V1 = "https://icedapi.niti.gov.in/v1"

DEFAULT_STAGING_ROOT = ".runtime/raw/iced"
RUN_LOG_NAME = "_stage-log.json"
DEFAULT_RETRIES = 4
DEFAULT_RETRY_DELAY_SECONDS = 5
DEFAULT_TIMEOUT_SECONDS = 120

# ICED is public, but a browser-ish UA avoids edge interstitials.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


@dataclass(frozen=True)
class FeedSpec:
    """One ICED feed to stage.

    Attributes:
        name: stable key used for ``--only`` and the run-log.
        host: ``HOST_BASE`` or ``HOST_V1``.
        path: API path verbatim.
        encrypted: True when the response is an AES envelope (needs backend
            decrypt before parsing).
        filename: where to stage it under ``<staging-root>/``.
        category: ``"existing"`` (re-ingest of a feed we already hold) or
            ``"new"`` (an agreed new target with no adapter yet).
        backend_ingest: the live ingest CLI that consumes it, or ``None``.
    """

    name: str
    host: str
    path: str
    encrypted: bool
    filename: str
    category: str
    backend_ingest: str | None


# Feeds mirror docs/architecture/data/energy-coverage.md section 4 (the agreed
# targets) plus the live-ingestable existing feeds. Daily peak demand
# (last-30-days) was dropped by the data owner and is intentionally absent.
FEEDS: tuple[FeedSpec, ...] = (
    # --- existing feeds with a live or near-live ingest ---
    FeedSpec("capacity_metatable", HOST_V1, "/capacity-metatable-data", False,
             "capacity_metatable_data.json", "existing", "ingest-iced-capacity"),
    FeedSpec("power_statistics", HOST_BASE, "/energy/powerStatistics", True,
             "power_statistics.json", "existing", "ingest-iced-peak-demand"),
    FeedSpec("retired_capacity_plants", HOST_V1, "/retired-capacity-plants", False,
             "retired_capacity_plants.json", "existing", None),
    FeedSpec("plant_pipeline_info", HOST_V1, "/plantPipelineInfo", False,
             "plant_pipeline_info.json", "existing", None),
    # --- agreed NEW targets (no adapter yet; phase-2 work) ---
    FeedSpec("solar_potential", HOST_BASE, "/energy/fuel-sources/solar/potential", True,
             "solar_potential_by_state.json", "new", None),
    FeedSpec("wind_potential", HOST_BASE, "/energy/fuel-sources/wind/potential", True,
             "wind_potential_by_state.json", "new", None),
    FeedSpec("bio_energy_potential", HOST_BASE, "/energy/fuel-sources/bio-energy/potential", True,
             "bio_energy_potential_by_state.json", "new", None),
    FeedSpec("ice_ev_vahan", HOST_BASE, "/analytics/ice-ev-vahan", True,
             "ice_ev_vahan.json", "new", None),
    FeedSpec("captive_power_industry", HOST_BASE,
             "/energy/electricity/captive-power/captive-power-industry", True,
             "captive_power_industry.json", "new", None),
    FeedSpec("transmission_substation_list", HOST_BASE,
             "/energy/electricity/transmission/substation-list", True,
             "transmission_substation_list.json", "new", None),
    FeedSpec("aq_coal_plant_impact", HOST_BASE,
             "/analytics/aqi-impact-due-to-coal-plants-list", True,
             "aq_coal_plant_impact.json", "new", None),
)

FEEDS_BY_NAME: dict[str, FeedSpec] = {f.name: f for f in FEEDS}


def feed_url(feed: FeedSpec) -> str:
    """Return the full GET URL for a feed."""
    return f"{feed.host}{feed.path}"


def looks_like_json_body(data: bytes) -> bool:
    """True when ``data`` is a plausible ICED response, not an HTML error.

    A plain feed starts with ``{`` or ``[``; an AES envelope is a JSON
    string literal starting with ``"``. An edge/error page starts with
    ``<`` (HTML). Empty bodies fail.
    """
    head = data.lstrip()[:1]
    return head in (b"{", b"[", b'"')


def build_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"},
    )


def fetch_bytes(
    url: str,
    *,
    retries: int,
    retry_delay_seconds: int,
    timeout_seconds: int,
) -> bytes:
    """GET ``url`` and return its bytes, retrying transient failures.

    A non-JSON body (an HTML interstitial) is retried, as are connection
    errors and 429/503. Any other HTTPError is raised immediately.

    Raises:
        RuntimeError: every attempt failed (loud, never a silent empty file).
    """
    last_error = "no attempts made"
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(
                build_request(url), timeout=timeout_seconds
            ) as response:
                body = response.read()
            if looks_like_json_body(body):
                return body
            sample = body[:48].decode("utf-8", errors="replace").strip()
            last_error = f"not a JSON response (got {sample!r})"
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code not in (429, 503):
                raise RuntimeError(
                    f"download failed for {url}: HTTP {exc.code}"
                ) from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            print(
                f"  attempt {attempt}/{retries} failed ({last_error}); "
                f"retrying in {retry_delay_seconds}s",
                flush=True,
            )
            time.sleep(retry_delay_seconds)
    raise RuntimeError(
        f"download failed for {url} after {retries} attempts: {last_error}"
    )


def stage_feed(
    feed: FeedSpec,
    *,
    staging_root: Path,
    force: bool,
    retries: int,
    retry_delay_seconds: int,
    timeout_seconds: int,
    fetch=fetch_bytes,
) -> dict[str, object]:
    """Download one feed into ``<staging-root>/<filename>`` atomically.

    Returns a run-log record. ``fetch`` is injectable so tests never touch
    the network (the one external boundary). Writes ``<target>.partial``
    first, validates it is a plausible JSON body, then renames -- a half
    download never masquerades as staged.
    """
    target = staging_root / feed.filename
    if target.exists() and not force:
        body = target.read_bytes()
        return _record(feed, url=feed_url(feed), status="skipped", body=body)

    url = feed_url(feed)
    body = fetch(
        url,
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
        timeout_seconds=timeout_seconds,
    )
    if not looks_like_json_body(body):
        raise RuntimeError(f"{feed.name}: staged body is not JSON-like")
    staging_root.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.partial")
    partial.write_bytes(body)
    partial.replace(target)
    return _record(feed, url=url, status="staged", body=body)


def _record(feed: FeedSpec, *, url: str, status: str, body: bytes) -> dict[str, object]:
    return {
        "feed": feed.name,
        "url": url,
        "status": status,
        "bytes": len(body),
        "sha256_12": hashlib.sha256(body).hexdigest()[:12],
        "encrypted": feed.encrypted,
        "category": feed.category,
        "backend_ingest": feed.backend_ingest,
        "staged_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def write_run_log(staging_root: Path, records: list[dict[str, object]]) -> Path:
    """Merge ``records`` into ``<staging-root>/_stage-log.json`` (control-plane)."""
    log_path = staging_root / RUN_LOG_NAME
    existing: dict[str, object] = {}
    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    for rec in records:
        existing[str(rec["feed"])] = rec
    staging_root.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return log_path


def select_feeds(only: list[str] | None, category: str | None) -> list[FeedSpec]:
    feeds = list(FEEDS)
    if category:
        feeds = [f for f in feeds if f.category == category]
    if only:
        unknown = [n for n in only if n not in FEEDS_BY_NAME]
        if unknown:
            raise SystemExit(
                f"unknown feed(s): {unknown}; known: {sorted(FEEDS_BY_NAME)}"
            )
        feeds = [f for f in feeds if f.name in set(only)]
    return feeds


def print_feed_table(feeds: list[FeedSpec]) -> None:
    print(f"{'feed':<30} {'cat':<8} {'enc':<4} {'ingest':<26} url")
    for f in feeds:
        print(
            f"{f.name:<30} {f.category:<8} "
            f"{'yes' if f.encrypted else 'no':<4} "
            f"{(f.backend_ingest or '-'):<26} {feed_url(f)}"
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stage ICED energy API feeds into a local dir for the backend "
            "ingest CLIs (no network in the ingest itself). See "
            "docs/architecture/data/energy-coverage.md."
        ),
    )
    parser.add_argument(
        "--staging-root", default=DEFAULT_STAGING_ROOT,
        help=f"Where to stage feeds (default: {DEFAULT_STAGING_ROOT}).",
    )
    parser.add_argument(
        "--only", action="append", metavar="FEED",
        help="Stage only this feed (repeatable). See --list for names.",
    )
    parser.add_argument(
        "--category", choices=("existing", "new"),
        help="Restrict to existing-reingest or new-target feeds.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Print the feed table and exit (no network).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be staged without fetching.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if a feed is already staged.",
    )
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument(
        "--retry-delay-seconds", type=int, default=DEFAULT_RETRY_DELAY_SECONDS
    )
    parser.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    feeds = select_feeds(args.only, args.category)

    if args.list:
        print_feed_table(feeds)
        return 0

    staging_root = Path(args.staging_root)
    print(f"iced_stage: {len(feeds)} feed(s) -> {staging_root.as_posix()}/")
    if args.dry_run:
        print_feed_table(feeds)
        print("(dry-run: nothing fetched)")
        return 0

    records: list[dict[str, object]] = []
    failures: list[str] = []
    for feed in feeds:
        try:
            rec = stage_feed(
                feed,
                staging_root=staging_root,
                force=args.force,
                retries=args.retries,
                retry_delay_seconds=args.retry_delay_seconds,
                timeout_seconds=args.timeout_seconds,
            )
            records.append(rec)
            enc = " [encrypted; needs backend decrypt]" if feed.encrypted else ""
            print(f"  {rec['status']:>7}  {feed.name}  ({rec['bytes']} bytes){enc}")
        except (RuntimeError, OSError) as exc:
            failures.append(feed.name)
            print(f"  FAILED   {feed.name}: {exc}", file=sys.stderr)

    if records:
        log_path = write_run_log(staging_root, records)
        print(f"run-log: {log_path.as_posix()}")
    if failures:
        print(f"iced_stage: {len(failures)} feed(s) FAILED: {failures}", file=sys.stderr)
        return 1
    print("iced_stage: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
