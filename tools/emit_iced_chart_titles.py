"""Emit `datasets/reference/in/iced-chart-titles.json` from ICED's `/chart-title` endpoint.

NITI Aayog's ICED dashboard exposes a 296 KB metadata blob listing every
chart on the public site with its page, section, title, subtitle,
footnote, and source attribution. This tool snapshots that blob into a
schema-validated reference dataset so yen-gov adapters can quote ICED's
own publisher-printed footnotes/source labels verbatim in indicator
artifacts (per CLAUDE.md §10 — adapter owns publisher vocabulary).

Idempotent: re-running with byte-identical upstream produces a
byte-identical artifact. The per-request `fetched_at` does drift on
re-fetch (the Fetcher's known smear bug, documented in
/memories/lessons.md 2026-05-16); fixing it is out of scope here.

Output: datasets/reference/in/iced-chart-titles.json (schema
iced-chart-titles.schema.json v1.0).
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from yen_gov.core.schema_registry import schema_id, schema_version  # noqa: E402
from yen_gov.sources.iced_common import IcedClient  # noqa: E402

OUT_PATH = REPO_ROOT / "datasets" / "reference" / "in" / "iced-chart-titles.json"
SCHEMA_FILE = "iced-chart-titles.schema.json"

# Field whitelist matching the schema. ICED occasionally adds new keys to
# its bundle; we drop anything not in the schema so the artifact stays
# stable as upstream evolves additively.
KEEP_FIELDS = (
    "id", "page", "section", "url", "tabs",
    "section_title", "section_subtitle",
    "chart_title", "chart_subtitle",
    "footnote", "source",
)


def main() -> int:
    client = IcedClient()
    resp = client.get("/chart-title")
    raw = resp.decrypted
    if not isinstance(raw, dict) or raw.get("status") not in (1, "success"):
        raise SystemExit(f"unexpected /chart-title envelope: {type(raw).__name__}")
    entries_in = raw.get("data")
    if not isinstance(entries_in, list):
        raise SystemExit(f"/chart-title 'data' is not a list: {type(entries_in).__name__}")

    entries_out: list[dict[str, object]] = []
    for row in entries_in:
        if not isinstance(row, dict):
            continue
        # Required fields must be present and non-empty strings.
        if not all(isinstance(row.get(k), str) and row.get(k) for k in ("id", "page", "section")):
            continue
        entries_out.append({k: row.get(k) for k in KEEP_FIELDS})

    artifact = {
        "$schema": schema_id(SCHEMA_FILE),
        "$schema_version": schema_version(SCHEMA_FILE),
        "sources": [
            {
                "url": resp.url,
                "fetched_at": resp.fetched_at.isoformat().replace("+00:00", "Z"),
                "name": "ICED — chart-title catalogue (NITI Aayog)",
                "authority": "NITI Aayog (India Climate & Energy Dashboard)",
            }
        ],
        "entries": entries_out,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rel = OUT_PATH.relative_to(REPO_ROOT).as_posix()
    print(f"wrote {len(entries_out)} entries -> {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
