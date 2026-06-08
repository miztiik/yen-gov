"""LGD (Local Government Directory) district-code -> entity_id resolution.

Single home for the ``lgd_code -> yen_gov entity_id`` mapping that any
NDLM / state-government data ingestor needs to translate publisher
district codes into the canonical ``entity_id`` shape
(``IN-S<n>-D<n>`` / ``IN-U<n>-D<n>``) used by ``ObservationRow``.

**Why a dedicated module** (per plan-doc Q#4, Gregor verdict E, bundled
with Phase 2.A of TODO/20260525-livestock-ndlm-ingest-plan.md):

* The mapping is sourced from ``datasets/taxonomy/entities.json`` -
  the SAME taxonomy the writer's FK gate validates entity_id against.
  Co-locating the resolver here keeps the producer (ingest tooling)
  and the consumer (writer FK gate) reading the same single file.
* The first consumer (an early livestock NDLM meadow tool, retired
  in the G6 tools/ prune 2026-06-08) had an inline
  ``_load_district_lookup()`` shaped exactly like this; the second
  consumer (any future NDLM meadow generator that pulls raw
  district-keyed responses by LGD code) will need the same logic.
  Extracting now keeps the next consumer additive.
* ``ValueError`` on miss (not a default ``None``) - silent misses are
  the canonical undercount trap; the writer's FK gate would catch it
  eventually but with a less actionable error message. Fail at the
  meadow-ingest boundary.

Memoised via ``functools.lru_cache``: ``entities.json`` is ~857 rows,
parsed once per process. The cache key is the resolved repo_root, so
callers passing a ``Path("./datasets/...")`` vs ``Path.cwd() / "..."``
both hit the cache as long as they resolve to the same absolute path
(which is guaranteed by ``Path.resolve()`` at the cache key).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def load_district_lookup(repo_root: Path) -> dict[str, str]:
    """Map LGD district code (string) -> yen-gov entity_id.

    Reads ``<repo_root>/datasets/taxonomy/entities.json`` and returns
    one entry per district that carries a non-null ``lgd_code``. Entries
    for country / state / UT / block / village are skipped (those are
    not LGD-district-coded). Entries with ``lgd_code: null`` are also
    skipped silently (defensive - the taxonomy may carry pre-LGD legacy
    districts that map by some other key).

    Cached via ``functools.lru_cache``; pass a resolved (absolute) repo
    root to avoid duplicate parses. The cache holds at most 8 entries
    (one per repo_root) - more than enough for any real workload.

    Raises:
        FileNotFoundError if ``entities.json`` is absent at the
        expected path.
        ValueError if the file is present but its JSON shape is not
        ``{"entities": [...]}`` (defensive - the taxonomy schema
        guarantees this shape, but a corrupted file should not silently
        return an empty dict).
    """
    entities_path = repo_root / "datasets" / "taxonomy" / "entities.json"
    data = json.loads(entities_path.read_text(encoding="utf-8"))
    if "entities" not in data or not isinstance(data["entities"], list):
        raise ValueError(
            f"Malformed entities.json at {entities_path}: "
            f"expected top-level 'entities' list, got keys {list(data.keys())}"
        )
    return {
        e["lgd_code"]: e["entity_id"]
        for e in data["entities"]
        if e.get("entity_type") == "district" and e.get("lgd_code")
    }


def resolve_district(lgd_code: str, district_lookup: dict[str, str]) -> str:
    """Translate an LGD district code to the canonical yen-gov entity_id.

    Args:
        lgd_code: LGD district code as a string (publisher may emit
            either a stringified int or a zero-padded string; the
            lookup is keyed on whatever ``entities.json`` carries -
            usually the plain stringified int).
        district_lookup: result of :func:`load_district_lookup`. Passed
            in (not re-loaded) so each adapter / meadow generator
            decides cache lifecycle.

    Returns:
        entity_id of shape ``IN-S<n>-D<n>`` or ``IN-U<n>-D<n>``.

    Raises:
        ValueError on miss. The error names the missing code AND the
        lookup size so the caller can distinguish "typo" from "empty
        taxonomy load". A silent miss would be a canonical undercount
        - the bug class this module exists to prevent.
    """
    try:
        return district_lookup[lgd_code]
    except KeyError as exc:
        raise ValueError(
            f"LGD district code {lgd_code!r} not found in entities.json "
            f"(lookup size: {len(district_lookup)} districts). "
            f"Check the publisher response or extend taxonomy/entities.json."
        ) from exc
