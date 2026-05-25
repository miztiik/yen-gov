"""Download a data.gov.in OGD resource as a paged CSV.

Agent-oriented helper for resources that expose the standard endpoint:

    https://api.data.gov.in/resource/<resource_uuid>

The API key must come from an environment variable, not from committed code.
The downloader writes ``<output>.partial`` while paging and only replaces the
final output after the row count matches the API metadata total.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


API_ROOT = "https://api.data.gov.in/resource"
DEFAULT_KEY_ENV = "DATAGOVIN_API_KEY"
DEFAULT_LIMIT = 10_000
DEFAULT_DELAY_SECONDS = 60
DEFAULT_RETRIES = 4
USER_AGENT = "Mozilla/5.0 yen-gov-datagovin-downloader"


@dataclass(frozen=True)
class ResourceMetadata:
    total: int
    columns: tuple[str, ...]
    title: str
    updated_date: str | None


def build_url(
    *,
    resource_uuid: str,
    api_key: str,
    offset: int,
    limit: int,
    response_format: str,
) -> str:
    params = urllib.parse.urlencode(
        {
            "api-key": api_key,
            "offset": str(offset),
            "limit": str(limit),
            "format": response_format,
        }
    )
    return f"{API_ROOT}/{resource_uuid}?{params}"


def fetch_bytes(url: str, *, timeout_seconds: int) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def fetch_metadata(
    *,
    resource_uuid: str,
    api_key: str,
    timeout_seconds: int,
) -> ResourceMetadata:
    body, content_type = fetch_bytes(
        build_url(
            resource_uuid=resource_uuid,
            api_key=api_key,
            offset=0,
            limit=1,
            response_format="json",
        ),
        timeout_seconds=timeout_seconds,
    )
    if "json" not in content_type.lower():
        raise RuntimeError(f"metadata response was not JSON: {content_type!r}")
    payload = json.loads(body.decode("utf-8"))
    records = payload.get("records") or []
    if not records:
        raise RuntimeError("metadata probe returned no records")
    total = int(payload["total"])
    columns = tuple(records[0].keys())
    title = str(payload.get("title") or resource_uuid)
    updated_date = payload.get("updated_date")
    return ResourceMetadata(
        total=total,
        columns=columns,
        title=title,
        updated_date=str(updated_date) if updated_date is not None else None,
    )


def parse_csv_page(body: bytes) -> tuple[tuple[str, ...], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
    if not rows:
        raise RuntimeError("empty CSV page")
    return tuple(rows[0]), rows[1:]


def read_partial_row_count(partial_path: Path, *, expected_header: tuple[str, ...]) -> int:
    if not partial_path.exists() or partial_path.stat().st_size == 0:
        return 0

    with partial_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = tuple(next(reader))
        except StopIteration:
            return 0
        if header != expected_header:
            raise RuntimeError(f"partial header mismatch: {header!r}")

        rows = 0
        for row in reader:
            if len(row) != len(expected_header):
                raise RuntimeError(
                    f"partial row {rows + 1} has {len(row)} columns; "
                    f"expected {len(expected_header)}"
                )
            rows += 1
        return rows


def request_csv_page(
    *,
    resource_uuid: str,
    api_key: str,
    offset: int,
    limit: int,
    expected_header: tuple[str, ...],
    timeout_seconds: int,
    retries: int,
    retry_delay_seconds: int,
) -> tuple[list[list[str]], int, str]:
    url = build_url(
        resource_uuid=resource_uuid,
        api_key=api_key,
        offset=offset,
        limit=limit,
        response_format="csv",
    )
    for attempt in range(1, retries + 1):
        try:
            body, content_type = fetch_bytes(url, timeout_seconds=timeout_seconds)
            if "csv" not in content_type.lower() and not body.startswith(b"circlename,"):
                sample = body[:160].decode("utf-8", errors="replace").replace("\n", " | ")
                raise RuntimeError(
                    f"non-CSV response at offset {offset}: "
                    f"content_type={content_type!r} sample={sample!r}"
                )
            header, rows = parse_csv_page(body)
            if header != expected_header:
                raise RuntimeError(f"CSV header mismatch at offset {offset}: {header!r}")
            return rows, len(body), content_type
        except urllib.error.HTTPError as exc:
            print(f"offset={offset} attempt={attempt} http_status={exc.code}", flush=True)
            if exc.code != 429 or attempt == retries:
                raise
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            print(
                f"offset={offset} attempt={attempt} transient_error={type(exc).__name__}",
                flush=True,
            )
            if attempt == retries:
                raise
        print(f"offset={offset} retry_delay={retry_delay_seconds}s", flush=True)
        time.sleep(retry_delay_seconds)
    raise AssertionError("unreachable retry loop")


def download_resource(
    *,
    resource_uuid: str,
    output_path: Path,
    api_key: str,
    limit: int,
    delay_seconds: int,
    timeout_seconds: int,
    retries: int,
    initial_delay_seconds: int,
) -> None:
    metadata = fetch_metadata(
        resource_uuid=resource_uuid,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    expected_header = metadata.columns
    partial_path = output_path.with_name(f"{output_path.name}.partial")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written_rows = read_partial_row_count(partial_path, expected_header=expected_header)
    mode = "a" if written_rows else "w"

    print(f"resource_uuid={resource_uuid}")
    print(f"title={metadata.title}")
    print(f"updated_date={metadata.updated_date}")
    print(f"total={metadata.total}")
    print(f"columns={','.join(expected_header)}")
    print(f"output={output_path}")
    print(f"partial={partial_path}")
    print(f"already_rows={written_rows}")
    print(f"limit={limit} delay_seconds={delay_seconds}")

    if initial_delay_seconds:
        print(f"initial_delay={initial_delay_seconds}s", flush=True)
        time.sleep(initial_delay_seconds)

    with partial_path.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if written_rows == 0:
            writer.writerow(expected_header)
            handle.flush()
            os.fsync(handle.fileno())

        page_number = 0
        while written_rows < metadata.total:
            if page_number > 0 and delay_seconds:
                print(f"between_page_delay={delay_seconds}s", flush=True)
                time.sleep(delay_seconds)

            remaining = metadata.total - written_rows
            page_limit = min(limit, remaining)
            page_number += 1
            print(
                f"requesting page={page_number} offset={written_rows} limit={page_limit}",
                flush=True,
            )
            rows, byte_count, content_type = request_csv_page(
                resource_uuid=resource_uuid,
                api_key=api_key,
                offset=written_rows,
                limit=page_limit,
                expected_header=expected_header,
                timeout_seconds=timeout_seconds,
                retries=retries,
                retry_delay_seconds=delay_seconds,
            )
            if len(rows) != page_limit:
                raise RuntimeError(
                    f"expected {page_limit} rows at offset {written_rows}; got {len(rows)}"
                )
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
            written_rows += len(rows)
            print(
                f"page={page_number} rows={len(rows)} bytes={byte_count} "
                f"ct={content_type} cumulative_rows={written_rows}",
                flush=True,
            )

    raw = partial_path.read_bytes()
    line_count = raw.count(b"\n")
    if line_count != metadata.total + 1:
        raise RuntimeError(f"expected {metadata.total + 1} lines; found {line_count}")

    sha256 = hashlib.sha256(raw).hexdigest()
    if output_path.exists():
        output_path.unlink()
    partial_path.replace(output_path)
    print(f"assembled={output_path}")
    print(f"data_rows={metadata.total}")
    print(f"lines={line_count}")
    print(f"bytes={output_path.stat().st_size}")
    print(f"sha256={sha256}")
    print("OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource_uuid", help="data.gov.in resource UUID")
    parser.add_argument("--output", required=True, type=Path, help="CSV output path")
    parser.add_argument("--api-key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument("--limit", default=DEFAULT_LIMIT, type=int)
    parser.add_argument("--delay-seconds", default=DEFAULT_DELAY_SECONDS, type=int)
    parser.add_argument("--initial-delay-seconds", default=DEFAULT_DELAY_SECONDS, type=int)
    parser.add_argument("--timeout-seconds", default=180, type=int)
    parser.add_argument("--retries", default=DEFAULT_RETRIES, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is required")
    download_resource(
        resource_uuid=args.resource_uuid,
        output_path=args.output,
        api_key=api_key,
        limit=args.limit,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
        initial_delay_seconds=args.initial_delay_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())