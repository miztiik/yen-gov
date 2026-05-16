"""Generate ICED NAMP air-quality artifacts from the captured fixture.

One-shot utility used to ship the NO2 / SO2 / PM10 sibling indicators
without a live fetch (the live ICED endpoint is slow / unreliable from
some environments). Loads the 2026-05-15 markers snapshot, calls the
shared parser per pollutant, and writes the artifact through the same
`write_artifact` chokepoint the live `ingest_*` functions use. The
`fetched_at` stamped on `sources[]` matches the PM2.5 artifact's
capture timestamp so all four NAMP-derived indicators share a single
provenance snapshot.

Live `ingest_no2 / ingest_so2 / ingest_pm10` in
`markers_ingest.py` remain the canonical entry points for future
refreshes; this script is for the first-touch artifact emission only.

Usage (from repo root):
    python tools/iced_aq_emit_from_fixture.py [no2|so2|pm10|all]
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# UTF-8 stdout (Windows cp1252 chokes on µ / ₂ / ³)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.core.io import Source, write_artifact  # noqa: E402
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version  # noqa: E402
from yen_gov.sources.iced_air_quality.markers_ingest import (  # noqa: E402
    CPCB_NAMP_URL,
    MARKERS_API_URL,
    NO2_SERIES_START_YEAR,
    _build_no2_payload,
)
from yen_gov.sources.iced_air_quality.markers_parsers import (  # noqa: E402
    NO2_FIELD,
    PM10_FIELD,
    SO2_FIELD,
    aggregate_state_year_mean,
)
from yen_gov.sources.iced_common import ICEDShapeError  # noqa: E402

FIXTURE_PATH = (
    REPO_ROOT
    / "backend"
    / "tests"
    / "fixtures"
    / "iced_air_quality"
    / "aq_aqi_map_markers_2026-05-15.json"
)

# Same fetched_at as the PM2.5 artifact already on disk — one snapshot,
# four sibling indicators.
SNAPSHOT_FETCHED_AT = datetime(2026, 5, 15, 14, 44, 39, tzinfo=timezone.utc)


def _write(*, out_filename: str, payload: dict) -> Path:
    out_path = (
        REPO_ROOT
        / "datasets"
        / "indicators"
        / "in"
        / "environment"
        / out_filename
    )
    write_artifact(
        path=out_path,
        schema_id=schema_id("indicator.schema.json"),
        schema_version=schema_version("indicator.schema.json"),
        payload=payload,
        sources=[
            Source(url=MARKERS_API_URL, fetched_at=SNAPSHOT_FETCHED_AT),
            Source(url=CPCB_NAMP_URL, fetched_at=SNAPSHOT_FETCHED_AT),
        ],
        schema_for_validation=schema_doc("indicator.schema.json"),
    )
    return out_path


def emit_no2(decrypted: dict) -> Path:
    parsed = [
        r for r in aggregate_state_year_mean(decrypted, pollutant=NO2_FIELD)
        if r.year >= NO2_SERIES_START_YEAR
    ]
    if not parsed:
        raise ICEDShapeError("NO2 aggregation returned zero rows")
    return _write(
        out_filename="state_no2_annual_mean_ug_m3.json",
        payload=_build_no2_payload(parsed=parsed),
    )


def emit_so2(decrypted: dict) -> Path:
    from yen_gov.sources.iced_air_quality.markers_ingest import (
        SO2_SERIES_START_YEAR,
        _build_so2_payload,
    )

    parsed = [
        r for r in aggregate_state_year_mean(decrypted, pollutant=SO2_FIELD)
        if r.year >= SO2_SERIES_START_YEAR
    ]
    if not parsed:
        raise ICEDShapeError("SO2 aggregation returned zero rows")
    return _write(
        out_filename="state_so2_annual_mean_ug_m3.json",
        payload=_build_so2_payload(parsed=parsed),
    )


def emit_pm10(decrypted: dict) -> Path:
    from yen_gov.sources.iced_air_quality.markers_ingest import (
        PM10_SERIES_START_YEAR,
        _build_pm10_payload,
    )

    parsed = [
        r for r in aggregate_state_year_mean(decrypted, pollutant=PM10_FIELD)
        if r.year >= PM10_SERIES_START_YEAR
    ]
    if not parsed:
        raise ICEDShapeError("PM10 aggregation returned zero rows")
    return _write(
        out_filename="state_pm10_annual_mean_ug_m3.json",
        payload=_build_pm10_payload(parsed=parsed),
    )


def main(argv: list[str]) -> int:
    which = argv[1] if len(argv) > 1 else "all"
    decrypted = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if which in ("no2", "all"):
        p = emit_no2(decrypted)
        print(f"wrote {p}")
    if which in ("so2", "all"):
        p = emit_so2(decrypted)
        print(f"wrote {p}")
    if which in ("pm10", "all"):
        p = emit_pm10(decrypted)
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
