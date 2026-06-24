"""Stage one RBI Handbook of Statistics XLSX table into a local dir.

Operator-facing helper. The canonical ingest pipeline never touches the
network (parent plan section 21.4: the network fetcher was deleted in the
rip; ``ingest-rbi-hbs`` reads operator-staged local files only). This tool
is the *separate* staging step the operator runs by hand: it fetches one
public RBI Handbook table and saves it under a year-tagged staging dir with
the filename the ingest spec expects. ``ingest-rbi-hbs`` then reads those
local files - it still imports nothing from here and reaches no network.

Three parameters, exactly the operator's mental model:

  --url     the public RBI XLSX link (from the Handbook page's "Document"
            link, e.g. https://rbidocs.rbi.org.in/rdocs/.../2T_...XLSX)
  --year    the Handbook edition (e.g. 2024-25); the file lands under
            ``<staging-root>/<year>/`` so multiple editions coexist
  --rename  the filename to save as - match the ingest spec's
            ``staging_filename`` (e.g. table-birth-rate.xlsx)

The RBI edge serves an HTML interstitial unless the request carries a
browser User-Agent and an rbi.org.in Referer, so both are sent by default.
The download is written to ``<target>.partial``, validated as a real XLSX
(ZIP magic), then atomically moved into place; a half-written file never
masquerades as staged. Re-running is a no-op when a valid file is already
staged (use --force to re-fetch).

Standalone: argparse + stdlib urllib only. No backend imports (tools/ rule).

Example::

    python tools/rbi_handbook_stage.py \\
      --url "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/2T_...XLSX" \\
      --year 2024-25 \\
      --rename table-birth-rate.xlsx
"""
from __future__ import annotations

import argparse
import http.client
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# RBI's edge returns an HTML page unless these are present.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
DEFAULT_REFERER = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
    "?head=Handbook+of+Statistics+on+Indian+States"
)
DEFAULT_STAGING_ROOT = ".runtime/raw/rbi/handbook-states"
DEFAULT_RETRIES = 5
DEFAULT_RETRY_DELAY_SECONDS = 6
DEFAULT_TIMEOUT_SECONDS = 120

# A real .xlsx is a ZIP container; these are the first bytes of a local
# file header. The RBI HTML interstitial begins with "<!DOCTYPE", so this
# magic check is what distinguishes a genuine download from a blocked one.
_XLSX_MAGIC = b"PK\x03\x04"


def staged_path(staging_root: Path, year: str, rename: str) -> Path:
    """Return ``<staging_root>/<year>/<rename>`` for one staged table.

    The year segment lets multiple Handbook editions sit side by side; the
    ingest CLI is then pointed at ``--staging-dir <staging_root>/<year>``.
    """
    return staging_root / year / rename


def is_xlsx_bytes(data: bytes) -> bool:
    """True when ``data`` starts with the ZIP/XLSX local-file-header magic."""
    return data.startswith(_XLSX_MAGIC)


def build_request(url: str, *, referer: str) -> urllib.request.Request:
    """Build the GET request with the browser headers RBI's edge requires."""
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Accept": (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet,*/*"
            ),
        },
    )


def fetch_xlsx_bytes(
    url: str,
    *,
    referer: str,
    retries: int,
    retry_delay_seconds: int,
    timeout_seconds: int,
) -> bytes:
    """Fetch ``url`` and return its bytes, retrying transient edge failures.

    RBI's edge intermittently closes the connection abruptly under load;
    that surfaces as ``URLError`` / ``OSError`` / an ``http.client``
    exception. Those are retried. A non-XLSX body (the HTML interstitial)
    is also retried, since it usually means a transient block. A genuine
    ``HTTPError`` other than 429/503 is raised immediately.

    Raises:
        RuntimeError: every attempt failed (loud, never a silent empty file).
    """
    last_error: str = "no attempts made"
    for attempt in range(1, retries + 1):
        try:
            request = build_request(url, referer=referer)
            with urllib.request.urlopen(
                request, timeout=timeout_seconds
            ) as response:
                body = response.read()
            if is_xlsx_bytes(body):
                return body
            sample = body[:32].decode("utf-8", errors="replace").strip()
            last_error = f"not an XLSX (got {sample!r}); edge likely blocked"
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


def stage_table(
    *,
    url: str,
    target: Path,
    referer: str,
    force: bool,
    retries: int,
    retry_delay_seconds: int,
    timeout_seconds: int,
) -> str:
    """Download ``url`` into ``target`` atomically; return a status word.

    Returns ``"skipped"`` when a valid XLSX is already staged and ``force``
    is false, else ``"staged"``. Writes ``<target>.partial`` first and only
    renames after the magic check passes, so an interrupted run never leaves
    a file that looks staged.
    """
    if target.exists() and not force:
        if is_xlsx_bytes(target.read_bytes()[:8]):
            return "skipped"
    body = fetch_xlsx_bytes(
        url,
        referer=referer,
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
        timeout_seconds=timeout_seconds,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.partial")
    partial.write_bytes(body)
    partial.replace(target)
    return "staged"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stage one public RBI Handbook XLSX table into a local dir for "
            "the ingest-rbi-hbs command (no network in the ingest itself)."
        ),
    )
    parser.add_argument(
        "--url",
        required=True,
        help='Public RBI XLSX link (the Handbook page "Document" link).',
    )
    parser.add_argument(
        "--year",
        required=True,
        help="Handbook edition tag, e.g. 2024-25; becomes a path segment.",
    )
    parser.add_argument(
        "--rename",
        required=True,
        help=(
            "Filename to save as; match the ingest spec staging_filename "
            "(e.g. table-birth-rate.xlsx)."
        ),
    )
    parser.add_argument(
        "--staging-root",
        default=DEFAULT_STAGING_ROOT,
        help=f"Staging root dir (default: {DEFAULT_STAGING_ROOT}).",
    )
    parser.add_argument(
        "--referer",
        default=DEFAULT_REFERER,
        help="Referer header sent to the RBI edge (default: Handbook page).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if a valid XLSX is already staged.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Max download attempts (default: {DEFAULT_RETRIES}).",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=int,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help=f"Delay between attempts (default: {DEFAULT_RETRY_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-request timeout (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    target = staged_path(Path(args.staging_root), args.year, args.rename)
    print(f"staging {args.rename} (edition {args.year}) -> {target.as_posix()}")
    try:
        status = stage_table(
            url=args.url,
            target=target,
            referer=args.referer,
            force=args.force,
            retries=args.retries,
            retry_delay_seconds=args.retry_delay_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    except RuntimeError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    size = target.stat().st_size
    print(f"  {status}: {size} bytes")
    print(
        "  next: python -m yen_gov ingest-rbi-hbs --root . "
        f"--staging-dir {(Path(args.staging_root) / args.year).as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
