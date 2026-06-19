"""Committed per-adapter year-checkpoint receipt (plan D4, Row 2).

A checkpoint is the pipeline's memory of "which years of this source have I
already pulled, and what did the raw bytes hash to?". It lives committed at
``datasets/_ops/ingest-state/<adapter_slug>.json`` and drives three behaviours
the autonomous ingest engine needs:

* **Delta-skip.** A re-run SKIPS a year iff the stored ``raw_sha256`` equals the
  hash of the freshly fetched raw payload AND that year is ``completed``
  (:func:`should_skip_year`). Nothing is re-parsed, re-enriched, or re-written.
* **Re-open on revision.** A CHANGED hash on an already-completed OLD year means
  the publisher restated it; the predicate returns ``False`` so the orchestrator
  re-processes that year (a provisional estimate becoming revised).
* **Resume.** A run that failed partway left some years ``completed=False``; a
  re-run re-processes exactly those (the skip predicate refuses to skip an
  incomplete year), so ``ingest run --resume`` continues from the last good year.

Design rulings (Gregor = contracts, Fowler = craft), baked here so a later row
does not re-litigate them:

* **Plain dict, not pydantic.** Plan D3 lists the JSON-Schema / ``x-version`` /
  ``_ops`` / ``manifest.json`` artifacts among the four data-contract seams that
  stay NON-pydantic. The checkpoint is exactly such an ``_ops`` artifact: it is
  round-tripped as a dict and validated by ``ingest-state.schema.json`` +
  ``tier_b_ingest_state_receipt``, mirroring ``operator_state`` /
  ``lgd-parse-receipt``. So this module speaks dicts.
* **Skip is raw-hash-only.** Row 2's spec defines the skip predicate purely as
  "stored raw_sha256 == fresh raw_sha256". ``spec_version`` is STORED on the
  checkpoint (a bump re-opens all years per Row 5) but is NOT folded into the
  skip predicate here -- the delta engine that consumes a spec bump is Row 5.
* **Pure mutators; caller owns the clock.** :func:`advance_year` and
  :func:`touch_year` are pure (deep-copy in, new dict out) and take
  ``last_checked`` as an argument. The wall-clock lives in :func:`now_iso_z`
  (the allowed ``_ops`` control-plane ``datetime.now()`` carve-out, CLAUDE.md);
  keeping it out of the mutators makes the skip/re-open/staleness behaviour
  deterministically testable.
* **Staleness never hides.** ``last_checked`` advances on EVERY check -- a SKIP
  still calls :func:`touch_year`. The staleness clock is the file's reason to
  exist, so a per-check touch is the contract, not spurious churn.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from yen_gov.core.schema_registry import schema_version

#: Committed checkpoint home, relative to the repo root (POSIX, CLAUDE.md sec 2).
CHECKPOINT_DIR = PurePosixPath("datasets/_ops/ingest-state")

#: The schema basename; the registry resolves ``x-version`` from it (no literals).
SCHEMA_FILENAME = "ingest-state.schema.json"

#: Value stamped into a written checkpoint's ``$schema`` field. The Tier-B
#: validator resolves a data file's schema by basename, so this matches the
#: ``_ops`` convention (e.g. ``./operator-state.schema.json``).
SCHEMA_REF = f"./{SCHEMA_FILENAME}"


def now_iso_z() -> str:
    """Return the current UTC time as an ISO-8601 ``...Z`` string.

    The single wall-clock seam for the checkpoint's ``last_checked`` staleness
    field. This is the allowed control-plane ``datetime.now()`` carve-out: the
    checkpoint is operator telemetry under ``_ops/``, never observation
    provenance. Kept out of the pure mutators so tests stay deterministic.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_payload(raw: bytes) -> str:
    """Return the sha256 hexdigest of a RAW fetched upstream payload.

    Hash the bytes BEFORE any parse/canonicalisation -- the checkpoint compares
    the upstream's raw shape, so a cosmetic re-encode upstream legitimately
    re-opens the year while a byte-identical re-fetch skips it.
    """
    return hashlib.sha256(raw).hexdigest()


def checkpoint_path(adapter_slug: str, root: Path) -> Path:
    """Return the on-disk path of ``adapter_slug``'s checkpoint under ``root``."""
    return root / Path(CHECKPOINT_DIR) / f"{adapter_slug}.json"


def empty_checkpoint(adapter_slug: str, spec_version: str = "") -> dict[str, Any]:
    """Return an in-memory checkpoint scaffold with no years recorded yet."""
    return {"adapter_slug": adapter_slug, "spec_version": spec_version, "years": []}


