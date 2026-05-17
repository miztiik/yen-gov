"""Small kit of pure helpers shared across ICED parsers.

Extracted 2026-05-17 from the verified duplication in `iced_power/parsers.py`,
`iced_socio/parsers.py`, and (read-only reference for `fy_to_period`)
`iced_state_wise/parsers.py`. Three concrete callers per helper at the
moment of extraction; `iced_state_wise` keeps its own strict variant because
it relies on raise-on-bad-input semantics rather than return-None semantics.

Doctrine (CLAUDE.md):
- §10 publisher-vocabulary: these helpers do NOT normalise ICED's source
  strings (kebab-case fuel sources, FY labels, etc.) — they parse them
  into the schema's time grammar but the upstream label survives in
  `facet` / `period_label` per Holy Law §10.
- §15 test discipline: every helper here ships with a unit test in
  `backend/tests/test_parser_kit.py` covering the boundary cases the
  per-adapter copies historically caught (bare YYYY input, YYYY-YY input,
  int input, garbage input, dedup last-write-wins ordering).

Adapter-specific quirks (envelope unwrapping for the AES-encrypted
endpoints vs. the JSON-direct v1 endpoints, sub-list flattening,
sector/sub-sector pivots) deliberately stay in the per-adapter parsers.
A declarative endpoint_spec engine was explicitly rejected in the
2026-05-17 design (TODO/20260517-iced-bulk-ingest-and-parity-oracle.md
§8 rejected #6) — ICED envelopes are too variable.

Public surface:

- :func:`fy_to_period`  — tolerant `"YYYY-YY"` / `"YYYY"` / int → period string.
- :func:`row`           — canonical row dict (additionalProperties-safe).
- :func:`dedup_sort`    — last-write-wins dedup on (entity_id, time, facet).
- :func:`unwrap_data`   — `{status, data}` envelope unwrap, else passthrough.
"""
from __future__ import annotations

import re
from typing import Any, Literal


__all__ = ("fy_to_period", "row", "dedup_sort", "unwrap_data")


_FY_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_RE = re.compile(r"^(\d{4})$")


def fy_to_period(
    raw: Any,
    *,
    time_grain: Literal["fiscal_year", "year"] = "fiscal_year",
) -> str | None:
    """Tolerant ICED period normaliser.

    Accepts `int` years, `"YYYY"` strings, or `"YYYY-YY"` FY labels.
    Returns the schema-valid period string for the requested ``time_grain``
    (``"YYYY-04"`` for ``fiscal_year``, ``"YYYY"`` for ``year``), or
    ``None`` if the input does not parse — caller decides whether to skip
    + count or escalate.

    Unlike :func:`yen_gov.sources.iced_common.entities.fy_to_period` (which
    raises :class:`ValueError` on bad input), this is the *tolerant*
    variant used by per-endpoint parsers that prefer to drop the row over
    failing the artifact.
    """
    if isinstance(raw, bool):                             # bool ⊂ int — exclude
        return None
    if isinstance(raw, int):
        s = str(raw)
    elif isinstance(raw, str):
        s = raw.strip()
    else:
        return None

    fy = _FY_RE.match(s)
    if fy:
        year = int(fy.group(1))
        return f"{year:04d}-04" if time_grain == "fiscal_year" else f"{year:04d}"

    yr = _YEAR_RE.match(s)
    if yr:
        year = int(yr.group(1))
        return f"{year:04d}-04" if time_grain == "fiscal_year" else f"{year:04d}"

    return None


def row(
    *,
    entity_id: str,
    time: str,
    value: float | None,
    facet: str | None = None,
    vintage: str | None = None,
    period_label: str | None = None,
) -> dict[str, Any]:
    """Build one canonical indicator row dict.

    Keys are emitted in canonical order so downstream JSON serialisation is
    stable across adapters: ``entity_id``, ``time``, ``value``, then any
    of the optional fields (``facet``, ``vintage``, ``period_label``) that
    were supplied. ``additionalProperties: false`` in the schema rejects
    any unknown key, so we never emit defaults here — only what the caller
    explicitly provided.
    """
    out: dict[str, Any] = {"entity_id": entity_id, "time": time, "value": value}
    if facet is not None:
        out["facet"] = facet
    if vintage is not None:
        out["vintage"] = vintage
    if period_label is not None:
        out["period_label"] = period_label
    return out


def dedup_sort(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable last-write-wins dedup on (entity_id, time, facet); sorted output.

    The "last-write-wins" semantics matches what every existing ICED
    parser does today — when ICED ships duplicate (state, year, source)
    triples (which it occasionally does, e.g. when a sub-sector total is
    repeated under two parent buckets), we keep the most-recent value as
    it appeared in the raw payload. Callers feed rows in payload order.
    """
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r["entity_id"], r["time"], r.get("facet") or "")
        by_key[key] = r
    return sorted(
        by_key.values(),
        key=lambda r: (r["entity_id"], r["time"], r.get("facet") or ""),
    )


def unwrap_data(decrypted: Any) -> Any:
    """Return ``decrypted["data"]`` if it's a ``{status, data}`` envelope, else ``decrypted``.

    ICED's `/api/...` endpoints wrap their payload in an envelope; the v1
    JSON-direct endpoints (e.g. ``/v1/capacity-metatable-data``) ship the
    payload at the top level. Parsers that may receive either call this
    once; parsers that only ever consume v1 may skip it.
    """
    if isinstance(decrypted, dict) and "data" in decrypted:
        return decrypted["data"]
    return decrypted
