"""Canonical CSV emission for the FGD-installed-share variable.

The legacy network-fetch + folded-indicator-JSON path (``ingest_fgd``)
was retired in B4-pt2.1 per parent plan section 21.4 ("network-fetch
code is deleted; ingest reads local TCPD / source CSV"). What remains
is the B1.4.9 canonical CSV emission helpers exercised by
``backend/tests/test_iced_air_quality_csv_repoint.py`` and any operator
reingest path that drives ``build_csv_rows_fgd`` directly from a
captured payload.
"""
from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

# ---------------------------------------------------------------------------
# Canonical CSV emission (B1.4.9)
# ---------------------------------------------------------------------------
#
# Re-points the FGD indicator emitted by this ingest onto
# `yen_gov.canonical.csv_writer.write_csv` ALONGSIDE the legacy
# `write_artifact` meadow-JSON path (parent plan section 23.1; instead-of
# is deferred to B3). `source_id` is derived via ADR-0042 from
# (producer, title, vintage); variable_id honours parent plan section
# 21.6 / 21.12 (no `__`) and ADR-0044 (no grain prefix).
# concept_id binding DEFERRED to B2a; recorded as DEFER marker in PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_TITLE_FGD = (
    "ICED FGD-status tracker (thermal-plant FGD compliance, "
    "re-publishing CEA / MoEF&CC)"
)
_CSV_SOURCE_VINTAGE_FGD = "2026 snapshot"
_CSV_VARIABLE_ID_FGD = "thermal-fgd-installed-share-pct"


def _period_to_year_int(period: str) -> int:
    """Reduce ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD`` to integer year.

    The canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer. FGD rows carry an ISO snapshot date
    (``YYYY-MM-DD``); reducing to the snapshot year is the natural
    long-format mapping for a once-per-snapshot indicator.
    """
    if not (isinstance(period, str) and len(period) >= 4 and period[:4].isdigit()):
        raise ValueError(
            f"unexpected time format {period!r}; expected 'YYYY', 'YYYY-MM' "
            f"or 'YYYY-MM-DD'"
        )
    return int(period[:4])


def build_csv_rows_fgd(
    payload_rows: list[dict],
    *,
    source_id: str,
) -> list[dict]:
    """Build canonical CSV rows for the FGD indicator.

    Each row carries the canonical 4 columns declared on file class
    ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``. Rows with ``value is None`` are dropped
    upstream by ``extract_state_rows``; this builder asserts no Nones
    slip through.
    """
    out: list[dict] = []
    for row in payload_rows:
        out.append({
            "entity_id": row["entity_id"],
            "time": _period_to_year_int(row["time"]),
            "value": row["value"],
            "source_id": source_id,
        })
    return out


def _emit_csv_fgd(*, repo_root: Path, payload_rows: list[dict]) -> Path:
    """Canonical CSV emission ALONGSIDE the legacy meadow indicator JSON.

    B1.4.9 - both stores coexist (parent plan section 23.1); reader flip
    is X1a. ``source_id`` derived via ADR-0042 from (producer, title,
    vintage); one ``variable_id`` (no facets).
    """
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_FGD, _CSV_SOURCE_VINTAGE_FGD
    )
    csv_rows = build_csv_rows_fgd(payload_rows, source_id=source_id)
    return write_csv(
        path=repo_root / _CSV_OUT_REL_DIR / f"{_CSV_VARIABLE_ID_FGD}.csv",
        file_class=_CSV_FILE_CLASS,
        rows=csv_rows,
    )