def load(adapter_slug: str, root: Path) -> dict[str, Any]:
    """Load ``adapter_slug``'s checkpoint, or an empty scaffold if absent.

    Returns a plain dict. The on-disk ``$schema`` / ``$schema_version`` stamps
    are preserved when present so a round-trip is lossless.
    """
    path = checkpoint_path(adapter_slug, root)
    if not path.is_file():
        return empty_checkpoint(adapter_slug)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(
            f"checkpoint {PurePosixPath(CHECKPOINT_DIR, f'{adapter_slug}.json').as_posix()} "
            f"is not a JSON object"
        )
    data.setdefault("adapter_slug", adapter_slug)
    data.setdefault("spec_version", "")
    data.setdefault("years", [])
    return data


def find_year(checkpoint: dict[str, Any], year: int) -> dict[str, Any] | None:
    """Return the year entry for ``year``, or ``None`` if not yet recorded."""
    for entry in checkpoint.get("years", []):
        if isinstance(entry, dict) and entry.get("year") == year:
            return entry
    return None


def should_skip_year(checkpoint: dict[str, Any], year: int, raw_payload: bytes) -> bool:
    """Return True iff ``year`` can be SKIPPED for this freshly fetched payload.

    Skip iff the year is already ``completed`` AND its stored ``raw_sha256``
    equals the hash of ``raw_payload``. A new year (absent), an incomplete year
    (a failed mid-run, so ``--resume`` re-processes it), or a changed hash (the
    publisher revised the year) all return ``False`` -> the caller processes it.
    """
    entry = find_year(checkpoint, year)
    if entry is None:
        return False
    if not entry.get("completed", False):
        return False
    return entry.get("raw_sha256") == hash_payload(raw_payload)


def advance_year(
    checkpoint: dict[str, Any],
    *,
    year: int,
    raw_payload: bytes,
    completed: bool,
    last_checked: str,
    estimate_status: str | None = None,
) -> dict[str, Any]:
    """Return a NEW checkpoint with ``year`` recorded/updated (process path).

    Upserts the year entry: ``raw_sha256`` = ``hash_payload(raw_payload)``,
    ``completed`` and ``last_checked`` as given, ``estimate_status`` set when
    provided (omitted otherwise). Years are kept sorted ascending. The input
    checkpoint is not mutated.
    """
    updated = copy.deepcopy(checkpoint)
    entry: dict[str, Any] = {
        "year": year,
        "raw_sha256": hash_payload(raw_payload),
        "completed": completed,
        "last_checked": last_checked,
    }
    if estimate_status is not None:
        entry["estimate_status"] = estimate_status
    _upsert_year(updated, entry)
    return updated


def touch_year(
    checkpoint: dict[str, Any],
    *,
    year: int,
    last_checked: str,
) -> dict[str, Any]:
    """Return a NEW checkpoint advancing ONLY ``year``'s ``last_checked``.

    The skip path: the payload is unchanged so ``raw_sha256`` / ``completed`` /
    ``estimate_status`` are preserved, but the staleness clock still ticks so a
    skip never hides staleness. Raises ``ValueError`` if ``year`` was never
    recorded -- a skip presupposes a prior recorded hash to compare against.
    """
    entry = find_year(checkpoint, year)
    if entry is None:
        raise ValueError(
            f"cannot touch year {year}: not recorded in checkpoint "
            f"{checkpoint.get('adapter_slug')!r}"
        )
    updated = copy.deepcopy(checkpoint)
    touched = find_year(updated, year)
    assert touched is not None  # deep-copied from the same shape
    touched["last_checked"] = last_checked
    return updated


def write(checkpoint: dict[str, Any], root: Path) -> Path:
    """Stamp schema metadata and persist ``checkpoint`` under ``root``.

    Stamps ``$schema`` + ``$schema_version`` (version sourced from the registry,
    never hand-typed), sorts ``years`` ascending, creates the checkpoint dir if
    needed, and writes pretty JSON with a trailing newline (ASCII-only). Returns
    the written path.
    """
    adapter_slug = checkpoint.get("adapter_slug")
    if not isinstance(adapter_slug, str) or not adapter_slug:
        raise ValueError("checkpoint is missing a non-empty 'adapter_slug'")

    out = copy.deepcopy(checkpoint)
    out["$schema"] = SCHEMA_REF
    out["$schema_version"] = schema_version(SCHEMA_FILENAME)
    out["years"] = sorted(
        out.get("years", []), key=lambda e: e.get("year", 0) if isinstance(e, dict) else 0
    )

    path = checkpoint_path(adapter_slug, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def _upsert_year(checkpoint: dict[str, Any], entry: dict[str, Any]) -> None:
    """Replace the entry for ``entry['year']`` in place, or append; then sort."""
    years = checkpoint.setdefault("years", [])
    for idx, existing in enumerate(years):
        if isinstance(existing, dict) and existing.get("year") == entry["year"]:
            years[idx] = entry
            break
    else:
        years.append(entry)
    years.sort(key=lambda e: e.get("year", 0) if isinstance(e, dict) else 0)
