"""One-off driver for B2b.2: emit per-indicator livestock CSVs from the
surviving parquets under ``datasets/livestock/``. Run from repo root.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.livestock_datapoints import FILE_CLASS, emit


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    parquet_dir = repo_root / "datasets" / "livestock"
    lgd_states_json = repo_root / "datasets" / "taxonomy" / "lgd_states.json"
    geo_entities_csv = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    out_dir = repo_root / "datasets" / "data" / "datapoints" / "geo"

    emitted = emit(
        parquet_dir=parquet_dir,
        lgd_states_json=lgd_states_json,
        geo_entities_csv=geo_entities_csv,
        out_dir=out_dir,
    )
    for path in emitted:
        validate_csv(path=path, file_class=FILE_CLASS, repo_root=repo_root)
    print(
        f"wrote {len(emitted)} CSV(s) under "
        f"{out_dir.relative_to(repo_root).as_posix()}"
    )


if __name__ == "__main__":
    main()
