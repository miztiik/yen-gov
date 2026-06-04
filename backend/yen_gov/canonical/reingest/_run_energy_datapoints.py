"""One-off driver for B2b.1: emit per-indicator energy CSVs from the
surviving parquets under ``datasets/energy/``. Run from repo root.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.energy_datapoints import FILE_CLASS, emit


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    parquet_dir = repo_root / "datasets" / "energy"
    lgd_states_json = repo_root / "datasets" / "taxonomy" / "lgd_states.json"
    out_dir = repo_root / "datasets" / "data" / "datapoints" / "geo"

    emitted = emit(
        parquet_dir=parquet_dir,
        lgd_states_json=lgd_states_json,
        out_dir=out_dir,
    )
    for path in emitted:
        validate_csv(path=path, file_class=FILE_CLASS, repo_root=repo_root)
    print(f"wrote {len(emitted)} CSV(s) under {out_dir.relative_to(repo_root).as_posix()}")


if __name__ == "__main__":
    main()
