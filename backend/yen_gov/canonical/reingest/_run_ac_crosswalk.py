"""One-off driver for B2b.4.6: emit
``datasets/data/entities/ac_crosswalk.csv`` from the surviving
``datasets/taxonomy/ac_crosswalk.parquet``. Run from repo root.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.ac_crosswalk import FILE_CLASS, emit


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    parquet_path = (
        repo_root / "datasets" / "taxonomy" / "ac_crosswalk.parquet"
    )
    lgd_states_json = (
        repo_root / "datasets" / "taxonomy" / "lgd_states.json"
    )
    out_path = (
        repo_root / "datasets" / "data" / "entities" / "ac_crosswalk.csv"
    )

    emitted = emit(
        parquet_path=parquet_path,
        out_path=out_path,
        lgd_states_json=lgd_states_json,
    )
    validate_csv(path=emitted, file_class=FILE_CLASS, repo_root=repo_root)
    print(f"wrote {emitted.relative_to(repo_root).as_posix()}")


if __name__ == "__main__":
    main()
