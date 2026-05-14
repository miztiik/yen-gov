"""Constants + thin write helper shared by RBI Handbook ingest scripts.

Two URL families to keep distinct (Fowler — pass publication as a parameter):

- ``HBS_IE_LANDING`` → *Handbook of Statistics on Indian Economy* landing page.
  Source for national time series, state SDP, national price indices.
- ``HBS_IS_LANDING`` → *Handbook of Statistics on Indian States* landing page.
  Source for per-state series (power, vital statistics, state finances).

Both URLs encode "+" not "%20" because that is the form RBI's portal canonicalises
to in its own navigation; preserving it avoids a redirect noise line in the
fetched-at history.

``LICENSE_RBI`` is the standard license block stamped on every emitted artifact.
The disclaimer URL is RBI's published terms; ``redistributable: True`` means the
project is permitted to publish derived datasets with attribution, which is what
``sources[].name`` and ``sources[].authority`` carry.

``setup_utf8_stdout()`` reconfigures ``sys.stdout`` to UTF-8 with replace-on-error
so that non-ASCII characters (₹, em-dash, state names with diacritics) print
without crashing on Windows code page 1252. Idempotent; call from each tool's
``main()``.

``write_artifact()`` is intentionally thin — it just JSON-dumps and prints a
one-line summary. The full artifact dict is composed in each caller (the
``$schema`` URL, ``coverage`` block, and ``indicator`` block vary too much
between sections to make a generic builder honest).
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

HBS_IE_LANDING = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy"
HBS_IS_LANDING = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States"

LICENSE_RBI = {
    "id": "RBI-publication",
    "name": "Reserve Bank of India publication (open for non-commercial use with attribution)",
    "url": "https://www.rbi.org.in/Scripts/Disclaimer.aspx",
    "redistributable": True,
}


def setup_utf8_stdout() -> None:
    """Force ``sys.stdout`` to UTF-8 with errors='replace'. Safe to call repeatedly."""
    if isinstance(sys.stdout, io.TextIOWrapper) and sys.stdout.encoding.lower() == "utf-8":
        return
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def write_artifact(out_path: Path, artifact: dict) -> None:
    """JSON-dump ``artifact`` to ``out_path`` and print a one-line summary.

    Creates parent directories. Uses 2-space indent + a trailing newline (the
    convention the rest of ``datasets/`` follows).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = artifact.get("rows", [])
    times = sorted({r["time"] for r in rows}) if rows else []
    entities = sorted({r["entity_id"] for r in rows}) if rows else []
    span = f"{times[0]}..{times[-1]}" if times else "(empty)"
    print(f"  wrote {out_path}  rows={len(rows)} entities={len(entities)} span={span}")
